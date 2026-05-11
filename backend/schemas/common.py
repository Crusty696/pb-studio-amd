"""Gemeinsame Schemas für alle Router."""

from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum


class StatusResponse(BaseModel):
    """Standard-Antwort für einfache Operationen."""
    success: bool = True
    message: str = ""


class BatchDeleteRequest(BaseModel):
    """Batch-Delete Request: Liste von Clip-IDs."""
    clip_ids: list[int] = Field(..., min_length=1, description="IDs der zu loeschenden Clips")


class DeleteResponse(BaseModel):
    """Antwort eines Delete-Calls (single oder batch)."""
    deleted_count: int = Field(..., description="Anzahl tatsaechlich geloeschter Clips")
    not_found_ids: list[int] = Field(default_factory=list, description="IDs die nicht gefunden wurden")


class ErrorResponse(BaseModel):
    """Fehler-Antwort."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class ProgressEvent(BaseModel):
    """SSE Progress-Event Daten."""
    task_id: str
    event_type: str  # analysis_progress, render_progress, etc.
    step: str = ""
    percent: float = 0.0
    message: str = ""
    metadata: Optional[dict[str, Any]] = None


class TaskStatus(str, Enum):
    """Status einer Background-Task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskInfo(BaseModel):
    """Info über eine laufende Background-Task."""
    task_id: str
    status: TaskStatus
    progress: float = 0.0
    message: str = ""
    result: Optional[Any] = None
    error: Optional[str] = None


class TimelineEntry(BaseModel):
    """Standardisiertes Timeline-Format für Pacing→Render Pipeline."""
    clip_id: str
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    file_path: str
    clip_start: float = Field(default=0.0, ge=0.0)
    clip_name: str = ""
    trigger_type: str = ""
    trigger_strength: float = 0.0
    segment_type: Optional[str] = None

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


def validate_timeline(entries: list[dict], audio_duration: float | None = None) -> tuple[list[str], list[str]]:
    """Validiert eine Timeline auf Konsistenz.

    Returns:
        Tuple (warnings, errors):
          - warnings: nicht-kritische Probleme (z.B. kurze Cuts, fehlender file_path)
          - errors:   kritische Fehler die ein Rendering blockieren:
              * end_time <= start_time
              * Überlappende Cuts (> 10ms Toleranz)
              * Timeline > Audio-Dauer (> 0.5s Toleranz)

    L-TI-5 (Audit Timeline-Integrity 2026-05-11): Overlap + Audio-Overflow
    waren zuvor nur warnings. User konnte fehlerhafte Timelines rendern;
    Renderer produzierte truncated frames / undefined FFmpeg-Behavior.
    Beide Cases sind jetzt errors -> HTTP 400 in den drei Validation-Pfaden
    (pacing /generate, pacing /timeline, render Pre-Render-Check).
    """
    warnings: list[str] = []
    errors: list[str] = []
    if not entries:
        return warnings, errors

    for i, entry in enumerate(entries):
        start = entry.get("start_time", 0.0)
        end = entry.get("end_time", 0.0)
        if end <= start:
            errors.append(f"Cut {i}: end_time ({end}) <= start_time ({start})")
        elif end - start < 0.1:
            warnings.append(f"Cut {i}: Dauer zu kurz ({end - start:.3f}s)")
        fp = entry.get("metadata", {}).get("file_path") or entry.get("file_path", "")
        if not fp:
            warnings.append(f"Cut {i}: Kein file_path")

    # Überlappungs-Check — L-TI-5: jetzt Error statt Warning.
    # Toleranz 10ms (relaxierter als der frueher 1ms-Wert), damit Sub-
    # Millisekunden-Float-Drift aus Beat-Berechnungen nicht zum Block fuehrt,
    # aber echte UI-Drag-Overlaps verlaesslich erkannt werden.
    sorted_entries = sorted(entries, key=lambda e: e.get("start_time", 0.0))
    for i in range(1, len(sorted_entries)):
        prev = sorted_entries[i - 1]
        curr = sorted_entries[i]

        prev_end = prev.get("end_time") or prev.get("start_time", 0.0) + prev.get("duration", 0.0)
        curr_start = curr.get("start_time", 0.0)

        if curr_start < prev_end - 0.01:  # 10ms Toleranz
            errors.append(
                f"Cut {i}: Überlappung mit vorherigem Cut "
                f"(prev_end={prev_end:.3f}, curr_start={curr_start:.3f})"
            )

    # Audio-Dauer-Check — L-TI-5: jetzt Error statt Warning.
    # 0.5s Toleranz erhalten (Audio-Decoding kann minimal abweichen).
    if audio_duration and audio_duration > 0 and entries:
        last_end = max(e.get("end_time", 0.0) for e in entries)
        if last_end > audio_duration + 0.5:
            errors.append(
                f"Timeline ({last_end:.1f}s) überschreitet Audio-Dauer ({audio_duration:.1f}s)"
            )

    return warnings, errors
