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
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from ..app_state import (
    AppState,
    ProjectContextChangedError,
    ProjectContextUnavailableError,
    ProjectOperationContext,
    get_app_state,
    persistence_error,
)
from ..config import config
from ..dependencies import with_gpu_task, publish_event, publish_log
from ..media_path_policy import MediaPathPolicyError, canonical_local_media_file
from ..schemas.video_schemas import (
    VideoImportRequest, VideoClipInfo,
    VideoAnalyzeRequest, VideoAnalysisResult,
    SceneInfo, MotionData,
    ThumbstripResponse,
    ClipwaveResponse,
)
from ..schemas.common import BatchDeleteRequest, DeleteResponse
from pb_studio.storage.recovery_barrier import recovery_write_operation
from pb_studio.core.stage_receipts import (
    StageReceipt as CoreStageReceipt,
    build_config_fingerprint,
    build_input_fingerprint,
    canonical_sha256,
    create_stage_receipt,
    derive_analysis_status,
    project_legacy_stage_receipts,
    receipt_to_dict,
    transition_stage_receipt,
    utc_now_rfc3339,
    validate_receipt_map,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/video", tags=["Video"])

MAX_MOTION_SAMPLES = 120
MAX_EMBEDDING_SAMPLES = 24
MAX_UNREADABLE_SAMPLE_FRAMES = 1
FRAME_SAMPLE_REPLACEMENT_RADIUS = 2
CAPTION_STAGE_TIMEOUT_SECONDS = 270.0
CAPTION_HEARTBEAT_INTERVAL_SECONDS = 5.0
CAPTION_PROGRESS_START_PERCENT = 60.0
CAPTION_PRIMARY_PROGRESS_END_PERCENT = 75.0
CAPTION_PROGRESS_END_PERCENT = 85.0
CAPTION_PROGRESS_TERMINAL_MARGIN = 0.1
SIGLIP_EMBEDDING_DIM = 1152
VIDEO_ANALYSIS_STATES = {
    "unavailable", "running", "completed", "partial", "failed"
}
VIDEO_ANALYSIS_STAGE_FIELDS = {
    "scenes": ("scene_count", "scenes"),
    "motion": ("avg_motion", "motion"),
    "embedding": ("embedding_dim", "embedding_samples", "has_embedding"),
    "colors": (
        "dominant_colors",
        "mood_tags",
        "avg_brightness",
        "avg_saturation",
        "avg_color_temp",
    ),
    "captions": ("tags", "tag_source"),
    "audio_key": ("audio_key",),
}
VIDEO_STAGE_REQUEST_FIELDS = {
    "scenes": "detect_scenes",
    "motion": "analyze_motion",
    "embedding": "generate_embeddings",
    "colors": "analyze_colors",
    "captions": "generate_captions",
    "audio_key": "analyze_audio_key",
}
VIDEO_STAGE_CONFIG_IDENTITIES = {
    "scenes": {"pipeline": "pyscenedetect"},
    "motion": {"pipeline": "raft_onnx", "provider": "DmlExecutionProvider"},
    "embedding": {
        "pipeline": "siglip_so400m_onnx",
        "provider": "DmlExecutionProvider",
        "dimension": SIGLIP_EMBEDDING_DIM,
        "store": "faiss_cpu",
    },
    "colors": {"pipeline": "dominant_color_kmeans", "clusters": 5},
    "captions": {
        "pipeline": "lmstudio_vision_then_moondream_onnx",
        "max_attempts_per_frame": 3,
    },
    "audio_key": {"pipeline": "video_audio_key_detector"},
}


def _empty_video_analysis_result(clip_id: int) -> dict[str, Any]:
    return {
        "clip_id": clip_id,
        "scene_count": 0,
        "scenes": [],
        "avg_motion": 0.0,
        "motion": None,
        "embedding_dim": 0,
        "embedding_samples": 0,
        "has_embedding": False,
        "dominant_colors": [],
        "tags": [],
        "tag_source": "none",
        "audio_key": None,
        "mood_tags": [],
        "avg_brightness": 0.5,
        "avg_saturation": 0.5,
        "avg_color_temp": 0.0,
        "status": "failed",
        "stage_status": {},
        "stage_errors": {},
        "stage_receipts": {},
        "stage_artifacts": {},
    }


def _capture_video_project_identity(
    state: AppState,
    context: ProjectOperationContext,
) -> tuple[str, int, int]:
    """Capture the immutable project identity before any asynchronous work."""

    with state.project_commit(context):
        project = state.current_project
        if not isinstance(project, dict):
            raise ProjectContextUnavailableError("Kein Projekt geoeffnet")
        try:
            project_uuid = str(UUID(str(project.get("project_uuid"))))
            project_id = int(project.get("db_project_id"))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ProjectContextUnavailableError(
                "Aktiver Projektkontext besitzt keine gueltige project_uuid"
            ) from exc
        if project_id != int(context.project_id):
            raise ProjectContextChangedError(
                "Projekt-ID aenderte sich waehrend der Video-Analyse"
            )
        return project_uuid, project_id, int(context.epoch)


def _video_media_sha256(clip: dict[str, Any]) -> str | None:
    stored = str(clip.get("video_hash") or "").strip().lower()
    if len(stored) == 64 and all(char in "0123456789abcdef" for char in stored):
        return stored
    path = Path(str(clip.get("path") or ""))
    if not path.is_file():
        return None
    from pb_studio.core.media_hash import media_hash

    return media_hash(path)


def _video_stage_artifact(
    stage: str,
    result: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    """Build one canonical composite artifact for a video analysis stage."""

    fields = VIDEO_ANALYSIS_STAGE_FIELDS.get(stage)
    if fields is None or any(field not in result for field in fields):
        return None
    artifact = {field: deepcopy(result[field]) for field in fields}
    if stage == "embedding":
        pending = result.get("_pending_embedding") or {}
        persisted_locator = (
            (result.get("stage_artifacts") or {}).get("embedding") or {}
        )
        artifact.update({
            "store": "faiss_cpu",
            "media_id": result.get(
                "_new_embedding_media_id",
                pending.get("media_id", persisted_locator.get("media_id")),
            ),
            "faiss_id": result.get(
                "_new_embedding_faiss_id",
                persisted_locator.get("faiss_id"),
            ),
            "media_sha256": result.get("media_sha256"),
        })
    return f"ai_data_json.stage_artifacts.{stage}", artifact


def _video_receipts_from_cache(
    cached: dict[str, Any],
) -> dict[str, CoreStageReceipt]:
    raw = cached.get("_stage_receipts")
    if not isinstance(raw, dict):
        raw = cached.get("stage_receipts")
    if isinstance(raw, dict) and raw:
        try:
            return validate_receipt_map(raw)
        except (TypeError, ValueError):
            logger.warning("Ungueltige Video-StageReceipts werden als Legacy gelesen")
    return project_legacy_stage_receipts(
        stage_status=cached.get("stage_status") or {},
        stage_errors=cached.get("stage_errors") or {},
    )


def _video_cached_receipt_artifact_is_valid(
    stage: str,
    receipt: CoreStageReceipt,
    cached: dict[str, Any],
    *,
    expected_input_fingerprint: str | None,
    expected_config_fingerprint: str,
) -> bool:
    if receipt.receipt_version == 0:
        return _video_stage_data_is_valid(stage, cached)
    reconstructed = _video_stage_artifact(stage, cached)
    stage_artifacts = cached.get("stage_artifacts")
    referenced_payload = (
        stage_artifacts.get(stage)
        if isinstance(stage_artifacts, dict)
        else None
    )
    if (
        reconstructed is None
        or not isinstance(referenced_payload, dict)
        or not _video_stage_data_is_valid(stage, cached)
    ):
        return False
    expected_ref, canonical_payload = reconstructed
    referenced_sha256 = canonical_sha256(referenced_payload)
    return bool(
        receipt.status == "completed"
        and receipt.artifact_valid is True
        and receipt.artifact_ref == expected_ref
        and receipt.artifact_sha256 == referenced_sha256
        and referenced_sha256 == canonical_sha256(canonical_payload)
        and receipt.input_fingerprint == expected_input_fingerprint
        and receipt.config_fingerprint == expected_config_fingerprint
    )


def _video_stage_fingerprints(
    *,
    request: VideoAnalyzeRequest,
    project_uuid: str,
    project_id: int,
    project_epoch: int,
    media_sha256: str | None,
) -> dict[str, tuple[str | None, str]]:
    request_flags = {
        request_field: bool(getattr(request, request_field))
        for request_field in VIDEO_STAGE_REQUEST_FIELDS.values()
    }
    request_flags["force"] = bool(request.force)
    fingerprints: dict[str, tuple[str | None, str]] = {}
    for stage in VIDEO_STAGE_REQUEST_FIELDS:
        input_fingerprint = None
        if media_sha256 is not None:
            input_fingerprint = build_input_fingerprint(
                project_uuid=project_uuid,
                catalog_project_id=project_id,
                project_epoch=project_epoch,
                clip_id=int(request.clip_id),
                media_sha256=media_sha256,
                stage_input_identity={"stage_id": stage},
            )
        fingerprints[stage] = (
            input_fingerprint,
            build_config_fingerprint(
                stage_request_flags=request_flags,
                effective_config_identity=VIDEO_STAGE_CONFIG_IDENTITIES[stage],
            ),
        )
    return fingerprints


def _build_video_request_receipts(
    *,
    request: VideoAnalyzeRequest,
    run_stage: dict[str, bool],
    cached: dict[str, Any],
    fingerprints: dict[str, tuple[str | None, str]],
    correlation_id: str,
) -> dict[str, CoreStageReceipt]:
    cached_receipts = _video_receipts_from_cache(cached)
    receipts: dict[str, CoreStageReceipt] = {}
    for stage, request_field in VIDEO_STAGE_REQUEST_FIELDS.items():
        requested = bool(getattr(request, request_field))
        input_fingerprint, config_fingerprint = fingerprints[stage]
        receipt = create_stage_receipt(
            stage,
            requested=requested,
            input_fingerprint=input_fingerprint,
            config_fingerprint=config_fingerprint,
            correlation_id=correlation_id,
        )
        if requested:
            receipt = transition_stage_receipt(receipt, "running")
            if not run_stage.get(stage, False):
                artifact = _video_stage_artifact(stage, cached)
                if artifact is None or not _video_stage_data_is_valid(stage, cached):
                    raise ValueError(f"Reusable Video-Stage {stage} has no valid artifact")
                artifact_ref, artifact_payload = artifact
                receipt = transition_stage_receipt(
                    receipt,
                    "completed",
                    artifact_ref=artifact_ref,
                    artifact=artifact_payload,
                )
        receipts[stage] = receipt
    return receipts


def _video_receipt_truth(
    receipts: dict[str, CoreStageReceipt],
    *,
    requested_stage_ids: frozenset[str],
) -> tuple[str, dict[str, str], dict[str, str]]:
    current = {
        stage: receipt
        for stage, receipt in receipts.items()
        if stage in requested_stage_ids
    }
    return (
        derive_analysis_status(current),
        {stage: receipt.status for stage, receipt in receipts.items()},
        {
            stage: str(receipt.error_message)
            for stage, receipt in receipts.items()
            if receipt.error_message
        },
    )


def _serialize_video_receipts(
    receipts: dict[str, CoreStageReceipt],
) -> dict[str, dict[str, Any]]:
    return {stage: receipt_to_dict(receipt) for stage, receipt in receipts.items()}


def _terminalize_video_stage_receipt(
    receipts: dict[str, CoreStageReceipt],
    stage: str,
    snapshot: dict[str, Any],
    status: str,
    error_message: str | None,
    *,
    error_code: str | None = None,
) -> None:
    receipt = receipts[stage]
    if receipt.status not in {"pending", "running"}:
        return
    terminal_status = status if status in {
        "completed", "partial", "failed", "interrupted", "unavailable"
    } else "failed"
    artifact = _video_stage_artifact(stage, snapshot)
    if terminal_status in {"completed", "partial"} and (
        artifact is None or not _video_stage_data_is_valid(stage, snapshot)
    ):
        terminal_status = "failed"
        error_code = "stage_artifact_invalid"
        error_message = error_message or f"Video stage {stage} artifact is invalid"
    kwargs: dict[str, Any] = {}
    if terminal_status in {"completed", "partial"} and artifact is not None:
        kwargs["artifact_ref"], artifact_payload = artifact
        kwargs["artifact"] = artifact_payload
    if terminal_status != "completed":
        kwargs["error_code"] = error_code or (
            "capability_unavailable"
            if terminal_status == "unavailable"
            else f"stage_{terminal_status}"
        )
        kwargs["error_message"] = error_message or f"Video stage {stage} {terminal_status}"
    if stage == "captions":
        kwargs["provider"] = snapshot.get("caption_provider")
        kwargs["model_id"] = snapshot.get("caption_model_id")
        kwargs["attempts"] = snapshot.get("caption_attempts") or ()
    receipts[stage] = transition_stage_receipt(
        receipt,
        terminal_status,
        **kwargs,
    )


def _apply_video_receipt_truth(
    result: dict[str, Any],
    receipts: dict[str, CoreStageReceipt],
    requested_stage_ids: frozenset[str],
) -> None:
    status, stage_status, stage_errors = _video_receipt_truth(
        receipts,
        requested_stage_ids=requested_stage_ids,
    )
    result["status"] = status
    result["stage_status"] = stage_status
    result["stage_errors"] = stage_errors
    result["stage_receipts"] = _serialize_video_receipts(receipts)
    artifacts = dict(result.get("stage_artifacts") or {})
    for stage, receipt in receipts.items():
        if receipt.status not in {"completed", "partial"}:
            continue
        artifact = _video_stage_artifact(stage, result)
        if artifact is not None and receipt.artifact_valid is True:
            _artifact_ref, artifact_payload = artifact
            artifacts[stage] = artifact_payload
    result["stage_artifacts"] = artifacts


def _video_stage_data_is_valid(stage: str, result: dict[str, Any]) -> bool:
    """Validate completed-stage payloads before treating them as reusable."""
    if stage == "scenes":
        scenes = result.get("scenes")
        scene_count = result.get("scene_count")
        return (
            isinstance(scenes, list)
            and isinstance(scene_count, int)
            and scene_count > 0
            and scene_count == len(scenes)
        )
    if stage == "motion":
        motion = result.get("motion")
        return (
            isinstance(motion, dict)
            and isinstance(motion.get("motion_curve"), list)
            and bool(motion["motion_curve"])
        )
    if stage == "embedding":
        return (
            result.get("has_embedding") is True
            and result.get("embedding_dim") == SIGLIP_EMBEDDING_DIM
            and int(result.get("embedding_samples", 0) or 0) > 0
        )
    if stage == "colors":
        return bool(result.get("dominant_colors"))
    if stage == "captions":
        return bool(result.get("tags")) and result.get("tag_source") not in {
            None,
            "none",
            "skipped",
            "error",
        }
    if stage == "audio_key":
        return isinstance(result.get("audio_key"), str) and bool(result["audio_key"])
    return False


def _video_stage_should_run(
    stage: str,
    requested: bool,
    force: bool,
    result: dict[str, Any],
) -> bool:
    """Run only requested stages lacking a reusable completed result."""
    if not requested:
        return False
    if force:
        return True
    status = (result.get("stage_status") or {}).get(stage)
    if status == "completed":
        return not _video_stage_data_is_valid(stage, result)
    # "unavailable" is a truthful terminal capability result. Explicit force
    # remains available when the environment changes later.
    return status != "unavailable"


def _video_analysis_resume_base(
    state: AppState,
    clip: dict[str, Any],
    project_id: int,
) -> dict[str, Any]:
    """Return a detached merge base from cache or durable partial truth."""
    existing = state.get_video_analysis(int(clip["id"]))
    if not existing:
        existing = _load_persisted_video_analysis(state, clip, project_id)
    existing = existing if isinstance(existing, dict) else {}

    result = _empty_video_analysis_result(int(clip["id"]))
    reusable_fields = {
        field
        for fields in VIDEO_ANALYSIS_STAGE_FIELDS.values()
        for field in fields
    }
    for field in reusable_fields:
        if field in existing:
            result[field] = deepcopy(existing[field])
    result["stage_status"] = dict(existing.get("stage_status") or {})
    result["stage_errors"] = dict(existing.get("stage_errors") or {})
    result["stage_receipts"] = dict(existing.get("stage_receipts") or {})
    result["stage_artifacts"] = dict(existing.get("stage_artifacts") or {})
    result["status"] = _video_analysis_status(
        existing,
        legacy_is_analyzed=bool(clip.get("is_analyzed", False)),
    )
    if result["status"] == "unavailable":
        result["status"] = "failed"
    return result


def _merge_video_stage_outcome(
    result: dict[str, Any],
    stage_result: dict[str, Any],
    stage: str,
) -> None:
    """Merge one attempted stage without clearing unrelated or prior data."""
    stage_status = stage_result.get("stage_status") or {}
    stage_errors = stage_result.get("stage_errors") or {}
    status = str(stage_status.get(stage) or "failed")
    result["stage_status"][stage] = status

    error = stage_errors.get(stage)
    if error:
        result["stage_errors"][stage] = str(error)
    elif status == "completed":
        result["stage_errors"].pop(stage, None)

    merge_partial_caption = (
        stage == "captions"
        and status == "partial"
        and _video_stage_data_is_valid("captions", stage_result)
    )
    if status != "completed" and not merge_partial_caption:
        return
    for field in VIDEO_ANALYSIS_STAGE_FIELDS[stage]:
        if field in stage_result:
            result[field] = deepcopy(stage_result[field])


def _derive_video_analysis_status(stage_status: dict[str, str]) -> str:
    failed = any(
        status in {"partial", "failed", "interrupted"}
        for status in stage_status.values()
    )
    if not failed:
        return "completed"
    return "partial" if "completed" in stage_status.values() else "failed"


def _video_analysis_status(data: Optional[dict], legacy_is_analyzed: bool = False) -> str:
    """Resolve persisted/cache analysis truth with a legacy-compatible fallback."""
    payload = data or {}
    status = (
        payload.get("analysis_status")
        or payload.get("_analysis_status")
        or payload.get("status")
    )
    if status in VIDEO_ANALYSIS_STATES:
        return str(status)
    return "completed" if legacy_is_analyzed else "unavailable"


def _load_persisted_video_analysis(
    state: AppState,
    clip: dict,
    project_id: int,
) -> dict[str, Any]:
    """Load analysis truth missing from cache, including partial/failed attempts."""
    try:
        from pb_studio.data.repositories.media_repository import MediaRepository

        row = MediaRepository().find_by_project_and_path(
            project_id=project_id,
            file_path=clip["path"],
        )
        if row is None:
            return {}
        payload = json.loads(row.get("ai_data_json") or "{}")
        return payload if isinstance(payload, dict) else {}
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        logger.warning(
            "Persistierter Videoanalyse-Status fuer Clip %s unlesbar: %s",
            clip.get("id"),
            exc,
        )
        return {}


def _persist_video_analysis_outcome(
    state: AppState,
    context: ProjectOperationContext,
    clip: dict,
    result: dict[str, Any],
) -> None:
    """Persist complete analysis outcome DB-first, then publish it to memory."""
    from pb_studio.data.repositories.media_repository import MediaRepository

    status = str(result.get("status") or "failed")
    if status not in VIDEO_ANALYSIS_STATES:
        raise ValueError(f"Ungueltiger Videoanalyse-Status: {status}")

    stage_status = dict(result.get("stage_status") or {})
    stage_errors = dict(result.get("stage_errors") or {})
    stage_receipts = dict(result.get("stage_receipts") or {})
    stage_artifacts = dict(result.get("stage_artifacts") or {})
    is_analyzed = status == "completed"
    repo = MediaRepository()
    row = repo.find_by_project_and_path(
        project_id=context.project_id,
        file_path=clip["path"],
    )
    if row is None:
        raise persistence_error(
            "video_analysis",
            f"Kein DB-Eintrag für Video-Clip {result.get('clip_id')}",
        )

    try:
        existing = json.loads(row.get("ai_data_json") or "{}")
        if not isinstance(existing, dict):
            existing = {}
    except (json.JSONDecodeError, TypeError):
        existing = {}

    persisted = dict(existing)
    for field in (
        "scene_count",
        "scenes",
        "avg_motion",
        "motion",
        "has_embedding",
        "embedding_dim",
        "embedding_samples",
        "dominant_colors",
        "tags",
        "tag_source",
        "audio_key",
        "avg_brightness",
        "avg_saturation",
        "avg_color_temp",
        "mood_tags",
        "media_sha256",
    ):
        if field in result:
            persisted[field] = result[field]
    persisted.update({
        "analysis_status": status,
        "stage_status": stage_status,
        "stage_errors": stage_errors,
        "stage_receipts": stage_receipts,
        "stage_artifacts": stage_artifacts,
        "is_analyzed": is_analyzed,
    })

    # Durable truth first. A failed write must not create a successful RAM state.
    try:
        repo.update_status(row["id"], status, ai_data=persisted)
    except Exception as exc:
        raise persistence_error(
            "video_analysis",
            f"Video-Analyse für Clip {result.get('clip_id')} nicht gespeichert",
            exc,
        ) from exc

    cache_result = {
        key: value
        for key, value in result.items()
        if not key.startswith("_")
    }
    cache_result.update({
        "analysis_status": status,
        "stage_status": stage_status,
        "stage_errors": stage_errors,
        "stage_receipts": stage_receipts,
        "stage_artifacts": stage_artifacts,
        "is_analyzed": is_analyzed,
    })
    state.set_video_analysis(int(result["clip_id"]), cache_result)
    state.update_video_clip(
        int(result["clip_id"]),
        is_analyzed=is_analyzed,
        analysis_status=status,
        stage_status=stage_status,
        stage_errors=stage_errors,
        stage_receipts=stage_receipts,
    )


def _compensate_new_video_embedding(result: dict[str, Any]) -> bool:
    """Discard pending/published vectors when canonical analysis commit fails."""
    discarded = result.pop("_pending_embedding", None) is not None
    media_id = result.pop("_new_embedding_media_id", None)
    faiss_id = result.pop("_new_embedding_faiss_id", None)
    if media_id is None or faiss_id is None:
        return discarded

    from pb_studio.data.vector_operation_outbox import VectorOperationOutbox

    operation_id = VectorOperationOutbox().remove_media_vector(
        int(media_id),
        int(faiss_id),
    )
    logger.warning(
        "Neues SigLIP-Embedding für media_id=%s nach Analysefehler kompensiert: %s",
        media_id,
        operation_id or "no-vector",
    )
    result["has_embedding"] = False
    result["embedding_dim"] = 0
    result["embedding_samples"] = 0
    return True


def _restore_video_embedding_after_compensation(
    result: dict[str, Any],
    resume_base: dict[str, Any],
) -> None:
    """Restore prior durable embedding truth after interrupted replacement."""
    if (
        resume_base.get("stage_status", {}).get("embedding") == "completed"
        and _video_stage_data_is_valid("embedding", resume_base)
    ):
        for field in VIDEO_ANALYSIS_STAGE_FIELDS["embedding"]:
            result[field] = deepcopy(resume_base[field])
        result["stage_status"]["embedding"] = "completed"
        old_error = resume_base.get("stage_errors", {}).get("embedding")
        if old_error:
            result["stage_errors"]["embedding"] = old_error
        else:
            result["stage_errors"].pop("embedding", None)
        return

    result["has_embedding"] = False
    result["embedding_dim"] = 0
    result["embedding_samples"] = 0
    result["stage_status"]["embedding"] = "interrupted"
    result["stage_errors"]["embedding"] = "Embedding-Analyse unterbrochen"


def _commit_pending_video_embedding(result: dict[str, Any]) -> None:
    """Publish a computed vector synchronously inside the canonical commit lock."""
    pending = result.pop("_pending_embedding", None)
    if pending is None:
        return

    from pb_studio.data.vector_store import VectorStore

    vector_store = VectorStore(index_name="video_index")
    faiss_id = vector_store.add_embedding_with_media_link(
        pending["vector"],
        meta_info=pending["meta_info"],
        media_id=int(pending["media_id"]),
        segment_start=0.0,
        segment_end=float(pending["segment_end"]),
        description=pending["description"],
    )
    result["_new_embedding_media_id"] = int(pending["media_id"])
    result["_new_embedding_faiss_id"] = int(faiss_id)

    _store_video_embedding_in_brain_cache(pending)


def _store_video_embedding_in_brain_cache(pending: dict[str, Any]) -> None:
    """
    Zweitschreibung des SigLIP-Vektors in den Brain-EmbeddingCache.

    Audit 2026-08-05 (C-3): ``EmbeddingCache.store()`` hatte im gesamten
    Produktivcode keinen einzigen Aufrufer — nur Tests und ein Verify-Skript.
    Die Live-DB unter ``%APPDATA%/PB_Studio/brain/embedding_cache.db`` hatte
    entsprechend 0 Zeilen, seit sie am 2026-05-31 angelegt wurde.

    Die Folge war kein Absturz, sondern eine stille Degradation: der
    Brain-Post-Processor sucht ueber ``media_hash``, der Vektor lag aber
    ausschliesslich in FAISS und war dort ueber ``media_id`` gekeyt. Der Lookup
    konnte strukturell nie treffen. Dadurch meldete
    ``feature_adapter._semantic_availability`` dauerhaft
    ``audio_and_video_embeddings_missing``, die Achse ``semantic_match_weight``
    fiel aus jedem ``bridge_values``-Dict heraus (0 von 2576 Cuts), und der
    Cross-Modal-Projektor bekam nie Trainingspaare.

    Der Dual-Write ist hier korrekt und keine Redundanz: FAISS ist
    projektgebunden ueber ``media_id``, der Brain-Cache bewusst projektuebergreifend
    ueber den Inhalts-Hash. Fehler duerfen die Analyse nicht abbrechen — der
    FAISS-Write ist zu diesem Zeitpunkt bereits durch.
    """
    meta_info = pending.get("meta_info") or {}
    video_hash = meta_info.get("video_hash")
    if not video_hash:
        logger.debug(
            "Brain-Cache-Write uebersprungen: kein video_hash in meta_info"
        )
        return

    try:
        from pb_studio.video import video_embedder
        from pb_studio.brain.brain_service import BrainService

        cache = getattr(BrainService.get().brain, "cache", None)
        if cache is None:
            logger.debug("Brain-Cache nicht verfuegbar — Write uebersprungen")
            return

        cache.store(
            media_hash=str(video_hash),
            media_type="video",
            embedding=pending["vector"],
            model_name=video_embedder.CURRENT_MODEL_NAME,
            model_version=video_embedder.CURRENT_MODEL_VERSION,
        )
    except Exception as exc:  # noqa: BLE001 - darf die Analyse nie abbrechen
        logger.warning(
            "Brain-Cache-Write fehlgeschlagen (Analyse bleibt gueltig): %s: %r",
            type(exc).__name__,
            exc,
        )


def _dedupe_old_video_embeddings(result: dict[str, Any]) -> None:
    """Tombstone older vectors only after the new analysis truth is durable."""
    media_id = result.pop("_new_embedding_media_id", None)
    faiss_id = result.pop("_new_embedding_faiss_id", None)
    if media_id is None or faiss_id is None:
        return

    from pb_studio.data.vector_operation_outbox import VectorOperationOutbox

    operation_id = VectorOperationOutbox().dedupe_media_vectors_except(
        int(media_id),
        int(faiss_id),
    )
    if operation_id is not None:
        logger.info(
            "Alte SigLIP-Vektoren für media_id=%s nach DB-Commit bereinigt: %s",
            media_id,
            operation_id,
        )


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
@recovery_write_operation("video-media")
async def import_videos(
    request: VideoImportRequest,
    state: AppState = Depends(get_app_state),
) -> list[VideoClipInfo]:
    """Importiert eine oder mehrere Video-Dateien."""
    try:
        async with state.project_operation() as context:
            return await _import_videos_in_project(request, state, context)
    except asyncio.CancelledError:
        raise
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _import_videos_in_project(
    request: VideoImportRequest,
    state: AppState,
    context: ProjectOperationContext,
) -> list[VideoClipInfo]:
    """Importiert Videos ausschliesslich in den erfassten Projektkontext."""
    imported = []
    supported = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv", ".flv"}
    input_total = len(request.paths)

    async def _publish_input_progress(
        input_index: int,
        message: str,
        clip_id: Optional[int] = None,
    ) -> None:
        await publish_event("import_progress", {
            "task_id": "video_import",
            "clip_id": clip_id,
            "step": "input",
            "percent": input_index * 100.0 / input_total,
            "message": message,
        })

    for input_index, path_str in enumerate(request.paths, start=1):
        try:
            video_path = canonical_local_media_file(
                path_str,
                label=f"Video-Importpfad {input_index}",
            )
        except MediaPathPolicyError as exc:
            logger.warning("Unsicherer Video-Importpfad abgelehnt: %s", exc)
            await _publish_input_progress(
                input_index,
                f"Uebersprungen {input_index}/{input_total}: unsicherer Pfad",
            )
            continue
        if video_path.suffix.lower() not in supported:
            logger.warning(f"Format nicht unterstützt: {video_path.suffix}")
            await _publish_input_progress(
                input_index, f"Uebersprungen {input_index}/{input_total}: Format"
            )
            continue

        try:
            info = await asyncio.to_thread(_get_video_info, str(video_path))
        except Exception as e:
            logger.error(f"Video-Info fehlgeschlagen: {video_path.name}: {e}")
            await _publish_input_progress(
                input_index, f"Uebersprungen {input_index}/{input_total}: Metadatenfehler"
            )
            continue

        # Plan Phase 1 #1: streaming sha256 hash for embedding-cache reuse.
        # User-Anforderung 2026-05-09: 0.01% per-chunk SSE-Progress.
        from pb_studio.core.media_hash import media_hash
        _loop = asyncio.get_running_loop()
        _vname = video_path.name
        _file_idx = input_index
        _file_total = input_total

        def _hash_progress(pct: float) -> None:
            try:
                # Map per-file 0..100% auf overall (file_idx-1 + pct/100) / total * 100
                overall = ((_file_idx - 1) + pct / 100.0) * 100.0 / _file_total
                asyncio.run_coroutine_threadsafe(
                    publish_event("import_progress", {
                        "task_id": "video_import",
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

        with state.project_commit(context):
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

        await _publish_input_progress(
            input_index,
            f"Importiert {input_index}/{input_total}: {video_path.name}",
            clip["id"],
        )

    # R15/M-01: Finales 100%-Event sicherstellen — bei übersprungenen Pfaden
    # (falsches Format, Info-Fehler) würde der letzte Event nie 100% erreichen.
    await publish_event("import_progress", {
        "task_id": "video_import",
        "clip_id": None,
        "percent": 100.0,
        "message": f"{len(imported)}/{input_total} Videos importiert",
    })

    logger.info(f"{len(imported)} von {input_total} Videos importiert")
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
    try:
        project_id = state.require_current_project_db_id()
    except (ProjectContextUnavailableError, RuntimeError):
        project_id = None
    clips = list(clips_snap.values())
    start = (page - 1) * limit
    end = start + limit

    result: list[VideoClipInfo] = []
    for c in clips[start:end]:
        clip_id = c["id"]
        va = analysis_snap.get(clip_id)
        if va is None and project_id is not None:
            va = _load_persisted_video_analysis(state, c, project_id)
        analysis_truth = va if isinstance(va, dict) and va else c
        analysis_status = _video_analysis_status(
            analysis_truth,
            legacy_is_analyzed=(
                bool(c.get("is_analyzed", False))
                or clip_id in analysis_snap
            ),
        )
        is_analyzed = analysis_status == "completed"
        tags = list(analysis_truth.get("tags") or [])
        stage_status = dict(analysis_truth.get("stage_status") or {})
        stage_errors = dict(analysis_truth.get("stage_errors") or {})
        stage_receipts = dict(analysis_truth.get("stage_receipts") or {})
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
        tag_source: Optional[str] = None
        if analysis_truth:
            motion = analysis_truth.get("motion") or {}
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
            _emb_dim = analysis_truth.get("embedding_dim")
            _emb_samples = analysis_truth.get("embedding_samples")
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
            has_embedding = bool(analysis_truth.get("has_embedding", False))
            tag_source = analysis_truth.get("tag_source")

        # L-N3: Felder die hier explizit als kwarg uebergeben werden, aus c_payload entfernen
        # damit kein TypeError "multiple values for keyword" auftritt (passiert nach analyze_video,
        # weil dort is_analyzed/avg_motion/peak_motion/motion_category/embedding_*/has_embedding
        # in state.set_video_clip() persistiert werden und somit im in-memory clip-dict landen).
        _explicit_kwargs = {
            "video_hash", "is_analyzed", "avg_motion", "peak_motion", "motion_category",
            "embedding_dim", "embedding_samples", "has_embedding", "tag_source",
            "analysis_status", "stage_status", "stage_errors",
            "stage_receipts", "tags",
        }
        c_payload = {k: v for k, v in c.items() if k not in _explicit_kwargs}
        result.append(
            VideoClipInfo(
                **c_payload,
                tags=tags,
                is_analyzed=is_analyzed,
                video_hash=video_hash_value,
                avg_motion=avg_motion,
                peak_motion=peak_motion,
                motion_category=motion_category,
                embedding_dim=embedding_dim,
                embedding_samples=embedding_samples,
                has_embedding=has_embedding,
                tag_source=tag_source,
                analysis_status=analysis_status,
                stage_status=stage_status,
                stage_errors=stage_errors,
                stage_receipts=stage_receipts,
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
    try:
        async with state.project_operation() as context:
            clip = state.get_video_clip(clip_id)
            if clip is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Clip {clip_id} nicht gefunden",
                )
            clip_path = str(clip["path"])
            jpeg_bytes = await asyncio.to_thread(
                _generate_thumbnail,
                clip_path,
            )
            with state.project_commit(context):
                current_clip = state.get_video_clip(clip_id)
                if (
                    current_clip is None
                    or str(current_clip.get("path")) != clip_path
                ):
                    raise ProjectContextChangedError(
                        "Video-Clip wurde während der Thumbnail-Generierung ersetzt"
                    )
                state.update_video_clip(
                    clip_id=clip_id,
                    thumbnail_available=True,
                )
            return Response(content=jpeg_bytes, media_type="image/jpeg")
    except HTTPException:
        raise
    except (
        ProjectContextChangedError,
        ProjectContextUnavailableError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Thumbnail-Generierung für Clip %s fehlgeschlagen",
            clip_id,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Thumbnail-Generierung fehlgeschlagen: {exc}",
        ) from exc


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
@recovery_write_operation("video-media")
async def delete_clip(
    clip_id: int,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Loescht einen einzelnen Video-Clip aus In-Memory + SQLite + FAISS-Cache."""
    try:
        async with state.project_operation() as context:
            if state.delete_video_clip(clip_id, context=context):
                await publish_log(f"Video-Clip {clip_id} geloescht", level="info", source="video.delete")
                return DeleteResponse(deleted_count=1, not_found_ids=[])
            return DeleteResponse(deleted_count=0, not_found_ids=[clip_id])
    except (ProjectContextChangedError, ProjectContextUnavailableError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/clips",
    response_model=DeleteResponse,
    summary="Video-Clips batch-loeschen",
)
@recovery_write_operation("video-media")
async def delete_clips_batch(
    request: BatchDeleteRequest,
    state: AppState = Depends(get_app_state),
) -> DeleteResponse:
    """Batch-Delete: loescht alle in clip_ids aufgefuehrten Video-Clips."""
    try:
        async with state.project_operation() as context:
            deleted = 0
            not_found = []
            for cid in request.clip_ids:
                if state.delete_video_clip(cid, context=context):
                    deleted += 1
                else:
                    not_found.append(cid)
            if deleted:
                await publish_log(
                    f"{deleted} Video-Clips batch-geloescht (von {len(request.clip_ids)} angefragt)",
                    level="info", source="video.delete",
                )
            return DeleteResponse(deleted_count=deleted, not_found_ids=not_found)
    except (ProjectContextChangedError, ProjectContextUnavailableError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
@recovery_write_operation("video-analysis")
async def analyze_video(
    request: VideoAnalyzeRequest,
    state: AppState = Depends(get_app_state),
    http_request: Request = None,
) -> VideoAnalysisResult:
    """Analysiert einen Video-Clip (GPU-Lock via Middleware)."""
    context: ProjectOperationContext | None = None
    try:
        async with state.project_operation() as context:
            return await _analyze_video_in_project(request, state, context)
    except asyncio.CancelledError as exc:
        if (
            http_request is not None
            and context is not None
            and not state.is_project_context_current(context)
        ):
            raise HTTPException(
                status_code=409,
                detail="Video-Analyse durch Projektwechsel unterbrochen",
            ) from exc
        raise
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _analyze_video_in_project(
    request: VideoAnalyzeRequest,
    state: AppState,
    context: ProjectOperationContext,
) -> VideoAnalysisResult:
    """Analysiert einen Clip ausschliesslich im erfassten Projektkontext."""
    clip = state.get_video_clip(request.clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail=f"Clip {request.clip_id} nicht gefunden")

    # R15/C-02: Datei-Existenz VOR GPU-Lock prüfen — fehlendes File würde sonst als
    # leeres Analyse-Ergebnis (scene_count=0, avg_motion=0.0) in die DB geschrieben
    # und vorherige Analysen überschreiben (Silent Data Corruption).
    correlation_id = str(uuid4())
    project_uuid, project_id, project_epoch = _capture_video_project_identity(
        state, context
    )
    media_path_exists = Path(clip["path"]).is_file()
    media_sha256 = _video_media_sha256(clip)

    # BUG-204/Feature-3: Multi-step SSE events fuer fein-granularen UI-Fortschritt.
    # 4 coarse Phasen (init/scenes/motion+embed/finalize). _run_video_analysis ist
    # via _loop + RAFT on_progress callback bereits per-frame instrumentiert
    # (siehe _motion_progress -> 'analysis_progress' SSE event), Audit C1.
    result = _video_analysis_resume_base(state, clip, context.project_id)
    result["media_sha256"] = media_sha256
    requested_stages = {
        "scenes": request.detect_scenes,
        "motion": request.analyze_motion,
        "embedding": request.generate_embeddings,
        "colors": request.analyze_colors,
        "captions": request.generate_captions,
        "audio_key": request.analyze_audio_key,
    }
    requested_stage_ids = frozenset(
        stage for stage, requested in requested_stages.items() if requested
    )
    fingerprints = _video_stage_fingerprints(
        request=request,
        project_uuid=project_uuid,
        project_id=project_id,
        project_epoch=project_epoch,
        media_sha256=media_sha256,
    )
    cached_receipts = _video_receipts_from_cache(result)
    run_stage: dict[str, bool] = {}
    for stage, requested in requested_stages.items():
        reusable = False
        cached_receipt = cached_receipts.get(stage)
        if requested and not request.force and cached_receipt is not None:
            expected_input, expected_config = fingerprints[stage]
            reusable = _video_cached_receipt_artifact_is_valid(
                stage,
                cached_receipt,
                result,
                expected_input_fingerprint=expected_input,
                expected_config_fingerprint=expected_config,
            )
        run_stage[stage] = bool(requested and not reusable)

    receipts = _build_video_request_receipts(
        request=request,
        run_stage=(
            run_stage
            if media_path_exists
            else {stage: requested for stage, requested in requested_stages.items()}
        ),
        cached=result,
        fingerprints=fingerprints,
        correlation_id=correlation_id,
    )

    if not media_path_exists:
        missing_message = f"Video-Datei nicht gefunden: {clip['path']!r}"
        for stage in requested_stage_ids:
            _terminalize_video_stage_receipt(
                receipts,
                stage,
                result,
                "failed",
                missing_message,
                error_code="media_missing",
            )
        _apply_video_receipt_truth(result, receipts, requested_stage_ids)
        with state.project_commit(context):
            _persist_video_analysis_outcome(state, context, clip, result)
        await publish_event("analysis_progress", {
            "clip_id": request.clip_id,
            "correlation_id": correlation_id,
            "step": "error",
            "percent": 0.0,
            "status": result["status"],
            "stage_status": result["stage_status"],
            "stage_errors": result["stage_errors"],
            "stage_receipts": result["stage_receipts"],
            "message": missing_message,
        })
        raise HTTPException(status_code=422, detail=missing_message)

    _apply_video_receipt_truth(result, receipts, requested_stage_ids)
    with state.project_commit(context):
        _persist_video_analysis_outcome(state, context, clip, result)

    logger.info(f"Starte Video-Analyse: {clip['name']}")
    await publish_log(
        f"Video-Analyse gestartet: {clip['name']}",
        level="info",
        source="video.analyze",
        detail=f"clip_id={request.clip_id} correlation_id={correlation_id}",
    )
    await publish_event("analysis_progress", {
        "clip_id": request.clip_id,
        "correlation_id": correlation_id,
        "step": "init",
        "step_index": 1,
        "step_total": 4,
        "percent": 1.0,
        "status": "running",
        "stage_status": result["stage_status"],
        "stage_receipts": result["stage_receipts"],
        "message": f"Starte Video-Analyse: {clip['name']}",
    })
    await publish_event("analysis_progress", {
        "clip_id": request.clip_id,
        "correlation_id": correlation_id,
        "step": "scenes",
        "step_index": 2,
        "step_total": 4,
        "percent": 15.0,
        "status": "running",
        "message": f"Scene-Detection laeuft: {clip['name']}",
    })

    def persist_receipt_checkpoint() -> None:
        _apply_video_receipt_truth(result, receipts, requested_stage_ids)
        with state.project_commit(context):
            _persist_video_analysis_outcome(state, context, clip, result)
    resume_base = deepcopy(result)
    active_stages: tuple[str, ...] = ()
    outcome_persisted = False
    current_stage = "scenes"
    try:
        # Step 2: Scene Detection (CPU-only)
        if run_stage["scenes"]:
            active_stages = ("scenes",)
            scene_res = await asyncio.to_thread(
                _run_scene_detection,
                clip["path"],
                True,
            )
            scene_res = _bound_scene_result_to_duration(
                scene_res,
                clip.get("duration_seconds"),
            )
            _merge_video_stage_outcome(result, scene_res, "scenes")
            _terminalize_video_stage_receipt(
                receipts, "scenes", result,
                result["stage_status"].get("scenes", "failed"),
                result["stage_errors"].get("scenes"),
            )
            persist_receipt_checkpoint()
            active_stages = ()

        await publish_event("analysis_progress", {
            "clip_id": request.clip_id,
            "step": "motion_embedding",
            "step_index": 3,
            "step_total": 4,
            "percent": 35.0,
            "message": f"Motion + Embedding (RAFT/SigLIP) laeuft: {clip['name']}",
        })
        # Audit C1: _loop an _run_video_gpu_analysis durchreichen
        current_stage = "motion_embedding"
        _loop = asyncio.get_running_loop()
        gpu_res: dict[str, Any] = {}
        if run_stage["motion"] or run_stage["embedding"]:
            active_stages = tuple(
                stage
                for stage in ("motion", "embedding")
                if run_stage[stage]
            )
            gpu_request = request.model_copy(update={
                "analyze_motion": run_stage["motion"],
                "generate_embeddings": run_stage["embedding"],
            })
            gpu_args: tuple[Any, ...] = (
                clip["path"],
                request.clip_id,
                gpu_request,
                _loop,
                clip.get("video_hash") if run_stage["embedding"] else None,
                state,
                context,
                clip.get("duration_seconds"),
            )
            gpu_res = await with_gpu_task(
                _run_video_gpu_analysis, *gpu_args,
                model_id="video_analysis_full",
                # RAFT und SigLIP verwalten ihre Sessions/Budgets selbst. Der äußere
                # Task braucht nur globalen GPU-Lock und gemeinsame Telemetrie.
                manage_vram=False,
            )
            gpu_stage_status = dict(gpu_res.get("stage_status") or {})
            gpu_stage_errors = dict(gpu_res.get("stage_errors") or {})
            if run_stage["motion"]:
                _merge_video_stage_outcome(result, gpu_res, "motion")
                _terminalize_video_stage_receipt(
                    receipts, "motion", result,
                    result["stage_status"].get("motion", "failed"),
                    result["stage_errors"].get("motion"),
                )
            if run_stage["embedding"]:
                _merge_video_stage_outcome(result, gpu_res, "embedding")
                if (
                    result["stage_status"].get("embedding") == "completed"
                    and gpu_res.get("_pending_embedding") is not None
                ):
                    result["_pending_embedding"] = gpu_res["_pending_embedding"]
                elif result["stage_status"].get("embedding") != "completed":
                    _terminalize_video_stage_receipt(
                        receipts, "embedding", result,
                        result["stage_status"].get("embedding", "failed"),
                        result["stage_errors"].get("embedding"),
                    )
            persist_receipt_checkpoint()
            active_stages = ()

        # Step 3: Color + Caption (CPU/HTTP & optional Moondream GPU Fallback)
        current_stage = "colors_captions"
        color_caption_res: dict[str, Any] = {}
        if run_stage["colors"] or run_stage["captions"]:
            active_stages = tuple(
                stage
                for stage in ("colors", "captions")
                if run_stage[stage]
            )
            def checkpoint_completed_colors(stage_result: dict[str, Any]) -> None:
                nonlocal active_stages
                if not run_stage["colors"]:
                    return
                _merge_video_stage_outcome(result, stage_result, "colors")
                _terminalize_video_stage_receipt(
                    receipts, "colors", result,
                    result["stage_status"].get("colors", "failed"),
                    result["stage_errors"].get("colors"),
                )
                persist_receipt_checkpoint()
                active_stages = tuple(
                    stage for stage in active_stages if stage != "colors"
                )

            def checkpoint_caption_attempt(stage_result: dict[str, Any]) -> None:
                result["caption_attempts"] = deepcopy(
                    stage_result.get("caption_attempts") or []
                )

            import inspect
            color_caption_kwargs: dict[str, Any] = {}
            if "on_colors_completed" in inspect.signature(
                _run_color_and_caption_analysis
            ).parameters:
                color_caption_kwargs["on_colors_completed"] = (
                    checkpoint_completed_colors
                )
            if "on_caption_attempted" in inspect.signature(
                _run_color_and_caption_analysis
            ).parameters:
                color_caption_kwargs["on_caption_attempted"] = (
                    checkpoint_caption_attempt
                )
            color_caption_res = await _run_color_and_caption_analysis(
                clip["path"],
                request.clip_id,
                run_stage["captions"],
                run_stage["colors"],
                **color_caption_kwargs,
            )
            if run_stage["colors"]:
                _merge_video_stage_outcome(result, color_caption_res, "colors")
                _terminalize_video_stage_receipt(
                    receipts, "colors", result,
                    result["stage_status"].get("colors", "failed"),
                    result["stage_errors"].get("colors"),
                )
                persist_receipt_checkpoint()
            if run_stage["captions"]:
                _merge_video_stage_outcome(result, color_caption_res, "captions")
                _terminalize_video_stage_receipt(
                    receipts, "captions", result,
                    result["stage_status"].get("captions", "failed"),
                    result["stage_errors"].get("captions"),
                    error_code=color_caption_res.get("caption_error_code"),
                )
                persist_receipt_checkpoint()
                caption_status = result["stage_status"]["captions"]
                await _publish_caption_progress(
                    request.clip_id,
                    step=(
                        "captions_complete"
                        if caption_status == "completed"
                        else "captions_partial"
                        if caption_status == "partial"
                        else "captions_error"
                    ),
                    percent=CAPTION_PROGRESS_END_PERCENT,
                    status=caption_status,
                    message=f"Vision-Analyse {caption_status}",
                    correlation_id=correlation_id,
                    stage_receipts=result["stage_receipts"],
                )
            active_stages = ()

        _apply_video_receipt_truth(result, receipts, requested_stage_ids)
        stage_status = dict(result["stage_status"])
        stage_errors = dict(result["stage_errors"])
        analysis_status = result["status"]

        # Zusammenführen der Ergebnisse

        # Audit-Fix 2026-07-10 (Sweep-Finding HIGH-10): Brightness/Saturation/
        # Color-Temp/Mood-Tags aus den bereits berechneten dominanten Farben
        # ableiten — Brain-Bridge-Achsen mood_match_weight/color_temp_match_weight
        # waren vorher strukturell tot, weil niemand diese Felder befuellte.
        if (
            run_stage["colors"]
            and result["stage_status"].get("colors") == "completed"
            and not all(
                field in color_caption_res
                for field in (
                    "avg_brightness",
                    "avg_saturation",
                    "avg_color_temp",
                    "mood_tags",
                )
            )
        ):
            from pb_studio.video.moondream_wrapper import compute_color_features
            color_features = compute_color_features(result["dominant_colors"])
            result["avg_brightness"] = color_features["avg_brightness"]
            result["avg_saturation"] = color_features["avg_saturation"]
            result["avg_color_temp"] = color_features["avg_color_temp"]
            result["mood_tags"] = color_features["mood_tags"]

        # Y3 / GPU-F2: L-K4 audio_key Detection OUTSIDE with_gpu_task - ffmpeg
        # extract 30s mono WAV + Krumhansl-Kessler ist pure CPU-Arbeit und darf
        # den GPU-Lock NICHT halten (sonst blocken parallele Stem-/Render-Tasks).
        current_stage = "audio_key"
        if run_stage["audio_key"]:
            active_stages = ("audio_key",)
            try:
                from pb_studio.video.audio_key_detector import detect_video_audio_key
                audio_key_val = await asyncio.to_thread(detect_video_audio_key, clip["path"])
                result["audio_key"] = audio_key_val
                if audio_key_val:
                    result["stage_status"]["audio_key"] = "completed"
                    result["stage_errors"].pop("audio_key", None)
                    logger.info(f"L-K4: Video-Audio-Key fuer clip {request.clip_id}: {audio_key_val}")
                else:
                    result["stage_status"]["audio_key"] = "unavailable"
                    result["stage_errors"]["audio_key"] = (
                        "Video besitzt keinen erkennbaren Audio-Key"
                    )
            except Exception as e:
                logger.warning(f"L-K4 audio_key extract failed (post-gpu-task): {e}")
                result["stage_status"]["audio_key"] = "unavailable"
                result["stage_errors"]["audio_key"] = str(e)
            _terminalize_video_stage_receipt(
                receipts, "audio_key", result,
                result["stage_status"].get("audio_key", "unavailable"),
                result["stage_errors"].get("audio_key"),
                error_code="audio_key_unavailable",
            )
            persist_receipt_checkpoint()
            active_stages = ()

        stage_status = dict(result["stage_status"])
        stage_errors = dict(result["stage_errors"])
        _apply_video_receipt_truth(result, receipts, requested_stage_ids)
        stage_status = dict(result["stage_status"])
        stage_errors = dict(result["stage_errors"])
        analysis_status = result["status"]
        current_stage = "persistence"
        with state.project_commit(context):
            _commit_pending_video_embedding(result)
            if run_stage["embedding"]:
                _terminalize_video_stage_receipt(
                    receipts, "embedding", result,
                    gpu_stage_status.get("embedding", "failed"),
                    gpu_stage_errors.get("embedding"),
                )
                _apply_video_receipt_truth(result, receipts, requested_stage_ids)
                stage_status = dict(result["stage_status"])
                stage_errors = dict(result["stage_errors"])
                analysis_status = result["status"]
            _persist_video_analysis_outcome(state, context, clip, result)
        outcome_persisted = True
        try:
            _dedupe_old_video_embeddings(result)
        except Exception as dedupe_exc:
            logger.error(
                "Alte SigLIP-Vektoren bleiben bis zur Outbox-Recovery erhalten: %s",
                dedupe_exc,
                exc_info=True,
            )

        try:
            await publish_log(
                f"Video-Analyse {analysis_status}: {clip['name']}",
                level="warning" if analysis_status == "partial" else "info",
                source="video.analyze",
                detail=f"clip_id={request.clip_id} scenes={int(result.get('scene_count', 0) or 0)} avg_motion={float(result.get('avg_motion', 0.0) or 0.0):.2f}",
            )
        except Exception as publish_exc:
            logger.warning("Videoanalyse-Logevent fehlgeschlagen: %s", publish_exc)

        # Feature-3: finalize-Event vor complete (DB-Persistenz schon passiert oben)
        try:
            await publish_event("analysis_progress", {
                "clip_id": request.clip_id,
                "correlation_id": correlation_id,
                "step": "finalize",
                "step_index": 4,
                "step_total": 4,
                "percent": 90.0,
                "message": f"Persistiere Ergebnisse: {clip['name']}",
            })
        except Exception as publish_exc:
            logger.warning("Videoanalyse-Finalize-Event fehlgeschlagen: %s", publish_exc)

        # BUG-204 Fix: Final-Event mit Ergebnis-Daten fuer UI-Status
        try:
            await publish_event("analysis_progress", {
                "clip_id": request.clip_id,
                "correlation_id": correlation_id,
                "step": "complete",
                "step_index": 4,
                "step_total": 4,
                "percent": 100.0,
                "status": analysis_status,
                "stage_status": stage_status,
                "stage_errors": stage_errors,
                "stage_receipts": result["stage_receipts"],
                "message": (
                    f"Video-Analyse {analysis_status}: {int(result.get('scene_count', 0) or 0)} Szenen, "
                    f"Motion {float(result.get('avg_motion', 0.0) or 0.0):.1f}"
                ),
            })
        except Exception as publish_exc:
            logger.warning("Videoanalyse-Complete-Event fehlgeschlagen: %s", publish_exc)
        return VideoAnalysisResult(**result)
    except asyncio.CancelledError:
        if not outcome_persisted:
            try:
                embedding_discarded = _compensate_new_video_embedding(result)
                if embedding_discarded:
                    _restore_video_embedding_after_compensation(result, resume_base)
            except Exception as compensation_exc:
                logger.error(
                    "Embedding-Kompensation nach Videoanalyse-Abbruch fehlgeschlagen: %s",
                    compensation_exc,
                    exc_info=True,
                )
                result["stage_errors"]["embedding_compensation"] = str(
                    compensation_exc
                )

            for stage in active_stages:
                result["stage_status"][stage] = "interrupted"
                result["stage_errors"][stage] = "Video-Analyse unterbrochen"
            for stage, receipt in tuple(receipts.items()):
                if stage in requested_stage_ids and receipt.status in {"pending", "running"}:
                    _terminalize_video_stage_receipt(
                        receipts, stage, result, "interrupted",
                        "Video-Analyse unterbrochen",
                        error_code="analysis_interrupted",
                    )
            _apply_video_receipt_truth(result, receipts, requested_stage_ids)
            try:
                with state.project_commit(context):
                    _persist_video_analysis_outcome(
                        state,
                        context,
                        clip,
                        result,
                    )
            except ProjectContextChangedError:
                logger.info(
                    "Videoanalyse-Abbruch nicht persistiert: Projektkontext wechselte"
                )
            except Exception as persist_exc:
                logger.error(
                    "Videoanalyse-Abbruchstatus konnte nicht persistiert werden: %s",
                    persist_exc,
                    exc_info=True,
                )

        terminal_step = "complete" if outcome_persisted else "interrupted"
        try:
            await publish_event("analysis_progress", {
                "clip_id": request.clip_id,
                "correlation_id": correlation_id,
                "step": terminal_step,
                "percent": 100.0 if outcome_persisted else 0.0,
                "status": result["status"],
                "stage_status": dict(result["stage_status"]),
                "stage_errors": dict(result["stage_errors"]),
                "stage_receipts": dict(result["stage_receipts"]),
                "message": (
                    f"Video-Analyse {result['status']}: {clip['name']}"
                    if outcome_persisted
                    else f"Video-Analyse unterbrochen: {clip['name']}"
                ),
            })
        except asyncio.CancelledError:
            pass
        except Exception as publish_exc:
            logger.warning(
                "Terminales Videoanalyse-Abbruch-Event fehlgeschlagen: %s",
                publish_exc,
            )
        raise
    except ProjectContextChangedError:
        _compensate_new_video_embedding(result)
        raise
    except Exception as e:
        for stage, receipt in tuple(receipts.items()):
            if stage in requested_stage_ids and receipt.status in {"pending", "running"}:
                _terminalize_video_stage_receipt(
                    receipts, stage, result, "failed", str(e),
                    error_code="analysis_worker_failed",
                )
        _apply_video_receipt_truth(result, receipts, requested_stage_ids)
        try:
            _compensate_new_video_embedding(result)
        except Exception as compensation_exc:
            logger.critical(
                "SigLIP-Embedding-Kompensation fehlgeschlagen: %s",
                compensation_exc,
                exc_info=True,
            )
            result["stage_errors"]["embedding_compensation"] = str(
                compensation_exc
            )
        try:
            with state.project_commit(context):
                _persist_video_analysis_outcome(state, context, clip, result)
        except ProjectContextChangedError:
            raise
        except Exception as persist_exc:
            logger.error(
                "Videoanalyse-Fehlerstatus konnte nicht persistiert werden: %s",
                persist_exc,
                exc_info=True,
            )
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
            "correlation_id": correlation_id,
            "step": "error",
            "percent": 0.0,
            "status": result["status"],
            "stage_status": result["stage_status"],
            "stage_errors": result["stage_errors"],
            "stage_receipts": result["stage_receipts"],
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
        clip = state.get_video_clip(clip_id)
        if clip is not None:
            try:
                analysis = _load_persisted_video_analysis(
                    state,
                    clip,
                    state.require_current_project_db_id(),
                )
            except (ProjectContextUnavailableError, RuntimeError):
                analysis = None
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
        clip = state.get_video_clip(clip_id)
        if clip is not None:
            try:
                analysis = _load_persisted_video_analysis(
                    state,
                    clip,
                    state.require_current_project_db_id(),
                )
            except (ProjectContextUnavailableError, RuntimeError):
                analysis = None
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
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    res = subprocess.check_output(
        cmd,
        stderr=subprocess.DEVNULL,
        timeout=30,
        startupinfo=startupinfo,
    )
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
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.run(
            cmd,
            capture_output=True,
            timeout=15,
            check=True,
            startupinfo=startupinfo,
        )
        return tmp_path.read_bytes()
    finally:
        # R20/LOW: unlink(missing_ok=True) avoids FileNotFoundError if ffmpeg
        # failed before creating the file.
        tmp_path.unlink(missing_ok=True)


def _run_scene_detection(video_path: str, detect_scenes: bool) -> dict[str, Any]:
    """Scene Detection via PySceneDetect (CPU-only)."""
    result = {
        "scene_count": 0,
        "scenes": [],
        "stage_status": {"scenes": "skipped" if not detect_scenes else "failed"},
        "stage_errors": {},
    }
    if detect_scenes:
        try:
            from pb_studio.video.scene_detect import SceneDetector
            scenes_raw = SceneDetector().detect_scenes(video_path)
            if not scenes_raw:
                raise RuntimeError("Scene detection produced no valid scenes")
            result["scenes"] = [
                {
                    "start_time": float(s[0]),
                    "end_time": float(s[1]),
                    "scene_type": "cut",
                    # PySceneDetect liefert hier keinen kalibrierten Score.
                    "confidence": None,
                }
                for s in scenes_raw
            ]
            result["scene_count"] = len(scenes_raw)
            result["stage_status"]["scenes"] = "completed"
        except Exception as e:
            logger.warning(f"Scene-Detection fehlgeschlagen: {e}")
            result["stage_errors"]["scenes"] = str(e)
    return result


def _positive_duration(value: Any) -> Optional[float]:
    """Return a finite positive duration or ``None``."""
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return None
    if duration <= 0.0 or duration == float("inf") or duration != duration:
        return None
    return duration


def _bound_scene_result_to_duration(
    result: dict[str, Any],
    duration_seconds: Any,
) -> dict[str, Any]:
    """Clamp scene metadata to the persisted ffprobe-visible duration."""
    duration = _positive_duration(duration_seconds)
    if duration is None or result.get("stage_status", {}).get("scenes") != "completed":
        return result

    bounded_scenes = []
    for scene in result.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        try:
            start = max(0.0, min(float(scene.get("start_time", 0.0)), duration))
            end = max(start, min(float(scene.get("end_time", start)), duration))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        bounded_scenes.append({**scene, "start_time": start, "end_time": end})

    if not bounded_scenes:
        bounded_scenes = [{
            "start_time": 0.0,
            "end_time": duration,
            "scene_type": "cut",
            "confidence": None,
        }]
    result["scenes"] = bounded_scenes
    result["scene_count"] = len(bounded_scenes)
    return result


def _representative_frame_indices(
    total_frames: int,
    desired_samples: int,
    max_samples: int,
    min_samples: int,
) -> list[int]:
    """Return bounded, evenly spaced indices covering the complete input."""
    if total_frames <= 0 or max_samples <= 0:
        return []
    sample_count = min(
        total_frames,
        max_samples,
        max(1, min_samples, desired_samples),
    )
    if sample_count == 1:
        return [0]
    last = total_frames - 1
    return sorted({
        round(position * last / (sample_count - 1))
        for position in range(sample_count)
    })


def _addressable_frame_count(
    reported_total_frames: int,
    fps: float,
    duration_seconds: Any,
) -> int:
    """Bound OpenCV's packet-inflated frame count by visible ffprobe duration."""
    if reported_total_frames <= 0:
        return 0
    duration = _positive_duration(duration_seconds)
    if duration is None or fps <= 0.0:
        return reported_total_frames
    duration_frames = max(1, int(round(duration * fps)))
    return min(reported_total_frames, duration_frames)


def _read_sample_frame(
    cap: Any,
    target_index: int,
    addressable_frames: int,
    used_indices: set[int],
) -> tuple[Optional[int], Any]:
    """Read one sample, replacing an unreadable target with a nearby frame."""
    candidates = [target_index]
    for offset in range(1, FRAME_SAMPLE_REPLACEMENT_RADIUS + 1):
        candidates.extend((target_index - offset, target_index + offset))

    import cv2

    for candidate in candidates:
        if not 0 <= candidate < addressable_frames or candidate in used_indices:
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, candidate)
        ret, frame = cap.read()
        if ret and frame is not None:
            used_indices.add(candidate)
            return candidate, frame
    return None, None


def _select_motion_peak_frames(
    motion_values: list[float],
    sampled_frame_indices: list[int],
    fps: float,
    max_peaks: int = 10,
) -> list[dict[str, Any]]:
    """Select real local maxima from RAFT motion values."""
    if not motion_values or len(sampled_frame_indices) < 2 or max_peaks <= 0:
        return []

    values = [max(0.0, float(value)) for value in motion_values]
    maximum = max(values)
    if maximum <= 0.0:
        return []

    candidates: list[tuple[int, float]] = []
    for index, value in enumerate(values):
        previous = values[index - 1] if index > 0 else float("-inf")
        following = values[index + 1] if index + 1 < len(values) else float("-inf")
        if value >= previous and value >= following and (value > previous or value > following):
            candidates.append((index, value))

    if not candidates:
        candidates = [(max(range(len(values)), key=values.__getitem__), maximum)]

    strongest = sorted(candidates, key=lambda item: item[1], reverse=True)[:max_peaks]
    strongest.sort(key=lambda item: item[0])
    safe_fps = max(float(fps), 1.0)
    peaks = []
    for motion_index, value in strongest:
        sampled_index = min(motion_index + 1, len(sampled_frame_indices) - 1)
        frame_index = int(sampled_frame_indices[sampled_index])
        peaks.append({
            "frame_index": frame_index,
            "time_seconds": round(frame_index / safe_fps, 3),
            "motion": value,
            "confidence": min(1.0, value / maximum),
        })
    return peaks


def _get_reusable_embedding_metadata(
    video_path: str,
    clip_id: int,
    video_hash: Optional[str],
    state: AppState,
    context: ProjectOperationContext,
) -> Optional[dict[str, int]]:
    """Return persisted embedding metadata only for a verified content/link hit."""
    if not video_hash:
        return None

    try:
        from pb_studio.data.database_core import DatabaseCore
        from pb_studio.data.repositories.media_repository import MediaRepository
        from pb_studio.data.vector_store import VectorStore

        state.require_project_context_current(context)
        clip = state.get_video_clip(clip_id) or {}
        cached = state.get_video_analysis(clip_id) or {}
        if clip.get("video_hash") != video_hash:
            return None

        embedding_dim = int(cached.get("embedding_dim", 0) or 0)
        embedding_samples = int(cached.get("embedding_samples", 0) or 0)
        if (
            not cached.get("has_embedding")
            or embedding_dim != SIGLIP_EMBEDDING_DIM
            or embedding_samples <= 0
        ):
            return None

        media_row = MediaRepository().find_by_project_and_path(
            project_id=context.project_id,
            file_path=video_path,
        )
        if not media_row or media_row.get("file_hash") != video_hash:
            return None

        db = DatabaseCore()
        conn = db.get_connection()
        faiss_ids = [
            int(row[0])
            for row in conn.execute(
                "SELECT faiss_id FROM vector_map WHERE media_id = ?",
                (media_row["id"],),
            )
        ]
        if not faiss_ids:
            return None

        vector_store = VectorStore(index_name="video_index")
        expected_path = Path(video_path).resolve()
        with vector_store._lock:
            vector_store._ensure_open()
            tombstones = getattr(vector_store, "_tombstoned_ids", set())
            for faiss_id in faiss_ids:
                if (
                    faiss_id in tombstones
                    or vector_store.index is None
                    or faiss_id >= vector_store.index.ntotal
                ):
                    continue
                metadata = vector_store.metadata.get(faiss_id) or {}
                metadata_path = metadata.get("path")
                metadata_hash = metadata.get("video_hash")
                if metadata_hash not in (None, video_hash):
                    continue
                if metadata_path and Path(metadata_path).resolve() == expected_path:
                    return {
                        "embedding_dim": embedding_dim,
                        "embedding_samples": embedding_samples,
                    }
    except ProjectContextChangedError:
        raise
    except Exception as exc:
        logger.warning("Embedding-Reuse-Pruefung fehlgeschlagen: %s", exc)
    return None


def _run_video_gpu_analysis(
    video_path: str,
    clip_id: int,
    request: VideoAnalyzeRequest,
    _loop=None,
    video_hash: Optional[str] = None,
    state: Optional[AppState] = None,
    context: Optional[ProjectOperationContext] = None,
    duration_seconds: Optional[float] = None,
) -> dict[str, Any]:
    """Motion + Embedding via RAFT und SigLIP (DirectML, GPU)."""
    if state is not None and context is not None:
        state.require_project_context_current(context)
    result = {
        "avg_motion": 0.0,
        "embedding_dim": 0,
        "embedding_samples": 0,
        "has_embedding": False,
        "embedding_reused": False,
        "stage_status": {},
        "stage_errors": {},
    }

    # 1. Motion-Analyse via RAFT
    if request.analyze_motion:
        try:
            import cv2
            from pb_studio.video.raft import MotionAnalyzer

            cap = cv2.VideoCapture(video_path)
            try:
                reported_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                total = _addressable_frame_count(
                    reported_total,
                    fps,
                    duration_seconds,
                )
                duration_sec = (
                    _positive_duration(duration_seconds)
                    or total / max(fps, 1.0)
                )
                frame_indices = _representative_frame_indices(
                    total,
                    desired_samples=max(2, int(duration_sec * 2)),
                    max_samples=MAX_MOTION_SAMPLES,
                    min_samples=2,
                )

                frames = []
                sampled_indices = []
                used_indices: set[int] = set()
                unreadable_samples = 0
                for frame_index in frame_indices:
                    sampled_index, frame = _read_sample_frame(
                        cap,
                        frame_index,
                        total,
                        used_indices,
                    )
                    if frame is None or sampled_index is None:
                        unreadable_samples += 1
                        if unreadable_samples > MAX_UNREADABLE_SAMPLE_FRAMES:
                            raise RuntimeError(
                                "RAFT sampling exceeded unreadable frame tolerance"
                            )
                        logger.warning(
                            "RAFT sample at frame %s unreadable; continuing with valid samples",
                            frame_index,
                        )
                        continue
                    h, w = frame.shape[:2]
                    if h > 360:
                        scale = 360.0 / h
                        new_w = int(w * scale)
                        frame = cv2.resize(frame, (new_w, 360), interpolation=cv2.INTER_AREA)
                    frames.append(frame)
                    sampled_indices.append(sampled_index)
            finally:
                cap.release()

            if len(frames) < 2:
                raise RuntimeError(
                    f"RAFT sampling produced {len(frames)} readable frames"
                )

            motion_analyzer = MotionAnalyzer()
            try:
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
                motion_curve_vals = [
                    float(value)
                    for value in motion_result.get("frame_motions", [])
                ]
                if not motion_curve_vals:
                    raise RuntimeError("RAFT returned no motion samples")

                peak_motion_value = float(max(motion_curve_vals))
                average_motion = float(motion_result.get("avg_motion", 0.0))
                result["motion"] = {
                    "clip_id": clip_id,
                    "avg_motion": average_motion,
                    "peak_motion": peak_motion_value,
                    "motion_curve": motion_curve_vals,
                    "peak_frames": _select_motion_peak_frames(
                        motion_curve_vals,
                        sampled_indices,
                        fps,
                    ),
                    "motion_category": _classify_motion(average_motion),
                }
                result["avg_motion"] = average_motion
                result["stage_status"]["motion"] = "completed"
            finally:
                motion_analyzer.unload()
                import gc; gc.collect()
                del motion_analyzer
        except ProjectContextChangedError:
            raise
        except Exception as e:
            logger.error(f"Motion-Analyse fehlgeschlagen: {e}")
            result["stage_status"]["motion"] = "failed"
            result["stage_errors"]["motion"] = str(e)
    else:
        result["stage_status"]["motion"] = "skipped"

    # 2. Embedding (SigLIP DirectML)
    if request.generate_embeddings:
        reusable = (
            _get_reusable_embedding_metadata(
                video_path,
                clip_id,
                video_hash,
                state,
                context,
            )
            if not request.force and state is not None and context is not None
            else None
        )
        if reusable is not None:
            result["has_embedding"] = True
            result["embedding_dim"] = reusable["embedding_dim"]
            result["embedding_samples"] = reusable["embedding_samples"]
            result["embedding_reused"] = True
            result["stage_status"]["embedding"] = "completed"
            logger.info(
                "SigLIP Embedding fuer Clip %s per Video-Hash wiederverwendet",
                clip_id,
            )
            return result

        try:
            import cv2
            from pb_studio.ai.siglip_wrapper import SigLIPWrapper

            wrapper = SigLIPWrapper(lazy_load=False)
            try:
                if not wrapper.is_ready:
                    raise RuntimeError(
                        "SigLIP DirectML model initialization failed; "
                        "embedding stage unavailable"
                    )
                if wrapper.is_ready:
                    import numpy as _np
                    from PIL import Image as _PILImage

                    cap = cv2.VideoCapture(video_path)
                    embeddings_collected = []
                    try:
                        reported_total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                        total_frames = _addressable_frame_count(
                            reported_total_frames,
                            fps,
                            duration_seconds,
                        )
                        duration_sec = (
                            _positive_duration(duration_seconds)
                            or total_frames / max(fps, 1.0)
                        )
                        embedding_indices = _representative_frame_indices(
                            total_frames,
                            desired_samples=max(3, int(duration_sec / 5.0)),
                            max_samples=MAX_EMBEDDING_SAMPLES,
                            min_samples=3,
                        )
                        used_indices: set[int] = set()
                        unreadable_samples = 0
                        for frame_index in embedding_indices:
                            sampled_index, frame = _read_sample_frame(
                                cap,
                                frame_index,
                                total_frames,
                                used_indices,
                            )
                            if frame is None or sampled_index is None:
                                unreadable_samples += 1
                                if unreadable_samples > MAX_UNREADABLE_SAMPLE_FRAMES:
                                    raise RuntimeError(
                                        "SigLIP sampling exceeded unreadable frame tolerance"
                                    )
                                logger.warning(
                                    "SigLIP sample at frame %s unreadable; continuing with valid samples",
                                    frame_index,
                                )
                                continue
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            pil_img = _PILImage.fromarray(frame_rgb)
                            emb = wrapper.encode_image(pil_img)
                            if emb is None:
                                raise RuntimeError(
                                    f"SigLIP inference failed at frame {sampled_index}"
                                )
                            embeddings_collected.append(emb)
                    finally:
                        cap.release()

                    if embeddings_collected:
                        stacked = _np.stack(embeddings_collected, axis=0)
                        embedding = stacked.mean(axis=0)
                        if embedding.shape != (SIGLIP_EMBEDDING_DIM,):
                            raise RuntimeError(
                                f"SigLIP embedding dimension {embedding.shape} != "
                                f"({SIGLIP_EMBEDDING_DIM},)"
                            )
                        norm = float(_np.linalg.norm(embedding))
                        if norm > 1e-3:
                            embedding = embedding / norm
                            if state is None or context is None:
                                raise RuntimeError(
                                    "SigLIP embedding commit requires project context"
                                )
                            from pb_studio.data.repositories.media_repository import MediaRepository
                            _vmr = MediaRepository()
                            _media_row = _vmr.find_by_project_and_path(
                                project_id=context.project_id,
                                file_path=video_path,
                            )
                            _media_id = _media_row["id"] if _media_row else None
                            if _media_id is None:
                                raise RuntimeError(
                                    f"Kein DB-Eintrag für Video-Clip {clip_id}"
                                )
                            embedding_duration_seconds = duration_sec
                            result["_pending_embedding"] = {
                                "vector": embedding.astype(_np.float32),
                                "meta_info": {
                                    "clip_id": clip_id,
                                    "path": video_path,
                                    "video_hash": video_hash,
                                    "scene_id": f"clip_{clip_id}_full",
                                    "duration": embedding_duration_seconds,
                                    "samples": len(embeddings_collected),
                                },
                                "media_id": int(_media_id),
                                "segment_end": embedding_duration_seconds,
                                "description": f"clip_{clip_id}_full",
                            }
                            result["has_embedding"] = True
                            result["embedding_dim"] = len(embedding)
                            result["embedding_samples"] = len(embeddings_collected)
                            result["stage_status"]["embedding"] = "completed"
                            logger.info(
                                f"SigLIP Embedding (Mittelwert ueber {len(embeddings_collected)} Frames) "
                                f"gespeichert fuer Clip {clip_id} (dim={len(embedding)})"
                            )
                        else:
                            raise RuntimeError("SigLIP returned a zero-norm embedding")
                    else:
                        raise RuntimeError("SigLIP returned no valid embeddings")
                else:
                    logger.info("SigLIP ONNX-Modell nicht gefunden — Embedding übersprungen.")
                    result["has_embedding"] = False
            finally:
                if 'wrapper' in locals() and wrapper is not None:
                    try:
                        wrapper.unload()
                    except Exception as unload_err:
                        logger.warning(f"Failed to unload SigLIPWrapper: {unload_err}")
                del wrapper
                import gc; gc.collect()
        except ProjectContextChangedError:
            raise
        except Exception as e:
            logger.error(f"Embedding-Generierung fehlgeschlagen: {e}")
            result["has_embedding"] = False
            result["stage_status"]["embedding"] = "failed"
            result["stage_errors"]["embedding"] = str(e)
    else:
        result["stage_status"]["embedding"] = "skipped"

    return result


def _run_moondream_inference_on_frames(frames_rgb: list) -> list[list[str]]:
    """Führt Moondream Tag-Generierung auf GPU aus. Läuft unter GPU-Lock 'moondream_fp16'."""
    tags_collected = []
    try:
        from pb_studio.video.moondream import MoondreamAnalyzer
        from pb_studio.video.moondream_wrapper import extract_tags_via_moondream
        moondream_analyzer = MoondreamAnalyzer(lazy_load=True)
        try:
            for f_rgb in frames_rgb:
                tags = extract_tags_via_moondream(f_rgb, analyzer=moondream_analyzer)
                tags_collected.append(tags)
        finally:
            moondream_analyzer.unload()
            import gc; gc.collect()
    except Exception as ma_err:
        logger.warning(f"Moondream Inferenz fehlgeschlagen: {ma_err}")
    return tags_collected


async def _publish_caption_progress(
    clip_id: int,
    *,
    step: str,
    percent: float,
    message: str,
    status: str,
    correlation_id: str | None = None,
    stage_receipts: dict[str, Any] | None = None,
) -> None:
    """Publish caption progress without letting cosmetic SSE break analysis."""
    try:
        payload = {
            "clip_id": clip_id,
            "step": step,
            "step_index": 3,
            "step_total": 4,
            "percent": percent,
            "status": status,
            "message": message,
        }
        if correlation_id is not None:
            payload["correlation_id"] = correlation_id
        if stage_receipts is not None:
            payload["stage_receipts"] = stage_receipts
        await publish_event("analysis_progress", payload)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.debug("Caption-Fortschritt konnte nicht publiziert werden: %s", exc)


async def _caption_progress_heartbeat(
    clip_id: int,
    progress_state: dict[str, Any],
) -> None:
    """Keep caption progress monotonic and visibly alive across providers."""
    loop = asyncio.get_running_loop()
    started_at = float(progress_state["started_at"])
    while True:
        await asyncio.sleep(CAPTION_HEARTBEAT_INTERVAL_SECONDS)
        now = loop.time()
        frame_total = max(int(progress_state.get("phase_total_frames", 0)), 1)
        completed = min(
            int(progress_state.get("phase_completed_frames", 0)),
            frame_total,
        )
        active_frame = min(
            max(int(progress_state.get("phase_active_frame", completed + 1)), 1),
            frame_total,
        )
        phase_started_at = float(progress_state.get("phase_started_at", started_at))
        phase_budget = max(
            float(progress_state.get("phase_budget_seconds", 0.0)),
            CAPTION_HEARTBEAT_INTERVAL_SECONDS,
        )
        phase_elapsed = max(0.0, now - phase_started_at)
        work_fraction = completed / frame_total
        elapsed_fraction = min(phase_elapsed / phase_budget, 0.98)
        fraction = min(max(work_fraction, elapsed_fraction), 0.98)
        phase_start = float(
            progress_state.get("phase_progress_start", CAPTION_PROGRESS_START_PERCENT)
        )
        phase_end = float(
            progress_state.get("phase_progress_end", CAPTION_PROGRESS_END_PERCENT)
        )
        candidate = phase_start + (phase_end - phase_start) * fraction
        terminal_ceiling = CAPTION_PROGRESS_END_PERCENT - CAPTION_PROGRESS_TERMINAL_MARGIN
        percent = min(
            terminal_ceiling,
            max(float(progress_state.get("reported_percent", phase_start)), candidate),
        )
        progress_state["reported_percent"] = percent
        elapsed = int(now - started_at)
        await _publish_caption_progress(
            clip_id,
            step="captions",
            percent=percent,
            status="running",
            message=(
                f"Vision-Analyse {progress_state.get('phase', 'Provider')}: "
                f"Frame {active_frame}/{frame_total}, Phase {int(phase_elapsed)}s, "
                f"gesamt {elapsed}s"
            ),
        )


async def _run_color_and_caption_analysis(
    video_path: str,
    clip_id: int,
    generate_captions: bool,
    analyze_colors: bool = True,
    on_colors_completed: Optional[Callable[[dict[str, Any]], None]] = None,
    on_caption_attempted: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict[str, Any]:
    """Extrahiert Farben und Tags (KMeans auf CPU, LM-Studio über HTTP, Moondream als GPU-Fallback)."""
    result = {
        "dominant_colors": [],
        "tags": [],
        "tag_source": "none",
        "stage_status": {
            "colors": "failed" if analyze_colors else "skipped",
            "captions": "failed" if generate_captions else "skipped",
        },
        "stage_errors": {},
        "caption_provider": None,
        "caption_model_id": None,
        "caption_attempts": [],
        "caption_error_code": None,
    }
    if not generate_captions:
        result["tag_source"] = "skipped"
    if not generate_captions and not analyze_colors:
        return result

    try:
        import cv2
        import numpy as _np
        from pb_studio.video.moondream_wrapper import (
            compute_color_features,
            extract_dominant_colors_with_weights,
        )

        # Frames sammeln (CPU)
        cap = cv2.VideoCapture(video_path)
        frames_rgb = []
        try:
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total > 0:
                indices = [max(0, total // 4), max(0, total // 2), max(0, total * 3 // 4)]
                indices = sorted(list(set(indices)))
                for idx in indices:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        frames_rgb.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        finally:
            cap.release()

        if frames_rgb:
            # 1. Dominante Farben (KMeans, CPU)
            if analyze_colors:
                combined_rgb = _np.vstack(frames_rgb)
                dominant_colors, color_weights = extract_dominant_colors_with_weights(
                    combined_rgb,
                    k=5,
                )
                result["dominant_colors"] = dominant_colors
                result.update(compute_color_features(dominant_colors, color_weights))
                result["stage_status"]["colors"] = "completed"
                if on_colors_completed is not None:
                    on_colors_completed(deepcopy(result))

            if not generate_captions:
                logger.info(
                    "KMeans: %s colors, Captioning uebersprungen fuer clip %s",
                    len(result["dominant_colors"]),
                    clip_id,
                )
                return result

            # 2. Tags extrahieren
            all_tags = []
            seen_tags = set()
            tag_sources = []
            caption_attempts = []
            first_contributor = None
            caption_error_code: Optional[str] = None
            caption_error_message: Optional[str] = None

            from pb_studio.config_manager import ConfigManager
            current_mode = ConfigManager().get("ai", {}).get("default_mode", "balance")

            from pb_studio.video.lmstudio_vision_wrapper import (
                VisionTagExtractionResult,
                extract_tag_result_via_lmstudio_async,
            )
            from pb_studio.video.moondream import onnx_models_available as moondream_onnx_models_available

            moondream_frames_to_run = []
            caption_loop = asyncio.get_running_loop()
            caption_started_at = caption_loop.time()
            caption_deadline = caption_started_at + CAPTION_STAGE_TIMEOUT_SECONDS
            caption_progress: dict[str, Any] = {
                "started_at": caption_started_at,
                "phase": "LM Studio",
                "phase_started_at": caption_started_at,
                "phase_budget_seconds": CAPTION_STAGE_TIMEOUT_SECONDS,
                "phase_total_frames": len(frames_rgb),
                "phase_completed_frames": 0,
                "phase_active_frame": 1,
                "phase_progress_start": CAPTION_PROGRESS_START_PERCENT,
                "phase_progress_end": CAPTION_PRIMARY_PROGRESS_END_PERCENT,
                "reported_percent": CAPTION_PROGRESS_START_PERCENT,
            }
            caption_timeout_error: Optional[str] = None

            def caption_remaining_seconds() -> float:
                return max(0.0, caption_deadline - caption_loop.time())

            async def run_lm_studio_frames() -> None:
                nonlocal first_contributor, caption_error_code, caption_error_message
                for frame_number, f_rgb in enumerate(frames_rgb, start=1):
                    caption_progress["phase_active_frame"] = frame_number
                    extraction = await extract_tag_result_via_lmstudio_async(
                        f_rgb,
                        mode=current_mode,
                    )
                    if isinstance(extraction, VisionTagExtractionResult):
                        tags = list(extraction.tags)
                        selection = extraction.selection_receipt
                        caption_attempts.extend(extraction.attempts)
                        if extraction.error_code:
                            caption_error_code = extraction.error_code
                            caption_error_message = extraction.error_message
                    else:
                        tags, used_model = extraction
                        selection = None
                    caption_progress["phase_completed_frames"] = frame_number
                    if tags:
                        for tag in tags:
                            if tag not in seen_tags:
                                all_tags.append(tag)
                                seen_tags.add(tag)
                        if selection is not None:
                            contributor = (selection.provider, selection.model_id)
                            if first_contributor is None:
                                first_contributor = contributor
                            source_label = f"{selection.provider}:{selection.model_id}"
                        else:
                            source_label = str(used_model)
                        if source_label not in tag_sources:
                            tag_sources.append(source_label)
                    else:
                        moondream_frames_to_run.append(f_rgb)

            await _publish_caption_progress(
                clip_id,
                step="captions",
                percent=CAPTION_PROGRESS_START_PERCENT,
                status="running",
                message=f"Vision-Analyse startet (0/{len(frames_rgb)} Frames)",
            )
            heartbeat_task = asyncio.create_task(
                _caption_progress_heartbeat(
                    clip_id,
                    caption_progress,
                )
            )
            try:
                remaining = caption_remaining_seconds()
                if remaining <= 0.0:
                    raise asyncio.TimeoutError
                await asyncio.wait_for(
                    run_lm_studio_frames(),
                    timeout=remaining,
                )
            except asyncio.TimeoutError:
                caption_timeout_error = (
                    "Captioning-Gesamtdeadline von "
                    f"{CAPTION_STAGE_TIMEOUT_SECONDS:.0f}s waehrend LM Studio erreicht"
                )
                completed = int(caption_progress["phase_completed_frames"])
                moondream_frames_to_run.extend(frames_rgb[completed:])
                logger.warning(
                    "%s fuer clip %s",
                    caption_timeout_error,
                    clip_id,
                )
                await _publish_caption_progress(
                    clip_id,
                    step="captions_primary_timeout",
                    percent=float(caption_progress["reported_percent"]),
                    status="running",
                    message=caption_timeout_error,
                )

            # Moondream Fallback falls LM Studio keine Tags geliefert hat (GPU)
            if moondream_frames_to_run and caption_remaining_seconds() <= 0.0:
                caption_timeout_error = (
                    caption_timeout_error
                    or "Captioning-Gesamtdeadline von "
                    f"{CAPTION_STAGE_TIMEOUT_SECONDS:.0f}s vor Moondream erreicht"
                )
                logger.warning("%s fuer clip %s", caption_timeout_error, clip_id)
                await publish_event("llm_status", {
                    "model": "Moondream2 (ONNX)",
                    "provider": "Local GPU (DirectML)",
                    "status": "failed",
                    "percent": 0.0,
                    "clip_id": clip_id,
                })
            elif moondream_frames_to_run and not moondream_onnx_models_available():
                # Audit-Fix (2026-07-10): ONNX-Modelldateien fehlen (nur .pt-Checkpoint
                # vorhanden, kein CPU-Fallback erlaubt - IRON RULE). Vorher wurde hier
                # trotzdem with_gpu_task gestartet, das lautlos 0 Tags lieferte, aber
                # danach "active"/100% als Erfolg publizierte - falsches Erfolgssignal.
                logger.info(
                    "Moondream ONNX-Modelle nicht gefunden - GPU-Fallback uebersprungen "
                    "(kein CPU-Fallback erlaubt, IRON RULE)."
                )
                await publish_event("llm_status", {
                    "model": "Moondream2 (ONNX)",
                    "provider": "Local GPU (DirectML)",
                    "status": "unavailable",
                    "percent": 0.0,
                    "clip_id": clip_id,
                })
            elif moondream_frames_to_run:
                moondream_worker_detached = False
                moondream_worker_started = asyncio.Event()
                moondream_worker_finished = False
                try:
                    remaining = caption_remaining_seconds()
                    caption_progress.update({
                        "phase": "Moondream",
                        "phase_started_at": caption_loop.time(),
                        "phase_budget_seconds": remaining,
                        "phase_total_frames": len(moondream_frames_to_run),
                        "phase_completed_frames": 0,
                        "phase_active_frame": 1,
                        "phase_progress_start": CAPTION_PRIMARY_PROGRESS_END_PERCENT,
                        "phase_progress_end": CAPTION_PROGRESS_END_PERCENT,
                    })

                    await publish_event("llm_status", {
                        "model": "Moondream2 (ONNX)",
                        "provider": "Local GPU (DirectML)",
                        "status": "loading",
                        "percent": 50.0,
                        "clip_id": clip_id,
                    })

                    remaining = caption_remaining_seconds()
                    if remaining <= 0.0:
                        raise asyncio.TimeoutError
                    caption_attempts.append({
                        "provider": "directml",
                        "model_id": "moondream_fp16",
                        "task": "video_captioning",
                        "mode": current_mode,
                        "required_capabilities": ["vision"],
                        "verified_capabilities": ["vision", "directml"],
                        "source": "moondream_onnx_fallback",
                        "reason": "LM Studio produced no retained tags",
                        "selected_at": utc_now_rfc3339(),
                    })
                    result["caption_attempts"] = deepcopy(caption_attempts)
                    if on_caption_attempted is not None:
                        on_caption_attempted(deepcopy(result))
                    moondream_tags_list = await asyncio.wait_for(
                        with_gpu_task(
                            _run_moondream_inference_on_frames,
                            moondream_frames_to_run,
                            model_id="moondream_fp16",
                            timeout_seconds=remaining,
                            worker_started_event=moondream_worker_started,
                        ),
                        timeout=remaining,
                    )
                    moondream_worker_finished = True
                    caption_progress["phase_completed_frames"] = len(
                        moondream_frames_to_run
                    )
                    caption_progress["phase_active_frame"] = len(
                        moondream_frames_to_run
                    )
                    used_model = "moondream"

                    collected_any = any(tags for tags in moondream_tags_list)
                    await publish_event("llm_status", {
                        "model": "Moondream2 (ONNX)",
                        "provider": "Local GPU (DirectML)",
                        "status": "active" if collected_any else "failed",
                        "percent": 100.0 if collected_any else 0.0,
                        "clip_id": clip_id,
                    })

                    for tags in moondream_tags_list:
                        if tags:
                            for tag in tags:
                                if tag not in seen_tags:
                                    all_tags.append(tag)
                                    seen_tags.add(tag)
                            if used_model not in tag_sources:
                                tag_sources.append(used_model)
                            if first_contributor is None:
                                first_contributor = ("directml", "moondream_fp16")
                except asyncio.CancelledError:
                    # with_gpu_task may keep the physical worker alive until its
                    # protected cleanup finishes. Do not claim idle meanwhile.
                    moondream_worker_detached = (
                        moondream_worker_started.is_set()
                        and not moondream_worker_finished
                    )
                    raise
                except Exception as moondream_err:
                    if isinstance(moondream_err, (asyncio.TimeoutError, TimeoutError)):
                        # with_gpu_task keeps a timed-out thread alive under the GPU
                        # lock until physical cleanup completes. Keep the truthful
                        # failed state instead of publishing a premature idle state.
                        moondream_worker_detached = (
                            moondream_worker_started.is_set()
                            and not moondream_worker_finished
                        )
                        caption_timeout_error = (
                            "Captioning-Gesamtdeadline von "
                            f"{CAPTION_STAGE_TIMEOUT_SECONDS:.0f}s waehrend Moondream erreicht"
                        )
                    # Log ZUERST — publish darf die Root-Cause nie maskieren
                    logger.warning(f"Moondream Fallback GPU-Inferenz fehlgeschlagen: {moondream_err}")
                    try:
                        await publish_event("llm_status", {
                            "model": "Moondream2 (ONNX)",
                            "provider": "Local GPU (DirectML)",
                            "status": "failed",
                            "percent": 0.0,
                            "clip_id": clip_id,
                        })
                    except Exception:
                        logger.debug("llm_status publish nach Moondream-Fehler fehlgeschlagen")
                finally:
                    # Review-Fix MEDIUM (2026-07-09): Terminal-State, damit das
                    # Widget nach synchronem Ende nicht dauerhaft "Aktiv" zeigt.
                    if not moondream_worker_detached:
                        try:
                            await publish_event("llm_status", {
                                "model": "none",
                                "provider": "Local GPU (DirectML)",
                                "status": "idle",
                                "percent": 0.0,
                                "clip_id": clip_id,
                            })
                        except Exception:
                            pass

            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

            result["tags"] = all_tags[:10]
            result["tag_source"] = "+".join(tag_sources) if tag_sources else "none"
            if first_contributor is not None:
                result["caption_provider"], result["caption_model_id"] = first_contributor
            result["caption_attempts"] = caption_attempts
            if result["tags"] and caption_timeout_error is None:
                result["stage_status"]["captions"] = "completed"
                result["stage_errors"].pop("captions", None)
            elif result["tags"]:
                result["stage_status"]["captions"] = "partial"
                result["stage_errors"]["captions"] = caption_timeout_error
            else:
                result["stage_status"]["captions"] = (
                    "unavailable"
                    if caption_error_code in {
                        "model_failover_exhausted", "provider_cooldown"
                    }
                    else "failed"
                )
                result["caption_error_code"] = (
                    "caption_provider_unavailable"
                    if result["stage_status"]["captions"] == "unavailable"
                    else "caption_generation_failed"
                )
                result["stage_errors"]["captions"] = (
                    caption_timeout_error
                    or caption_error_message
                    or "Keine Tags von verfuegbarem Vision-Provider erzeugt"
                )

            # Review-Fix MEDIUM (2026-07-09): Terminal-State auch fuer den
            # reinen LM-Studio-Pfad (Wrapper endet mit "active").
            if not moondream_frames_to_run:
                try:
                    await publish_event("llm_status", {
                        "model": "none",
                        "provider": "LM Studio",
                        "status": "idle",
                        "percent": 0.0,
                        "clip_id": clip_id,
                    })
                except Exception:
                    pass

            logger.info(
                f"KMeans+LMStudio/Moondream-Split: {len(result['dominant_colors'])} colors, "
                f"{len(result['tags'])} tags ({result['tag_source']}) fuer clip {clip_id}"
            )
        else:
            result["dominant_colors"] = []
            result["tags"] = []
            result["tag_source"] = "none"
            if analyze_colors:
                result["stage_errors"]["colors"] = (
                    "Keine lesbaren Frames fuer Farbanalyse"
                )
            if generate_captions:
                result["stage_errors"]["captions"] = (
                    "Keine lesbaren Frames fuer Captioning"
                )

    except asyncio.CancelledError:
        heartbeat_task = locals().get("heartbeat_task")
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        raise
    except Exception as e:
        heartbeat_task = locals().get("heartbeat_task")
        if heartbeat_task is not None and not heartbeat_task.done():
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        logger.warning(f"Color/Tag-Analyse fehlgeschlagen (unkritisch): {e}")
        result["tags"] = []
        result["tag_source"] = "error"
        if analyze_colors and result["stage_status"]["colors"] != "completed":
            result["stage_status"]["colors"] = "failed"
            result["stage_errors"]["colors"] = str(e)
        if generate_captions:
            result["stage_status"]["captions"] = "failed"
            result["stage_errors"]["captions"] = str(e)

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
