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
from pb_studio.data.repositories.project_repository import ProjectRepository

logger = logging.getLogger(__name__)


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

    def get_current_project_db_id(self) -> int:
        """Aktive DB-Projekt-ID; 1 bleibt Legacy-Fallback wenn kein Projekt geöffnet ist."""
        with self._state_lock:
            return resolve_project_db_id(self.current_project)

    def sync_project_db_record(self) -> None:
        """Schreibt current_project in die Projects-Tabelle, falls eine DB-Projekt-ID bekannt ist."""
        with self._state_lock:
            project = dict(self.current_project) if isinstance(self.current_project, dict) else None

        if not project:
            return

        project_id = resolve_project_db_id(project)
        project_data = {
            "path": project.get("path"),
            "audio_count": project.get("audio_count", 0),
            "video_count": project.get("video_count", 0),
            "has_timeline": project.get("has_timeline", False),
            "created_at": project.get("created_at"),
            "modified_at": project.get("modified_at"),
        }
        try:
            ProjectRepository().update_project(project_id, name=project.get("name"), data=project_data)
        except Exception as e:
            logger.warning("Projekt-DB-Sync fehlgeschlagen (unkritisch): %s", e)

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
            row = repo.find_by_project_and_path(
                project_id=self.get_current_project_db_id(),
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
            row = repo.find_by_project_and_path(
                project_id=self.get_current_project_db_id(),
                file_path=clip_data["path"],
            )
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

    def update_audio_analysis(
        self,
        clip_id: int,
        bpm: float,
        key: Optional[str],
        beat_count: int,
        beats_json: str,
        is_analyzed: bool,
    ) -> None:
        """
        Persistiert Audio-Analyse-Ergebnisse (BPM, Key, BeatCount, Beats) in der ai_data_json-Spalte
        des zugehörigen media-Eintrags.
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
            # beats_json is already a serialised JSON string — parse it back to a list
            # so that the surrounding json.dumps() in the repository layer does not
            # double-encode it into a string-of-a-string.
            try:
                beats_list = json.loads(beats_json) if beats_json else []
            except (json.JSONDecodeError, TypeError):
                beats_list = []
                logger.warning("update_audio_analysis: beats_json konnte nicht geparst werden; leere Liste verwendet")

            ai_data = {
                "bpm": bpm,
                "key": key,
                "beat_count": beat_count,
                "beats_json": beats_list,
                "is_analyzed": is_analyzed,
            }
            repo.update_status(row["id"], "analyzed", ai_data=ai_data)
            logger.debug(f"Audio-Analyse für Clip {clip_id} in DB persistiert (bpm={bpm:.1f}, key={key})")
        except Exception as e:
            logger.warning(f"Audio-Analyse DB-Persistenz fehlgeschlagen (unkritisch): {e}")

    def update_video_analysis(
        self,
        clip_id: int,
        scene_count: int,
        avg_motion: float,
        has_embedding: bool,
        is_analyzed: bool,
    ) -> None:
        """
        Persistiert Video-Analyse-Ergebnisse (scene_count, avg_motion, has_embedding) in der
        ai_data_json-Spalte des zugehörigen media-Eintrags.
        Fehler werden NUR geloggt — nie geworfen (nicht kritisch für den Analyseworkflow).
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
            if row is None:
                logger.warning(f"update_video_analysis: Kein DB-Eintrag für Clip {clip_id} ({clip['path']})")
                return
            ai_data = {
                "scene_count": scene_count,
                "avg_motion": avg_motion,
                "has_embedding": has_embedding,
                "is_analyzed": is_analyzed,
            }
            repo.update_status(row["id"], "analyzed", ai_data=ai_data)
            logger.debug(f"Video-Analyse für Clip {clip_id} in DB persistiert (scenes={scene_count}, motion={avg_motion:.2f})")
        except Exception as e:
            logger.warning(f"Video-Analyse DB-Persistenz fehlgeschlagen (unkritisch): {e}")

    def persist_audio_clip(self, clip: dict) -> None:
        """
        Persistiert einen Audio-Clip in SQLite für das aktuell aktive Projekt.
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
                project_id=self.get_current_project_db_id(),
                file_path=clip["path"],
                file_hash="",
                duration=clip.get("duration_seconds", 0.0),
                meta=meta,
            )
            logger.debug(f"Audio Clip {clip['id']} in DB persistiert")
        except Exception as e:
            logger.error(f"Audio-Clip DB-Persistenz fehlgeschlagen (unkritisch): {e}", exc_info=True)

    def persist_video_clip(self, clip: dict) -> None:
        """
        Persistiert einen Video-Clip in SQLite für das aktuell aktive Projekt.
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
                project_id=self.get_current_project_db_id(),
                file_path=clip["path"],
                file_hash="",
                duration=clip.get("duration_seconds", 0.0),
                meta=meta,
            )
            logger.debug(f"Video Clip {clip['id']} in DB persistiert")
        except Exception as e:
            logger.error(f"Video-Clip DB-Persistenz fehlgeschlagen (unkritisch): {e}", exc_info=True)

    def load_from_db(self, project_id: Optional[int] = None) -> None:
        """
        Lädt alle persistierten Clips aus SQLite für das aktive bzw. übergebene Projekt.
        Stellt audio_clips, video_clips und ID-Counter wieder her.
        Fehler werden NUR geloggt — Backend startet immer (leerer State ist OK).

        Wichtig: Vor dem Restore wird der aktuelle Medienkatalog ersetzt statt gemerged,
        damit Re-Open/Restore deterministisch bleibt und keine stale In-Memory-Clips mitschleppt.
        """
        try:
            from pb_studio.data.repositories.media_repository import MediaRepository
            repo = MediaRepository()
            project_id = int(project_id or self.get_current_project_db_id())
            rows = repo.get_by_project(project_id=project_id)

            with self._state_lock:
                self.audio_clips.clear()
                self.audio_analysis_cache.clear()
                self.video_clips.clear()
                self.video_analysis_cache.clear()
            with self._lock:
                self._audio_next_id = 1
                self._video_next_id = 1

            max_audio_id = 0
            max_video_id = 0
            audio_count = 0
            video_count = 0
            stale_count = 0

            # Clips und Analyse-Caches in lokalen Variablen sammeln, dann unter Lock zuweisen
            tmp_audio: dict[int, dict] = {}
            tmp_video: dict[int, dict] = {}
            tmp_audio_analysis: dict[int, dict] = {}
            tmp_video_analysis: dict[int, dict] = {}

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

                try:
                    clip_id = int(clip_id)
                except (TypeError, ValueError):
                    logger.warning("Ungültige clip_id in Media-DB-Eintrag: %r", clip_id)
                    continue

                # Analyse-Daten aus ai_data_json laden
                raw_ai = row.get("ai_data_json") or "{}"
                try:
                    ai_data = json.loads(raw_ai)
                except json.JSONDecodeError:
                    ai_data = {}

                if clip_type == "audio":
                    is_analyzed = bool(ai_data.get("is_analyzed", False))
                    clip = {
                        "id": clip_id,
                        "name": meta.get("name", ""),
                        "path": row["file_path"],
                        "duration_seconds": row.get("duration_sec") or 0.0,
                        "sample_rate": meta.get("sample_rate", 44100),
                        "channels": meta.get("channels", 2),
                        "format": meta.get("format", ""),
                        "bpm": float(ai_data.get("bpm", 0.0) or 0.0),
                        "key": ai_data.get("key"),
                        "beat_count": int(ai_data.get("beat_count", 0) or 0),
                        "is_analyzed": is_analyzed,
                    }
                    tmp_audio[clip_id] = clip
                    max_audio_id = max(max_audio_id, clip_id)
                    audio_count += 1

                    # Audio-Analyse-Cache wiederherstellen (Beats aus beats_json)
                    if is_analyzed and ai_data:
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
                            "energy_curve": [],
                            "structure_segments": [],
                            "spectral_data": None,
                            "duration_seconds": row.get("duration_sec") or 0.0,
                        }

                elif clip_type == "video":
                    is_analyzed = bool(ai_data.get("is_analyzed", False))
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
                    tmp_video[clip_id] = clip
                    max_video_id = max(max_video_id, clip_id)
                    video_count += 1

                    # Video-Analyse-Cache wiederherstellen
                    if is_analyzed and ai_data:
                        tmp_video_analysis[clip_id] = {
                            "clip_id": clip_id,
                            "scene_count": int(ai_data.get("scene_count", 0) or 0),
                            "avg_motion": float(ai_data.get("avg_motion", 0.0) or 0.0),
                            "has_embedding": bool(ai_data.get("has_embedding", False)),
                            "scenes": [],
                            "motion": {},
                            "dominant_colors": [],
                            "tags": [],
                        }

            # Unter Lock alle Clips und Analyse-Caches atomar zuweisen
            with self._state_lock:
                self.audio_clips.update(tmp_audio)
                self.video_clips.update(tmp_video)
                if tmp_audio_analysis:
                    self.audio_analysis_cache.update(tmp_audio_analysis)
                if tmp_video_analysis:
                    self.video_analysis_cache.update(tmp_video_analysis)

            # ID-Counter nach dem Load anpassen
            with self._lock:
                if max_audio_id > 0:
                    self._audio_next_id = max_audio_id + 1
                if max_video_id > 0:
                    self._video_next_id = max_video_id + 1

            logger.info(
                f"DB-Load OK für Projekt {project_id}: {audio_count} Audio-Clips, {video_count} Video-Clips wiederhergestellt"
                f" (Audio-Analyse: {len(tmp_audio_analysis)}, Video-Analyse: {len(tmp_video_analysis)} gecacht,"
                f" {stale_count} verwaiste Einträge übersprungen)"
            )

        except Exception as e:
            logger.warning(f"DB-Load fehlgeschlagen (unkritisch — leerer State): {e}")


# Prozess-weiter Singleton
_state = AppState()


def get_app_state() -> AppState:
    """FastAPI Dependency: Gibt den globalen AppState zurück."""
    return _state
