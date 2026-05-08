"""
Pacing Router – Cut-List Generierung und Timeline.

Endpoints:
  POST /pacing/generate  — Cut-Liste generieren
  GET  /pacing/timeline  — Aktuelle Timeline abrufen
  POST /pacing/preview   — Preview-Video generieren
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..app_state import AppState, get_app_state
from ..dependencies import publish_event, publish_log
from ..schemas.common import validate_timeline, StatusResponse
from ..schemas.pacing_schemas import (
    PacingConfigSchema, TriggerSettingsSchema, CutListResponse, CutListEntrySchema,
    TimelineResponse, TimelineEntrySchema, TimelineUpdateRequest,
    PreviewRequest, PreviewResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pacing", tags=["Pacing"])


@router.post(
    "/generate",
    response_model=CutListResponse,
    summary="Cut-Liste generieren",
    description=(
        "Generiert eine optimierte Cut-Liste via AdvancedPacingEngine + SmartDirector. "
        "Nutzt Audio-Analyse (Beats, BPM, Struktur-Segmente) und optionales Motion-Matching "
        "um Schnitte auf Musik-Events zu legen. "
        "Audio- und Video-Clips müssen zuvor via /audio/import und /video/import importiert worden sein."
    ),
)
async def generate_cut_list(
    config: PacingConfigSchema,
    state: AppState = Depends(get_app_state),
) -> CutListResponse:
    """Generiert eine Cut-Liste basierend auf Pacing-Konfiguration."""
    logger.info(
        f"Cut-Liste generieren: BPM={config.expected_bpm}, "
        f"Motion={config.use_motion_matching}, "
        f"Clips={len(config.video_clip_ids)}"
    )
    await publish_log(
        "Pacing-Generierung gestartet",
        level="info",
        source="pacing.generate",
        detail=f"audio_clip_id={config.audio_clip_id} video_clips={len(config.video_clip_ids)} bpm={config.expected_bpm}",
    )

    # Audio- und Video-Daten aus AppState extrahieren (thread-safe Snapshots)
    audio_clips_snapshot = state.get_audio_clips_snapshot()
    video_clips_snapshot = state.get_video_clips_snapshot()

    # BUG-027 Fix: Validierung VOR asyncio.to_thread() — sonst kein HTTP 4xx möglich
    if config.audio_clip_id not in audio_clips_snapshot:
        raise HTTPException(status_code=404, detail=f"Audio-Clip {config.audio_clip_id} nicht gefunden")
    if not config.video_clip_ids:
        raise HTTPException(status_code=400, detail="Keine Video-Clips ausgewählt")
    missing_video_ids = [vid for vid in config.video_clip_ids if vid not in video_clips_snapshot]
    if missing_video_ids:
        raise HTTPException(status_code=404, detail=f"Video-Clips nicht gefunden: {missing_video_ids}")

    # Gecachte Audio-Analyse-Daten extrahieren (Beats, BPM, Energie)
    cached_analysis = state.get_audio_analysis(config.audio_clip_id) or {}

    # Video-Analyse-Cache Snapshot für Motion Matching
    video_analysis_snapshot = state.get_video_analysis_snapshot() if config.use_motion_matching else {}

    try:
        import time as _time
        _t_pacing_start = _time.perf_counter()
        cuts = await asyncio.to_thread(
            _run_pacing_generation, config, audio_clips_snapshot, video_clips_snapshot,
            cached_analysis, video_analysis_snapshot,
        )
        _t_pacing_elapsed_ms = (_time.perf_counter() - _t_pacing_start) * 1000.0
        _t_brain_elapsed_ms = 0.0

        # Plan Phase 4: brain post-processor — annotates and persists cuts
        if getattr(config, "use_brain", False):
            try:
                from pb_studio.brain.brain_service import BrainService
                from pb_studio.brain.post_processor import annotate_cuts_with_brain

                svc = BrainService.get()
                # video analysis indexed by clip_id (str)
                vab: dict[str, dict] = {}
                for vid_id, va in video_analysis_snapshot.items():
                    vab[f"clip_{vid_id}"] = va

                # R-Brain-03: collect media-hashes fuer EmbeddingCache lookups
                audio_clip_meta = audio_clips_snapshot.get(config.audio_clip_id, {})
                audio_hash_value = (
                    audio_clip_meta.get("audio_hash")
                    or audio_clip_meta.get("media_hash")
                )
                video_hashes_by_clip: dict[str, str] = {}
                for vid_id, vmeta in video_clips_snapshot.items():
                    h = vmeta.get("video_hash") or vmeta.get("media_hash")
                    if h:
                        video_hashes_by_clip[f"clip_{vid_id}"] = h

                _t_brain_start = _time.perf_counter()
                cuts = await asyncio.to_thread(
                    annotate_cuts_with_brain,
                    cuts,
                    weight_store=svc.weights,
                    audio_analysis=cached_analysis,
                    video_analysis_by_clip=vab,
                    audio_clip_id=config.audio_clip_id,
                    audio_path=audio_clip_meta.get("path"),
                    persist_to_state_conn=svc.state_conn,
                    min_confidence=float(getattr(config, "brain_min_confidence", 0.0)),
                    embedding_cache=svc.brain.cache,
                    audio_hash=audio_hash_value,
                    video_hashes_by_clip=video_hashes_by_clip,
                )
                _t_brain_elapsed_ms = (_time.perf_counter() - _t_brain_start) * 1000.0
                logger.info(
                    "Pacing performance: pacing=%.1fms brain=%.1fms cuts=%d",
                    _t_pacing_elapsed_ms, _t_brain_elapsed_ms, len(cuts),
                )
                if _t_brain_elapsed_ms > 500.0:
                    logger.warning(
                        "Brain overhead %.1fms > 500ms target", _t_brain_elapsed_ms
                    )
            except Exception as brain_e:
                logger.warning(f"Brain post-processor failed: {brain_e}", exc_info=True)

        # Timeline validieren
        audio_dur = audio_clips_snapshot.get(config.audio_clip_id, {}).get("duration_seconds")
        timeline_warnings, timeline_errors = validate_timeline(cuts, audio_duration=audio_dur)
        if timeline_errors:
            raise HTTPException(status_code=400, detail=f"Ungültige Timeline: {'; '.join(timeline_errors)}")
        for w in timeline_warnings:
            logger.warning(f"Timeline-Validierung: {w}")

        # Timeline im State speichern (thread-safe)
        state.current_audio_path = (
            audio_clips_snapshot[config.audio_clip_id]["path"]
            if config.audio_clip_id in audio_clips_snapshot
            else None
        )
        state.set_timeline(cuts)

        total_dur = cuts[-1]["end_time"] if cuts else 0.0
        avg_dur = sum(c["end_time"] - c["start_time"] for c in cuts) / len(cuts) if cuts else 0.0

        await publish_event("analysis_progress", {
            "step": "pacing",
            "percent": 100.0,
            "message": f"{len(cuts)} Cuts generiert",
        })
        await publish_log(
            "Pacing-Generierung abgeschlossen",
            level="info",
            source="pacing.generate",
            detail=f"cuts={len(cuts)} total_duration={total_dur:.2f}s",
        )

        return CutListResponse(
            cuts=[CutListEntrySchema(**c) for c in cuts],
            total_duration=total_dur,
            cut_count=len(cuts),
            average_cut_duration=round(avg_dur, 2),
        )
    except Exception as e:
        logger.error(f"Pacing-Generierung fehlgeschlagen: {e}", exc_info=True)
        await publish_log(
            "Pacing-Generierung fehlgeschlagen",
            level="error",
            source="pacing.generate",
            detail=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Generierung fehlgeschlagen: {e}")


@router.get(
    "/timeline",
    response_model=TimelineResponse,
    summary="Aktuelle Timeline abrufen",
    description=(
        "Gibt die zuletzt generierte Timeline zurück. "
        "Enthält alle Clip-Zuweisungen mit Start/End-Zeiten, Trigger-Typ und -Stärke. "
        "Leere Timeline wenn noch keine Cut-Liste generiert wurde."
    ),
)
async def get_timeline(state: AppState = Depends(get_app_state)) -> TimelineResponse:
    """Gibt die aktuelle Timeline zurück."""
    entries = []
    for cut in state.get_timeline_snapshot():
        meta = cut.get("metadata", {})
        entries.append(TimelineEntrySchema(
            clip_id=cut.get("clip_id", ""),
            clip_name=meta.get("clip_name", "Unknown"),
            file_path=meta.get("file_path", ""),
            start_time=cut.get("start_time", 0.0),
            end_time=cut.get("end_time", 0.0),
            clip_start=meta.get("clip_start", 0.0),
            trigger_type=meta.get("trigger_type", ""),
            trigger_strength=meta.get("trigger_strength", 0.0),
            segment_type=meta.get("segment_type"),
            brain_confidence=float(meta.get("brain_final_score", 0.0) or 0.0),
            cut_id=meta.get("cut_id"),
        ))

    total = entries[-1].end_time if entries else 0.0
    return TimelineResponse(
        entries=entries,
        total_duration=total,
        audio_path=state.current_audio_path,
    )


@router.post(
    "/timeline",
    response_model=StatusResponse,
    summary="Timeline manuell aktualisieren",
    description="Ersetzt die aktuelle Timeline durch eine manuell bearbeitete Version.",
)
async def update_timeline(
    request: TimelineUpdateRequest,
    state: AppState = Depends(get_app_state)
) -> StatusResponse:
    """Aktualisiert die Timeline im State."""
    internal_cuts = []
    for entry in request.entries:
        internal_cuts.append({
            "clip_id": entry.clip_id,
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "metadata": {
                "clip_name": entry.clip_name,
                "file_path": entry.file_path,
                "clip_start": entry.clip_start,
                "trigger_type": entry.trigger_type,
                "trigger_strength": entry.trigger_strength,
                "segment_type": entry.segment_type,
            }
        })

    audio_dur = 0.0
    if state.current_audio_path:
        from pb_studio.rendering.render_service import RenderService
        audio_dur = RenderService()._get_audio_duration(state.current_audio_path) or 0.0

    warnings, errors = validate_timeline(internal_cuts, audio_duration=audio_dur)
    if errors:
        raise HTTPException(status_code=400, detail=f"Ungültige Timeline: {'; '.join(errors)}")

    state.set_timeline(internal_cuts)
    logger.info(f"Timeline manuell aktualisiert: {len(internal_cuts)} Schnitte")
    
    return StatusResponse(
        success=True,
        message=f"Timeline mit {len(internal_cuts)} Schnitten aktualisiert"
    )


@router.post(
    "/preview",
    response_model=PreviewResponse,
    summary="Preview-Video generieren",
    description=(
        "Rendert einen Ausschnitt der aktuellen Timeline als niedrig-aufgelöstes Preview-Video "
        "(640×360). Benötigt eine vorhandene Timeline via POST /pacing/generate."
    ),
)
async def generate_preview(
    request: PreviewRequest,
    state: AppState = Depends(get_app_state),
) -> PreviewResponse:
    """Generiert ein Preview-Video für einen Timeline-Abschnitt."""
    if not state.current_timeline:
        raise HTTPException(status_code=400, detail="Keine Timeline vorhanden")

    timeline_snapshot = list(state.current_timeline)

    try:
        preview_path = await asyncio.to_thread(
            _render_preview, timeline_snapshot, request.start_sec, request.duration
        )
        return PreviewResponse(
            preview_path=preview_path,
            duration=request.duration,
            resolution="640x360",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview fehlgeschlagen: {e}")


# --- Private Hilfsfunktionen ---

def _run_pacing_generation(
    config: PacingConfigSchema,
    audio_clips: dict[int, dict[str, Any]],
    video_clips: dict[int, dict[str, Any]],
    cached_analysis: dict[str, Any] | None = None,
    video_analysis_cache: dict[int, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Generiert Cut-Liste via PacingService (blockierend)."""
    from pb_studio.services.pacing_service import PacingService

    service = PacingService()

    audio_path = ""
    audio_dur = 0.0
    if config.audio_clip_id in audio_clips:
        ac = audio_clips[config.audio_clip_id]
        audio_path = ac["path"]
        audio_dur = ac.get("duration_seconds", 0.0)

    if not audio_path:
        raise ValueError(f"Audio-Clip {config.audio_clip_id} nicht gefunden")

    clips = []
    for vid in config.video_clip_ids:
        if vid in video_clips:
            vc = video_clips[vid]
            clip_data = {
                "id": vc["id"],
                "name": vc["name"],
                "file_path": vc["path"],
                "duration": vc["duration_seconds"],
            }
            if video_analysis_cache and vid in video_analysis_cache:
                va = video_analysis_cache[vid]
                motion = va.get("motion", {})
                clip_data["motion_score"] = va.get("avg_motion", 0.0)
                clip_data["avg_motion"] = motion.get("avg_motion", 0.0) if motion else 0.0
                clip_data["peak_motion"] = motion.get("peak_motion", 0.0) if motion else 0.0
                clip_data["peak_frames"] = motion.get("peak_frames", []) if motion else []
                clip_data["scene_changes"] = va.get("scenes", [])
            clips.append(clip_data)

    pacing_config = {
        "trigger_settings": (config.trigger_settings or TriggerSettingsSchema()).model_dump(),
        "expected_bpm": config.expected_bpm,
        "use_motion_matching": config.use_motion_matching,
        "use_semantic_matching": config.use_semantic_matching,
        "use_structure_awareness": config.use_structure_awareness,
        "min_cut_interval": config.min_cut_interval,
        # Plan Phase 4 deep-hook: forward brain flags to PacingService
        "use_brain": getattr(config, "use_brain", False),
        "brain_min_confidence": getattr(config, "brain_min_confidence", 0.0),
    }

    cut_list = service.generate_cut_list(
        audio_path=audio_path,
        clips=clips,
        pacing_config=pacing_config,
        total_duration=audio_dur,
        duration_limit=config.duration_limit,
        cached_analysis=cached_analysis,
    )

    return [
        {
            "clip_id": c.clip_id,
            "start_time": c.start_time,
            "end_time": c.end_time,
            "metadata": c.metadata or {},
        }
        for c in cut_list
    ]


def _render_preview(timeline: list[dict[str, Any]], start_sec: float, duration: float) -> str:
    """Rendert ein Preview-Video (blockierend)."""
    try:
        from pb_studio.rendering.preview_renderer import PreviewGenerator, TimelineEntry
        entries = []
        for cut in timeline:
            meta = cut.get("metadata", {})
            fp = meta.get("file_path", "") or cut.get("file_path", "")
            clip_start = meta.get("clip_start", 0.0)
            cut_duration = cut.get("end_time", 0.0) - cut.get("start_time", 0.0)
            entries.append(TimelineEntry(
                video_path=fp,
                start_time=clip_start,
                end_time=clip_start + cut_duration,
                timeline_start=cut.get("start_time", 0.0),
                timeline_end=cut.get("end_time", 0.0),
            ))
        generator = PreviewGenerator()
        result = generator.generate_preview(entries, start_sec, duration)
        return str(result) if result else ""
    except ImportError:
        raise RuntimeError("PreviewGenerator nicht verfügbar")
