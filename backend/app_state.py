"""
Zentraler In-Memory App-State für alle FastAPI Router.

Ersetzt die verteilten module-level Dictionaries in audio_router,
video_router, pacing_router und render_router.

Vorteile gegenüber dem alten Design:
- Eliminiert Cross-Router Imports (pacing→audio, render→pacing)
- Einziger Ort für State-Debugging und State-Reset
- Thread-sichere ID-Vergabe via Lock
- SQLite-Persistenz via DatabaseCore/MediaRepository (ADR-003 Phase 2)

Einschränkungen (akzeptabel für Single-User Desktop-App):
- Keine Session-Isolation (nur ein User gleichzeitig)
"""

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from pb_studio.data.database_core import normalize_media_path
from pb_studio.data.repositories.project_repository import ProjectRepository

logger = logging.getLogger(__name__)


def _emit_persist_error(source: str, message: str, detail: str) -> None:
    """C2-Fix (Pe-C1, GAP-1 silent-failure, 2026-05-19): Persist-Fehler dürfen
    nicht mehr als "unkritisch" geschluckt werden — UI MUSS sie sehen.

    Versucht ein SSE-Event "persist_error" zu publizieren, damit das Frontend
    einen Toast anzeigen kann. Fallback: nur Log (wenn kein Event-Loop läuft,
    z.B. in pytest-Sync-Context).

    Iron Rule 10 (100% Honesty): User darf nicht denken, ein Import war OK
    wenn er in Wirklichkeit nur in-memory war und beim Restart weg ist.
    """
    payload: dict[str, Any] = {
        "source": source,
        "message": message,
        "detail": detail[:500] if detail else "",
        "severity": "error",
    }
    try:
        from backend.dependencies import publish_event  # lazy import, vermeidet circular
        loop = asyncio.get_running_loop()
        # Schedule coroutine without blocking — fire-and-forget
        loop.create_task(publish_event("persist_error", payload))
    except RuntimeError:
        # Kein running loop (z.B. sync test context oder startup-Phase) — Fallback Log
        logger.error(f"persist_error [{source}] {message}: {detail}")
    except Exception as exc:
        # Defensive: emit failure darf den eigentlichen Fail-Path nicht blocken
        logger.error(f"persist_error emit fehlgeschlagen ({exc}) [{source}] {message}: {detail}")


def _thumbnail_exists_for_clip(
    clip_id: int,
    project: Optional[dict],
    file_path: Optional[str],
) -> bool:
    """D-H1 (Audit V2): pruefe Disk statt fix-False auf Reload.

    Konvention: project_dir/proxy_cache/clip_{id}_thumb.jpg (siehe
    thumbnail_generator.generate_clip_thumbnail). Fallback: Source-Video-Dir
    statt project_dir, weil generate_clip_thumbnail bei fehlendem project_root
    auf Path(video_path).parent / 'proxy_cache' faellt.
    """
    candidates: list[Path] = []
    try:
        if isinstance(project, dict) and project.get("path"):
            candidates.append(Path(project["path"]) / "proxy_cache" / f"clip_{clip_id}_thumb.jpg")
        if file_path:
            candidates.append(Path(file_path).parent / "proxy_cache" / f"clip_{clip_id}_thumb.jpg")
    except (TypeError, ValueError, OSError):
        return False
    return any(p.exists() for p in candidates)


def resolve_active_project_root(state: "AppState", fallback_root: str | Path) -> Path:
    """Gibt den aktiven Projekt-Root zurück, sonst den konfigurierten Fallback."""
    current = state.current_project or {}
    current_path = current.get("path") if isinstance(current, dict) else None
    if current_path:
        return Path(current_path).resolve()
    return Path(fallback_root).resolve()


def resolve_project_db_id(project_data: Optional[dict]) -> int:
    """Extrahiert die DB-Projekt-ID aus current_project; Fallback bleibt 1 für Legacy-Fälle."""
    if isinstance(project_data, dict):
        raw = project_data.get("db_project_id")
        if raw not in (None, ""):
            try:
                return int(raw)
            except (TypeError, ValueError):
                logger.warning("Ungültige db_project_id im AppState: %r", raw)
    return 1


@dataclass
class AppState:
    """Thread-sicherer In-Memory State für alle FastAPI Router."""

    # --- Project ---
    current_project: Optional[dict] = None

    # --- Audio ---
    audio_clips: dict[int, dict] = field(default_factory=dict)
    audio_analysis_cache: dict[int, dict] = field(default_factory=dict)

    # --- Video ---
    video_clips: dict[int, dict] = field(default_factory=dict)
    video_analysis_cache: dict[int, dict] = field(default_factory=dict)

    # --- Pacing / Timeline ---
    current_timeline: list[dict] = field(default_factory=list)
    current_audio_path: Optional[str] = None

    # --- Render Tasks ---
    render_tasks: dict[str, dict] = field(default_factory=dict)
    cancel_flags: dict[str, bool] = field(default_factory=dict)

    # --- Thread-sichere ID-Zähler ---
    _audio_next_id: int = field(default=1)
    _video_next_id: int = field(default=1)
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _state_lock: threading.RLock = field(default_factory=threading.RLock)

    def next_audio_id(self) -> int:
        """Gibt die nächste Audio-Clip-ID zurück (thread-safe)."""
        with self._lock:
            clip_id = self._audio_next_id
            self._audio_next_id += 1
            return clip_id

    def next_video_id(self) -> int:
        """Gibt die nächste Video-Clip-ID zurück (thread-safe)."""
        with self._lock:
            clip_id = self._video_next_id
            self._video_next_id += 1
            return clip_id

    # =========================================================================
    # Thread-safe Accessor-Methoden
    # =========================================================================

    def get_audio_clip(self, clip_id: int) -> Optional[dict]:
        """Thread-safe Zugriff auf einen Audio-Clip (shallow copy, safe to mutate)."""
        with self._state_lock:
            clip = self.audio_clips.get(clip_id)
            return dict(clip) if clip is not None else None

    def set_audio_clip(self, clip_id: int, clip: dict) -> None:
        """Thread-safe Setzen eines Audio-Clips."""
        with self._state_lock:
            self.audio_clips[clip_id] = clip

    def get_video_clip(self, clip_id: int) -> Optional[dict]:
        """Thread-safe Zugriff auf einen Video-Clip (shallow copy, safe to mutate)."""
        with self._state_lock:
            clip = self.video_clips.get(clip_id)
            return dict(clip) if clip is not None else None

    def set_video_clip(self, clip_id: int, clip: dict) -> None:
        """Thread-safe Setzen eines Video-Clips."""
        with self._state_lock:
            self.video_clips[clip_id] = clip

    def update_video_clip(self, clip_id: int, **kwargs) -> None:
        """L-N7: Thread-safe Update von in-memory Video-Clip-Feldern.

        Aktuell genutzt fuer thumbnail_available (gesetzt nach erfolgreichem
        /video/thumbnails/{id}). Unbekannte clip_ids werden ignoriert (kein
        Crash) — der Caller (video_router) soll ohne explizite Existenz-Pruefung
        flags setzen koennen.

        Nicht persistent: aenderungen bleiben im in-memory state. thumbnail_available
        wird beim load_from_db wieder auf False gesetzt (siehe Audit-Begruendung:
        Thumbnails werden on-demand neu generiert wenn die UI sie anfordert).
        """
        with self._state_lock:
            clip = self.video_clips.get(clip_id)
            if clip is None:
                return
            for key, value in kwargs.items():
                clip[key] = value

    def get_audio_clips_snapshot(self) -> dict[int, dict]:
        """Thread-safe Snapshot aller Audio-Clips (deep copy of dicts)."""
        with self._state_lock:
            # BUG-063 FIX: Deep copy to prevent external mutation of state
            return {k: dict(v) for k, v in self.audio_clips.items()}

    def get_video_clips_snapshot(self) -> dict[int, dict]:
        """Thread-safe Snapshot aller Video-Clips (deep copy of dicts)."""
        with self._state_lock:
            # BUG-063 FIX: Deep copy
            return {k: dict(v) for k, v in self.video_clips.items()}

    def delete_audio_clip(self, clip_id: int) -> bool:
        """Loescht Audio-Clip aus In-Memory + SQLite. Returns True wenn gefunden+geloescht.

        Cleanup: audio_clips, audio_analysis_cache, MediaRepository row.
        Foreign-Key-Cascade entfernt vector_map-Eintraege automatisch.
        """
        with self._state_lock:
            clip = self.audio_clips.get(clip_id)
        if clip is None:
            return False
        try:
            from pb_studio.data.repositories.media_repository import MediaRepository
            repo = MediaRepository()
            row = repo.find_by_project_and_path(
                project_id=self.get_current_project_db_id(),
                file_path=clip["path"],
            )
            if row:
                repo.delete_media(row["id"])
        except Exception as e:
            logger.error("Audio-Clip DB-Delete fehlgeschlagen: %s", e, exc_info=True)
            _emit_persist_error(
                "audio_delete",
                f"Audio-Clip {clip_id} konnte nicht gelöscht werden",
                str(e),
            )
            raise
        with self._state_lock:
            self.audio_clips.pop(clip_id, None)
            self.audio_analysis_cache.pop(clip_id, None)
        return True

    def delete_video_clip(self, clip_id: int) -> bool:
        """Loescht Video-Clip aus In-Memory + SQLite. Returns True wenn gefunden+geloescht.

        SQLite-/FAISS-Mutationen laufen ueber eine durable, idempotente Outbox.
        Bei einem Fehler bleibt der Runtime-Clip erhalten; die vorbereitete
        Operation kann beim naechsten Projekt-Load sicher fortgesetzt werden.
        """
        with self._state_lock:
            clip = self.video_clips.get(clip_id)
        if clip is None:
            return False
        try:
            from pb_studio.data.repositories.media_repository import MediaRepository
            repo = MediaRepository()
            row = repo.find_by_project_and_path(
                project_id=self.get_current_project_db_id(),
                file_path=clip["path"],
            )
            if row:
                from pb_studio.data.vector_operation_outbox import VectorOperationOutbox

                VectorOperationOutbox().delete_media(row["id"])
        except Exception as e:
            logger.error("Video-Clip Persistenz-Delete fehlgeschlagen: %s", e, exc_info=True)
            _emit_persist_error(
                "video_delete",
                f"Video-Clip {clip_id} konnte nicht gelöscht werden",
                str(e),
            )
            raise
        with self._state_lock:
            self.video_clips.pop(clip_id, None)
            self.video_analysis_cache.pop(clip_id, None)
        return True

    def get_audio_analysis(self, clip_id: int) -> Optional[dict]:
        """Thread-safe Zugriff auf Audio-Analyse-Cache."""
        with self._state_lock:
            return self.audio_analysis_cache.get(clip_id)

    def set_audio_analysis(self, clip_id: int, data: dict) -> None:
        """Thread-safe Setzen eines Audio-Analyse-Eintrags."""
        with self._state_lock:
            self.audio_analysis_cache[clip_id] = data

    def get_video_analysis(self, clip_id: int) -> Optional[dict]:
        """Thread-safe Zugriff auf Video-Analyse-Cache."""
        with self._state_lock:
            return self.video_analysis_cache.get(clip_id)

    def set_video_analysis(self, clip_id: int, data: dict) -> None:
        """Thread-safe Setzen eines Video-Analyse-Eintrags."""
        with self._state_lock:
            self.video_analysis_cache[clip_id] = data

    def get_video_analysis_snapshot(self) -> dict[int, dict]:
        """Thread-safe Snapshot des gesamten Video-Analyse-Caches."""
        with self._state_lock:
            return dict(self.video_analysis_cache)

    def get_timeline_snapshot(self) -> list[dict]:
        """Thread-safe Snapshot der aktuellen Timeline."""
        with self._state_lock:
            return list(self.current_timeline)

    def set_timeline(self, timeline: list[dict]) -> None:
        """Thread-safe Setzen der Timeline."""
        with self._state_lock:
            self.current_timeline = timeline

    def get_render_task(self, task_id: str) -> Optional[dict]:
        """Thread-safe Zugriff auf einen Render-Task."""
        with self._state_lock:
            return self.render_tasks.get(task_id)

    def set_render_task(self, task_id: str, task: dict) -> None:
        """Thread-safe Setzen eines Render-Tasks."""
        with self._state_lock:
            self.render_tasks[task_id] = task

    def update_render_task(self, task_id: str, updates: dict) -> None:
        """Thread-safe Update eines Render-Tasks."""
        with self._state_lock:
            if task_id in self.render_tasks:
                self.render_tasks[task_id].update(updates)

    def is_render_active(self) -> bool:
        """Prüft thread-safe, ob aktuell ein Render-Task aktiv läuft."""
        with self._state_lock:
            for task in self.render_tasks.values():
                status = task.get("status")
                if status in ("running", "processing", "pending"):
                    return True
            return False

    def set_cancel_flag(self, task_id: str, value: bool) -> None:
        """Thread-safe Setzen eines Cancel-Flags."""
        with self._state_lock:
            self.cancel_flags[task_id] = value

    def get_cancel_flag(self, task_id: str) -> bool:
        """Thread-safe Lesen eines Cancel-Flags.

        M5-Fix (D-M1, 2026-05-20): Wenn task_id NICHT in cancel_flags
        AND auch NICHT in render_tasks → defensive True. Pattern:
        - Vor Fix: nach reset() + render_tasks.clear() + cancel_flags.pop()
          sah Render-Thread False → lief weiter trotz Projekt-Close.
        - Nach Fix: kein flag + kein active task = orphan = cancelled.
        """
        with self._state_lock:
            flag = self.cancel_flags.get(task_id)
            if flag is not None:
                return flag
            # Unknown task_id — orphan check: wenn nicht in render_tasks, gilt
            # task als cancelled (defensive). Verhindert die race aus L-TI-1.
            return task_id not in self.render_tasks

    def reset(self) -> None:
        """Setzt den gesamten State zurück (z.B. bei neuem Projekt).

        MEDIUM-015 Fix: cancel_flags wird NICHT geleert, sondern alle verbleibenden Flags
        werden auf True gesetzt. close_project setzt die Flags vor reset(); würden sie hier
        sofort geleert, sähen laufende Render-Threads das Cancel-Signal nie, weil reset()
        vom Event-Loop und der Render-Check vom Thread-Pool aus ausgeführt werden.
        Individuelle Cleanup: render_router.py entfernt Flags per .pop() nach Abschluss.
        """
        with self._state_lock:
            with self._lock:
                self.current_project = None
                self.audio_clips.clear()
                self.audio_analysis_cache.clear()
                self.video_clips.clear()
                self.video_analysis_cache.clear()
                self.current_timeline.clear()
                self.current_audio_path = None
                self.render_tasks.clear()
                # Alle in-flight Tasks als abgebrochen markieren statt Flags zu leeren.
                # Render-Threads sehen beim nächsten get_cancel_flag() True und stoppen.
                for tid in list(self.cancel_flags.keys()):
                    self.cancel_flags[tid] = True
                self._audio_next_id = 1
                self._video_next_id = 1

    # =========================================================================
    # ADR-003 Phase 2: SQLite-Persistenz
    # =========================================================================

    def get_current_project_db_id(self) -> int:
        """Aktive DB-Projekt-ID; 1 bleibt Legacy-Fallback wenn kein Projekt geöffnet ist."""
        with self._state_lock:
            return resolve_project_db_id(self.current_project)

    def require_current_project_db_id(self) -> int:
        """Liefert die aktive DB-Projekt-ID oder bricht ohne Projekt explizit ab."""
        with self._state_lock:
            project = self.current_project
            if not isinstance(project, dict):
                raise RuntimeError("Kein Projekt geöffnet")
            raw_project_id = project.get("db_project_id")
        if raw_project_id in (None, ""):
            raise RuntimeError("Aktives Projekt besitzt keine DB-Projekt-ID")
        try:
            return int(raw_project_id)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Aktive DB-Projekt-ID ist ungültig") from exc

    def sync_project_db_record(self) -> bool:
        """Schreibt current_project in die Projects-Tabelle, falls eine DB-Projekt-ID bekannt ist."""
        with self._state_lock:
            project = dict(self.current_project) if isinstance(self.current_project, dict) else None

        if not project:
            return False

        project_id = resolve_project_db_id(project)
        project_data = {
            "path": project.get("path"),
            "db_project_id": project_id,
            "audio_count": project.get("audio_count", 0),
            "video_count": project.get("video_count", 0),
            "has_timeline": project.get("has_timeline", False),
            "created_at": project.get("created_at"),
            "modified_at": project.get("modified_at"),
        }
        try:
            ProjectRepository().update_project(project_id, name=project.get("name"), data=project_data)
            return True
        except Exception as e:
            logger.error("Projekt-DB-Sync fehlgeschlagen: %s", e)
            _emit_persist_error("project_sync", "Projekt-DB-Sync fehlgeschlagen", str(e))
            return False

    def _find_audio_clip_by_path(self, file_path: str) -> Optional[dict]:
        normalized = normalize_media_path(file_path)
        with self._state_lock:
            for clip in self.audio_clips.values():
                if normalize_media_path(clip.get("path", "")) == normalized:
                    return dict(clip)
        return None

    def _find_video_clip_by_path(self, file_path: str) -> Optional[dict]:
        normalized = normalize_media_path(file_path)
        with self._state_lock:
            for clip in self.video_clips.values():
                if normalize_media_path(clip.get("path", "")) == normalized:
                    return dict(clip)
        return None

    def register_audio_clip(self, clip_data: dict) -> dict:
        """Reuse an existing canonical audio clip for the same real file when possible."""
        project_id = self.require_current_project_db_id()
        in_memory = self._find_audio_clip_by_path(clip_data["path"])
        if in_memory:
            return in_memory

        try:
            from pb_studio.data.repositories.media_repository import MediaRepository
            repo = MediaRepository()
            row = repo.find_by_project_and_path(
                project_id=project_id,
                file_path=clip_data["path"],
            )
            if row:
                meta = json.loads(row.get("metadata_json") or "{}")
                if meta.get("clip_type") == "audio" and meta.get("clip_id") is not None:
                    clip_id = int(meta["clip_id"])
                    clip = {
                        "id": clip_id,
                        "name": meta.get("name", clip_data.get("name", "")),
                        "path": row.get("file_path") or clip_data["path"],
                        "duration_seconds": row.get("duration_sec") or clip_data.get("duration_seconds", 0.0),
                        "sample_rate": meta.get("sample_rate", clip_data.get("sample_rate", 44100)),
                        "channels": meta.get("channels", clip_data.get("channels", 2)),
                        "format": meta.get("format", clip_data.get("format", "")),
                        # L-N2: audio_hash mit-uebernehmen — wenn schon persisted dann nutzen,
                        # sonst Wert aus Import (frisches hashing) behalten.
                        "audio_hash": (
                            meta.get("audio_hash")
                            or row.get("file_hash")
                            or clip_data.get("audio_hash")
                        ),
                        # L-AUDIO-8 (CD-1): stems_paths mit-uebernehmen
                        "stems_paths": (
                            meta.get("stems_paths")
                            or clip_data.get("stems_paths")
                        ),
                    }
                    self.set_audio_clip(clip_id, clip)
                    with self._lock:
                        self._audio_next_id = max(self._audio_next_id, clip_id + 1)
                    return clip
        except Exception as e:
            logger.warning(f"Audio-Clip-Reuse aus DB fehlgeschlagen (Fallback auf neue ID): {e}")

        clip = dict(clip_data)
        clip["id"] = self.next_audio_id()
        self.set_audio_clip(clip["id"], clip)
        self.persist_audio_clip(clip, project_id=project_id)
        return clip

    def register_video_clip(self, clip_data: dict) -> dict:
        """Reuse an existing canonical video clip for the same real file when possible."""
        project_id = self.require_current_project_db_id()
        in_memory = self._find_video_clip_by_path(clip_data["path"])
        if in_memory:
            return in_memory

        try:
            from pb_studio.data.repositories.media_repository import MediaRepository
            repo = MediaRepository()
            row = repo.find_by_project_and_path(
                project_id=project_id,
                file_path=clip_data["path"],
            )
            if row:
                meta = json.loads(row.get("metadata_json") or "{}")
                if meta.get("clip_type") == "video" and meta.get("clip_id") is not None:
                    clip_id = int(meta["clip_id"])
                    # BUG-058 FIX: Update next_id strictly via max() to avoid collisions
                    with self._lock:
                        self._video_next_id = max(self._video_next_id, clip_id + 1)
                    clip = {
                        "id": clip_id,
                        "name": meta.get("name", clip_data.get("name", "")),
                        "path": row.get("file_path") or clip_data["path"],
                        "duration_seconds": row.get("duration_sec") or clip_data.get("duration_seconds", 0.0),
                        "width": meta.get("width", clip_data.get("width", 1920)),
                        "height": meta.get("height", clip_data.get("height", 1080)),
                        "fps": meta.get("fps", clip_data.get("fps", 30.0)),
                        "codec": meta.get("codec", clip_data.get("codec", "")),
                        "thumbnail_available": False,
                        "tags": [],
                        # L-VIDEO-3: video_hash aus DB-Meta + frischem clip_data fallback.
                        "video_hash": (
                            meta.get("video_hash")
                            or row.get("file_hash")
                            or clip_data.get("video_hash")
                        ),
                    }
                    self.set_video_clip(clip_id, clip)
                    with self._lock:
                        self._video_next_id = max(self._video_next_id, clip_id + 1)
                    return clip
        except Exception as e:
            logger.warning(f"Video-Clip-Reuse aus DB fehlgeschlagen (Fallback auf neue ID): {e}")

        clip = dict(clip_data)
        clip["id"] = self.next_video_id()
        self.set_video_clip(clip["id"], clip)
        self.persist_video_clip(clip, project_id=project_id)
        return clip

    def update_audio_analysis(
        self,
        clip_id: int,
        bpm: Optional[float] = None,
        key: Optional[str] = None,
        beat_count: Optional[int] = None,
        beats_json: Optional[str] = None,
        is_analyzed: Optional[bool] = None,
        energy_curve=None,
        structure_segments=None,
        spectral_data=None,
        subtrack_segments=None,  # L-K1: Sub-Track-Segmente (Mix-Import)
        tempo_curve=None,        # L-K1: Tempo-Verlauf ueber den Mix
        onset_times=None,        # Audit-Fix 2026-07-10: Onset-Trigger-Kandidaten
        kick_times=None,         # Audit-Fix 2026-07-10: Kick-Trigger-Kandidaten
        snare_times=None,        # Audit-Fix 2026-07-10: Snare-Trigger-Kandidaten
        hihat_times=None,        # Audit-Fix 2026-07-10: HiHat-Trigger-Kandidaten
        chunk_evidence=None,     # T316: vollstaendige Long-Mix-Chunk-Provenance
        analysis_status: Optional[str] = None,
        stage_status=None,
        stage_errors=None,
        downbeats=None,
        downbeat_provenance=None,
    ) -> None:
        """
        Persistiert Audio-Analyse-Ergebnisse (BPM, Key, BeatCount, Beats, EnergyCurve,
        StructureSegments, SpectralData, SubtrackSegments, TempoCurve) in der
        ai_data_json-Spalte des zugehörigen media-Eintrags.

        Alle Felder sind optional — nur tatsaechlich uebergebene Werte ueberschreiben
        bestehende DB-/Cache-Eintraege. Das erlaubt partielle Updates (z.B. nur
        Subtracks aus dem Import-Pfad, ohne BPM/Beats zu loeschen).

        Fehler werden NUR geloggt — nie geworfen (nicht kritisch für den Analyseworkflow).
        """
        try:
            from pb_studio.data.repositories.media_repository import MediaRepository
            repo = MediaRepository()
            clip = self.get_audio_clip(clip_id)
            if clip is None:
                logger.warning(f"update_audio_analysis: Clip {clip_id} nicht im In-Memory State")
                return
            row = repo.find_by_project_and_path(
                project_id=self.get_current_project_db_id(),
                file_path=clip["path"],
            )
            if row is None:
                logger.warning(f"update_audio_analysis: Kein DB-Eintrag für Clip {clip_id} ({clip['path']})")
                return

            # Existing ai_data laden — partielle Updates muessen vorhandene Felder
            # bewahren (z.B. nur Subtracks setzen, ohne BPM/Beats zu loeschen).
            try:
                existing_ai = json.loads(row.get("ai_data_json") or "{}")
                if not isinstance(existing_ai, dict):
                    existing_ai = {}
            except (json.JSONDecodeError, TypeError):
                existing_ai = {}

            ai_data: dict = dict(existing_ai)
            # Nur Felder ueberschreiben, die explizit uebergeben wurden.
            if bpm is not None:
                ai_data["bpm"] = bpm
            if key is not None:
                ai_data["key"] = key
            if beat_count is not None:
                ai_data["beat_count"] = beat_count
            if beats_json is not None:
                # beats_json kann serialisierter JSON-String sein — parse zu Liste,
                # damit json.dumps() in der Repository-Schicht nicht doppelt encoded.
                try:
                    beats_list = json.loads(beats_json) if beats_json else []
                except (json.JSONDecodeError, TypeError):
                    beats_list = []
                    logger.warning("update_audio_analysis: beats_json konnte nicht geparst werden; leere Liste verwendet")
                ai_data["beats_json"] = beats_list
            if is_analyzed is not None:
                ai_data["is_analyzed"] = is_analyzed
            elif "is_analyzed" not in ai_data:
                ai_data["is_analyzed"] = False
            if energy_curve is not None:
                ai_data["energy_curve"] = energy_curve
            if structure_segments is not None:
                ai_data["structure_segments"] = structure_segments
            if spectral_data is not None:
                ai_data["spectral_data"] = spectral_data
            if subtrack_segments is not None:
                ai_data["subtrack_segments"] = subtrack_segments
            if tempo_curve is not None:
                ai_data["tempo_curve"] = tempo_curve
            if onset_times is not None:
                ai_data["onset_times"] = onset_times
            if kick_times is not None:
                ai_data["kick_times"] = kick_times
            if snare_times is not None:
                ai_data["snare_times"] = snare_times
            if hihat_times is not None:
                ai_data["hihat_times"] = hihat_times
            if chunk_evidence is not None:
                ai_data["chunk_evidence"] = chunk_evidence
            if analysis_status is not None:
                ai_data["analysis_status"] = analysis_status
            if stage_status is not None:
                ai_data["stage_status"] = stage_status
            if stage_errors is not None:
                ai_data["stage_errors"] = stage_errors
            if downbeats is not None:
                ai_data["downbeats"] = downbeats
            if downbeat_provenance is not None:
                ai_data["downbeat_provenance"] = downbeat_provenance

            repo.update_status(row["id"], "analyzed", ai_data=ai_data)

            # Diff dictionary fuer den In-Memory-Cache (nur tatsaechlich gesetzte Felder).
            cache_update: dict = {}
            if bpm is not None:
                cache_update["bpm"] = bpm
            if key is not None:
                cache_update["key"] = key
            if beat_count is not None:
                cache_update["beat_count"] = beat_count
            if beats_json is not None:
                cache_update["beats_json"] = ai_data["beats_json"]
            if is_analyzed is not None:
                cache_update["is_analyzed"] = is_analyzed
            if energy_curve is not None:
                cache_update["energy_curve"] = energy_curve
            if structure_segments is not None:
                cache_update["structure_segments"] = structure_segments
            if spectral_data is not None:
                cache_update["spectral_data"] = spectral_data
            if subtrack_segments is not None:
                cache_update["subtrack_segments"] = subtrack_segments
            if tempo_curve is not None:
                cache_update["tempo_curve"] = tempo_curve
            if onset_times is not None:
                cache_update["onset_times"] = onset_times
            if kick_times is not None:
                cache_update["kick_times"] = kick_times
            if snare_times is not None:
                cache_update["snare_times"] = snare_times
            if hihat_times is not None:
                cache_update["hihat_times"] = hihat_times
            if chunk_evidence is not None:
                cache_update["chunk_evidence"] = chunk_evidence
            if analysis_status is not None:
                cache_update["_analysis_status"] = analysis_status
            if stage_status is not None:
                cache_update["_stage_status"] = stage_status
            if stage_errors is not None:
                cache_update["_stage_errors"] = stage_errors
            if downbeats is not None:
                cache_update["downbeats"] = downbeats
            if downbeat_provenance is not None:
                cache_update["downbeat_provenance"] = downbeat_provenance

            # C3-Fix (D-C1, 2026-05-19): NICHT nur audio_analysis_cache updaten,
            # sondern auch audio_clips[clip_id] — sonst sehen Endpoints, die
            # direkt aus audio_clips lesen (z.B. GET /audio/clips), inkonsistente
            # Werte zum cache. Vor dem Fix: cache hatte bpm=128, audio_clips
            # noch bpm=0.0 bis zum naechsten load_from_db.
            with self._state_lock:
                if clip_id in self.audio_analysis_cache:
                    self.audio_analysis_cache[clip_id].update(cache_update)
                else:
                    self.audio_analysis_cache[clip_id] = {
                        "clip_id": clip_id,
                        **cache_update,
                        "duration_seconds": clip.get("duration_seconds", 0.0),
                    }
                # D-C1 Truth-Source-Konsolidierung: spiegele cache_update in audio_clips
                if clip_id in self.audio_clips:
                    self.audio_clips[clip_id].update(cache_update)

            bpm_str = f"{bpm:.1f}" if isinstance(bpm, (int, float)) else "—"
            logger.debug(
                f"Audio-Analyse für Clip {clip_id} in DB persistiert "
                f"(bpm={bpm_str}, key={key}, subtracks={'yes' if subtrack_segments is not None else '—'})"
            )
        except Exception as e:
            logger.error(f"Audio-Analyse DB-Persistenz fehlgeschlagen: {e}", exc_info=True)
            _emit_persist_error(
                "audio_analysis",
                f"Audio-Analyse für Clip {clip_id} nicht gespeichert",
                str(e),
            )

    def update_video_analysis(
        self,
        clip_id: int,
        scene_count: Optional[int] = None,
        avg_motion: Optional[float] = None,
        has_embedding: Optional[bool] = None,
        is_analyzed: bool = False,
        scenes=None,
        motion=None,
        dominant_colors=None,
        tags=None,
        audio_key: Optional[str] = None,
        embedding_dim: Optional[int] = None,   # L-M8
        embedding_samples: Optional[int] = None,  # L-M8
        tag_source: Optional[str] = None,
        avg_brightness: Optional[float] = None,   # Audit-Fix 2026-07-10
        avg_saturation: Optional[float] = None,   # Audit-Fix 2026-07-10
        avg_color_temp: Optional[float] = None,   # Audit-Fix 2026-07-10
        mood_tags=None,                            # Audit-Fix 2026-07-10
    ) -> None:
        """
        Persistiert Video-Analyse-Ergebnisse in der ai_data_json-Spalte des
        zugehörigen media-Eintrags UND aktualisiert den In-Memory
        video_analysis_cache (analog zu update_audio_analysis).

        Alle Felder sind optional — nur tatsaechlich uebergebene Werte ueberschreiben
        bestehende DB-/Cache-Eintraege. Das erlaubt partielle Updates (z.B. nur
        embedding-meta nach SigLIP-Pass, ohne scene_count/avg_motion zu loeschen).

        Fehler werden NUR geloggt — nie geworfen (nicht kritisch für den
        Analyseworkflow).

        L-K4: audio_key (Tonart des Video-Audio-Tracks) wird persistiert damit
        UseKeyMatching im Pacing nach Reload des Projekts weiterhin wirkt.
        L-M8: embedding_dim + embedding_samples werden persistiert damit Reload
        die SigLIP-Embedding-Metadaten wieder zeigt (vorher 0).
        """
        try:
            from pb_studio.data.repositories.media_repository import MediaRepository
            repo = MediaRepository()
            clip = self.get_video_clip(clip_id)
            if clip is None:
                logger.warning(f"update_video_analysis: Clip {clip_id} nicht im In-Memory State")
                return
            row = repo.find_by_project_and_path(
                project_id=self.get_current_project_db_id(),
                file_path=clip["path"],
            )

            # Existing ai_data laden — partielle Updates muessen vorhandene Felder
            # bewahren (z.B. nur embedding-meta setzen, ohne scene_count zu loeschen).
            if row is not None:
                try:
                    existing_ai = json.loads(row.get("ai_data_json") or "{}")
                    if not isinstance(existing_ai, dict):
                        existing_ai = {}
                except (json.JSONDecodeError, TypeError):
                    existing_ai = {}
            else:
                existing_ai = {}
                logger.warning(f"update_video_analysis: Kein DB-Eintrag für Clip {clip_id} ({clip['path']})")

            ai_data: dict = dict(existing_ai)

            # Nur Felder ueberschreiben, die explizit uebergeben wurden.
            if scene_count is not None:
                ai_data["scene_count"] = scene_count
            if avg_motion is not None:
                ai_data["avg_motion"] = avg_motion
            if has_embedding is not None:
                ai_data["has_embedding"] = bool(has_embedding)
            if is_analyzed:
                ai_data["is_analyzed"] = True
            elif "is_analyzed" not in ai_data:
                ai_data["is_analyzed"] = False
            if scenes is not None:
                ai_data["scenes"] = scenes
            if motion is not None:
                ai_data["motion"] = motion
            if dominant_colors is not None:
                ai_data["dominant_colors"] = dominant_colors
            if tags is not None:
                ai_data["tags"] = tags
            if audio_key is not None:
                ai_data["audio_key"] = audio_key
            if tag_source is not None:
                ai_data["tag_source"] = tag_source
            # L-M8: embedding-meta persistieren
            if embedding_dim is not None:
                ai_data["embedding_dim"] = int(embedding_dim)
                # has_embedding aus embedding_dim ableiten (overrides expliziten Wert
                # nur wenn embedding_dim explizit angegeben wurde).
                ai_data["has_embedding"] = bool(int(embedding_dim) > 0)
            if embedding_samples is not None:
                ai_data["embedding_samples"] = int(embedding_samples)
            if avg_brightness is not None:
                ai_data["avg_brightness"] = float(avg_brightness)
            if avg_saturation is not None:
                ai_data["avg_saturation"] = float(avg_saturation)
            if avg_color_temp is not None:
                ai_data["avg_color_temp"] = float(avg_color_temp)
            if mood_tags is not None:
                ai_data["mood_tags"] = mood_tags

            # DB-Persist nur wenn ein passender Media-Row existiert.
            if row is not None:
                repo.update_status(row["id"], "analyzed", ai_data=ai_data)

            # Diff-Dictionary fuer den In-Memory-Cache (nur tatsaechlich gesetzte Felder).
            cache_update: dict = {}
            if scene_count is not None:
                cache_update["scene_count"] = scene_count
            if avg_motion is not None:
                cache_update["avg_motion"] = avg_motion
            if has_embedding is not None:
                cache_update["has_embedding"] = bool(has_embedding)
            if is_analyzed:
                cache_update["is_analyzed"] = True
            if scenes is not None:
                cache_update["scenes"] = scenes
            if motion is not None:
                cache_update["motion"] = motion
            if dominant_colors is not None:
                cache_update["dominant_colors"] = dominant_colors
            if tags is not None:
                cache_update["tags"] = tags
            if audio_key is not None:
                cache_update["audio_key"] = audio_key
            if tag_source is not None:
                cache_update["tag_source"] = tag_source
            # L-M8: embedding-meta in den Cache uebernehmen
            if embedding_dim is not None:
                cache_update["embedding_dim"] = int(embedding_dim)
                cache_update["has_embedding"] = bool(int(embedding_dim) > 0)
            if embedding_samples is not None:
                cache_update["embedding_samples"] = int(embedding_samples)
            if avg_brightness is not None:
                cache_update["avg_brightness"] = float(avg_brightness)
            if avg_saturation is not None:
                cache_update["avg_saturation"] = float(avg_saturation)
            if avg_color_temp is not None:
                cache_update["avg_color_temp"] = float(avg_color_temp)
            if mood_tags is not None:
                cache_update["mood_tags"] = mood_tags

            # C3-Fix (D-C1, 2026-05-19): cache + video_clips synchron halten
            # (Truth-Source-Konsolidierung analog Audio-Pfad).
            with self._state_lock:
                if clip_id in self.video_analysis_cache:
                    self.video_analysis_cache[clip_id].update(cache_update)
                else:
                    self.video_analysis_cache[clip_id] = {
                        "clip_id": clip_id,
                        **cache_update,
                        "duration_seconds": clip.get("duration_seconds", 0.0),
                    }
                # D-C1 Truth-Source: spiegele cache_update in video_clips
                if clip_id in self.video_clips:
                    self.video_clips[clip_id].update(cache_update)

            motion_str = f"{avg_motion:.2f}" if isinstance(avg_motion, (int, float)) else "—"
            logger.debug(
                f"Video-Analyse für Clip {clip_id} persistiert "
                f"(scenes={scene_count}, motion={motion_str}, "
                f"emb_dim={embedding_dim}, emb_samples={embedding_samples})"
            )
        except Exception as e:
            logger.error(f"Video-Analyse DB-Persistenz fehlgeschlagen: {e}", exc_info=True)
            _emit_persist_error(
                "video_analysis",
                f"Video-Analyse für Clip {clip_id} nicht gespeichert",
                str(e),
            )

    def persist_audio_clip(self, clip: dict, project_id: Optional[int] = None) -> None:
        """
        Persistiert einen Audio-Clip in SQLite für das aktuell aktive Projekt.
        Fehler werden NUR geloggt — niemals geworfen (nicht kritisch für Import).
        """
        try:
            active_project_id = (
                int(project_id)
                if project_id is not None
                else self.require_current_project_db_id()
            )
            from pb_studio.data.repositories.media_repository import MediaRepository
            repo = MediaRepository()
            meta = {
                "clip_type": "audio",
                "clip_id": clip["id"],
                "name": clip.get("name", ""),
                "sample_rate": clip.get("sample_rate", 44100),
                "channels": clip.get("channels", 2),
                "format": clip.get("format", ""),
                # L-N2: audio_hash in Metadata persistieren damit Reload den
                # Cache-Hash sieht (UI-Badge + EmbeddingCache-Lookup).
                "audio_hash": clip.get("audio_hash"),
                # L-AUDIO-8 (CD-1): Demucs-Stem-Pfade persistieren — sonst geht
                # use_stem_pacing nach Backend-Restart silent kaputt
                # (Demucs ist 10min GPU-Aufwand pro Track).
                "stems_paths": clip.get("stems_paths"),
            }
            repo.add_media(
                project_id=active_project_id,
                file_path=clip["path"],
                file_hash=clip.get("audio_hash") or "",
                duration=clip.get("duration_seconds", 0.0),
                meta=meta,
            )
            logger.debug(f"Audio Clip {clip['id']} in DB persistiert")
        except Exception as e:
            logger.error(f"Audio-Clip DB-Persistenz fehlgeschlagen: {e}", exc_info=True)
            _emit_persist_error(
                "audio_import",
                f"Audio-Clip {clip.get('id')} nicht in DB gespeichert — beim Restart weg",
                str(e),
            )

    def persist_video_clip(self, clip: dict, project_id: Optional[int] = None) -> None:
        """
        Persistiert einen Video-Clip in SQLite für das aktuell aktive Projekt.
        Fehler werden NUR geloggt — niemals geworfen (nicht kritisch für Import).
        """
        try:
            active_project_id = (
                int(project_id)
                if project_id is not None
                else self.require_current_project_db_id()
            )
            from pb_studio.data.repositories.media_repository import MediaRepository
            repo = MediaRepository()
            meta = {
                "clip_type": "video",
                "clip_id": clip["id"],
                "name": clip.get("name", ""),
                "width": clip.get("width", 1920),
                "height": clip.get("height", 1080),
                "fps": clip.get("fps", 30.0),
                "codec": clip.get("codec", ""),
                # L-VIDEO-3 (CD-3): video_hash in Metadata persistieren — analog
                # L-N2 audio_hash. Wird vom EmbeddingCache + CACHED-Badge gelesen.
                "video_hash": clip.get("video_hash"),
            }
            repo.add_media(
                project_id=active_project_id,
                file_path=clip["path"],
                # L-VIDEO-3: file_hash explizit setzen (vorher hardcoded "").
                # Erlaubt EmbeddingCache-Hit nach Restart.
                file_hash=clip.get("video_hash") or "",
                duration=clip.get("duration_seconds", 0.0),
                meta=meta,
            )
            logger.debug(f"Video Clip {clip['id']} in DB persistiert")
        except Exception as e:
            logger.error(f"Video-Clip DB-Persistenz fehlgeschlagen: {e}", exc_info=True)
            _emit_persist_error(
                "video_import",
                f"Video-Clip {clip.get('id')} nicht in DB gespeichert — beim Restart weg",
                str(e),
            )

    def load_from_db(self, project_id: Optional[int] = None) -> bool:
        """
        Lädt alle persistierten Clips aus SQLite für das aktive bzw. übergebene Projekt.
        Stellt audio_clips, video_clips und ID-Counter wieder her.
        Fehler werden NUR geloggt — Backend startet immer (leerer State ist OK).

        Wichtig: Vor dem Restore wird der aktuelle Medienkatalog ersetzt statt gemerged,
        damit Re-Open/Restore deterministisch bleibt und keine stale In-Memory-Clips mitschleppt.
        """
        try:
            from pb_studio.data.repositories.media_repository import MediaRepository
            from pb_studio.data.vector_operation_outbox import VectorOperationOutbox

            repo = MediaRepository()
            project_id = int(project_id or self.get_current_project_db_id())
            repository_db = getattr(repo, "db", None)
            if repository_db is not None:
                recovered = VectorOperationOutbox(db=repository_db).recover_pending(
                    project_id=project_id
                )
                if recovered:
                    logger.info(
                        "Vector-Outbox-Recovery fuer Projekt %s: %s Operation(en)",
                        project_id,
                        recovered,
                    )
            rows = repo.get_by_project(project_id=project_id)

            max_audio_id = 0
            max_video_id = 0
            audio_count = 0
            video_count = 0
            unavailable_count = 0

            # Clips und Analyse-Caches in lokalen Variablen sammeln, dann unter Lock zuweisen
            tmp_audio: dict[int, dict] = {}
            tmp_video: dict[int, dict] = {}
            tmp_audio_analysis: dict[int, dict] = {}
            tmp_video_analysis: dict[int, dict] = {}

            for row in rows:
                raw_meta = row.get("metadata_json") or "{}"
                try:
                    meta = json.loads(raw_meta)
                except json.JSONDecodeError:
                    logger.warning(f"Ungültige metadata_json in DB-Row: {raw_meta[:80]}")
                    continue

                clip_type = meta.get("clip_type")
                clip_id = meta.get("clip_id")

                # Sicherheitsprüfung: clip_id und clip_type müssen vorhanden sein
                if not clip_type or clip_id is None:
                    continue

                try:
                    clip_id = int(clip_id)
                except (TypeError, ValueError):
                    logger.warning("Ungültige clip_id in Media-DB-Eintrag: %r", clip_id)
                    continue

                if clip_type == "audio":
                    max_audio_id = max(max_audio_id, clip_id)
                elif clip_type == "video":
                    max_video_id = max(max_video_id, clip_id)
                else:
                    logger.warning(
                        "Ungültiger clip_type in Media-DB-Eintrag %r: %r",
                        row.get("id"),
                        clip_type,
                    )
                    continue

                file_path = row.get("file_path")
                if not file_path:
                    unavailable_count += 1
                    logger.warning(
                        "Medium derzeit nicht erreichbar; DB-Eintrag %r bleibt erhalten: %s",
                        row.get("id"),
                        file_path,
                    )
                    continue
                from backend.media_path_policy import (
                    MediaPathPolicyError,
                    canonical_local_media_file,
                    canonical_local_media_reference,
                )
                try:
                    file_reference = canonical_local_media_reference(
                        str(file_path),
                        label=f"Media-DB-Eintrag {row.get('id')} file_path",
                    )
                except MediaPathPolicyError as exc:
                    raise ValueError(
                        f"Unsicherer Medienpfad in DB-Eintrag {row.get('id')}: {exc}"
                    ) from exc
                if not file_reference.is_file():
                    unavailable_count += 1
                    logger.warning(
                        "Medium derzeit nicht erreichbar; DB-Eintrag %r bleibt erhalten: %s",
                        row.get("id"),
                        file_reference,
                    )
                    continue
                file_path = str(
                    canonical_local_media_file(
                        str(file_reference),
                        label=f"Media-DB-Eintrag {row.get('id')} file_path",
                    )
                )

                # Analyse-Daten aus ai_data_json laden
                raw_ai = row.get("ai_data_json") or "{}"
                try:
                    ai_data = json.loads(raw_ai)
                except json.JSONDecodeError:
                    ai_data = {}

                # C4-Fix (S-C1, 2026-05-19): Schema-Drift abfangen — legacy-Blobs
                # ohne __schema_version werden on-the-fly migriert (audio_hash,
                # stems_paths, video_hash, subtrack_segments etc. werden defaulted).
                from pb_studio.data.schemas.media_json_schema import (
                    migrate_audio_metadata, migrate_audio_ai_data,
                    migrate_video_metadata, migrate_video_ai_data,
                )
                if clip_type == "audio":
                    meta = migrate_audio_metadata(meta)
                    ai_data = migrate_audio_ai_data(ai_data)
                elif clip_type == "video":
                    meta = migrate_video_metadata(meta)
                    ai_data = migrate_video_ai_data(ai_data)

                if clip_type == "audio":
                    is_analyzed = bool(ai_data.get("is_analyzed", False))
                    clip = {
                        "id": clip_id,
                        "name": meta.get("name", ""),
                        "path": file_path,
                        "duration_seconds": row.get("duration_sec") or 0.0,
                        "sample_rate": meta.get("sample_rate", 44100),
                        "channels": meta.get("channels", 2),
                        "format": meta.get("format", ""),
                        "bpm": float(ai_data.get("bpm", 0.0) or 0.0),
                        "key": ai_data.get("key"),
                        "beat_count": int(ai_data.get("beat_count", 0) or 0),
                        "is_analyzed": is_analyzed,
                        # L-N2: audio_hash aus Meta (oder Legacy file_hash) zurueck
                        # ins In-Memory-Dict damit UI-Badge + Pacing-Cache funktionieren.
                        "audio_hash": meta.get("audio_hash") or row.get("file_hash") or None,
                        # L-AUDIO-8 (CD-1): Stem-Pfade restoren — pacing_router liest sie
                        # direkt via state.audio_clips[id]["stems_paths"].
                        # Dict {vocals|drums|bass|other -> path}.
                        "stems_paths": meta.get("stems_paths"),
                    }
                    tmp_audio[clip_id] = clip
                    audio_count += 1

                    # Audio-Analyse-Cache wiederherstellen (Beats aus beats_json)
                    # L-AUDIO-6 (CD-4 / M-3): Cache-Restore entkoppelt von is_analyzed —
                    # Import-Flow (subtrack-detect via librosa) schreibt subtrack_segments
                    # und tempo_curve ohne is_analyzed=True. Diese duerfen beim Reload
                    # nicht silent verloren gehen. Subtrack-Detection ist 15-30s CPU,
                    # Tempo-Curve braucht audio re-load → nicht billig.
                    if ai_data:
                        beats_raw = ai_data.get("beats_json", "[]")
                        try:
                            beats = json.loads(beats_raw) if isinstance(beats_raw, str) else beats_raw
                        except json.JSONDecodeError:
                            beats = []
                        tmp_audio_analysis[clip_id] = {
                            "clip_id": clip_id,
                            "bpm": float(ai_data.get("bpm", 0.0) or 0.0),
                            "key": ai_data.get("key"),
                            "beat_count": int(ai_data.get("beat_count", 0) or 0),
                            "beats": beats,
                            "energy_curve": ai_data.get("energy_curve", []),
                            "structure_segments": ai_data.get("structure_segments", []),
                            "spectral_data": ai_data.get("spectral_data"),
                            # L-AUDIO-6: Subtracks + Tempo-Curve mit-restoren
                            "subtrack_segments": ai_data.get("subtrack_segments", []),
                            "tempo_curve": ai_data.get("tempo_curve", []),
                            # Audit-Fix 2026-07-10: Onset/Drum-Trigger-Kandidaten restoren
                            "onset_times": ai_data.get("onset_times", []),
                            "kick_times": ai_data.get("kick_times", []),
                            "snare_times": ai_data.get("snare_times", []),
                            "hihat_times": ai_data.get("hihat_times", []),
                            "chunk_evidence": ai_data.get("chunk_evidence", {}),
                            "_analysis_status": ai_data.get(
                                "analysis_status",
                                "completed" if is_analyzed else "partial",
                            ),
                            "_stage_status": ai_data.get("stage_status", {}),
                            "_stage_errors": ai_data.get("stage_errors", {}),
                            "downbeats": ai_data.get("downbeats", []),
                            "downbeat_provenance": ai_data.get(
                                "downbeat_provenance",
                                {
                                    "status": "unavailable",
                                    "method": "legacy_cache",
                                    "synthetic": False,
                                    "measured_count": 0,
                                },
                            ),
                            "is_analyzed": is_analyzed,
                            "duration_seconds": row.get("duration_sec") or 0.0,
                        }

                elif clip_type == "video":
                    is_analyzed = bool(ai_data.get("is_analyzed", False))
                    clip = {
                        "id": clip_id,
                        "name": meta.get("name", ""),
                        "path": file_path,
                        "duration_seconds": row.get("duration_sec") or 0.0,
                        "width": meta.get("width", 1920),
                        "height": meta.get("height", 1080),
                        "fps": meta.get("fps", 30.0),
                        "codec": meta.get("codec", ""),
                        # D-H1 fix (Audit V2): filesystem-check statt fix False.
                        # Thumbnail-Konvention: project_dir/proxy_cache/clip_{id}_thumb.jpg
                        # (siehe thumbnail_generator.generate_clip_thumbnail). Wenn vorhanden
                        # → True; sonst False, UI rendert dann fallback.
                        "thumbnail_available": _thumbnail_exists_for_clip(
                            clip_id, self.current_project, file_path
                        ),
                        "tags": [],
                        # L-VIDEO-3 (CD-3): video_hash aus Meta (oder Legacy
                        # file_hash) zurueck ins In-Memory-Dict damit
                        # UI-CACHED-Badge + EmbeddingCache-Lookup funktionieren.
                        "video_hash": meta.get("video_hash") or row.get("file_hash") or None,
                    }
                    tmp_video[clip_id] = clip
                    video_count += 1

                    # Video-Analyse-Cache wiederherstellen
                    if is_analyzed and ai_data:
                        tmp_video_analysis[clip_id] = {
                            "clip_id": clip_id,
                            "scene_count": int(ai_data.get("scene_count", 0) or 0),
                            "avg_motion": float(ai_data.get("avg_motion", 0.0) or 0.0),
                            "has_embedding": bool(ai_data.get("has_embedding", False)),
                            "scenes": ai_data.get("scenes", []),
                            "motion": ai_data.get("motion", {}),
                            "dominant_colors": ai_data.get("dominant_colors", []),
                            "tags": ai_data.get("tags", []),
                            # L-M8: SigLIP-Embedding-Metadaten nach Reload zeigen
                            "embedding_dim": int(ai_data.get("embedding_dim", 0) or 0),
                            "embedding_samples": int(ai_data.get("embedding_samples", 0) or 0),
                            "audio_key": ai_data.get("audio_key"),
                            # Audit-Fix 2026-07-10 (Sweep-Finding HIGH-10)
                            "avg_brightness": float(ai_data.get("avg_brightness", 0.5) or 0.5),
                            "avg_saturation": float(ai_data.get("avg_saturation", 0.5) or 0.5),
                            "avg_color_temp": float(ai_data.get("avg_color_temp", 0.0) or 0.0),
                            "mood_tags": ai_data.get("mood_tags", []),
                        }

            # Unter Lock alle Clips und Caches atomar leeren und zuweisen (R-2 Fix)
            with self._state_lock:
                self.audio_clips.clear()
                self.audio_clips.update(tmp_audio)
                
                self.video_clips.clear()
                self.video_clips.update(tmp_video)
                
                self.audio_analysis_cache.clear()
                if tmp_audio_analysis:
                    self.audio_analysis_cache.update(tmp_audio_analysis)
                    
                self.video_analysis_cache.clear()
                if tmp_video_analysis:
                    self.video_analysis_cache.update(tmp_video_analysis)

            # ID-Counter nach dem Load atomar anpassen
            with self._lock:
                self._audio_next_id = max_audio_id + 1 if max_audio_id > 0 else 1
                self._video_next_id = max_video_id + 1 if max_video_id > 0 else 1

            logger.info(
                f"DB-Load OK für Projekt {project_id}: {audio_count} Audio-Clips, {video_count} Video-Clips wiederhergestellt"
                f" (Audio-Analyse: {len(tmp_audio_analysis)}, Video-Analyse: {len(tmp_video_analysis)} gecacht,"
                f" {unavailable_count} nicht erreichbare Medien übersprungen und in DB erhalten)"
            )
            return True

        except Exception as e:
            logger.warning(f"DB-Load fehlgeschlagen (unkritisch — leerer State): {e}")
            return False

    # =========================================================================
    # Render-Queue-Persistenz (Resume on startup)
    # =========================================================================

    def restore_render_queue_on_startup(self) -> list[str]:
        """Resume on startup: alle persistierten Render-Jobs mit Status 'running'
        werden auf 'interrupted' gesetzt und damit re-queued.

        Wird einmal aus dem FastAPI-Lifespan-Startup aufgerufen, BEVOR neue
        Render-Requests angenommen werden. Idempotent: leerer Restore (keine
        running-Zeilen) ist OK; Fehler werden nur geloggt, das Backend startet
        immer.

        Returns:
            Liste der job_ids, die von 'running' nach 'interrupted' überführt
            wurden (kann leer sein).
        """
        try:
            from pb_studio.rendering.render_queue import get_render_queue
            queue = get_render_queue()
            requeued = queue.restore_running_as_interrupted()
            if requeued:
                logger.info(
                    "Render-Queue Restore: %d Job(s) als 'interrupted' requeued: %s",
                    len(requeued), requeued,
                )
            else:
                logger.debug("Render-Queue Restore: keine 'running' Jobs vorhanden")
            return requeued
        except Exception as e:
            logger.warning(
                "Render-Queue Restore-on-Startup fehlgeschlagen (unkritisch): %s", e,
            )
            return []


# Prozess-weiter Singleton
_state = AppState()


def get_app_state() -> AppState:
    """FastAPI Dependency: Gibt den globalen AppState zurück."""
    return _state
