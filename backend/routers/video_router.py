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
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..app_state import AppState, get_app_state
from ..dependencies import with_gpu_task, publish_event, publish_log
from ..schemas.video_schemas import (
    VideoImportRequest, VideoClipInfo,
    VideoAnalyzeRequest, VideoAnalysisResult,
    SceneInfo, MotionData,
)

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
        if not video_path.exists():
            logger.warning(f"Video nicht gefunden: {path_str}")
            continue
        if video_path.suffix.lower() not in supported:
            logger.warning(f"Format nicht unterstützt: {video_path.suffix}")
            continue

        try:
            info = await asyncio.to_thread(_get_video_info, str(video_path))
        except Exception as e:
            logger.error(f"Video-Info fehlgeschlagen: {video_path.name}: {e}")
            continue

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
    return [VideoClipInfo(**c, is_analyzed=c["id"] in analysis_snap) for c in clips[start:end]]


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
        return Response(content=jpeg_bytes, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Thumbnail-Generierung fehlgeschlagen: {e}")


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

    try:
        result = await with_gpu_task(
            _run_video_analysis, clip["path"], request.clip_id, request,
            model_id="video_analysis_full",  # VRAM-Budget-Check via VRAMBudgetManager (RAFT + SigLIP)
        )
        state.set_video_analysis(request.clip_id, result)

        # P-2: Analyse-Ergebnisse in SQLite persistieren
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
        )

        await publish_log(
            f"Video-Analyse abgeschlossen: {clip['name']}",
            level="info",
            source="video.analyze",
            detail=f"clip_id={request.clip_id} scenes={int(result.get('scene_count', 0) or 0)} avg_motion={float(result.get('avg_motion', 0.0) or 0.0):.2f}",
        )
        return VideoAnalysisResult(**result)
    except Exception as e:
        logger.error(f"Video-Analyse fehlgeschlagen: {e}", exc_info=True)
        await publish_log(
            f"Video-Analyse fehlgeschlagen: {clip['name']}",
            level="error",
            source="video.analyze",
            detail=str(e),
        )
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
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,codec_name,duration",
        "-show_entries", "format=duration",
        "-of", "json", path,
    ]
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    res = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=30, startupinfo=startupinfo)
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

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-ss", "1", "-frames:v", "1",
            "-vf", "scale=320:-1",
            str(tmp_path),
        ]
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.run(cmd, capture_output=True, timeout=15, check=True, startupinfo=startupinfo)
        return tmp_path.read_bytes()
    finally:
        # R20/LOW: unlink(missing_ok=True) avoids FileNotFoundError if ffmpeg
        # failed before creating the file.
        tmp_path.unlink(missing_ok=True)


def _run_video_analysis(video_path: str, clip_id: int, request: VideoAnalyzeRequest) -> dict[str, Any]:
    """Führt Video-Analyse durch (blockierend, GPU)."""
    result: dict = {"clip_id": clip_id, "scene_count": 0, "avg_motion": 0.0}

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
            import numpy as np
            from pb_studio.video.raft import MotionAnalyzer

            # Frames gleichmäßig samplen — temporal-dichte (~2 Frames/s), min 2, max 30
            cap = cv2.VideoCapture(video_path)
            try:
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                duration_sec = total / max(fps, 1.0)
                n_frames = min(30, max(2, int(duration_sec * 2)))  # ~2 Samples/s
                step = max(1, total // n_frames)

                frames = []
                for i in range(0, total - step, step):
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
                    motion_result = motion_analyzer.analyze_video_segment(frames, stride=1)

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

                    result["motion"] = {
                        "clip_id": clip_id,
                        "avg_motion": float(motion_result.get("avg_motion", 0.0)),
                        "motion_curve": [float(v) for v in motion_result.get("frame_motions", [])],
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
                    # Repräsentatives Frame aus Mitte des Videos
                    cap = cv2.VideoCapture(video_path)
                    try:
                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        mid = max(0, total_frames // 2)
                        cap.set(cv2.CAP_PROP_POS_FRAMES, mid)
                        ret, frame = cap.read()
                    finally:
                        cap.release()

                    if ret:
                        import numpy as _np
                        from PIL import Image as _PILImage
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        pil_img = _PILImage.fromarray(frame_rgb)
                        embedding = wrapper.encode_image(pil_img)

                        if embedding is not None:
                            raw_norm = float(_np.linalg.norm(embedding))
                            if raw_norm < 1e-3:
                                logger.warning(
                                    f"SigLIP near-zero embedding (norm={raw_norm:.2e}) für clip {clip_id} "
                                    "— FAISS-Insert übersprungen"
                                )
                                result["has_embedding"] = False
                            else:
                                # FAISS VectorStore speichern (index "video_index")
                                vs = VectorStore(index_name="video_index")
                                vs.add_embedding(embedding.astype(_np.float32), {
                                    "clip_id": clip_id,
                                    "path": video_path,
                                    "scene_id": f"clip_{clip_id}_mid",
                                    "duration": result.get("duration_seconds", 0.0),
                                })
                                result["has_embedding"] = True
                                result["embedding_dim"] = len(embedding)
                                logger.info(f"SigLIP Embedding gespeichert für Clip {clip_id} (dim={len(embedding)})")
                        else:
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

    return result


def _classify_motion(avg_motion: float) -> str:
    """Klassifiziert Motion-Stärke in Kategorien."""
    if avg_motion < 2.0:
        return "static"
    if avg_motion < 8.0:
        return "low"
    if avg_motion < 20.0:
        return "medium"
    return "high"
