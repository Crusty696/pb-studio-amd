"""
Audio Router – Import, Analyse, Beats, Waveform, Stems.

Endpoints:
  POST /audio/import           — Audio-Datei importieren
  POST /audio/analyze          — Audio analysieren (Beats, Struktur, Spektral)
  GET  /audio/beats/{id}       — Beat-Daten abrufen
  GET  /audio/waveform/{id}    — Waveform-Daten abrufen
  POST /audio/stems/separate   — Stem-Separation starten
  GET  /audio/structure/{id}   — Struktur-Segmente abrufen
  GET  /audio/spectral/{id}    — Spektral-Analyse abrufen
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..app_state import (
    AppState,
    PersistenceError,
    ProjectContextChangedError,
    ProjectContextUnavailableError,
    ProjectOperationContext,
    get_app_state,
)
from ..config import config
from ..dependencies import with_gpu_task, publish_event, publish_log
from ..media_path_policy import (
    MediaPathPolicyError,
    canonical_local_media_file,
    canonical_local_media_reference,
)
from ..schemas.audio_schemas import (
    AudioImportRequest, AudioClipInfo,
    AudioAnalyzeRequest, AudioAnalysisResult,
    BeatData, WaveformData,
    StemSeparateRequest, StemResult,
    StructureSegment, SpectralData,
)
from ..schemas.common import BatchDeleteRequest, DeleteResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audio", tags=["Audio"])

# Module-level BeatDetector singleton — avoids re-initializing (model load) on every call
_beat_detector: "Any | None" = None
_beat_detector_lock = __import__("threading").Lock()
_LONG_STEM_TIMEOUT_RATIO = 0.75
def _stem_timeout_for_duration(duration_seconds: float, configured_timeout: float) -> float:
    """Allow long mixes enough wall time while retaining the configured floor."""
    duration = max(0.0, float(duration_seconds))
    return max(float(configured_timeout), duration * _LONG_STEM_TIMEOUT_RATIO)


def _find_reusable_stem_files(
    audio_path: str,
    model_name: str,
    output_dir: Path,
) -> list[str]:
    """Return stems only when an exact successful-run marker still validates."""
    import json
    import soundfile as sf

    source = Path(audio_path)
    required_roles = _required_stem_roles(model_name)
    if not required_roles:
        return []

    marker_path = _stem_cache_marker_path(source, model_name, output_dir)
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []

    if (
        marker.get("schema_version") != 1
        or marker.get("source") != _stem_source_identity(source)
        or marker.get("model") != Path(model_name).name.casefold()
    ):
        return []

    outputs = marker.get("outputs")
    if not isinstance(outputs, dict) or set(outputs) != required_roles:
        return []

    output_root = output_dir.resolve()
    complete: list[str] = []
    for role in sorted(required_roles):
        record = outputs.get(role)
        if not isinstance(record, dict):
            return []
        try:
            path = Path(record["path"]).resolve()
            if not path.is_relative_to(output_root):
                return []
            if _exact_stem_role(path) != role:
                return []
            stat = path.stat()
            info = sf.info(str(path))
            if (
                stat.st_size <= 0
                or stat.st_size != record.get("size")
                or int(stat.st_mtime_ns) != record.get("mtime_ns")
                or int(info.frames) <= 0
                or int(info.frames) != record.get("frames")
                or int(info.samplerate) != record.get("sample_rate")
                or int(info.channels) != record.get("channels")
            ):
                return []
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return []
        complete.append(str(path.resolve()))
    return sorted(complete)


def _required_stem_roles(model_name: str) -> set[str]:
    model_token = Path(model_name).stem.casefold()
    if "htdemucs" in model_token:
        return {"vocals", "drums", "bass", "other"}
    if "mdx" in model_token or "inst" in model_token:
        return {"vocals", "instrumental"}
    return set()


def _exact_stem_role(path: Path) -> str | None:
    import re

    matches = re.findall(
        r"\((vocals|instrumental|drums|bass|other)\)",
        path.stem,
        flags=re.IGNORECASE,
    )
    return matches[0].casefold() if len(matches) == 1 else None


def _stem_source_identity(source: Path) -> dict[str, int | str]:
    import os

    resolved = source.resolve(strict=True)
    stat = resolved.stat()
    return {
        "path": os.path.normcase(str(resolved)),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _stem_cache_marker_path(
    source: Path,
    model_name: str,
    output_dir: Path,
) -> Path:
    import hashlib
    import json

    identity = {
        "source": _stem_source_identity(source),
        "model": Path(model_name).name.casefold(),
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return output_dir.resolve() / f".{source.stem}.{digest}.stems-complete.json"


def _write_stem_cache_marker(
    audio_path: str,
    model_name: str,
    output_dir: Path,
    stem_files: list[str],
    *,
    state: AppState | None = None,
    context: ProjectOperationContext | None = None,
) -> None:
    """Atomically publish validated output metadata after separator success."""
    import json
    import os
    import soundfile as sf
    import uuid

    source = Path(audio_path)
    required_roles = _required_stem_roles(model_name)
    if not required_roles:
        raise ValueError(f"Unbekanntes Stem-Modell: {model_name}")

    source_duration = float(sf.info(str(source)).duration)
    duration_tolerance = 0.25
    output_root = output_dir.resolve()
    outputs: dict[str, dict[str, int | str]] = {}
    for file_name in stem_files:
        path = Path(file_name).resolve()
        role = _exact_stem_role(path)
        if role is None:
            raise ValueError(f"Stem-Datei hat keine eindeutige exakte Rolle: {path.name}")
        if role not in required_roles or role in outputs:
            raise ValueError(f"Stem-Rolle ist unerwartet oder doppelt: {role}")
        if not path.is_relative_to(output_root):
            raise ValueError(f"Stem-Datei liegt ausserhalb des Output-Ordners: {path}")
        stat = path.stat()
        info = sf.info(str(path))
        if (
            stat.st_size <= 0
            or int(info.frames) <= 0
            or abs(float(info.duration) - source_duration) > duration_tolerance
        ):
            raise ValueError(f"Stem-Datei ist unvollstaendig: {path.name}")
        outputs[role] = {
            "path": str(path),
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "frames": int(info.frames),
            "sample_rate": int(info.samplerate),
            "channels": int(info.channels),
        }

    if set(outputs) != required_roles:
        missing = ", ".join(sorted(required_roles - set(outputs)))
        raise ValueError(f"Stem-Rollen fehlen: {missing}")

    marker_path = _stem_cache_marker_path(source, model_name, output_dir)
    marker = {
        "schema_version": 1,
        "source": _stem_source_identity(source),
        "model": Path(model_name).name.casefold(),
        "outputs": outputs,
    }
    temp_path = marker_path.with_name(f"{marker_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(marker, handle, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        if state is not None and context is not None:
            with state.project_commit(context):
                os.replace(temp_path, marker_path)
        else:
            os.replace(temp_path, marker_path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def _get_beat_detector() -> "Any":
    """Return the module-level BeatDetector singleton (thread-safe init)."""
    global _beat_detector
    # R17/MEDIUM: double-checked locking prevents two worker threads from
    # simultaneously constructing BeatDetector (CPU-intensive, no GPU).
    if _beat_detector is None:
        with _beat_detector_lock:
            if _beat_detector is None:
                from pb_studio.audio.beat_detector import BeatDetector
                _beat_detector = BeatDetector(mode='offline', inference_model='DBN')
    return _beat_detector


@router.post(
    "/import",
    response_model=AudioClipInfo,
    summary="Audio-Datei importieren",
    description=(
        "Importiert eine Audio-Datei (MP3, WAV, FLAC, OGG, M4A, AAC) in den Clip-Store. "
        "Ermittelt Dauer via ffprobe und gibt die Clip-Metadaten zurück."
    ),
)
async def import_audio(
    request: AudioImportRequest,
    state: AppState = Depends(get_app_state),
) -> AudioClipInfo:
    try:
        async with state.project_operation() as context:
            return await _import_audio_in_context(request, state, context)
    except asyncio.CancelledError:
        raise
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _import_audio_in_context(
    request: AudioImportRequest,
    state: AppState,
    context: ProjectOperationContext,
) -> AudioClipInfo:
    """Importiert eine Audio-Datei."""
    try:
        state.require_current_project_db_id()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        audio_reference = canonical_local_media_reference(
            request.path,
            label="Audio-Importpfad",
        )
    except MediaPathPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not audio_reference.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Audio-Datei nicht gefunden: {audio_reference}",
        )
    try:
        audio_path = canonical_local_media_file(
            str(audio_reference),
            label="Audio-Importpfad",
        )
    except MediaPathPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if audio_path.suffix.lower() not in {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".aiff", ".aif"}:
        raise HTTPException(status_code=400, detail=f"Nicht unterstütztes Format: {audio_path.suffix}")

    try:
        probe_info = await asyncio.to_thread(_probe_audio_info, str(audio_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio-Info nicht ermittelbar: {e}")

    # Plan Phase 1 #1: streaming sha256 hash for embedding-cache reuse.
    # User-Anforderung 2026-05-09: feingranulares 0.01% Progress per chunk SSE.
    from pb_studio.core.media_hash import media_hash
    _loop = asyncio.get_running_loop()
    _file_name = audio_path.name

    def _hash_progress(pct: float) -> None:
        try:
            asyncio.run_coroutine_threadsafe(
                publish_event("import_progress", {
                    "task_id": "audio_import",
                    "step": "hash",
                    "percent": pct,
                    "message": f"Hashing {_file_name}: {pct:.2f}%",
                }),
                _loop,
            )
        except Exception:
            pass

    try:
        audio_hash_value = await asyncio.to_thread(
            media_hash, str(audio_path), _hash_progress
        )
    except Exception as e:
        logger.warning(f"media_hash fehlgeschlagen für {audio_path}: {e}")
        audio_hash_value = None

    with state.project_commit(context):
        clip = dict(state.register_audio_clip({
            "name": audio_path.stem,
            "path": str(audio_path.absolute()),
            "duration_seconds": probe_info["duration"],
            "sample_rate": probe_info["sample_rate"],
            "channels": probe_info["channels"],
            "format": audio_path.suffix.lstrip("."),
            "bpm": 0.0,
            "key": None,
            "beat_count": 0,
            "is_analyzed": False,
            "audio_hash": audio_hash_value,
            "has_audio_embedding": False,
        }))

    # Plan Phase 1 #6: synchronous sub-track-detection during mix-import.
    # Skip for short clips (< 60s) — sub-tracks meaningless there.
    if probe_info["duration"] >= 60.0:
        try:
            from pb_studio.audio.subtrack_detector import SubtrackDetector
            detector = SubtrackDetector()
            result = await asyncio.to_thread(detector.detect, str(audio_path))
            clip["subtrack_segments"] = [
                {
                    "start_time": s, "end_time": e, "confidence": c,
                    "sub_bpm": None, "sub_key": None,
                }
                for (s, e, c) in result.segments
            ]
            clip["tempo_curve"] = result.tempo_curve
        except Exception as e:
            logger.warning(f"Sub-Track-Detection fehlgeschlagen: {e}")
            clip["subtrack_segments"] = []
            clip["tempo_curve"] = []
    else:
        clip["subtrack_segments"] = []
        clip["tempo_curve"] = []

    # L-K1: Cache befuellen damit PacingService die Subtracks lesen kann.
    # Vorher landeten subtrack_segments + tempo_curve nur im in-memory clip-dict
    # und nie im audio_analysis_cache — _pre_cached_subtracks (Audit E3) wurde
    # nie sinnvoll aufgerufen.
    with state.project_commit(context):
        state.update_audio_analysis(
            clip_id=clip["id"],
            subtrack_segments=clip["subtrack_segments"],
            tempo_curve=clip["tempo_curve"],
        )

    logger.info(f"Audio importiert: {audio_path.name} (ID={clip['id']}, {probe_info['duration']:.1f}s)")
    await publish_log(
        f"Audio importiert: {audio_path.name}",
        level="info",
        source="audio.import",
        detail=f"clip_id={clip['id']} duration={probe_info['duration']:.2f}s",
    )
    await publish_event("import_progress", {
        "task_id": "audio_import",
        "clip_id": clip["id"],
        "percent": 100.0,
        "message": "Import abgeschlossen",
    })
    return AudioClipInfo(**clip)


@router.get(
    "/clips",
    response_model=list[AudioClipInfo],
    summary="Audio-Clip-Liste abrufen",
    description=(
        "Gibt alle importierten Audio-Clips zurück. Unterstützt Paginierung via "
        "'page' (1-basiert) und 'limit' (max. 200 Einträge pro Seite)."
    ),
)
async def list_clips(
    page: int = Query(1, ge=1, description="Seitennummer (1-basiert)"),
    limit: int = Query(50, ge=1, le=200, description="Einträge pro Seite"),
    state: AppState = Depends(get_app_state),
) -> list[AudioClipInfo]:
    """Gibt die Audio-Clip-Liste zurück (paginiert)."""
    clips = list(state.get_audio_clips_snapshot().values())
    start = (page - 1) * limit
    end = start + limit

    items: list[AudioClipInfo] = []
    for clip in clips[start:end]:
        analysis = state.get_audio_analysis(clip["id"])
        merged = dict(clip)
        merged["bpm"] = float(analysis.get("bpm", 0.0)) if analysis else float(clip.get("bpm", 0.0) or 0.0)
        merged["key"] = analysis.get("key") if analysis else clip.get("key")
        merged["beat_count"] = int(analysis.get("beat_count", 0)) if analysis else int(clip.get("beat_count", 0) or 0)
        cached_status = analysis.get("_analysis_status") if analysis else None
        merged["analysis_status"] = cached_status or (
            "completed" if bool(clip.get("is_analyzed", False)) else "unavailable"
        )
        merged["stage_status"] = (
            dict(analysis.get("_stage_status") or {}) if analysis else {}
        )
        merged["stage_errors"] = (
            dict(analysis.get("_stage_errors") or {}) if analysis else {}
        )
        merged["is_analyzed"] = (
            cached_status == "completed"
            if cached_status is not None
            else bool(clip.get("is_analyzed", False))
        )
        # L-N4: stems_paths kann JSON-String oder dict sein (pacing_router-Logik analog).
        # Pydantic-Schema erwartet Dict[str,str] -> normalisieren.
        raw_stems = merged.get("stems_paths")
        if isinstance(raw_stems, str):
            try:
                import json as _json
                parsed = _json.loads(raw_stems)
                merged["stems_paths"] = parsed if isinstance(parsed, dict) else None
            except Exception:
                merged["stems_paths"] = None
        elif raw_stems is not None and not isinstance(raw_stems, dict):
            merged["stems_paths"] = None
        items.append(AudioClipInfo(**merged))

    return items


@router.delete(
    "/clips/{clip_id}",
    response_model=DeleteResponse,
    summary="Audio-Clip loeschen (single)",
)
async def delete_clip(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Loescht einen einzelnen Audio-Clip aus In-Memory + SQLite."""
    if state.delete_audio_clip(clip_id):
        await publish_log(f"Audio-Clip {clip_id} geloescht", level="info", source="audio.delete")
        return DeleteResponse(deleted_count=1, not_found_ids=[])
    return DeleteResponse(deleted_count=0, not_found_ids=[clip_id])


@router.delete(
    "/clips",
    response_model=DeleteResponse,
    summary="Audio-Clips batch-loeschen",
)
async def delete_clips_batch(
    request: BatchDeleteRequest,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Batch-Delete: loescht alle in clip_ids aufgefuehrten Audio-Clips."""
    deleted = 0
    not_found = []
    for cid in request.clip_ids:
        if state.delete_audio_clip(cid):
            deleted += 1
        else:
            not_found.append(cid)
    if deleted:
        await publish_log(
            f"{deleted} Audio-Clips batch-geloescht (von {len(request.clip_ids)} angefragt)",
            level="info", source="audio.delete",
        )
    return DeleteResponse(deleted_count=deleted, not_found_ids=not_found)


def _band_stft_params(
    sr: int,
    fmin: float,
    fmax: float | None,
    max_mels: int = 64,
) -> tuple[int, int]:
    """
    Waehlt ``n_fft`` und ``n_mels`` passend zur Bandbreite.

    Audit 2026-08-05 (M-2): Eine feste Filterzahl ueber ein schmales Band
    erzeugt leere Mel-Filter — das Band liefert dann keine oder eine
    unbrauchbare Onset-Envelope. Regel: erst die FFT-Auflousung so waehlen,
    dass genug Bins im Band liegen, dann hoechstens halb so viele Filter wie
    Bins vergeben.

    Returns:
        ``(n_fft, n_mels)`` — ``n_fft`` als Zweierpotenz, ``n_mels`` mindestens 4.
    """
    upper = float(fmax) if fmax else float(sr) / 2.0
    span = max(1.0, upper - float(fmin))

    n_fft = 2048
    # Mindestens 24 Bins im Band anstreben, aber nicht ueber 8192 gehen.
    while n_fft < 8192 and (span / (sr / n_fft)) < 24.0:
        n_fft *= 2

    bins_in_band = max(1, int(span / (sr / n_fft)))
    n_mels = max(4, min(max_mels, bins_in_band // 2))
    return n_fft, n_mels


async def _store_audio_embedding_in_brain_cache(
    *,
    audio_path: str,
    audio_hash: str | None,
) -> None:
    """
    Erzeugt das CLAP-Audio-Embedding und legt es im Brain-EmbeddingCache ab.

    Audit 2026-08-05 (C-3/H-5): Der Lesepfad existierte laengst
    (``post_processor._load_audio_embedding``), der Schreibpfad nie. Ohne
    Audio-Embedding meldet ``feature_adapter._semantic_availability`` bestenfalls
    ``partial`` und die Bruecke ``semantic_match_weight`` faellt komplett aus dem
    Score — sie fehlte empirisch in allen 2576 persistierten Cuts.

    Bewusst best-effort: schlaegt die Berechnung fehl (Asset fehlt, GPU belegt),
    bleibt die Audio-Analyse gueltig. Kein CPU-Fallback (IRON RULE 1) — CLAP
    laeuft ueber DirectML oder gar nicht.
    """
    if not audio_hash:
        logger.debug("CLAP-Cache-Write uebersprungen: kein audio_hash")
        return

    try:
        from pb_studio.audio import audio_embedder
        from pb_studio.brain.brain_service import BrainService

        cache = getattr(BrainService.get().brain, "cache", None)
        if cache is None:
            return

        existing = cache.lookup(
            str(audio_hash),
            audio_embedder.CURRENT_MODEL_NAME,
            audio_embedder.CURRENT_MODEL_VERSION,
        )
        if existing is not None:
            return

        from pb_studio.ai.clap_wrapper import CLAPAnalyzer

        analyzer = CLAPAnalyzer()
        embedding = await asyncio.to_thread(analyzer.encode_audio, audio_path)
        if embedding is None:
            logger.info(
                "CLAP-Audio-Embedding nicht verfuegbar fuer %s — "
                "Semantik-Achse bleibt fuer diesen Clip unavailable",
                Path(audio_path).name,
            )
            return

        cache.store(
            media_hash=str(audio_hash),
            media_type="audio",
            embedding=embedding,
            model_name=audio_embedder.CURRENT_MODEL_NAME,
            model_version=audio_embedder.CURRENT_MODEL_VERSION,
        )
        logger.info(
            "CLAP-Audio-Embedding im Brain-Cache abgelegt (dim=%d)",
            int(getattr(embedding, "size", 0)),
        )
    except Exception as exc:  # noqa: BLE001 - darf die Analyse nie abbrechen
        logger.warning(
            "CLAP-Cache-Write fehlgeschlagen (Analyse bleibt gueltig): %s: %r",
            type(exc).__name__,
            exc,
        )


_AUDIO_STAGE_REQUEST_FIELDS = {
    "beats": "detect_beats",
    "structure": "detect_structure",
    "spectral": "spectral_analysis",
    "key": "detect_key",
}
_AUDIO_STAGE_RESULT_FIELDS = {
    "beats": (
        "bpm",
        "beat_count",
        "beats",
        "energy_curve",
        "downbeats",
        "downbeat_provenance",
        "onset_times",
        "kick_times",
        "snare_times",
        "hihat_times",
        "_chunk_evidence",
    ),
    "structure": ("structure_segments",),
    "spectral": ("spectral_data",),
    "key": ("key",),
}


def _audio_stage_result_is_valid(stage: str, analysis: dict[str, Any]) -> bool:
    """Return whether a completed cached stage still has its required payload."""
    if stage == "beats":
        required_lists = (
            "beats",
            "energy_curve",
            "downbeats",
            "onset_times",
            "kick_times",
            "snare_times",
            "hihat_times",
        )
        return (
            isinstance(analysis.get("bpm"), (int, float))
            and isinstance(analysis.get("beat_count"), int)
            and all(isinstance(analysis.get(name), list) for name in required_lists)
            and isinstance(analysis.get("downbeat_provenance"), dict)
        )
    if stage == "structure":
        return bool(analysis.get("structure_segments"))
    if stage == "spectral":
        spectral = analysis.get("spectral_data")
        return (
            isinstance(spectral, dict)
            and bool(spectral.get("times"))
            and isinstance(spectral.get("bands"), dict)
        )
    if stage == "key":
        key = analysis.get("key")
        return isinstance(key, str) and bool(key.strip()) and key != "Unknown"
    return False


def _plan_audio_analysis(
    request: AudioAnalyzeRequest,
    cached: dict[str, Any],
) -> AudioAnalyzeRequest:
    """Plan only requested stages that are not reusable, unless force is set."""
    cached_status = dict(cached.get("_stage_status") or {})
    updates: dict[str, bool] = {}
    for stage, request_field in _AUDIO_STAGE_REQUEST_FIELDS.items():
        requested = bool(getattr(request, request_field))
        reusable = (
            cached_status.get(stage) == "completed"
            and _audio_stage_result_is_valid(stage, cached)
        )
        updates[request_field] = requested and (request.force or not reusable)
    return request.model_copy(update=updates)


def _audio_plan_has_work(request: AudioAnalyzeRequest) -> bool:
    return any(
        bool(getattr(request, request_field))
        for request_field in _AUDIO_STAGE_REQUEST_FIELDS.values()
    )


def _merge_audio_analysis_result(
    *,
    cached: dict[str, Any],
    fresh: dict[str, Any],
    requested: AudioAnalyzeRequest,
    planned: AudioAnalyzeRequest,
) -> dict[str, Any]:
    """Merge stage payloads without clearing data from stages not executed."""
    merged = dict(cached)
    if "_chunk_evidence" not in merged and "chunk_evidence" in merged:
        merged["_chunk_evidence"] = merged["chunk_evidence"]
    merged["clip_id"] = int(fresh.get("clip_id", requested.clip_id))
    fresh_duration = float(fresh.get("duration_seconds", 0.0) or 0.0)
    if fresh_duration > 0.0:
        merged["duration_seconds"] = fresh_duration

    stage_status = dict(cached.get("_stage_status") or {})
    stage_errors = dict(cached.get("_stage_errors") or {})
    fresh_status = dict(fresh.get("_stage_status") or {})
    fresh_errors = dict(fresh.get("_stage_errors") or {})

    for stage, request_field in _AUDIO_STAGE_REQUEST_FIELDS.items():
        if not bool(getattr(planned, request_field)):
            continue
        status = fresh_status.get(stage, "completed")
        if status == "skipped":
            continue
        stage_status[stage] = status
        if status == "completed":
            stage_errors.pop(stage, None)
        elif stage in fresh_errors:
            stage_errors[stage] = fresh_errors[stage]

        if status not in {"completed", "partial"}:
            continue
        for field in _AUDIO_STAGE_RESULT_FIELDS[stage]:
            if field in fresh and fresh[field] is not None:
                merged[field] = fresh[field]

    for field in ("subtrack_segments", "tempo_curve"):
        if field in fresh and fresh[field] is not None:
            merged[field] = fresh[field]

    degraded = any(
        status in {"partial", "failed", "interrupted"}
        for status in stage_status.values()
    )
    merged["_analysis_status"] = "partial" if degraded else "completed"
    merged["_stage_status"] = stage_status
    merged["_stage_errors"] = stage_errors
    return merged


@router.post(
    "/analyze",
    response_model=AudioAnalysisResult,
    summary="Audio-Clip analysieren",
    description=(
        "Analysiert einen importierten Audio-Clip: Beats (BeatNet), Struktur-Segmente, "
        "spektrale Daten. Ergebnis wird gecacht. Kann mehrere Sekunden dauern."
    ),
)
async def analyze_audio(
    request: AudioAnalyzeRequest,
    state: AppState = Depends(get_app_state),
) -> AudioAnalysisResult:
    try:
        async with state.project_operation() as context:
            return await _analyze_audio_in_context(request, state, context)
    except asyncio.CancelledError:
        raise
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _analyze_audio_in_context(
    request: AudioAnalyzeRequest,
    state: AppState,
    context: ProjectOperationContext,
) -> AudioAnalysisResult:
    """Analysiert einen Audio-Clip (Beats, Struktur, Spektral)."""
    clip = state.get_audio_clip(request.clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Clip {request.clip_id} nicht gefunden")

    audio_path = clip["path"]

    # R17/MEDIUM: Verify file exists on disk BEFORE to_thread boundary — same guard
    # added to video_router in R15. Without this, a deleted/moved file returns HTTP 500
    # instead of the correct HTTP 422 (Unprocessable Entity).
    if not Path(audio_path).exists():
        raise HTTPException(
            status_code=422,
            detail=f"Audio-Datei nicht gefunden: {audio_path!r}",
        )

    logger.info(f"Starte Audio-Analyse für Clip {request.clip_id}: {clip['name']}")
    await publish_log(
        f"Audio-Analyse gestartet: {clip['name']}",
        level="info",
        source="audio.analyze",
        detail=f"clip_id={request.clip_id}",
    )
    await publish_event("analysis_progress", {
        "event": "analysis_progress",
        "task_id": str(request.clip_id),
        "status": "running",
        "percent": 0,
        "message": f"Analyse gestartet: Clip {request.clip_id}",
    })

    try:
        _loop = asyncio.get_running_loop()
        # Cache bleibt Merge-Basis: gezielte Retries bewahren alle anderen Stages.
        _pre_cached = dict(state.get_audio_analysis(request.clip_id) or {})
        planned_request = _plan_audio_analysis(request, _pre_cached)
        stems_paths = clip.get("stems_paths") or {}
        if isinstance(stems_paths, str):
            try:
                import json as _json
                parsed = _json.loads(stems_paths)
                stems_paths = parsed if isinstance(parsed, dict) else {}
            except Exception:
                stems_paths = {}
        if _audio_plan_has_work(planned_request):
            fresh_result = await asyncio.to_thread(
                _run_audio_analysis,
                audio_path,
                request.clip_id,
                planned_request,
                stems_paths,
                _loop,
            )
        else:
            fresh_result = {
                "clip_id": request.clip_id,
                "duration_seconds": float(
                    _pre_cached.get("duration_seconds", clip.get("duration_seconds", 0.0))
                    or 0.0
                ),
                "_stage_status": {},
                "_stage_errors": {},
            }
        result = _merge_audio_analysis_result(
            cached=_pre_cached,
            fresh=fresh_result,
            requested=request,
            planned=planned_request,
        )

        clip["bpm"] = float(result.get("bpm", 0.0) or 0.0)
        clip["key"] = result.get("key")
        clip["beat_count"] = int(result.get("beat_count", 0) or 0)
        analysis_status = result.get("_analysis_status", "completed")
        clip["is_analyzed"] = analysis_status == "completed"
        # R4-HOCH-9: Update duration from librosa when ffprobe returned 0.0
        analysis_dur = float(result.get("duration_seconds", 0.0) or 0.0)
        if analysis_dur > 0.0 and float(clip.get("duration_seconds", 0.0) or 0.0) <= 0.0:
            clip["duration_seconds"] = analysis_dur

        # Audit 2026-08-05 (C-3/H-5, T3.4): CLAP-Audio-Embedding erzeugen und in
        # den Brain-Cache schreiben. Bis hierher existierte KEIN Producer fuer
        # Audio-Embeddings — `EmbeddingCache.store(media_type="audio", ...)` kam
        # ausschliesslich in Tests vor. Zusammen mit der fehlenden Video-Seite
        # war das der Grund, warum `semantic_match_weight` in 0 von 2576 Cuts
        # auftauchte und der Cross-Modal-Projektor nie Trainingspaare bekam.
        if _audio_plan_has_work(planned_request):
            await _store_audio_embedding_in_brain_cache(
                audio_path=audio_path,
                audio_hash=clip.get("audio_hash"),
            )

        # P-1: Analyse-Ergebnisse in SQLite persistieren
        import json as _json
        beats_json = _json.dumps(result.get("beats", []))
        with state.project_commit(context):
            state.update_audio_analysis(
                clip_id=request.clip_id,
                bpm=clip["bpm"],
                key=clip["key"],
                beat_count=clip["beat_count"],
                beats_json=beats_json,
                is_analyzed=clip["is_analyzed"],
                energy_curve=result.get("energy_curve"),
                structure_segments=result.get("structure_segments"),
                spectral_data=result.get("spectral_data"),
                # L-AUDIO-5 / Z5: Subtracks + Tempo-Curve mit-persistieren in DB.
                subtrack_segments=result.get("subtrack_segments"),
                tempo_curve=result.get("tempo_curve"),
                # Audit-Fix 2026-07-10: Onset/Drum-Trigger-Kandidaten mit-persistieren.
                onset_times=result.get("onset_times"),
                kick_times=result.get("kick_times"),
                snare_times=result.get("snare_times"),
                hihat_times=result.get("hihat_times"),
                chunk_evidence=result.get("_chunk_evidence"),
                analysis_status=analysis_status,
                stage_status=result.get("_stage_status", {}),
                stage_errors=result.get("_stage_errors", {}),
                downbeats=result.get("downbeats", []),
                downbeat_provenance=result.get("downbeat_provenance"),
            )

        await publish_log(
            f"Audio-Analyse {analysis_status}: {clip['name']}",
            level="warning" if analysis_status == "partial" else "info",
            source="audio.analyze",
            detail=f"clip_id={request.clip_id} bpm={float(result.get('bpm', 0.0) or 0.0):.2f} beats={int(result.get('beat_count', 0) or 0)}",
        )
        await publish_event("analysis_progress", {
            "event": "analysis_progress",
            "task_id": str(request.clip_id),
            "status": analysis_status,
            "percent": 100,
            "message": (
                f"Analyse teilweise abgeschlossen: BPM={float(result.get('bpm', 0.0) or 0.0):.1f}"
                if analysis_status == "partial"
                else f"Analyse abgeschlossen: BPM={float(result.get('bpm', 0.0) or 0.0):.1f}"
            ),
            "stage_status": result.get("_stage_status", {}),
            "stage_errors": result.get("_stage_errors", {}),
        })
        public_result = dict(result)
        public_result["analysis_status"] = analysis_status
        public_result["stage_status"] = result.get("_stage_status", {})
        public_result["stage_errors"] = result.get("_stage_errors", {})
        public_result["chunk_evidence"] = result.get("_chunk_evidence", {})
        return AudioAnalysisResult(**public_result)
    except asyncio.CancelledError:
        raise
    except ProjectContextChangedError:
        raise
    except Exception as e:
        logger.error(f"Audio-Analyse fehlgeschlagen: {e}", exc_info=True)
        await publish_log(
            f"Audio-Analyse fehlgeschlagen: {clip['name']}",
            level="error",
            source="audio.analyze",
            detail=str(e),
        )
        await publish_event("analysis_progress", {
            "event": "analysis_progress",
            "task_id": str(request.clip_id),
            "status": "failed",
            "percent": 0,
            "message": f"Analyse fehlgeschlagen: {str(e)}",
            "error": str(e),
        })
        raise HTTPException(status_code=500, detail=f"Analyse fehlgeschlagen: {e}")


@router.get(
    "/beats/{clip_id}",
    response_model=list[BeatData],
    summary="Beat-Daten abrufen",
    description="Gibt die detektierten Beat-Zeitpunkte für einen zuvor analysierten Clip zurück.",
)
async def get_beats(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> list[BeatData]:
    """Gibt Beat-Daten für einen Clip zurück."""
    analysis = state.get_audio_analysis(clip_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Keine Analyse für Clip {clip_id}")
    beats = analysis.get("beats", [])
    return [BeatData(**b) if isinstance(b, dict) else b for b in beats]


@router.get(
    "/onsets/{clip_id}",
    response_model=list[float],
    summary="Onset-Zeitpunkte abrufen",
    description="Gibt die detektierten Onset-Zeitpunkte (Einsätze) für einen zuvor analysierten Clip zurück.",
)
async def get_onsets(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> list[float]:
    """Gibt Onset-Daten für einen Clip zurück (Thread-safe)."""
    analysis = state.get_audio_analysis(clip_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Keine Analyse für Clip {clip_id}")
    return [float(value) for value in analysis.get("onset_times", [])]


@router.get(
    "/waveform/{clip_id}",
    response_model=WaveformData,
    summary="Waveform-Daten abrufen",
    description=(
        "Extrahiert Multi-Band Waveform-Daten für die Visualisierung im WPF Frontend. "
        "Der Parameter 'bands' bestimmt die Anzahl der Frequenzbänder (Standard: 3)."
    ),
)
async def get_waveform(
    clip_id: int,
    bands: int = Query(3, ge=1, le=8, description="Frequenzbänder (1-8)"),
    state: AppState = Depends(get_app_state),
) -> WaveformData:
    """Gibt Waveform-Daten für einen Clip zurück."""
    clip = state.get_audio_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} nicht gefunden")
    try:
        waveform = await asyncio.to_thread(_extract_waveform, clip["path"], bands)
        return WaveformData(
            clip_id=clip_id,
            sample_rate=44100,
            bands=waveform,
            duration_seconds=clip["duration_seconds"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Waveform-Extraktion fehlgeschlagen: {e}")


@router.post(
    "/stems/separate",
    response_model=StemResult,
    summary="Stem-Separation starten",
    description=(
        "Trennt einen Audio-Clip in Stems (Vocals, Instrumental, Drums, Bass, Other) "
        "via Demucs-ONNX auf der AMD DirectML GPU. "
        "Belegt GPU-Lock für die Dauer der Separation (kann mehrere Minuten dauern)."
    ),
)
async def separate_stems(
    request: StemSeparateRequest,
    state: AppState = Depends(get_app_state),
) -> StemResult:
    try:
        async with state.project_operation() as context:
            return await _separate_stems_in_context(request, state, context)
    except asyncio.CancelledError:
        raise
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _separate_stems_in_context(
    request: StemSeparateRequest,
    state: AppState,
    context: ProjectOperationContext,
) -> StemResult:
    """Führt Stem-Separation durch (GPU-Lock via Middleware)."""
    clip = state.get_audio_clip(request.clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Clip {request.clip_id} nicht gefunden")
    logger.info(f"Starte Stem-Separation: {clip['name']} mit {request.model.value}")

    # Audit C2: per-stage stem_progress SSE callback (init/loading/inference/saving/complete).
    _loop = asyncio.get_running_loop()
    _clip_id = request.clip_id

    def _stem_progress(pct: float) -> None:
        state.require_project_context_current(context)
        if _loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                publish_event("stem_progress", {
                    "clip_id": _clip_id,
                    "percent": float(pct),
                    "message": f"Stem-Separation: {float(pct):.0f}%",
                }),
                _loop,
            )
        except Exception:
            pass

    try:
        # B3-Fix (2026-05-19): explizit stem_timeout uebergeben (900s default
        # statt gpu_timeout_seconds 300s) — Demucs auf 90min Mixe brauchte
        # in der Vergangenheit >300s und brach mit GPU-Task-Timeout ab.
        from backend.config import config as _server_config
        # Audit 2026-08-06 (T4.2): Das dauerabhaengige Budget existierte laengst,
        # aber es griff nicht. Im Log vom 2026-07-28 feuerte der Timeout nach
        # 900 s, obwohl die Datei 6335 s lang war — 0.75 * 6335 = 4751 s haetten
        # gereicht (die Separation brauchte real 2710 s). Ursache: `clip
        # ["duration_seconds"]` war 0, weil ffprobe beim Import 0 geliefert hatte
        # und die Korrektur erst in /audio/analyze passiert. Wer Stems ohne
        # vorherige Analyse trennt, landete damit auf dem Minimum-Budget.
        # Folge fuer den User: HTTP 500, waehrend der Worker 30 Minuten
        # weiterlief und am Ende doch korrekt schrieb — beim Retry dann
        # "magischer" Erfolg aus dem Cache.
        _stem_duration = float(clip.get("duration_seconds", 0.0) or 0.0)
        if _stem_duration <= 0.0:
            try:
                import librosa as _librosa

                _stem_duration = float(
                    await asyncio.to_thread(_librosa.get_duration, path=clip["path"])
                )
                logger.info(
                    "Stem-Timeout: Dauer war unbekannt, nachgemessen: %.1fs",
                    _stem_duration,
                )
            except Exception as exc:  # noqa: BLE001 - Floor bleibt als Rueckfall
                logger.warning(
                    "Dauer fuer Stem-Timeout nicht messbar (%s) — nutze Minimum-Budget",
                    type(exc).__name__,
                )
                _stem_duration = 0.0
        stem_timeout = _stem_timeout_for_duration(
            _stem_duration,
            _server_config.stem_timeout,
        )
        logger.info(
            "Stem-Separation Budget: %.0fs (Dauer %.1fs, Minimum %.0fs)",
            stem_timeout,
            _stem_duration,
            float(_server_config.stem_timeout),
        )
        result = await with_gpu_task(
            _run_stem_separation, clip["path"], request.model.value, _stem_progress,
            model_id="stem_separation_full",
            manage_vram=False,  # StemSeparator owns ONNX model budgets; Demucs is CPU.
            timeout_seconds=stem_timeout,
            state=state,
            context=context,
        )

        # L-N4: stems_paths in audio_clip persistieren — pacing_router liest das
        # via audio_clips.get("stems_paths") fuer den Stem-Pacing-Branch.
        # Mapping: result-Keys (vocals_path/drums_path/...) -> stems-dict-Keys
        # (vocals/drums/...). Nur nicht-leere Eintraege uebernehmen.
        stems_paths: dict[str, str] = {}
        for stem_name in ("vocals", "instrumental", "drums", "bass", "other"):
            p = result.get(f"{stem_name}_path")
            if p:
                stems_paths[stem_name] = p
        if stems_paths:
            clip["stems_paths"] = stems_paths
            # L-AUDIO-8 (CD-1): meta sofort in DB upserten damit Reload nach
            # Backend-Restart die Stem-Pfade kennt - Demucs ist ~10min GPU,
            # darf nicht silent verloren gehen.
            try:
                with state.project_commit(context):
                    state.persist_audio_clip(clip, project_id=context.project_id)
                    state.set_audio_clip(request.clip_id, clip)
            except asyncio.CancelledError:
                raise
            except ProjectContextChangedError:
                raise
            except Exception as e:
                logger.error("stems_paths-DB-Persistierung fehlgeschlagen: %s", e)
                raise

            # Lücke schliessen: Re-run der Sub-Track-Detection mit echten Stems für hochpräzise Boundaries!
            try:
                logger.info(f"Starte hochpräzise Sub-Track-Detection mit frisch generierten Stems für Clip {request.clip_id}...")
                from pb_studio.audio.subtrack_detector import SubtrackDetector
                detector = SubtrackDetector()
                
                # Da librosa-Ladevorgänge blockieren, im Threadpool ausführen
                subtrack_res = await asyncio.to_thread(detector.detect, clip["path"], stems_paths)
                
                clip["subtrack_segments"] = [
                    {
                        "start_time": s, "end_time": e, "confidence": c,
                        "sub_bpm": None, "sub_key": None,
                    }
                    for (s, e, c) in subtrack_res.segments
                ]
                clip["tempo_curve"] = subtrack_res.tempo_curve
                
                # State und Analyse-Cache mit den neuen Werten aktualisieren
                with state.project_commit(context):
                    state.update_audio_analysis(
                        clip_id=clip["id"],
                        subtrack_segments=clip["subtrack_segments"],
                        tempo_curve=clip["tempo_curve"],
                    )
                
                logger.info(f"Sub-Track-Detection mit Stems erfolgreich aktualisiert und im Cache/DB persistiert für Clip {request.clip_id}.")
            except asyncio.CancelledError:
                raise
            except ProjectContextChangedError:
                raise
            except PersistenceError:
                raise
            except Exception as sub_err:
                logger.error(f"Re-Run der Sub-Track-Detection mit Stems fehlgeschlagen: {sub_err}", exc_info=True)

        return StemResult(clip_id=request.clip_id, **result)
    except asyncio.CancelledError:
        raise
    except ProjectContextChangedError:
        raise
    except Exception as e:
        logger.error(f"Stem-Separation fehlgeschlagen: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Stem-Separation fehlgeschlagen: {e}")


@router.get(
    "/structure/{clip_id}",
    response_model=list[StructureSegment],
    summary="Struktur-Segmente abrufen",
    description=(
        "Gibt die detektierten Struktur-Segmente (Intro, Verse, Chorus, Bridge, Outro) "
        "für einen analysierten Clip zurück. Benötigt vorherige Analyse via POST /audio/analyze."
    ),
)
async def get_structure(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> list[StructureSegment]:
    """Gibt Struktur-Segmente für einen Clip zurück."""
    analysis = state.get_audio_analysis(clip_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Keine Analyse für Clip {clip_id}")
    segments = analysis.get("structure_segments", [])
    return [StructureSegment(**s) if isinstance(s, dict) else s for s in segments]


@router.get(
    "/spectral/{clip_id}",
    response_model=SpectralData,
    summary="Spektral-Analyse abrufen",
    description=(
        "Gibt die spektralen Analysedaten (Frequenzspektrum, Energie pro Band) "
        "für einen analysierten Clip zurück."
    ),
)
async def get_spectral(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> SpectralData:
    """Gibt Spektral-Analyse Daten zurück."""
    analysis = state.get_audio_analysis(clip_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Keine Analyse für Clip {clip_id}")
    spectral = analysis.get("spectral_data", {}) or {}
    if spectral.get("clip_id") != clip_id:
        spectral = {**spectral, "clip_id": clip_id}
    return SpectralData(**spectral)


# --- Private Hilfsfunktionen (blockierend, werden via to_thread aufgerufen) ---

def _probe_audio_info(path: str) -> dict[str, Any]:
    """Ermittelt Audio-Dauer, Sample-Rate und Channels via ffprobe."""
    import json
    import subprocess
    cmd = [
        str(config.ffprobe_path), "-v", "error",
        "-show_entries", "format=duration",
        "-show_entries", "stream=sample_rate,channels",
        "-select_streams", "a:0",
        "-of", "json", path,
    ]
    res = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30)
    data = json.loads(res)

    duration = float(data.get("format", {}).get("duration", 0.0))

    # Sample-Rate und Channels aus dem ersten Audio-Stream
    sample_rate = 44100  # Fallback
    channels = 2         # Fallback
    streams = data.get("streams", [])
    if streams:
        stream = streams[0]
        try:
            sample_rate = int(stream.get("sample_rate", 44100))
        except (ValueError, TypeError):
            pass
        try:
            channels = int(stream.get("channels", 2))
        except (ValueError, TypeError):
            pass

    return {"duration": duration, "sample_rate": sample_rate, "channels": channels}


def _emit_analysis_progress(loop, step: str, percent: float, message: str) -> None:
    """Sendet ein analysis_progress SSE-Event aus einem Worker-Thread (fire-and-forget)."""
    if loop is None:
        return
    try:
        asyncio.run_coroutine_threadsafe(
            publish_event("analysis_progress", {"step": step, "percent": percent, "message": message}),
            loop,
        )
    except Exception:
        pass


def _run_audio_analysis(
    audio_path: str,
    clip_id: int,
    request: AudioAnalyzeRequest,
    stems_paths: dict[str, str] = None,
    _loop=None,
) -> dict[str, Any]:
    """Führt die vollständige Audio-Analyse durch (blockierend)."""
    import librosa
    import numpy as np

    _emit_analysis_progress(_loop, "load", 5.0, "Audio wird geladen…")

    if stems_paths is None:
        stems_paths = {}
    drums_path = stems_paths.get("drums")
    instrumental_path = stems_paths.get("instrumental")

    # L-AUDIO-1 / Y4 (M-2 CRITICAL): Streaming-Branch fuer lange Mixe (>10min) vermeidet
    # OOM bei 90min-DJ-Mix (~480MB float32-Array). Probe Duration via get_duration
    # (kein vollstaendiges Decoding), dann decision: Streaming oder Full-Load.
    # Bei Streaming wird y/sr nur fuer einen 600s-Snapshot geladen (StructureAnalyzer
    # + KeyDetector + Spectral arbeiten auf Mix-Header — Heuristik fuer DJ-Mixe).
    _probe_dur = 0.0
    try:
        _probe_dur = float(librosa.get_duration(path=audio_path))
    except Exception:
        try:
            _probe_dur = float(librosa.get_duration(filename=audio_path))
        except Exception as exc:
            raise RuntimeError(
                f"Audio-Dauer konnte nicht sicher ermittelt werden: {audio_path}"
            ) from exc
    if _probe_dur <= 0.0:
        raise RuntimeError(
            f"Audio-Dauer konnte nicht sicher ermittelt werden: {audio_path}"
        )

    _use_streaming = _probe_dur > 600.0  # 10min
    _stream_beats = None
    _stream_bpm = None
    _stream_energy = None
    _stream_triggers = None
    _stream_features = None
    _stream_stage_errors: dict[str, list[str]] = {}
    _stream_chunk_evidence: dict = {}
    _stage_status: dict[str, str] = {}
    _stage_errors: dict[str, str] = {}

    def _mark_stage_completed(stage: str, stream_error_keys: tuple[str, ...]) -> None:
        errors = [
            error
            for key in stream_error_keys
            for error in _stream_stage_errors.get(key, [])
        ]
        if _use_streaming and errors:
            _stage_status[stage] = "partial"
            _stage_errors[stage] = "; ".join(errors)
        else:
            _stage_status[stage] = "completed"

    analysis_sr = 44100 if request.spectral_analysis else 22050

    if _use_streaming:
        try:
            from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer

            def _stream_progress(pct: float) -> None:
                overall = 5.0 + (max(0.0, min(100.0, pct)) / 100.0) * 40.0
                _emit_analysis_progress(
                    _loop, "beat_chunk", overall, f"Streaming-Analyse {pct:.1f}%"
                )

            # Verwende Drums-Spur für Beat-Tracking falls vorhanden und valide (>0 Bytes), sonst Instrumental, sonst Original
            analysis_path = drums_path if drums_path and Path(drums_path).exists() and Path(drums_path).stat().st_size > 0 else (instrumental_path if instrumental_path and Path(instrumental_path).exists() else audio_path)
            logger.info(f"Streaming-Analyse verwendet Pfad für Beats: {analysis_path}")
            try:
                _stream_res = StreamingAudioAnalyzer().analyze(analysis_path, on_progress=_stream_progress)
            except Exception as e:
                if analysis_path != audio_path:
                    logger.warning(f"Streaming-Analyse mit {analysis_path} fehlgeschlagen: {e}. Versuche Fallback auf Original-Mix...")
                    _stream_res = StreamingAudioAnalyzer().analyze(audio_path, on_progress=_stream_progress)
                else:
                    raise

            duration = _stream_res.duration_seconds
            _stream_beats = list(_stream_res.beats)
            _stream_bpm = float(_stream_res.bpm)
            _stream_energy = list(_stream_res.energy_curve)
            _stream_triggers = {
                "onset_times": list(_stream_res.onset_times),
                "kick_times": list(_stream_res.kick_times),
                "snare_times": list(_stream_res.snare_times),
                "hihat_times": list(_stream_res.hihat_times),
            }
            _stream_features = _stream_res
            _stream_stage_errors = dict(_stream_res.stage_errors)
            _stream_chunk_evidence = {
                "schema_version": 1,
                "primary": {
                    "source_role": (
                        "original_mix"
                        if analysis_path == audio_path
                        else "beat_source"
                    ),
                    "window_count": _stream_res.window_count,
                    "chunks": list(_stream_res.chunk_evidence),
                },
            }

            # AP4.1 (Audit 2026-06-10): Kamen die Beats vom Drums-/Instrumental-Stem,
            # repraesentierte die Energy-Curve nur Stem-RMS statt Mix-Energie —
            # Konsumenten (Pacing, Onsets, UI) bekamen still andere Semantik.
            # Energy jetzt in separatem energy_only-Pass vom Original-Mix.
            if analysis_path != audio_path:
                try:
                    _emit_analysis_progress(_loop, "energy_mix", 45.0, "Energy-Kurve vom Original-Mix…")
                    _energy_res = StreamingAudioAnalyzer().analyze(audio_path, energy_only=True)
                    _stream_energy = list(_energy_res.energy_curve)
                    _stream_features = _energy_res
                    _stream_chunk_evidence["mix_energy"] = {
                        "source_role": "original_mix_energy",
                        "window_count": _energy_res.window_count,
                        "chunks": list(_energy_res.chunk_evidence),
                    }
                    for stage_name, errors in _energy_res.stage_errors.items():
                        _stream_stage_errors.setdefault(stage_name, []).extend(errors)
                except Exception as energy_e:
                    logger.warning(
                        f"Mix-Energy-Pass fehlgeschlagen ({energy_e}) — verwende Stem-Energy als Fallback"
                    )

            # y/sr Snapshot fuer Structure/Spectral/Key — max 600s ab Anfang (Mix-Header).
            y, sr = librosa.load(
                audio_path,
                sr=analysis_sr,
                mono=True,
                duration=600.0,
            )
        except Exception as e:
            raise RuntimeError(
                f"Streaming-Audioanalyse fehlgeschlagen; Full-Load ist gesperrt: {e}"
            ) from e

    if not _use_streaming:
        # Audio einmalig laden — wird von StructureAnalyzer und KeyDetector benötigt
        try:
            y, sr = librosa.load(audio_path, sr=analysis_sr, mono=True)
        except Exception as e:
            logger.error(f"Audio-Load fehlgeschlagen: {audio_path}: {e}")
            raise RuntimeError(f"Audio-Datei konnte nicht geladen werden: {audio_path}: {e}")
        duration = float(len(y)) / sr if sr > 0 else 0.0

    _emit_analysis_progress(_loop, "load", 15.0, "Audio geladen — starte Beat-Erkennung…")
    _stage_status["load"] = "completed"

    # 1. BeatNet Beat-Detection
    beats: list[dict] = []
    downbeats: list[float] = []
    downbeat_provenance: dict = {
        "status": "unavailable",
        "method": "not_requested",
        "synthetic": False,
        "measured_count": 0,
    }
    bpm: float = 0.0
    energy_curve: list[float] = []

    if request.detect_beats:
        try:
            if _use_streaming and _stream_beats is not None:
                # L-AUDIO-1 / Y4: Streaming-Branch hat Beats + BPM + Energy bereits
                # geliefert - keine Re-Detection auf Full-Load (waere ineffizient).
                arr = np.asarray(_stream_beats, dtype=np.float64)
                from pb_studio.audio.beat_detector import BeatDetector as _BD
                # AP4.2 (Audit 2026-06-10): y ist nur der 600s-Snapshot — Beats
                # jenseits davon wurden vorher auf den letzten Snapshot-Frame
                # geclampt (alle mit demselben Bogus-Strength). Jetzt: echte
                # Strengths nur fuer Beats im Snapshot, Rest neutral 1.0.
                _snap_dur = float(len(y)) / sr if sr > 0 else 0.0
                _snap_times = [float(t) for t in arr if float(t) <= _snap_dur]
                _snap_strengths = (
                    _BD.compute_beat_strengths(y, sr, _snap_times) if _snap_times else []
                )
                _snap_iter = iter(_snap_strengths)
                strengths = [
                    (float(next(_snap_iter, 1.0)) if float(t) <= _snap_dur else 1.0)
                    for t in arr
                ]
                for t, s in zip(arr, strengths):
                    beats.append({
                        "time": float(t),
                        "strength": float(s),
                        "beat_type": "beat",
                    })
                bpm = float(_stream_bpm or 0.0)
                energy_curve = list(_stream_energy or [])
                downbeat_provenance = {
                    "status": "unavailable",
                    "method": "streaming_librosa_beat_track",
                    "synthetic": False,
                    "measured_count": 0,
                }
            else:
                # Use module-level singleton to avoid re-initializing on every call
                detector = _get_beat_detector()

                # Per-stage progress: detect_beats emittiert pct in [0..100],
                # mappen auf overall [15..45] (beats-Phase im Audio-Pipeline).
                def _beat_progress(pct: float) -> None:
                    overall = 15.0 + (max(0.0, min(100.0, pct)) / 100.0) * 30.0
                    _emit_analysis_progress(
                        _loop, "beat_chunk", overall, f"BeatNet inference {pct:.1f}%"
                    )

                # detect_beats gibt list[float] zurück - BeatNet oder Librosa-Fallback
                beat_detect_path = drums_path if drums_path and Path(drums_path).exists() and Path(drums_path).stat().st_size > 0 else (instrumental_path if instrumental_path and Path(instrumental_path).exists() else audio_path)
                logger.info(f"Beat-Detection verwendet Pfad: {beat_detect_path}")
                try:
                    beat_times = detector.detect_beats(beat_detect_path, on_progress=_beat_progress)
                except Exception as e:
                    if beat_detect_path != audio_path:
                        logger.warning(f"Beat-Detection mit {beat_detect_path} fehlgeschlagen: {e}. Versuche Fallback auf Original-Mix...")
                        beat_times = detector.detect_beats(audio_path, on_progress=_beat_progress)
                    else:
                        raise
                if beat_times:
                    arr = np.asarray(beat_times, dtype=np.float64)


                    # Audit L-N8: real per-beat strength via librosa.onset.onset_strength.
                    # Vorher: hardcoded 1.0 - Engine konnte beats nicht gewichten.
                    from pb_studio.audio.beat_detector import BeatDetector as _BD
                    strengths = _BD.compute_beat_strengths(y, sr, arr.tolist())

                    for t, s in zip(arr, strengths):
                        beats.append({
                            "time": float(t),
                            "strength": float(s),
                            "beat_type": "beat",
                        })
                    if len(arr) > 1:
                        intervals = np.diff(arr)
                        avg_interval = float(np.median(intervals))
                        bpm = 60.0 / avg_interval if avg_interval > 0 else 0.0
                downbeat_provenance = {
                    "status": "unavailable",
                    "method": "beat_time_only_detector",
                    "synthetic": False,
                    "measured_count": 0,
                }

                # Energy-Curve via librosa (unabhängig von BeatNet-Verfügbarkeit)
                rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
                rms_max = float(np.max(rms)) if len(rms) > 0 else 1.0
                energy_curve = (rms / rms_max).tolist() if rms_max > 0 else rms.tolist()
            _mark_stage_completed("beats", ("load", "beats", "energy"))
        except Exception as e:
            logger.warning(f"Beat-Analyse fehlgeschlagen: {e}")
            _stage_status["beats"] = "failed"
            _stage_errors["beats"] = str(e)
    else:
        _stage_status["beats"] = "skipped"
        downbeat_provenance = {
            "status": "unavailable",
            "method": "beat_detection_disabled",
            "synthetic": False,
            "measured_count": 0,
        }

    # 1b. Onset/Drum-Trigger-Kandidaten (Audit-Fix 2026-07-10, Sweep-Finding HIGH-1):
    # advanced_pacing_engine.py erwartete diese Daten von einem toten
    # `core.session_manager`-Import (Modul existierte nie) — Onset/Kick/Snare/HiHat-
    # Trigger waren im normalen (pre-cached) Pacing-Pfad dadurch wirkungslos, weil
    # das Audio dort bewusst nicht neu geladen wird (RAM-Optimierung fuer lange
    # DJ-Mixe). Hier werden dieselben librosa-Parameter wie im Live-Fallback
    # (`AdvancedPacingEngine._extract_other_triggers`) einmalig auf dem bereits
    # geladenen y/sr berechnet und mit-persistiert, damit der Cache-Pfad echte
    # Trigger-Kandidaten hat statt sie stillschweigend zu verlieren.
    onset_times: list[float] = []
    kick_times: list[float] = []
    snare_times: list[float] = []
    hihat_times: list[float] = []
    if request.detect_beats and _use_streaming and _stream_triggers is not None:
        onset_times = _stream_triggers["onset_times"]
        kick_times = _stream_triggers["kick_times"]
        snare_times = _stream_triggers["snare_times"]
        hihat_times = _stream_triggers["hihat_times"]
    elif request.detect_beats:
        try:
            onset_times = librosa.frames_to_time(
                librosa.onset.onset_detect(y=y, sr=sr, units="frames"), sr=sr
            ).tolist()
        except Exception as e:
            logger.warning(f"Onset-Detection fehlgeschlagen: {e}")
        try:
            _hop = 512
            # Audit 2026-08-05 (M-2/HIGH-AUDIO-1): Hier standen fuer alle drei
            # Baender fest 64 Mel-Filter. Bei sr=22050 und n_fft=2048 ist ein
            # FFT-Bin ~10,8 Hz breit — fuer das Kick-Band (20-150 Hz) stehen
            # damit nur ~12 Bins zur Verfuegung. 64 Filter darauf ergeben eine
            # degenerierte Filterbank; librosa warnt mit "Empty filters detected
            # in mel frequency basis". Empirisch: kick_times war in 4 von 6
            # Rows leer, und onset/snare/hihat kollabierten auf identische
            # Trefferzahlen (15/15/15) — die Bandtrennung fand faktisch nicht
            # statt. Filterzahl und FFT-Groesse haengen jetzt an der Bandbreite.
            _kick_fft, _kick_mels = _band_stft_params(sr, 20.0, 150.0)
            kick_env = librosa.onset.onset_strength(
                y=librosa.effects.preemphasis(y), sr=sr, hop_length=_hop,
                aggregate=np.median, fmax=150,
                n_fft=_kick_fft, n_mels=_kick_mels,
            )
            kick_times = librosa.frames_to_time(
                librosa.onset.onset_detect(onset_envelope=kick_env, sr=sr, hop_length=_hop),
                sr=sr, hop_length=_hop,
            ).tolist()
            _snare_fft, _snare_mels = _band_stft_params(sr, 200.0, 400.0)
            snare_env = librosa.onset.onset_strength(
                y=y, sr=sr, hop_length=_hop, fmin=200, fmax=400,
                n_fft=_snare_fft, n_mels=_snare_mels,
            )
            snare_times = librosa.frames_to_time(
                librosa.onset.onset_detect(onset_envelope=snare_env, sr=sr, hop_length=_hop),
                sr=sr, hop_length=_hop,
            ).tolist()
            _hihat_fft, _hihat_mels = _band_stft_params(sr, 5000.0, None)
            hihat_env = librosa.onset.onset_strength(
                y=y, sr=sr, hop_length=_hop, fmin=5000,
                n_fft=_hihat_fft, n_mels=_hihat_mels,
            )
            hihat_times = librosa.frames_to_time(
                librosa.onset.onset_detect(onset_envelope=hihat_env, sr=sr, hop_length=_hop),
                sr=sr, hop_length=_hop,
            ).tolist()
        except Exception as e:
            logger.warning(f"Drum-Onset-Detection fehlgeschlagen: {e}")

    _emit_analysis_progress(_loop, "beats", 45.0, "Beats erkannt — starte Struktur-Analyse…")

    # 2. Struktur-Analyse (Novelty + Clustering)
    structure_segments: list = []
    if request.detect_structure:
        try:
            from pb_studio.audio.structure_analyzer import StructureAnalyzer
            # AP4.3 (Audit 2026-06-10): echte Datei-Dauer uebergeben — y ist im
            # Streaming-Pfad nur der 600s-Snapshot, wodurch der DJ-Mix-Branch
            # (600.0 > 600 = False) nie erreichbar war.
            structure_analyzer = StructureAnalyzer()
            if _use_streaming:
                struct_result = structure_analyzer.analyze_streaming_energy(
                    list(_stream_energy or []),
                    duration,
                )
            else:
                struct_result = structure_analyzer.analyze_song_structure(
                    y, sr, total_duration=_probe_dur
                )
            structure_segments = struct_result.get("segments", [])
            if not structure_segments:
                raise RuntimeError("Struktur-Analyse lieferte keine Segmente")
            _mark_stage_completed("structure", ("load", "energy"))
        except Exception as e:
            logger.warning(f"Struktur-Analyse fehlgeschlagen: {e}")
            _stage_status["structure"] = "failed"
            _stage_errors["structure"] = str(e)
    else:
        _stage_status["structure"] = "skipped"

    _emit_analysis_progress(_loop, "structure", 70.0, "Struktur analysiert — starte Spektral-Analyse…")

    # 3. Spektral-Analyse (8-Band STFT) — nutzt bereits geladenes y/sr (kein erneuter Disk-Zugriff)
    spectral_data = None
    if request.spectral_analysis:
        try:
            from pb_studio.audio.spectral_analyzer import (
                SpectralAnalyzer,
                FREQUENCY_BANDS,
                add_aggregate_bands,
            )
            if _use_streaming:
                if _stream_features is None or not _stream_features.spectral_times:
                    raise RuntimeError("Streaming-Spektralrepräsentation ist leer")
                band_arrays = {
                    name: np.asarray(values, dtype=np.float64)
                    for name, values in _stream_features.spectral_bands.items()
                }
                spec_result = {
                    "times": list(_stream_features.spectral_times),
                    "band_energies": {
                        name: values.tolist()
                        for name, values in band_arrays.items()
                    },
                    "centroids": list(_stream_features.spectral_centroids),
                    "band_means": {
                        name: float(np.mean(values)) if values.size else 0.0
                        for name, values in band_arrays.items()
                    },
                    "band_variances": {
                        name: float(np.var(values)) if values.size else 0.0
                        for name, values in band_arrays.items()
                    },
                    "events": [],
                }
            else:
                spec_result = SpectralAnalyzer(sr=sr).analyze_from_array(y, sr)
            # Audit 2026-08-05 (CRIT-AUDIO-1/T2.4): Aggregate low/mid/high
            # ergaenzen — die Pacing-Engine liest genau diese drei Namen, der
            # Analyzer lieferte nur die acht Einzelbaender.
            _spec_bands = add_aggregate_bands(
                dict(spec_result.get("band_energies", {}) or {})
            )
            spectral_data = {
                "clip_id": clip_id,
                "times": spec_result.get("times", []),
                "bands": _spec_bands,
                "centroids": spec_result.get("centroids", []),
                "frequency_ranges": {k: list(v) for k, v in FREQUENCY_BANDS.items()},
                # L-AUDIO-4 / Z4: Drop/Buildup/Breakdown-Events + Band-Statistik
                # mit-durchreichen (waren zuvor im Mapping verworfen).
                "band_means": spec_result.get("band_means", {}),
                "band_variances": spec_result.get("band_variances", {}),
                "events": spec_result.get("events", []),
            }
            if not spectral_data["times"]:
                raise RuntimeError("Spektral-Analyse lieferte keine Zeitachse")
            _mark_stage_completed("spectral", ("load", "features"))
        except Exception as e:
            logger.warning(f"Spektral-Analyse fehlgeschlagen: {e}")
            _stage_status["spectral"] = "failed"
            _stage_errors["spectral"] = str(e)
    else:
        _stage_status["spectral"] = "skipped"

    _emit_analysis_progress(_loop, "spectral", 85.0, "Spektrum analysiert — starte Tonart-Erkennung…")

    # 4. Tonart-Erkennung (Krumhansl-Kessler)
    key = None
    if request.detect_key:
        try:
            from pb_studio.audio.key_detector import KeyDetector
            if _use_streaming:
                if _stream_features is None or not _stream_features.chroma_mean:
                    raise RuntimeError("Streaming-Chromarepräsentation ist leer")
                key = KeyDetector().detect_key_from_chroma(
                    _stream_features.chroma_mean
                )
            elif instrumental_path and Path(instrumental_path).exists():
                logger.info(f"Key-Detection verwendet Instrumental-Pfad: {instrumental_path}")
                y_inst, sr_inst = librosa.load(instrumental_path, sr=22050, mono=True, duration=600.0)
                key = KeyDetector().detect_key(y_inst, sr_inst)
            else:
                key = KeyDetector().detect_key(y, sr)
            if not key or key == "Unknown":
                raise RuntimeError("Tonart konnte nicht ermittelt werden")
            _mark_stage_completed("key", ("load", "features"))
        except Exception as e:
            logger.warning(f"Key-Detection fehlgeschlagen: {e}")
            _stage_status["key"] = "failed"
            _stage_errors["key"] = str(e)
    else:
        _stage_status["key"] = "skipped"


    _emit_analysis_progress(_loop, "key", 95.0, "Tonart erkannt — Analyse abgeschlossen")

    requested_stages = [
        name
        for name, enabled in (
            ("beats", request.detect_beats),
            ("structure", request.detect_structure),
            ("spectral", request.spectral_analysis),
            ("key", request.detect_key),
        )
        if enabled
    ]
    degraded_stages = [
        name
        for name in requested_stages
        if _stage_status.get(name) in {"partial", "failed"}
    ]
    failed_stages = [
        name for name in requested_stages if _stage_status.get(name) == "failed"
    ]
    if failed_stages and len(failed_stages) == len(requested_stages):
        raise RuntimeError(
            "Alle angeforderten Audio-Stages fehlgeschlagen: "
            + ", ".join(failed_stages)
        )
    analysis_status = "partial" if degraded_stages else "completed"

    return {
        "clip_id": clip_id,
        "duration_seconds": duration,
        "bpm": bpm,
        "beat_count": len(beats),
        "beats": beats,
        "downbeats": downbeats,
        "downbeat_provenance": downbeat_provenance,
        "key": key,
        "energy_curve": energy_curve,
        "structure_segments": structure_segments,
        "spectral_data": spectral_data,
        "onset_times": onset_times,
        "kick_times": kick_times,
        "snare_times": snare_times,
        "hihat_times": hihat_times,
        "_analysis_status": analysis_status,
        "_stage_status": _stage_status,
        "_stage_errors": _stage_errors,
        "_chunk_evidence": _stream_chunk_evidence,
    }


from pb_studio.audio.waveform_cache import WaveformCache

# Globaler LRU-Waveform-Cache zur Drosselung redundanter FFT-Berechnungen (T023)
_waveform_cache = WaveformCache(max_size=50)


def _extract_waveform(audio_path: str, bands: int) -> list[list[float]]:
    """Extrahiert N-Band Waveform-Daten, blockierend.

    bands=1: nur 'mid', bands=2: 'low'+'high', bands=3: 'low'+'mid'+'high'
    bands>=4: alle 3 Bänder (max verfügbar)
    """
    try:
        # 1. Versuche aus Cache zu lesen (T023)
        result = _waveform_cache.get(audio_path)
        if result is None:
            from pb_studio.audio.waveform_analyzer import WaveformAnalyzer
            result = WaveformAnalyzer().get_downsampled_waveform(
                audio_path, target_points=1000
            )
            if result:
                _waveform_cache.put(audio_path, result)

        if not result:
            return []

        # result: dict mit 'low', 'mid', 'high' als numpy arrays
        all_keys = ["low", "mid", "high"]
        if bands <= 1:
            band_keys = ["mid"]
        elif bands == 2:
            band_keys = ["low", "high"]
        else:
            band_keys = all_keys
        output = []
        for k in band_keys:
            arr = result.get(k)
            if arr is not None:
                output.append([float(v) for v in arr])
        return output
    except ImportError:
        logger.warning("WaveformAnalyzer nicht verfuegbar, leere Daten")
        return []
    except Exception as e:
        logger.warning(f"Waveform-Extraktion fehlgeschlagen: {e}")
        return []


def _run_stem_separation(
    audio_path: str,
    model_name: str,
    on_progress=None,
    *,
    state: AppState | None = None,
    context: ProjectOperationContext | None = None,
) -> dict[str, Any]:
    """Führt Stem-Separation durch (blockierend, GPU)."""
    from pb_studio.config_manager import ConfigManager
    from pb_studio.audio.separator import StemSeparator

    config_manager = ConfigManager()
    output_dir_raw = config_manager.get("paths", {}).get("temp_dir", "./temp")
    output_dir = config_manager.resolve_path(output_dir_raw)
    reusable = _find_reusable_stem_files(audio_path, model_name, output_dir)
    used_reusable_cache = bool(reusable)
    if reusable:
        logger.info("Verwende %d vollständig validierte Stem-Dateien erneut", len(reusable))
        if on_progress is not None:
            on_progress(100.0)
        result = {"stems": reusable}
    else:
        separator = StemSeparator()
        if state is not None and context is not None:
            state.require_project_context_current(context)
        result = separator.separate(audio_path, model_name=model_name, on_progress=on_progress)

    # Fehler vom Separator prüfen
    if "error" in result:
        raise RuntimeError(f"Stem-Separation fehlgeschlagen: {result['error']}")

    # StemSeparator.separate() kann relative Dateinamen zurückgeben.
    # Diese auf den konfigurierten Output-/Temp-Ordner normalisieren.
    # StemSeparator.separate() gibt {"stems": [path1, path2, ...]} zurück.
    # audio-separator benennt Output-Dateien mit (Vocals), (Instrumental), etc.
    stem_files = result.get("stems", [])
    normalized_stem_files: list[str] = []
    for fpath in stem_files:
        p = Path(fpath)
        resolved = p.resolve() if p.is_absolute() else (output_dir / p).resolve()
        normalized_stem_files.append(str(resolved))

    mapped: dict[str, str | None] = {
        "vocals_path": None,
        "instrumental_path": None,
        "drums_path": None,
        "bass_path": None,
        "other_path": None,
        "model_used": model_name,
    }

    for fpath in normalized_stem_files:
        name_lower = Path(fpath).stem.lower()
        if "vocal" in name_lower:
            mapped["vocals_path"] = fpath
        elif "instrumental" in name_lower or "no_vocals" in name_lower or "instrum" in name_lower:
            mapped["instrumental_path"] = fpath
        elif "drum" in name_lower:
            mapped["drums_path"] = fpath
        elif "bass" in name_lower:
            mapped["bass_path"] = fpath
        elif "other" in name_lower:
            mapped["other_path"] = fpath
        else:
            # Unbekannter Stem — als "other" zuweisen falls noch frei
            if mapped["other_path"] is None:
                mapped["other_path"] = fpath

    # Synthetisiere instrumental_path falls htdemucs (drums, bass, other, vocals vorhanden, aber kein instrumental)
    if (mapped["vocals_path"] and mapped["drums_path"] and mapped["bass_path"] and mapped["other_path"] 
            and mapped["instrumental_path"] is None):
        try:
            logger.info("Synthetisiere Instrumental-Stem aus Drums + Bass + Other...")
            import soundfile as sf
            import numpy as np
            
            # Ausgabepfad generieren (im selben Verzeichnis wie die anderen Stems)
            drums_p = Path(mapped["drums_path"])
            inst_p = drums_p.parent / f"{drums_p.stem.replace('(Drums)', '(Instrumental)').replace('drums', 'instrumental')}.wav"
            
            data_drums, sr = sf.read(mapped["drums_path"])
            data_bass, _ = sf.read(mapped["bass_path"])
            data_other, _ = sf.read(mapped["other_path"])
            
            # Sicherstellen, dass die Arrays die gleiche Länge haben (falls minimal abweichend)
            min_len = min(len(data_drums), len(data_bass), len(data_other))
            data_inst = data_drums[:min_len] + data_bass[:min_len] + data_other[:min_len]
            
            # Amplitudenbegrenzung gegen Clipping
            data_inst = np.clip(data_inst, -1.0, 1.0)
            
            if state is not None and context is not None:
                with state.project_commit(context):
                    sf.write(str(inst_p), data_inst, sr)
            else:
                sf.write(str(inst_p), data_inst, sr)
            mapped["instrumental_path"] = str(inst_p)
            logger.info(f"Instrumental-Stem erfolgreich synthetisiert unter: {inst_p}")
        except Exception as synth_err:
            logger.error(f"Fehler bei der Synthese des Instrumental-Stems: {synth_err}", exc_info=True)

    logger.info(f"Stem-Mapping: {len(normalized_stem_files)} Dateien → {sum(1 for v in mapped.values() if v and v != model_name)} Stems")
    if not used_reusable_cache:
        try:
            _write_stem_cache_marker(
                audio_path,
                model_name,
                output_dir,
                normalized_stem_files,
                state=state,
                context=context,
            )
        except ProjectContextChangedError:
            raise
        except (OSError, RuntimeError, ValueError) as marker_error:
            logger.warning(
                "Stem-Erfolgsmarker konnte nicht publiziert werden; Reuse deaktiviert: %s",
                marker_error,
            )

    return mapped
