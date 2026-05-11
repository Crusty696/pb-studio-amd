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

from ..app_state import AppState, get_app_state
from ..config import config
from ..dependencies import with_gpu_task, publish_event, publish_log
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
    """Importiert eine Audio-Datei."""
    audio_path = Path(request.path)

    # SEC-001: Nur absolute Pfade erlauben (Path-Traversal-Schutz)
    if not audio_path.is_absolute():
        raise HTTPException(status_code=400, detail="Nur absolute Pfade erlaubt")

    try:
        if not audio_path.exists():
            raise HTTPException(status_code=404, detail=f"Datei nicht gefunden: {request.path}")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Zugriff verweigert")

    if audio_path.suffix.lower() not in {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}:
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

    clip = state.register_audio_clip({
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
    })

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
    await publish_event("import_progress", {"clip_id": clip['id'], "percent": 100.0, "message": "Import abgeschlossen"})
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
        merged["is_analyzed"] = analysis is not None or bool(clip.get("is_analyzed", False))
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
        result = await asyncio.to_thread(
            _run_audio_analysis, audio_path, request.clip_id, request, _loop
        )
        state.set_audio_analysis(request.clip_id, result)
        clip["bpm"] = float(result.get("bpm", 0.0) or 0.0)
        clip["key"] = result.get("key")
        clip["beat_count"] = int(result.get("beat_count", 0) or 0)
        clip["is_analyzed"] = True
        # R4-HOCH-9: Update duration from librosa when ffprobe returned 0.0
        analysis_dur = float(result.get("duration_seconds", 0.0) or 0.0)
        if analysis_dur > 0.0 and float(clip.get("duration_seconds", 0.0) or 0.0) <= 0.0:
            clip["duration_seconds"] = analysis_dur
        state.set_audio_clip(request.clip_id, clip)

        # P-1: Analyse-Ergebnisse in SQLite persistieren
        import json as _json
        beats_json = _json.dumps(result.get("beats", []))
        state.update_audio_analysis(
            clip_id=request.clip_id,
            bpm=clip["bpm"],
            key=clip["key"],
            beat_count=clip["beat_count"],
            beats_json=beats_json,
            is_analyzed=True,
            energy_curve=result.get("energy_curve"),
            structure_segments=result.get("structure_segments"),
            spectral_data=result.get("spectral_data"),
        )

        await publish_log(
            f"Audio-Analyse abgeschlossen: {clip['name']}",
            level="info",
            source="audio.analyze",
            detail=f"clip_id={request.clip_id} bpm={float(result.get('bpm', 0.0) or 0.0):.2f} beats={int(result.get('beat_count', 0) or 0)}",
        )
        await publish_event("analysis_progress", {
            "event": "analysis_progress",
            "task_id": str(request.clip_id),
            "status": "completed",
            "percent": 100,
            "message": f"Analyse abgeschlossen: BPM={float(result.get('bpm', 0.0) or 0.0):.1f}",
        })
        return AudioAnalysisResult(**result)
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
    
    # Onsets werden aus der Energy-Curve extrahiert
    energy = analysis.get("energy_curve", [])
    if not energy:
        return []
    
    # C1/FIX: Offload heavy math to threadpool
    from fastapi.concurrency import run_in_threadpool
    return await run_in_threadpool(_calculate_onsets_sync, energy)


def _calculate_onsets_sync(energy: list[float]) -> list[float]:
    """Synchronous math for onset detection."""
    from scipy.signal import find_peaks
    
    # 512 hop_length bei 22050 Hz -> ~0.023s per point
    fps = 22050 / 512
    peaks, _ = find_peaks(energy, height=0.3, distance=int(0.1 * fps))
    return (peaks / fps).tolist()


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
            sample_rate=44100,  # WaveformAnalyzer analysiert immer bei 44100 Hz
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
    """Führt Stem-Separation durch (GPU-Lock via Middleware)."""
    clip = state.get_audio_clip(request.clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Clip {request.clip_id} nicht gefunden")
    logger.info(f"Starte Stem-Separation: {clip['name']} mit {request.model.value}")

    # Audit C2: per-stage stem_progress SSE callback (init/loading/inference/saving/complete).
    _loop = asyncio.get_running_loop()
    _clip_id = request.clip_id

    def _stem_progress(pct: float) -> None:
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
        result = await with_gpu_task(
            _run_stem_separation, clip["path"], request.model.value, _stem_progress,
            model_id="mdx_net_inst",  # VRAM-Budget-Check via VRAMBudgetManager
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
            state.set_audio_clip(request.clip_id, clip)

        return StemResult(clip_id=request.clip_id, **result)
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


def _run_audio_analysis(audio_path: str, clip_id: int, request: AudioAnalyzeRequest, _loop=None) -> dict[str, Any]:
    """Führt die vollständige Audio-Analyse durch (blockierend)."""
    import librosa
    import numpy as np

    _emit_analysis_progress(_loop, "load", 5.0, "Audio wird geladen…")

    # Audio einmalig laden — wird von StructureAnalyzer und KeyDetector benötigt
    try:
        y, sr = librosa.load(audio_path, sr=22050, mono=True)
    except Exception as e:
        logger.error(f"Audio-Load fehlgeschlagen: {audio_path}: {e}")
        raise RuntimeError(f"Audio-Datei konnte nicht geladen werden: {audio_path}: {e}")

    duration = float(len(y)) / sr if sr > 0 else 0.0
    _emit_analysis_progress(_loop, "load", 15.0, "Audio geladen — starte Beat-Erkennung…")

    # 1. BeatNet Beat-Detection
    beats: list[dict] = []
    bpm: float = 0.0
    energy_curve: list[float] = []

    if request.detect_beats:
        try:
            # Use module-level singleton to avoid re-initializing on every call
            detector = _get_beat_detector()

            # Per-stage progress: detect_beats emittiert pct in [0..100],
            # mappen auf overall [15..45] (beats-Phase im Audio-Pipeline).
            def _beat_progress(pct: float) -> None:
                overall = 15.0 + (max(0.0, min(100.0, pct)) / 100.0) * 30.0
                _emit_analysis_progress(
                    _loop, "beat_chunk", overall, f"BeatNet inference {pct:.1f}%"
                )

            # detect_beats gibt list[float] zurück — BeatNet oder Librosa-Fallback
            beat_times = detector.detect_beats(audio_path, on_progress=_beat_progress)
            if beat_times:
                arr = np.asarray(beat_times, dtype=np.float64)

                # Audit L-N8: real per-beat strength via librosa.onset.onset_strength.
                # Vorher: hardcoded 1.0 — Engine konnte beats nicht gewichten.
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

            # Energy-Curve via librosa (unabhängig von BeatNet-Verfügbarkeit)
            rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
            rms_max = float(np.max(rms)) if len(rms) > 0 else 1.0
            energy_curve = (rms / rms_max).tolist() if rms_max > 0 else rms.tolist()
        except Exception as e:
            logger.warning(f"Beat-Analyse fehlgeschlagen: {e}")

    _emit_analysis_progress(_loop, "beats", 45.0, "Beats erkannt — starte Struktur-Analyse…")

    # 2. Struktur-Analyse (Novelty + Clustering)
    structure_segments: list = []
    if request.detect_structure:
        try:
            from pb_studio.audio.structure_analyzer import StructureAnalyzer
            struct_result = StructureAnalyzer().analyze_song_structure(y, sr)
            structure_segments = struct_result.get("segments", [])
        except Exception as e:
            logger.warning(f"Struktur-Analyse fehlgeschlagen: {e}")

    _emit_analysis_progress(_loop, "structure", 70.0, "Struktur analysiert — starte Spektral-Analyse…")

    # 3. Spektral-Analyse (8-Band STFT) — nutzt bereits geladenes y/sr (kein erneuter Disk-Zugriff)
    spectral_data = None
    if request.spectral_analysis:
        try:
            from pb_studio.audio.spectral_analyzer import SpectralAnalyzer, FREQUENCY_BANDS
            spec_result = SpectralAnalyzer(sr=sr).analyze_from_array(y, sr)
            spectral_data = {
                "clip_id": clip_id,
                "times": spec_result.get("times", []),
                "bands": spec_result.get("band_energies", {}),
                "centroids": spec_result.get("centroids", []),
                "frequency_ranges": {k: list(v) for k, v in FREQUENCY_BANDS.items()},
            }
        except Exception as e:
            logger.warning(f"Spektral-Analyse fehlgeschlagen: {e}")

    _emit_analysis_progress(_loop, "spectral", 85.0, "Spektrum analysiert — starte Tonart-Erkennung…")

    # 4. Tonart-Erkennung (Krumhansl-Kessler, immer aktiv)
    key = None
    try:
        from pb_studio.audio.key_detector import KeyDetector
        key = KeyDetector().detect_key(y, sr)
    except Exception as e:
        logger.warning(f"Key-Detection fehlgeschlagen: {e}")

    _emit_analysis_progress(_loop, "key", 95.0, "Tonart erkannt — Analyse abgeschlossen")

    return {
        "clip_id": clip_id,
        "duration_seconds": duration,
        "bpm": bpm,
        "beat_count": len(beats),
        "beats": beats,
        "key": key,
        "energy_curve": energy_curve,
        "structure_segments": structure_segments,
        "spectral_data": spectral_data,
    }


def _extract_waveform(audio_path: str, bands: int) -> list[list[float]]:
    """Extrahiert N-Band Waveform-Daten, blockierend.

    bands=1: nur 'mid', bands=2: 'low'+'high', bands=3: 'low'+'mid'+'high'
    bands>=4: alle 3 Bänder (max verfügbar)
    """
    try:
        from pb_studio.audio.waveform_analyzer import WaveformAnalyzer
        result = WaveformAnalyzer().get_downsampled_waveform(
            audio_path, target_points=1000
        )
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
        logger.warning("WaveformAnalyzer nicht verfügbar, leere Daten")
        return []
    except Exception as e:
        logger.warning(f"Waveform-Extraktion fehlgeschlagen: {e}")
        return []


def _run_stem_separation(audio_path: str, model_name: str, on_progress=None) -> dict[str, Any]:
    """Führt Stem-Separation durch (blockierend, GPU)."""
    from pb_studio.audio.separator import StemSeparator

    separator = StemSeparator()
    result = separator.separate(audio_path, model_name=model_name, on_progress=on_progress)

    # Fehler vom Separator prüfen
    if "error" in result:
        raise RuntimeError(f"Stem-Separation fehlgeschlagen: {result['error']}")

    # StemSeparator.separate() kann relative Dateinamen zurückgeben.
    # Diese auf den konfigurierten Output-/Temp-Ordner normalisieren.
    output_dir_raw = separator.config.get("paths", {}).get("temp_dir", "./temp")
    output_dir = separator.config.resolve_path(output_dir_raw)

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

    logger.info(f"Stem-Mapping: {len(normalized_stem_files)} Dateien → {sum(1 for v in mapped.values() if v and v != model_name)} Stems")
    return mapped
