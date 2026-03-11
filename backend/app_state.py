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

import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pb_studio.data.database_core import normalize_media_path

logger = logging.getLogger(__name__)


def resolve_active_project_root(state: "AppState", fallback_root: str | Path) -> Path:
    """Gibt den aktiven Projekt-Root zurück, sonst den konfigurierten Fallback."""
    current = state.current_project or {}
    current_path = current.get("path") if isinstance(current, dict) else None
    if current_path:
        return Path(current_path).resolve()
    return Path(fallback_root).resolve()


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
        """Thread-safe Zugriff auf einen Audio-Clip."""
        with self._state_lock:
            return self.audio_clips.get(clip_id)

    def set_audio_clip(self, clip_id: int, clip: dict) -> None:
        """Thread-safe Setzen eines Audio-Clips."""
        with self._state_lock:
            self.audio_clips[clip_id] = clip

    def get_video_clip(self, clip_id: int) -> Optional[dict]:
        """Thread-safe Zugriff auf einen Video-Clip."""
        with self._state_lock:
            return self.video_clips.get(clip_id)

    def set_video_clip(self, clip_id: int, clip: dict) -> None:
        """Thread-safe Setzen eines Video-Clips."""
        with self._state_lock:
            self.video_clips[clip_id] = clip

    def get_audio_clips_snapshot(self) -> dict[int, dict]:
        """Thread-safe Snapshot aller Audio-Clips."""
        with self._state_lock:
            return dict(self.audio_clips)

    def get_video_clips_snapshot(self) -> dict[int, dict]:
        """Thread-safe Snapshot aller Video-Clips."""
        with self._state_lock:
            return dict(self.video_clips)

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

    def set_cancel_flag(self, task_id: str, value: bool) -> None:
        """Thread-safe Setzen eines Cancel-Flags."""
        with self._state_lock:
            self.cancel_flags[task_id] = value

    def get_cancel_flag(self, task_id: str) -> bool:
        """Thread-safe Lesen eines Cancel-Flags."""
        with self._state_lock:
            return self.cancel_flags.get(task_id, False)

    def reset(self) -> None:
        """Setzt den gesamten State zurück (z.B. bei neuem Projekt)."""
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
                self.cancel_flags.clear()
                self._audio_next_id = 1
                self._video_next_id = 1

    # =========================================================================
    # ADR-003 Phase 2: SQLite-Persistenz
    # =========================================================================

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
        in_memory = self._find_audio_clip_by_path(clip_data["path"])
        if in_memory:
            return in_memory

        try:
            from pb_studio.data.repositories.media_repository import MediaRepository
            repo = MediaRepository()
            row = repo.find_by_project_and_path(project_id=1, file_path=clip_data["path"])
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
        self.persist_audio_clip(clip)
        return clip

    def register_video_clip(self, clip_data: dict) -> dict:
        """Reuse an existing canonical video clip for the same real file when possible."""
        in_memory = self._find_video_clip_by_path(clip_data["path"])
        if in_memory:
            return in_memory

        try:
            from pb_studio.data.repositories.media_repository import MediaRepository
            repo = MediaRepository()
            row = repo.find_by_project_and_path(project_id=1, file_path=clip_data["path"])
            if row:
                meta = json.loads(row.get("metadata_json") or "{}")
                if meta.get("clip_type") == "video" and meta.get("clip_id") is not None:
                    clip_id = int(meta["clip_id"])
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
        self.persist_video_clip(clip)
        return clip

    def persist_audio_clip(self, clip: dict) -> None:
        """
        Persistiert einen Audio-Clip in SQLite (project_id=1).
        Fehler werden NUR geloggt — niemals geworfen (nicht kritisch für Import).
        """
        try:
            from pb_studio.data.repositories.media_repository import MediaRepository
            repo = MediaRepository()
            meta = {
                "clip_type": "audio",
                "clip_id": clip["id"],
                "name": clip.get("name", ""),
                "sample_rate": clip.get("sample_rate", 44100),
                "channels": clip.get("channels", 2),
                "format": clip.get("format", ""),
            }
            repo.add_media(
                project_id=1,
                file_path=clip["path"],
                file_hash="",
                duration=clip.get("duration_seconds", 0.0),
                meta=meta,
            )
            logger.debug(f"Audio Clip {clip['id']} in DB persistiert")
        except Exception as e:
            logger.warning(f"Audio-Clip DB-Persistenz fehlgeschlagen (unkritisch): {e}")

    def persist_video_clip(self, clip: dict) -> None:
        """
        Persistiert einen Video-Clip in SQLite (project_id=1).
        Fehler werden NUR geloggt — niemals geworfen (nicht kritisch für Import).
        """
        try:
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
            }
            repo.add_media(
                project_id=1,
                file_path=clip["path"],
                file_hash="",
                duration=clip.get("duration_seconds", 0.0),
                meta=meta,
            )
            logger.debug(f"Video Clip {clip['id']} in DB persistiert")
        except Exception as e:
            logger.warning(f"Video-Clip DB-Persistenz fehlgeschlagen (unkritisch): {e}")

    def load_from_db(self) -> None:
        """
        Lädt alle persistierten Clips aus SQLite beim Backend-Startup.
        Stellt audio_clips, video_clips und ID-Counter wieder her.
        Fehler werden NUR geloggt — Backend startet immer (leerer State ist OK).
        """
        try:
            from pb_studio.data.repositories.media_repository import MediaRepository
            repo = MediaRepository()
            rows = repo.get_by_project(project_id=1)

            max_audio_id = 0
            max_video_id = 0
            audio_count = 0
            video_count = 0
            stale_count = 0

            for row in rows:
                file_path = row.get("file_path")
                if not file_path or not Path(file_path).exists():
                    stale_count += 1
                    media_id = row.get("id")
                    logger.warning(f"Überspringe verwaisten Media-DB-Eintrag {media_id}: {file_path}")
                    if media_id is not None:
                        try:
                            repo.delete_media(media_id)
                        except Exception as cleanup_error:
                            logger.warning(
                                f"Konnte verwaisten Media-DB-Eintrag {media_id} nicht löschen: {cleanup_error}"
                            )
                    continue

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

                if clip_type == "audio":
                    clip = {
                        "id": clip_id,
                        "name": meta.get("name", ""),
                        "path": row["file_path"],
                        "duration_seconds": row.get("duration_sec") or 0.0,
                        "sample_rate": meta.get("sample_rate", 44100),
                        "channels": meta.get("channels", 2),
                        "format": meta.get("format", ""),
                    }
                    self.audio_clips[clip_id] = clip
                    max_audio_id = max(max_audio_id, clip_id)
                    audio_count += 1

                elif clip_type == "video":
                    clip = {
                        "id": clip_id,
                        "name": meta.get("name", ""),
                        "path": row["file_path"],
                        "duration_seconds": row.get("duration_sec") or 0.0,
                        "width": meta.get("width", 1920),
                        "height": meta.get("height", 1080),
                        "fps": meta.get("fps", 30.0),
                        "codec": meta.get("codec", ""),
                        "thumbnail_available": False,
                        "tags": [],
                    }
                    self.video_clips[clip_id] = clip
                    max_video_id = max(max_video_id, clip_id)
                    video_count += 1

            # ID-Counter nach dem Load anpassen
            with self._lock:
                if max_audio_id > 0:
                    self._audio_next_id = max_audio_id + 1
                if max_video_id > 0:
                    self._video_next_id = max_video_id + 1

            logger.info(
                f"DB-Load OK: {audio_count} Audio-Clips, {video_count} Video-Clips wiederhergestellt"
                f" ({stale_count} verwaiste Einträge übersprungen)"
            )

        except Exception as e:
            logger.warning(f"DB-Load fehlgeschlagen (unkritisch — leerer State): {e}")


# Prozess-weiter Singleton
_state = AppState()


def get_app_state() -> AppState:
    """FastAPI Dependency: Gibt den globalen AppState zurück."""
    return _state
