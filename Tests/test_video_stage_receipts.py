"""OBJ77 Wave-1 contracts for durable video StageReceipts."""

from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from backend.schemas.video_schemas import VideoAnalyzeRequest
from pb_studio.core.stage_receipts import (
    canonical_sha256,
    create_stage_receipt,
    receipt_to_dict,
    transition_stage_receipt,
)


STAGES = ("scenes", "motion", "embedding", "colors", "captions", "audio_key")


def _fingerprints():
    return {stage: ("a" * 64, "b" * 64) for stage in STAGES}


def test_fresh_request_creates_requested_and_skipped_receipts():
    from backend.routers.video_router import _build_video_request_receipts

    request = VideoAnalyzeRequest(
        clip_id=7,
        detect_scenes=True,
        analyze_motion=False,
        generate_embeddings=False,
        analyze_colors=True,
        generate_captions=False,
        analyze_audio_key=False,
    )
    receipts = _build_video_request_receipts(
        request=request,
        run_stage={stage: stage in {"scenes", "colors"} for stage in STAGES},
        cached={},
        fingerprints=_fingerprints(),
        correlation_id=str(uuid4()),
    )

    assert receipts["scenes"].requested is True
    assert receipts["scenes"].status == "running"
    assert receipts["colors"].requested is True
    assert receipts["colors"].status == "running"
    for stage in {"motion", "embedding", "captions", "audio_key"}:
        assert receipts[stage].requested is False
        assert receipts[stage].status == "skipped"


def test_requested_unavailable_uses_shared_aggregate_and_typed_reason():
    from backend.routers.video_router import (
        _terminalize_video_stage_receipt,
        _video_receipt_truth,
    )

    correlation_id = str(uuid4())
    receipts = {
        stage: transition_stage_receipt(
            create_stage_receipt(
                stage,
                requested=True,
                input_fingerprint="a" * 64,
                config_fingerprint="b" * 64,
                correlation_id=correlation_id,
            ),
            "running",
        )
        for stage in ("scenes", "captions")
    }
    snapshot = {
        "scene_count": 1,
        "scenes": [{"start_time": 0.0, "end_time": 1.0}],
        "tags": [],
        "tag_source": "none",
    }
    _terminalize_video_stage_receipt(
        receipts,
        "scenes",
        snapshot,
        "completed",
        None,
    )
    _terminalize_video_stage_receipt(
        receipts,
        "captions",
        snapshot,
        "unavailable",
        "No compatible vision provider",
        error_code="caption_provider_unavailable",
    )

    status, stage_status, errors = _video_receipt_truth(
        receipts,
        requested_stage_ids=frozenset({"scenes", "captions"}),
    )
    assert status == "partial"
    assert stage_status == {"scenes": "completed", "captions": "unavailable"}
    assert errors["captions"] == "No compatible vision provider"
    assert receipts["captions"].error_code == "caption_provider_unavailable"


def test_all_requested_unavailable_is_failed_but_unrequested_does_not_count():
    from backend.routers.video_router import _video_receipt_truth

    correlation_id = str(uuid4())
    running = transition_stage_receipt(
        create_stage_receipt(
            "captions",
            requested=True,
            input_fingerprint="a" * 64,
            config_fingerprint="b" * 64,
            correlation_id=correlation_id,
        ),
        "running",
    )
    unavailable = transition_stage_receipt(
        running,
        "unavailable",
        error_code="caption_provider_unavailable",
        error_message="No provider",
    )
    receipts = {
        "captions": unavailable,
        "motion": create_stage_receipt(
            "motion",
            requested=False,
            input_fingerprint="a" * 64,
            config_fingerprint="b" * 64,
            correlation_id=correlation_id,
        ),
    }

    status, _, _ = _video_receipt_truth(
        receipts,
        requested_stage_ids=frozenset({"captions"}),
    )
    assert status == "failed"


def test_completed_multifield_artifact_uses_canonical_stage_payload():
    from backend.routers.video_router import _video_stage_artifact

    snapshot = {
        "scene_count": 1,
        "scenes": [{"start_time": 0.0, "end_time": 2.0}],
    }
    artifact_ref, artifact = _video_stage_artifact("scenes", snapshot)

    assert artifact_ref == "ai_data_json.stage_artifacts.scenes"
    assert artifact == {
        "scene_count": 1,
        "scenes": [{"start_time": 0.0, "end_time": 2.0}],
    }
    assert canonical_sha256(artifact) == canonical_sha256(deepcopy(artifact))


def test_v1_completed_receipt_reuse_requires_exact_fingerprints_and_artifact_hash():
    from backend.routers.video_router import _video_cached_receipt_artifact_is_valid

    artifact = {
        "scene_count": 1,
        "scenes": [{"start_time": 0.0, "end_time": 2.0}],
    }
    cached = {
        **artifact,
        "stage_artifacts": {"scenes": artifact},
    }
    receipt = transition_stage_receipt(
        transition_stage_receipt(
            create_stage_receipt(
                "scenes",
                requested=True,
                input_fingerprint="a" * 64,
                config_fingerprint="b" * 64,
            ),
            "running",
        ),
        "completed",
        artifact_ref="ai_data_json.stage_artifacts.scenes",
        artifact=artifact,
    )

    assert _video_cached_receipt_artifact_is_valid(
        "scenes",
        receipt,
        cached,
        expected_input_fingerprint="a" * 64,
        expected_config_fingerprint="b" * 64,
    )
    tampered = deepcopy(cached)
    tampered["scenes"][0]["end_time"] = 3.0
    tampered["stage_artifacts"]["scenes"] = {
        "scene_count": 1,
        "scenes": tampered["scenes"],
    }
    assert not _video_cached_receipt_artifact_is_valid(
        "scenes",
        receipt,
        tampered,
        expected_input_fingerprint="a" * 64,
        expected_config_fingerprint="b" * 64,
    )
    assert not _video_cached_receipt_artifact_is_valid(
        "scenes",
        receipt,
        cached,
        expected_input_fingerprint="c" * 64,
        expected_config_fingerprint="b" * 64,
    )

    missing_referenced_artifact = deepcopy(cached)
    missing_referenced_artifact["stage_artifacts"] = {}
    assert not _video_cached_receipt_artifact_is_valid(
        "scenes",
        receipt,
        missing_referenced_artifact,
        expected_input_fingerprint="a" * 64,
        expected_config_fingerprint="b" * 64,
    )

    mismatched_referenced_artifact = deepcopy(cached)
    mismatched_referenced_artifact["stage_artifacts"]["scenes"] = {
        "scene_count": 1,
        "scenes": [{"start_time": 0.0, "end_time": 9.0}],
    }
    assert not _video_cached_receipt_artifact_is_valid(
        "scenes",
        receipt,
        mismatched_referenced_artifact,
        expected_input_fingerprint="a" * 64,
        expected_config_fingerprint="b" * 64,
    )


def test_caption_receipt_persists_provider_model_attempts_and_correlation():
    from pb_studio.ai.model_registry import ModelSelectionReceipt
    from backend.routers.video_router import _terminalize_video_stage_receipt

    correlation_id = str(uuid4())
    selection = ModelSelectionReceipt(
        provider="lmstudio",
        model_id="qwen-vl",
        task="video_captioning",
        mode="balance",
        required_capabilities=("vision",),
        verified_capabilities=("vision",),
        source="live_inventory",
        reason="selected",
        selected_at="2026-08-12T10:00:00Z",
    )
    receipt = transition_stage_receipt(
        create_stage_receipt(
            "captions",
            requested=True,
            input_fingerprint="a" * 64,
            config_fingerprint="b" * 64,
            correlation_id=correlation_id,
        ),
        "running",
    )
    receipts = {"captions": receipt}
    snapshot = {
        "tags": ["club", "neon"],
        "tag_source": "lmstudio:qwen-vl",
        "caption_provider": "lmstudio",
        "caption_model_id": "qwen-vl",
        "caption_attempts": [selection],
    }

    _terminalize_video_stage_receipt(
        receipts,
        "captions",
        snapshot,
        "completed",
        None,
    )

    serialized = receipt_to_dict(receipts["captions"])
    assert serialized["provider"] == "lmstudio"
    assert serialized["model_id"] == "qwen-vl"
    assert serialized["correlation_id"] == correlation_id
    assert [attempt["model_id"] for attempt in serialized["attempts"]] == ["qwen-vl"]
