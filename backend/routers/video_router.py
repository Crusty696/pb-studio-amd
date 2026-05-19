"""
Video Router – Import, Analyse, Thumbnails, Scenes, Motion.

Endpoints:
  POST /video/import          — Video-Dateien importieren
  GET  /video/clips           — Video-Clip Liste
  GET  /video/thumbnails/{id} — Thumbnail als JPEG
  POST /video/analyze         — Video analysieren
  GET  /video/scenes/{id}     — Scene-Cuts abrufen
  GET  /video/motion/{id}     — Motion-Daten abrufen
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..app_state import AppState, get_app_state
from ..config import config
from ..dependencies import with_gpu_task, publish_event, publish_log
from ..schemas.video_schemas import (
    VideoImportRequest, VideoClipInfo,
    VideoAnalyzeRequest, VideoAnalysisResult,
    SceneInfo, MotionData,
    ThumbstripResponse,
    ClipwaveResponse,
)
from ..schemas.common import BatchDeleteRequest, DeleteResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/video", tags=["Video"])


@router.post(
    "/import",
    response_model=list[VideoClipInfo],
    summary="Video-Dateien importieren",
    description=(
        "Importiert eine oder mehrere Video-Dateien (MP4, AVI, MKV, MOV, WEBM, WMV, FLV). "
        "Ermittelt Metadaten (Auflösung, FPS, Dauer, Codec) via ffprobe. "
        "Dateien die nicht existieren oder ein nicht unterstütztes Format haben werden übersprungen."
    ),
)
async def import_videos(
    request: VideoImportRequest,
    state: AppState = Depends(get_app_state),
) -> list[VideoClipInfo]:
    """Importiert eine oder mehrere Video-Dateien."""
    imported = []
    supported = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv", ".flv"}

    for path_str in request.paths:
        video_path = Path(path_str)
        # SEC-001: Nur absolute Pfade erlauben
        if not video_path.is_absolute():
            logger.warning(f"Relativer Pfad abgelehnt: {path_str}")
            continue
        try:
            if not video_path.exists():
                logger.warning(f"Video nicht gefunden: {path_str}")
                continue
        except PermissionError:
            logger.warning(f"Zugriff verweigert: {path_str}")
            continue
        if video_path.suffix.lower() not in supported:
            logger.warning(f"Format nicht unterstützt: {video_path.suffix}")
            continue

        try:
            info = await asyncio.to_thread(_get_video_info, str(video_path))
        except Exception as e:
            logger.error(f"Video-Info fehlgeschlagen: {video_path.name}: {e}")
            continue

        # Plan Phase 1 #1: streaming sha256 hash for embedding-cache reuse.
        # User-Anforderung 2026-05-09: 0.01% per-chunk SSE-Progress.
        from pb_studio.core.media_hash import media_hash
        _loop = asyncio.get_running_loop()
        _vname = video_path.name
        _file_idx = len(imported) + 1
        _file_total = len(request.paths)

        def _hash_progress(pct: float) -> None:
            try:
                # Map per-file 0..100% auf overall (file_idx-1 + pct/100) / total * 100
                overall = ((_file_idx - 1) + pct / 100.0) * 100.0 / _file_total
                asyncio.run_coroutine_threadsafe(
                    publish_event("import_progress", {
                        "step": "hash",
                        "percent": overall,
                        "message": f"Hash {_file_idx}/{_file_total} {_vname}: {pct:.2f}%",
                    }),
                    _loop,
                )
            except Exception:
                pass

        try:
            video_hash_value = await asyncio.to_thread(
                media_hash, str(video_path), _hash_progress
            )
        except Exception as e:
            logger.warning(f"media_hash fehlgeschlagen für {video_path}: {e}")
            video_hash_value = None

        clip = state.register_video_clip({
            "name": video_path.stem,
            "path": str(video_path.absolute()),
            "duration_seconds": info.get("duration", 0.0),
            "width": info.get("width", 1920),
            "height": info.get("height", 1080),
            "fps": info.get("fps", 30.0),
            "codec": info.get("codec", ""),
            "thumbnail_available": False,
            "tags": [],
            "video_hash": video_hash_value,
            "has_video_embedding": False,
        })
        imported.append(VideoClipInfo(**clip))

        await publish_log(
            f"Video importiert: {video_path.name}",
            level="info",
            source="video.import",
            detail=f"clip_id={clip['id']} duration={info.get('duration', 0.0):.2f}s fps={info.get('fps', 0.0):.2f}",
        )

        await publish_event("import_progress", {
            "clip_id": clip["id"],
            "percent": len(imported) / len(request.paths) * 100,
            "message": f"Importiert: {video_path.name}",
        })

    # R15/M-01: Finales 100%-Event sicherstellen — bei übersprungenen Pfaden
    # (falsches Format, Info-Fehler) würde der letzte Event nie 100% erreichen.
    await publish_event("import_progress", {
        "clip_id": None,
        "percent": 100.0,
        "message": f"{len(imported)}/{len(request.paths)} Videos importiert",
    })

    logger.info(f"{len(imported)} von {len(request.paths)} Videos importiert")
    return imported


@router.get(
    "/clips",
    response_model=list[VideoClipInfo],
    summary="Video-Clip-Liste abrufen",
    description=(
        "Gibt alle importierten Video-Clips zurück. Unterstützt Paginierung via "
        "'page' (1-basiert) und 'limit' (max. 200 Einträge pro Seite)."
    ),
)
async def list_clips(
    page: int = Query(1, ge=1, description="Seitennummer (1-basiert)"),
    limit: int = Query(50, ge=1, le=200, description="Einträge pro Seite"),
    state: AppState = Depends(get_app_state),
) -> list[VideoClipInfo]:
    """Gibt die Video-Clip-Liste zurück (paginiert)."""
    clips_snap = state.get_video_clips_snapshot()
    analysis_snap = state.get_video_analysis_snapshot()
    clips = list(clips_snap.values())
    start = (page - 1) * limit
    end = start + limit

    result: list[VideoClipInfo] = []
    for c in clips[start:end]:
        clip_id = c["id"]
        is_analyzed = clip_id in analysis_snap
        # L-N3: video_hash aus in-memory state (None falls Hashing fehlgeschlagen
        # oder Clip aus aelterer DB-Persistenz ohne Hash-Spalte geladen wurde).
        # UI rendert daraus einen "CACHED"-Badge auf der VideoClip-Card.
        video_hash_value = c.get("video_hash")
        # L-M4: Motion-Daten aus analysis_cache extrahieren fuer UI-Detail-Card.
        # Falls Clip noch nicht analysiert oder kein motion-Block vorhanden -> None.
        avg_motion: Optional[float] = None
        peak_motion: Optional[float] = None
        motion_category: Optional[str] = None
        # L-M8: SigLIP-Embedding-Meta aus analysis_cache (0 wenn nicht analysiert).
        embedding_dim: Optional[int] = None
        embedding_samples: Optional[int] = None
        has_embedding: bool = False
        if is_analyzed:
            va = analysis_snap.get(clip_id) or {}
            motion = va.get("motion") or {}
            if motion:
                _avg = motion.get("avg_motion")
                _peak = motion.get("peak_motion")
                _cat = motion.get("motion_category")
                if _avg is not None:
                    try:
                        avg_motion = float(_avg)
                    except (TypeError, ValueError):
                        avg_motion = None
                if _peak is not None:
                    try:
                        peak_motion = float(_peak)
                    except (TypeError, ValueError):
                        peak_motion = None
                if _cat:
                    motion_category = str(_cat)
                # Falls motion_category fehlt aber avg_motion vorhanden ist,
                # ueber _classify_motion ableiten (static/low/medium/high).
                elif avg_motion is not None:
                    motion_category = _classify_motion(avg_motion)
            # L-M8: embedding-Meta
            _emb_dim = va.get("embedding_dim")
            _emb_samples = va.get("embedding_samples")
            if _emb_dim is not None:
                try:
                    embedding_dim = int(_emb_dim)
                except (TypeError, ValueError):
                    embedding_dim = None
            if _emb_samples is not None:
                try:
                    embedding_samples = int(_emb_samples)
                except (TypeError, ValueError):
                    embedding_samples = None
            has_embedding = bool(va.get("has_embedding", False))

        # L-N3: video_hash separat extrahieren damit es nicht doppelt via **c
        # an VideoClipInfo gereicht wird (TypeError "multiple values for keyword").
        c_payload = {k: v for k, v in c.items() if k != "video_hash"}
        result.append(
            VideoClipInfo(
                **c_payload,
                is_analyzed=is_analyzed,
                video_hash=video_hash_value,
                avg_motion=avg_motion,
                peak_motion=peak_motion,
                motion_category=motion_category,
                embedding_dim=embedding_dim,
                embedding_samples=embedding_samples,
                has_embedding=has_embedding,
            )
        )
    return result


@router.get(
    "/thumbnails/{clip_id}",
    summary="Thumbnail abrufen",
    description=(
        "Generiert und gibt das Thumbnail eines Video-Clips als JPEG zurück (Content-Type: image/jpeg). "
        "Thumbnail wird vom ersten Frame nach 1 Sekunde generiert, skaliert auf 320px Breite."
    ),
    responses={200: {"content": {"image/jpeg": {}}}},
)
async def get_thumbnail(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> Response:
    """Gibt das Thumbnail eines Clips als JPEG zurück."""
    clip = state.get_video_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} nicht gefunden")
    try:
        jpeg_bytes = await asyncio.to_thread(_generate_thumbnail, clip["path"])
        # L-N7: in-memory Flag setzen damit list_clips den korrekten Wert liefert.
        # Update darf nie crashen (best-effort).
        try:
            state.update_video_clip(clip_id=clip_id, thumbnail_available=True)
        except Exception as ex:
            logger.debug(f"L-N7 thumbnail_available update fehlgeschlagen (unkritisch): {ex}")
        return Response(content=jpeg_bytes, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Thumbnail-Generierung fehlgeschlagen: {e}")


@router.get(
    "/thumbstrip/{clip_id}",
    response_model=ThumbstripResponse,
    summary="Thumbnail-Strip (N Frames) abrufen",
    description=(
        "Liefert N evenly-spaced JPEG-Thumbnails als base64-Datenstrings, "
        "fuer den Timeline-Clip-Strip (Premiere/Davinci-Style). "
        "n wird auf [1,32] geklammert."
    ),
)
async def get_thumbstrip(
    clip_id: int,
    n: int = 8,
    state: AppState = Depends(get_app_state),
) -> ThumbstripResponse:
    clip = state.get_video_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Video-Clip {clip_id} nicht gefunden")
    n = max(1, min(32, n))
    try:
        frames = await asyncio.to_thread(_extract_thumbstrip, clip["path"], n, (160, 90))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Thumbstrip-Erzeugung fehlgeschlagen: {e}")

    import base64
    import io
    data_urls: list[str] = []
    for img in frames:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        data_urls.append(f"data:image/jpeg;base64,{b64}")
    return ThumbstripResponse(clip_id=clip_id, count=len(data_urls), frames=data_urls)


def _extract_thumbstrip(video_path: str, n: int, size: tuple) -> list:
    """Indirection so tests can monkeypatch the heavy work."""
    from pb_studio.video.frame_extractor import FrameGrabber
    return FrameGrabber().extract_thumbnail_strip(video_path, n=n, size=size)


@router.get(
    "/clipwave/{clip_id}",
    response_model=ClipwaveResponse,
    summary="Clip-Audio-Peaks (downsampled mono) abrufen",
    description=(
        "Liefert N normalisierte (0..1) Peak-Werte fuer die Audio-Spur eines "
        "Video-Clips. Used vom Timeline-Mini-Waveform-Layer. n geklammert auf [1,2048]."
    ),
)
async def get_clipwave(
    clip_id: int,
    n: int = 256,
    state: AppState = Depends(get_app_state),
) -> ClipwaveResponse:
    clip = state.get_video_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Video-Clip {clip_id} nicht gefunden")
    n = max(1, min(2048, n))
    try:
        peaks = await asyncio.to_thread(_extract_clip_peaks, clip["path"], n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Peaks-Erzeugung fehlgeschlagen: {e}")
    return ClipwaveResponse(clip_id=clip_id, count=len(peaks), peaks=peaks)


def _extract_clip_peaks(media_path: str, n: int) -> list[float]:
    """Indirection for tests."""
    from pb_studio.video.clip_audio_peaks import extract_peaks
    return extract_peaks(media_path, n_buckets=n)


@router.delete(
    "/clips/{clip_id}",
    response_model=DeleteResponse,
    summary="Video-Clip loeschen (single)",
)
async def delete_clip(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Loescht einen einzelnen Video-Clip aus In-Memory + SQLite + FAISS-Cache."""
    if state.delete_video_clip(clip_id):
        await publish_log(f"Video-Clip {clip_id} geloescht", level="info", source="video.delete")
        return DeleteResponse(deleted_count=1, not_found_ids=[])
    return DeleteResponse(deleted_count=0, not_found_ids=[clip_id])


@router.delete(
    "/clips",
    response_model=DeleteResponse,
    summary="Video-Clips batch-loeschen",
)
async def delete_clips_batch(
    request: BatchDeleteRequest,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Batch-Delete: loescht alle in clip_ids aufgefuehrten Video-Clips."""
    deleted = 0
    not_found = []
    for cid in request.clip_ids:
        if state.delete_video_clip(cid):
            deleted += 1
        else:
            not_found.append(cid)
    if deleted:
        await publish_log(
            f"{deleted} Video-Clips batch-geloescht (von {len(request.clip_ids)} angefragt)",
            level="info", source="video.delete",
        )
    return DeleteResponse(deleted_count=deleted, not_found_ids=not_found)


@router.post(
    "/analyze",
    response_model=VideoAnalysisResult,
    summary="Video-Clip analysieren",
    description=(
        "Analysiert einen Video-Clip: Scene-Detection (PySceneDetect), "
        "Motion-Analyse (RAFT ONNX via DirectML), Embedding-Generierung (SigLIP). "
        "Belegt GPU-Lock. Ergebnis wird gecacht."
    ),
)
async def analyze_video(
    request: VideoAnalyzeRequest,
    state: AppState = Depends(get_app_state),
) -> VideoAnalysisResult:
    """Analysiert einen Video-Clip (GPU-Lock via Middleware)."""
    clip = state.get_video_clip(request.clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Clip {request.clip_id} nicht gefunden")

    # R15/C-02: Datei-Existenz VOR GPU-Lock prüfen — fehlendes File würde sonst als
    # leeres Analyse-Ergebnis (scene_count=0, avg_motion=0.0) in die DB geschrieben
    # und vorherige Analysen überschreiben (Silent Data Corruption).
    if not Path(clip["path"]).exists():
        raise HTTPException(status_code=422, detail=f"Video-Datei nicht gefunden: {clip['path']!r}")

    logger.info(f"Starte Video-Analyse: {clip['name']}")
    await publish_log(
        f"Video-Analyse gestartet: {clip['name']}",
        level="info",
        source="video.analyze",
        detail=f"clip_id={request.clip_id}",
    )

    # BUG-204/Feature-3: Multi-step SSE events fuer fein-granularen UI-Fortschritt.
    # 4 coarse Phasen (init/scenes/motion+embed/finalize). _run_video_analysis ist
    # via _loop + RAFT on_progress callback bereits per-frame instrumentiert
    # (siehe _motion_progress -> 'analysis_progress' SSE event), Audit C1.
    await publish_event("analysis_progress", {
        "clip_id": request.clip_id,
        "step": "init",
        "step_index": 1,
        "step_total": 4,
        "percent": 1.0,
        "message": f"Starte Video-Analyse: {clip['name']}",
    })

    await publish_event("analysis_progress", {
        "clip_id": request.clip_id,
        "step": "scenes",
        "step_index": 2,
        "step_total": 4,
        "percent": 15.0,
        "message": f"Scene-Detection laeuft: {clip['name']}",
    })

    try:
        await publish_event("analysis_progress", {
            "clip_id": request.clip_id,
            "step": "motion_embedding",
            "step_index": 3,
            "step_total": 4,
            "percent": 35.0,
            "message": f"Motion + Embedding (RAFT/SigLIP) laeuft: {clip['name']}",
        })
        # Audit C1: _loop an _run_video_analysis durchreichen, damit der RAFT
        # on_progress callback per-frame SSE-Events publishen kann (asyncio
        # run_coroutine_threadsafe braucht den Event-Loop des FastAPI-Workers).
        _loop = asyncio.get_running_loop()
        result = await with_gpu_task(
            _run_video_analysis, clip["path"], request.clip_id, request, _loop,
            model_id="video_analysis_full",  # VRAM-Budget-Check via VRAMBudgetManager (RAFT + SigLIP)
        )

        # Y3 / GPU-F2: L-K4 audio_key Detection OUTSIDE with_gpu_task — ffmpeg
        # extract 30s mono WAV + Krumhansl-Kessler ist pure CPU-Arbeit und darf
        # den GPU-Lock NICHT halten (sonst blocken parallele Stem-/Render-Tasks).
        try:
            from pb_studio.video.audio_key_detector import detect_video_audio_key
            audio_key_val = await asyncio.to_thread(detect_video_audio_key, clip["path"])
            result["audio_key"] = audio_key_val
            if audio_key_val:
                logger.info(f"L-K4: Video-Audio-Key fuer clip {request.clip_id}: {audio_key_val}")
        except Exception as e:
            logger.warning(f"L-K4 audio_key extract failed (post-gpu-task): {e}")
            result["audio_key"] = None

        state.set_video_analysis(request.clip_id, result)

        # P-2: Analyse-Ergebnisse in SQLite persistieren
        # L-M8: embedding_dim + embedding_samples mit-persistieren damit
        # Reload die SigLIP-Embedding-Metadaten zeigt (vorher 0).
        state.update_video_analysis(
            clip_id=request.clip_id,
            scene_count=int(result.get("scene_count", 0) or 0),
            avg_motion=float(result.get("avg_motion", 0.0) or 0.0),
            has_embedding=bool(result.get("has_embedding", False)),
            is_analyzed=True,
            scenes=result.get("scenes"),
            motion=result.get("motion"),
            dominant_colors=result.get("dominant_colors"),
            tags=result.get("tags"),
            audio_key=result.get("audio_key"),  # L-K4
            embedding_dim=int(result.get("embedding_dim", 0) or 0),       # L-M8
            embedding_samples=int(result.get("embedding_samples", 0) or 0),  # L-M8
        )

        await publish_log(
            f"Video-Analyse abgeschlossen: {clip['name']}",
            level="info",
            source="video.analyze",
            detail=f"clip_id={request.clip_id} scenes={int(result.get('scene_count', 0) or 0)} avg_motion={float(result.get('avg_motion', 0.0) or 0.0):.2f}",
        )

        # Feature-3: finalize-Event vor complete (DB-Persistenz schon passiert oben)
        await publish_event("analysis_progress", {
            "clip_id": request.clip_id,
            "step": "finalize",
            "step_index": 4,
            "step_total": 4,
            "percent": 90.0,
            "message": f"Persistiere Ergebnisse: {clip['name']}",
        })

        # BUG-204 Fix: Final-Event mit Ergebnis-Daten fuer UI-Status
        await publish_event("analysis_progress", {
            "clip_id": request.clip_id,
            "step": "complete",
            "step_index": 4,
            "step_total": 4,
            "percent": 100.0,
            "message": (
                f"Video-Analyse fertig: {int(result.get('scene_count', 0) or 0)} Szenen, "
                f"Motion {float(result.get('avg_motion', 0.0) or 0.0):.1f}"
            ),
        })
        return VideoAnalysisResult(**result)
    except Exception as e:
        logger.error(f"Video-Analyse fehlgeschlagen: {e}", exc_info=True)
        await publish_log(
            f"Video-Analyse fehlgeschlagen: {clip['name']}",
            level="error",
            source="video.analyze",
            detail=str(e),
        )
        # BUG-204 Fix: Error-Event so UI nicht ewig im "Loading" haengt
        await publish_event("analysis_progress", {
            "clip_id": request.clip_id,
            "step": "error",
            "percent": 0.0,
            "message": f"Video-Analyse fehlgeschlagen: {clip['name']} ({type(e).__name__})",
        })
        raise HTTPException(status_code=500, detail=f"Analyse fehlgeschlagen: {e}")


@router.get(
    "/scenes/{clip_id}",
    response_model=list[SceneInfo],
    summary="Scene-Cuts abrufen",
    description=(
        "Gibt die detektierten Scene-Cuts (Start/End-Zeit, Typ, Confidence) "
        "für einen analysierten Video-Clip zurück."
    ),
)
async def get_scenes(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> list[SceneInfo]:
    """Gibt Scene-Cuts für einen Clip zurück."""
    analysis = state.get_video_analysis(clip_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Keine Analyse für Clip {clip_id}")
    scenes = analysis.get("scenes", [])
    return [SceneInfo(**s) if isinstance(s, dict) else s for s in scenes]


@router.get(
    "/motion/{clip_id}",
    response_model=MotionData,
    summary="Motion-Analyse abrufen",
    description=(
        "Gibt die Motion-Analysedaten (Durchschnittsbewegung, Motion-Kurve, Peak-Frames) "
        "für einen analysierten Video-Clip zurück. Wird vom SmartDirector für Motion-Matching genutzt."
    ),
)
async def get_motion(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> MotionData:
    """Gibt Motion-Analyse Daten zurück."""
    analysis = state.get_video_analysis(clip_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Keine Analyse für Clip {clip_id}")
    motion = analysis.get("motion", {})
    if not motion:
        return MotionData(clip_id=clip_id)
    if "clip_id" not in motion:
        motion = {**motion, "clip_id": clip_id}
    return MotionData(**motion)


# --- Private Hilfsfunktionen ---

def _get_video_info(path: str) -> dict[str, Any]:
    """Ermittelt Video-Informationen via ffprobe."""
    import json
    import subprocess

    cmd = [
        str(config.ffprobe_path), "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,codec_name,duration",
        "-show_entries", "format=duration",
        "-of", "json", path,
    ]
    res = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=30)
    data = json.loads(res)

    stream = data.get("streams", [{}])[0]
    fmt = data.get("format", {})

    fps_str = stream.get("r_frame_rate", "30/1")
    try:
        num, den = fps_str.split("/")
        fps = float(num) / float(den)
    except (ValueError, ZeroDivisionError):
        fps = 30.0

    # R20/MEDIUM-020-5: ffprobe returns "N/A" for some formats (e.g. .wmv stream duration).
    # "N/A" is truthy so the `or` short-circuit does NOT protect float() from ValueError.
    # Resolve to format-level duration when the stream value is unusable.
    _stream_dur = stream.get("duration", 0)
    _fmt_dur = fmt.get("duration", 0)
    try:
        duration = float(_stream_dur) if _stream_dur not in (None, "", "N/A") else float(_fmt_dur or 0)
    except (ValueError, TypeError):
        try:
            duration = float(_fmt_dur or 0)
        except (ValueError, TypeError):
            duration = 0.0

    return {
        "width": int(stream.get("width", 1920)),
        "height": int(stream.get("height", 1080)),
        "fps": round(fps, 2),
        "codec": stream.get("codec_name", ""),
        "duration": duration,
    }


def _generate_thumbnail(video_path: str) -> bytes:
    """Generiert ein Thumbnail-JPEG (blockierend)."""
    import subprocess
    import tempfile
    from ..config import config

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        cmd = [
            str(config.ffmpeg_path), "-y", "-i", video_path,
            "-ss", "1", "-frames:v", "1",
            "-vf", "scale=320:-1",
            str(tmp_path),
        ]
        subprocess.run(cmd, capture_output=True, timeout=15, check=True)
        return tmp_path.read_bytes()
    finally:
        # R20/LOW: unlink(missing_ok=True) avoids FileNotFoundError if ffmpeg
        # failed before creating the file.
        tmp_path.unlink(missing_ok=True)


def _run_video_analysis(
    video_path: str,
    clip_id: int,
    request: VideoAnalyzeRequest,
    _loop=None,
) -> dict[str, Any]:
    """Führt Video-Analyse durch (blockierend, GPU).

    Audit C1: optionaler _loop Parameter ermöglicht per-frame SSE-Events aus
    dem RAFT MotionAnalyzer.analyze_video_segment on_progress callback heraus.
    None-default für Tests / Sync-Aufrufe ohne Event-Loop.
    """
    # L-M8: embedding_dim/samples standardmaessig 0 setzen damit Persistenz
    # nach Reload deterministisch 0 zeigt (nicht None) wenn kein Embedding
    # generiert wurde.
    result: dict = {
        "clip_id": clip_id,
        "scene_count": 0,
        "avg_motion": 0.0,
        "embedding_dim": 0,
        "embedding_samples": 0,
        "has_embedding": False,
    }

    # 1. Scene-Detection via PySceneDetect
    if request.detect_scenes:
        try:
            from pb_studio.video.scene_detect import SceneDetector
            scenes_raw = SceneDetector().detect_scenes(video_path)
            # SceneDetector gibt [(start_sec, end_sec), ...] zurück
            result["scenes"] = [
                {
                    "start_time": float(s[0]),
                    "end_time": float(s[1]),
                    "scene_type": "cut",
                    "confidence": 0.85,
                }
                for s in scenes_raw
            ]
            result["scene_count"] = len(scenes_raw)
        except Exception as e:
            logger.warning(f"Scene-Detection fehlgeschlagen: {e}")

    # 2. Motion-Analyse via RAFT (benötigt Frames — via FrameGrabber extrahieren)
    if request.analyze_motion:
        try:
            import cv2
            from pb_studio.video.raft import MotionAnalyzer

            # User-Anforderung 2026-05-09: jeder Analyse-Schritt MUSS volle Datei-Laenge
            # abdecken (kein Sampling-Cap). Cap min(30,...) entfernt. 2 Frames/s Grid
            # ueber GESAMTES Video. Lange Videos brauchen entsprechend laenger.
            cap = cv2.VideoCapture(video_path)
            try:
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                duration_sec = total / max(fps, 1.0)
                n_frames = max(2, int(duration_sec * 2))  # 2 Samples/s, KEIN cap
                step = max(1, total // n_frames)

                frames = []
                # L-VIDEO-5: range(0, total - step, step) liess das letzte Sample
                # bei i=total-step ausfallen (range schliesst oberen Wert aus).
                # Folge: Motion-Curve verpasst Outro-Frames. total statt total-step.
                for i in range(0, total, step):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        frames.append(frame)
                    if len(frames) >= n_frames:
                        break
            finally:
                cap.release()

            if len(frames) >= 2:
                motion_analyzer = MotionAnalyzer()
                try:
                    # Audit C1: per-frame SSE Progress callback. Mappe RAFT-internes
                    # 0..100% auf 35..65% (motion-Phase im Pipeline-Pipeline:
                    # init=0..15, scenes=15..35, motion=35..65, embedding=65..90,
                    # finalize=90..100).
                    def _motion_progress(pct: float) -> None:
                        if _loop is None:
                            return
                        overall = 35.0 + (pct / 100.0) * 30.0
                        try:
                            asyncio.run_coroutine_threadsafe(
                                publish_event("analysis_progress", {
                                    "clip_id": clip_id,
                                    "step": "motion_frame",
                                    "step_index": 3,
                                    "step_total": 4,
                                    "percent": overall,
                                    "message": f"RAFT frame {pct:.2f}%",
                                }),
                                _loop,
                            )
                        except Exception:
                            pass

                    motion_result = motion_analyzer.analyze_video_segment(
                        frames, stride=1, on_progress=_motion_progress
                    )

                    # Übersetze Sample-Indizes zu echten Video-Frame-Nummern
                    translated_scene_changes = [
                        {
                            "frame_index": sc["frame_index"] * step,
                            "time_seconds": round((sc["frame_index"] * step) / max(fps, 1.0), 3),
                            "confidence": sc.get("confidence", 0.0),
                        }
                        for sc in motion_result.get("scene_changes", [])
                        if isinstance(sc, dict)
                    ]

                    # L-K3: peak_motion aus motion_curve max berechnen
                    motion_curve_vals = motion_result.get("frame_motions", [])
                    peak_motion_value = float(max(motion_curve_vals)) if motion_curve_vals else 0.0

                    result["motion"] = {
                        "clip_id": clip_id,
                        "avg_motion": float(motion_result.get("avg_motion", 0.0)),
                        "peak_motion": peak_motion_value,  # L-K3 NEU
                        "motion_curve": [float(v) for v in motion_curve_vals],
                        "peak_frames": translated_scene_changes,
                        "motion_category": _classify_motion(motion_result.get("avg_motion", 0.0)),
                    }
                    result["avg_motion"] = result["motion"]["avg_motion"]
                finally:
                    # FIX 4: .unload() aufrufen um DirectML VRAM explizit freizugeben
                    motion_analyzer.unload()
                    import gc; gc.collect()
                    del motion_analyzer
        except Exception as e:
            logger.warning(f"Motion-Analyse fehlgeschlagen: {e}")

    # 3. Embedding (SigLIP DirectML — optional, benötigt ONNX-Modell-Datei)
    if request.generate_embeddings:
        try:
            import cv2
            from pb_studio.ai.siglip_wrapper import SigLIPWrapper
            from pb_studio.data.vector_store import VectorStore

            wrapper = SigLIPWrapper(lazy_load=False)
            try:
                if wrapper.is_ready:
                    # User-Anforderung 2026-05-09: jeder Schritt muss volle Datei-Laenge
                    # abdecken. Statt 1 Frame aus Mitte: N Frames gleichmaessig verteilt
                    # ueber Gesamt-Dauer, dann Embedding-Mittelwert (L2-normalisiert).
                    import numpy as _np
                    from PIL import Image as _PILImage

                    cap = cv2.VideoCapture(video_path)
                    embeddings_collected: list = []
                    try:
                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                        duration_sec = total_frames / max(fps, 1.0)
                        # 1 Sample / 5s ueber GESAMTES Video, min 3 Samples
                        n_emb_samples = max(3, int(duration_sec / 5.0))
                        sample_step = max(1, total_frames // n_emb_samples)
                        # L-VIDEO-5: total_frames statt total_frames - sample_step
                        # damit letztes Sample bei i=total_frames-sample_step nicht
                        # ausgelassen wird. range schliesst oberen Wert ohnehin aus.
                        for i in range(0, max(total_frames, 1), sample_step):
                            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                            ret, frame = cap.read()
                            if not ret or frame is None:
                                continue
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            pil_img = _PILImage.fromarray(frame_rgb)
                            emb = wrapper.encode_image(pil_img)
                            if emb is not None:
                                embeddings_collected.append(emb)
                            if len(embeddings_collected) >= n_emb_samples:
                                break
                    finally:
                        cap.release()

                    if embeddings_collected:
                        stacked = _np.stack(embeddings_collected, axis=0)
                        embedding = stacked.mean(axis=0)
                        # L2-normalisieren damit Mittelwert wieder Unit-Vector ist
                        norm = float(_np.linalg.norm(embedding))
                        if norm > 1e-3:
                            embedding = embedding / norm
                            # Y6 / L-STATE-2: add_embedding_with_media_link statt
                            # add_embedding — schreibt zusaetzlich vector_map-Row, sodass
                            # delete_video_clip per Cascade die FAISS-IDs tombstoned
                            # (sonst Orphan-Hits in Pacing-Semantic-Matcher).
                            from pb_studio.data.repositories.media_repository import MediaRepository
                            _vmr = MediaRepository()
                            _media_row = _vmr.find_by_project_and_path(
                                project_id=state.get_current_project_db_id(),
                                file_path=video_path,
                            )
                            _media_id = _media_row["id"] if _media_row else None
                            vs = VectorStore(index_name="video_index")
                            vs.add_embedding_with_media_link(
                                embedding.astype(_np.float32),
                                meta_info={
                                    "clip_id": clip_id,
                                    "path": video_path,
                                    "scene_id": f"clip_{clip_id}_full",
                                    "duration": result.get("duration_seconds", 0.0),
                                    "samples": len(embeddings_collected),
                                },
                                media_id=_media_id,
                                segment_start=0.0,
                                segment_end=float(result.get("duration_seconds", 0.0) or 0.0),
                                description=f"clip_{clip_id}_full",
                            )
                            result["has_embedding"] = True
                            result["embedding_dim"] = len(embedding)
                            result["embedding_samples"] = len(embeddings_collected)
                            logger.info(
                                f"SigLIP Embedding (Mittelwert ueber {len(embeddings_collected)} Frames) "
                                f"gespeichert fuer Clip {clip_id} (dim={len(embedding)})"
                            )
                        else:
                            logger.warning(
                                f"SigLIP near-zero mean embedding (norm={norm:.2e}) fuer clip {clip_id} "
                                "- FAISS-Insert uebersprungen"
                            )
                            result["has_embedding"] = False
                    else:
                        result["has_embedding"] = False
                else:
                    # ONNX-Modell nicht vorhanden — kein Fehler, nur Info
                    logger.info(
                        "SigLIP ONNX-Modell nicht gefunden — Embedding übersprungen. "
                        "Pacing verwendet Round-Robin Fallback."
                    )
                    result["has_embedding"] = False
            finally:
                del wrapper  # Release SigLIP ONNX session / DirectML VRAM

        except Exception as e:
            logger.warning(f"Embedding-Generierung fehlgeschlagen (unkritisch): {e}")
            result["has_embedding"] = False

    # 4. L-K2: Dominant Colors (KMeans) + Tags (Moondream optional, lazy ONNX).
    # Vorher waren beide Felder NIE in result -> Audit E4 Helper-API
    # (tags_overlap_score, dominant_color_similarity in semantic_matcher) nutzlos
    # weil Daten leer. Mid-frame als reprasentative Probe; KMeans ist billig
    # (~50ms), Moondream nur wenn ONNX-Modell + DirectML verfuegbar.
    if request.generate_captions:
        try:
            import cv2
            from pb_studio.video.moondream_wrapper import (
                extract_dominant_colors,
                extract_tags_via_moondream,
            )
            from pb_studio.video.lmstudio_vision_wrapper import (
                extract_tags_via_lmstudio,
            )

            cap = cv2.VideoCapture(video_path)
            try:
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                mid = max(0, total // 2)
                cap.set(cv2.CAP_PROP_POS_FRAMES, mid)
                ret, frame = cap.read()
            finally:
                cap.release()

            if ret and frame is not None:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result["dominant_colors"] = extract_dominant_colors(frame_rgb, k=5)

                # Primary: LM Studio Auto-Selection (Vision-Modell aus Registry).
                # Fallback: Moondream ONNX wenn LM Studio down/leer ist
                # (Iron Rule 10: keine silent fails — Tag-Quelle wird geloggt).
                tag_source = "lmstudio"
                tags = extract_tags_via_lmstudio(frame_rgb, mode="balance")
                if not tags:
                    tag_source = "moondream_fallback"
                    tags = extract_tags_via_moondream(frame_rgb)
                result["tags"] = tags
                result["tag_source"] = tag_source

                logger.info(
                    f"L-K2: {len(result['dominant_colors'])} colors, "
                    f"{len(result['tags'])} tags ({tag_source}) fuer clip {clip_id}"
                )
            else:
                result["dominant_colors"] = []
                result["tags"] = []
                result["tag_source"] = "none"
        except Exception as e:
            logger.warning(f"Tag/Color-Extract fehlgeschlagen (unkritisch): {e}")
            result["dominant_colors"] = []
            result["tags"] = []
            result["tag_source"] = "error"
    else:
        result["dominant_colors"] = []
        result["tags"] = []
        result["tag_source"] = "skipped"

    # Y3 / GPU-F2: L-K4 audio_key Detection (FFmpeg+librosa, ~30s CPU) wird
    # JETZT NICHT mehr hier ausgefuehrt — sie haelt sonst den globalen GPU-Lock
    # blockierend fuer reine CPU-Arbeit. Der Aufrufer (analyze_video Endpoint)
    # macht den Detection-Step NACH with_gpu_task, damit andere GPU-Tasks
    # (Stem-Separation, Render-Preview) waehrenddessen laufen koennen.
    result["audio_key"] = None

    return result


def _classify_motion(avg_motion: float) -> str:
    """Klassifiziert Motion-Stärke in Kategorien."""
    if avg_motion < 2.0:
        return "static"
    if avg_motion < 8.0:
        return "low"
    if avg_motion < 20.0:
        return "medium"
    