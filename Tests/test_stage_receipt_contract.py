from __future__ import annotations

import importlib
from dataclasses import asdict, is_dataclass
from datetime import datetime

import pytest


RECEIPT_FIELDS = {
    "receipt_version",
    "stage_id",
    "requested",
    "status",
    "input_fingerprint",
    "config_fingerprint",
    "artifact_ref",
    "artifact_sha256",
    "artifact_valid",
    "started_at_utc",
    "finished_at_utc",
    "error_code",
    "error_message",
    "provider",
    "model_id",
    "attempts",
    "correlation_id",
}

ATTEMPT_FIELDS = {
    "provider",
    "model_id",
    "task",
    "mode",
    "required_capabilities",
    "verified_capabilities",
    "source",
    "reason",
    "selected_at",
}


def _import(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name == name:
            pytest.fail(f"Wave-1 contract module is missing: {name}")
        raise


def _field_names(model: type) -> set[str]:
    fields = getattr(model, "model_fields", None)
    assert fields is not None, f"{model.__name__} must be a Pydantic v2 model"
    return set(fields)


def _to_dict(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if is_dataclass(value):
        return asdict(value)
    raise AssertionError(f"Receipt is not serializable: {type(value)!r}")


def test_stage_receipt_and_attempt_models_have_exact_additive_fields():
    schemas = _import("backend.schemas.stage_receipt")

    assert _field_names(schemas.StageReceipt) == RECEIPT_FIELDS
    assert _field_names(schemas.StageAttemptReceipt) == ATTEMPT_FIELDS


@pytest.mark.parametrize(
    ("module_name", "model_name"),
    [
        ("backend.schemas.audio_schemas", "AudioClipInfo"),
        ("backend.schemas.audio_schemas", "AudioAnalysisResult"),
        ("backend.schemas.video_schemas", "VideoClipInfo"),
        ("backend.schemas.video_schemas", "VideoAnalysisResult"),
    ],
)
def test_audio_and_video_transport_models_expose_stage_receipts(
    module_name: str,
    model_name: str,
):
    module = _import(module_name)
    model = getattr(module, model_name)
    fields = getattr(model, "model_fields")

    assert "stage_receipts" in fields
    assert fields["stage_receipts"].default_factory is dict


def test_legacy_projection_is_v0_and_preserves_requested_truth():
    contract = _import("pb_studio.core.stage_receipts")
    projector = getattr(contract, "project_legacy_stage_receipts", None)
    assert callable(projector), "project_legacy_stage_receipts is missing"

    projected = projector(
        stage_status={
            "beats": "completed",
            "captions": "skipped",
            "motion": "failed",
        },
        stage_errors={"motion": "model unavailable"},
    )
    receipts = {key: _to_dict(value) for key, value in projected.items()}

    assert set(receipts) == {"beats", "captions", "motion"}
    assert all(receipt["receipt_version"] == 0 for receipt in receipts.values())
    assert receipts["beats"]["requested"] is True
    assert receipts["captions"]["requested"] is False
    assert receipts["motion"]["requested"] is True
    assert receipts["motion"]["error_message"] == "model unavailable"
    for stage_id, receipt in receipts.items():
        assert receipt["stage_id"] == stage_id
        assert set(receipt) == RECEIPT_FIELDS


@pytest.mark.parametrize(
    "migrator_name",
    ["migrate_audio_ai_data", "migrate_video_ai_data"],
)
def test_json_blob_reader_projects_v0_receipts_without_mutating_legacy_input(
    migrator_name: str,
):
    schema = _import("pb_studio.data.schemas.media_json_schema")
    legacy = {"analysis_status": "partial", "stage_status": {"beats": "completed"}}
    before = {"analysis_status": "partial", "stage_status": {"beats": "completed"}}

    migrated = getattr(schema, migrator_name)(legacy)

    assert legacy == before, "Reading a legacy blob must not rewrite the source object"
    assert migrated is not legacy
    assert set(migrated["stage_receipts"]) == {"beats"}
    assert migrated["stage_receipts"]["beats"]["receipt_version"] == 0
    assert migrated["stage_receipts"]["beats"]["requested"] is True
    assert migrated["stage_receipts"]["beats"]["status"] == "completed"
    assert migrated[schema.SCHEMA_VERSION_KEY] == schema.CURRENT_SCHEMA_VERSION
    assert schema.CURRENT_SCHEMA_VERSION >= 2


def test_canonical_hash_is_order_independent_and_payload_sensitive():
    contract = _import("pb_studio.core.stage_receipts")

    first = contract.canonical_sha256({"b": [2, 1], "a": {"x": True}})
    reordered = contract.canonical_sha256({"a": {"x": True}, "b": [2, 1]})
    changed = contract.canonical_sha256({"a": {"x": False}, "b": [2, 1]})

    assert first == reordered
    assert first != changed
    assert len(first) == 64


def test_utc_timestamp_and_attempt_roundtrip_match_registry_receipt():
    contract = _import("pb_studio.core.stage_receipts")
    registry = _import("pb_studio.ai.model_registry")
    selection = registry.ModelSelectionReceipt(
        provider="lmstudio",
        model_id="vision-model",
        task="video_captioning",
        mode="quality",
        required_capabilities=("vision",),
        verified_capabilities=("chat", "vision"),
        source="explicit_override",
        reason="test receipt",
        selected_at="2026-08-12T10:00:00+00:00",
    )
    timestamp = contract.utc_now_rfc3339()
    datetime.fromisoformat(timestamp[:-1] + "+00:00")

    receipt = contract.create_stage_receipt(
        "captions", requested=True, attempts=[selection]
    )
    serialized = contract.receipt_to_dict(receipt)

    assert timestamp.endswith("Z")
    assert serialized["attempts"] == [{
        **selection.to_dict(),
        "required_capabilities": ["vision"],
        "verified_capabilities": ["chat", "vision"],
        "selected_at": "2026-08-12T10:00:00Z",
    }]


def test_artifact_validation_accepts_exact_payload_and_rejects_missing_or_tampered():
    contract = _import("pb_studio.core.stage_receipts")
    artifact = {"bpm": 128.0, "beats": [0.0, 0.5]}
    pending = contract.create_stage_receipt("beats", requested=True)
    running = contract.transition_stage_receipt(pending, "running")
    completed = contract.transition_stage_receipt(
        running,
        "completed",
        artifact_ref="ai_data_json.beats",
        artifact=artifact,
    )

    assert contract.validate_receipt_artifact(completed, {"beats": artifact}) is True
    assert contract.validate_receipt_artifact(completed, {}) is False
    assert (
        contract.validate_receipt_artifact(
            completed, {"beats": {"bpm": 129.0, "beats": [0.0, 0.5]}}
        )
        is False
    )


def test_completed_receipt_without_validated_artifact_is_rejected():
    contract = _import("pb_studio.core.stage_receipts")
    running = contract.transition_stage_receipt(
        contract.create_stage_receipt("beats", requested=True), "running"
    )

    with pytest.raises(ValueError, match="artifact"):
        contract.transition_stage_receipt(running, "completed")


def test_versioned_and_nested_blob_reads_are_deep_copy_non_mutating():
    schema = _import("pb_studio.data.schemas.media_json_schema")
    source = {
        schema.SCHEMA_VERSION_KEY: schema.CURRENT_SCHEMA_VERSION,
        "stage_receipts": {},
        "nested": {"values": [1, 2]},
    }

    migrated = schema.migrate_audio_ai_data(source)
    migrated["nested"]["values"].append(3)

    assert source["nested"]["values"] == [1, 2]
    assert migrated is not source


def test_transport_receipt_typing_and_json_serialization():
    schemas = _import("backend.schemas.stage_receipt")
    attempt = {
        "provider": "lmstudio",
        "model_id": "vision-model",
        "task": "video_captioning",
        "mode": "quality",
        "required_capabilities": ["vision"],
        "verified_capabilities": ["vision"],
        "source": "live_fallback",
        "reason": "available",
        "selected_at": "2026-08-12T10:00:00+00:00",
    }
    payload = {
        "receipt_version": 1,
        "stage_id": "captions",
        "requested": True,
        "status": "unavailable",
        "input_fingerprint": None,
        "config_fingerprint": None,
        "artifact_ref": None,
        "artifact_sha256": None,
        "artifact_valid": None,
        "started_at_utc": "2026-08-12T10:00:00Z",
        "finished_at_utc": "2026-08-12T10:00:01Z",
        "error_code": "capability_unavailable",
        "error_message": "no usable model",
        "provider": "lmstudio",
        "model_id": "vision-model",
        "attempts": [attempt],
        "correlation_id": "8c47ee26-cd59-4f61-bb3d-a7aa68c399eb",
    }

    receipt = schemas.StageReceipt.model_validate(payload)

    assert isinstance(receipt.attempts[0], schemas.StageAttemptReceipt)
    serialized = receipt.model_dump(mode="json")
    assert serialized == {
        **payload,
        "attempts": [{**attempt, "selected_at": "2026-08-12T10:00:00Z"}],
    }


def _core_receipt_dataclass(contract, **overrides):
    values = {
        "receipt_version": 1,
        "stage_id": "beats",
        "requested": True,
        "status": "running",
        "input_fingerprint": None,
        "config_fingerprint": None,
        "artifact_ref": None,
        "artifact_sha256": None,
        "artifact_valid": None,
        "started_at_utc": "2026-08-12T10:00:00Z",
        "finished_at_utc": None,
        "error_code": None,
        "error_message": None,
        "provider": None,
        "model_id": None,
        "attempts": (),
        "correlation_id": "8c47ee26-cd59-4f61-bb3d-a7aa68c399eb",
    }
    values.update(overrides)
    return contract.StageReceipt(**values)


def test_direct_core_dataclasses_cannot_bypass_validation():
    contract = _import("pb_studio.core.stage_receipts")
    schemas = _import("backend.schemas.stage_receipt")
    with pytest.raises(ValueError, match="unavailable|error_code|error_message"):
        _core_receipt_dataclass(
            contract,
            status="unavailable",
            finished_at_utc="2026-08-12T10:00:01Z",
        )
    with pytest.raises(ValueError, match="provider|selected_at"):
        contract.StageAttemptReceipt(
            provider="",
            model_id="vision-model",
            task="video_captioning",
            mode="quality",
            required_capabilities=("vision",),
            verified_capabilities=("vision",),
            source="live_fallback",
            reason="available",
            selected_at="not-a-time",
        )
    with pytest.raises(ValueError, match="provider|selected_at"):
        schemas.StageAttemptReceipt(
            provider="",
            model_id="vision-model",
            task="video_captioning",
            mode="quality",
            required_capabilities=["vision"],
            verified_capabilities=["vision"],
            source="live_fallback",
            reason="available",
            selected_at="not-a-time",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("receipt_version", True),
        ("receipt_version", "1"),
        ("requested", 1),
        ("requested", "true"),
    ],
)
def test_core_and_pydantic_reject_coerced_version_and_requested_types(
    field: str, value: object
):
    contract = _import("pb_studio.core.stage_receipts")
    schemas = _import("backend.schemas.stage_receipt")
    core_payload = asdict(_core_receipt_dataclass(contract))
    core_payload[field] = value

    with pytest.raises((TypeError, ValueError)):
        contract.coerce_stage_receipt(core_payload)
    with pytest.raises(ValueError):
        schemas.StageReceipt.model_validate(core_payload)


def test_v1_requested_skipped_is_illegal():
    contract = _import("pb_studio.core.stage_receipts")

    with pytest.raises(ValueError, match="requested|skipped"):
        _core_receipt_dataclass(
            contract,
            status="skipped",
            finished_at_utc="2026-08-12T10:00:01Z",
        )


@pytest.mark.parametrize(
    ("initial", "target"),
    [
        ("pending", "completed"),
        ("pending", "partial"),
        ("pending", "skipped"),
        ("running", "running"),
        ("failed", "running"),
        ("interrupted", "running"),
        ("unavailable", "running"),
        ("partial", "running"),
        ("completed", "running"),
        ("skipped", "running"),
    ],
)
def test_transition_state_machine_rejects_illegal_or_terminal_changes(
    initial: str, target: str
):
    contract = _import("pb_studio.core.stage_receipts")
    if initial == "pending":
        receipt = contract.create_stage_receipt("beats", requested=True)
    elif initial == "running":
        receipt = contract.transition_stage_receipt(
            contract.create_stage_receipt("beats", requested=True), "running"
        )
    elif initial == "skipped":
        receipt = contract.create_stage_receipt("beats", requested=False)
    else:
        running = contract.transition_stage_receipt(
            contract.create_stage_receipt("beats", requested=True), "running"
        )
        if initial == "completed":
            receipt = contract.transition_stage_receipt(
                running,
                "completed",
                artifact_ref="ai_data_json.beats",
                artifact={"beats": [0.0]},
            )
        else:
            kwargs = (
                {
                    "error_code": "capability_unavailable",
                    "error_message": "not available",
                }
                if initial == "unavailable"
                else {}
            )
            receipt = contract.transition_stage_receipt(running, initial, **kwargs)

    with pytest.raises(ValueError, match="transition|immutable|terminal"):
        contract.transition_stage_receipt(receipt, target)


def test_only_documented_v1_transitions_are_accepted():
    contract = _import("pb_studio.core.stage_receipts")
    pending = contract.create_stage_receipt("beats", requested=True)

    assert contract.transition_stage_receipt(pending, "running").status == "running"
    for status in ("failed", "interrupted"):
        assert contract.transition_stage_receipt(pending, status).status == status
    assert (
        contract.transition_stage_receipt(
            pending,
            "unavailable",
            error_code="capability_unavailable",
            error_message="not available",
        ).status
        == "unavailable"
    )

    for status in ("partial", "failed", "interrupted"):
        running = contract.transition_stage_receipt(pending, "running")
        assert contract.transition_stage_receipt(running, status).status == status
    running = contract.transition_stage_receipt(pending, "running")
    assert (
        contract.transition_stage_receipt(
            running,
            "unavailable",
            error_code="capability_unavailable",
            error_message="not available",
        ).status
        == "unavailable"
    )


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-08-12Z",
        "2026-08-12 10:00:00Z",
        "2026-08-12T10:00Z",
        "2026-08-12T10:00:00+00:00",
    ],
)
def test_receipt_timestamps_require_full_rfc3339_utc_z(timestamp: str):
    contract = _import("pb_studio.core.stage_receipts")

    with pytest.raises(ValueError, match="RFC3339|timestamp|started_at"):
        _core_receipt_dataclass(contract, started_at_utc=timestamp)


def test_terminal_timestamp_cannot_precede_start():
    contract = _import("pb_studio.core.stage_receipts")

    with pytest.raises(ValueError, match="finished_at|started_at|before"):
        _core_receipt_dataclass(
            contract,
            status="failed",
            started_at_utc="2026-08-12T10:00:02Z",
            finished_at_utc="2026-08-12T10:00:01Z",
        )


@pytest.mark.parametrize("digest", ["A" * 64, "g" * 64, "a" * 63, "a" * 65])
def test_sha256_fields_require_exact_lowercase_hex(digest: str):
    contract = _import("pb_studio.core.stage_receipts")

    with pytest.raises(ValueError, match="SHA-256|sha256"):
        _core_receipt_dataclass(contract, input_fingerprint=digest)


@pytest.mark.parametrize("artifact", [{"value": float("nan")}, {"value": object()}])
def test_artifact_canonicalization_errors_are_invalid_not_exceptions(artifact: object):
    contract = _import("pb_studio.core.stage_receipts")
    receipt = _core_receipt_dataclass(
        contract,
        status="completed",
        artifact_ref="ai_data_json.beats",
        artifact_sha256="a" * 64,
        artifact_valid=True,
        finished_at_utc="2026-08-12T10:00:01Z",
    )

    assert contract.validate_receipt_artifact(receipt, {"beats": artifact}) is False


def test_video_clip_transport_accepts_running_aggregate_status():
    video_schemas = _import("backend.schemas.video_schemas")

    clip = video_schemas.VideoClipInfo(
        id=1,
        name="clip.mp4",
        path=r"C:\media\clip.mp4",
        duration_seconds=1.0,
        analysis_status="running",
    )

    assert clip.analysis_status == "running"
