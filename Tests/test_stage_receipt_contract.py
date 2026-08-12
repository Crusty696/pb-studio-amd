from __future__ import annotations

import importlib
from dataclasses import asdict, is_dataclass

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
def test_json_blob_reader_adds_empty_receipt_map_without_mutating_legacy_input(
    migrator_name: str,
):
    schema = _import("pb_studio.data.schemas.media_json_schema")
    legacy = {"analysis_status": "partial", "stage_status": {"beats": "completed"}}
    before = {"analysis_status": "partial", "stage_status": {"beats": "completed"}}

    migrated = getattr(schema, migrator_name)(legacy)

    assert legacy == before, "Reading a legacy blob must not rewrite the source object"
    assert migrated is not legacy
    assert migrated["stage_receipts"] == {}
    assert migrated[schema.SCHEMA_VERSION_KEY] == schema.CURRENT_SCHEMA_VERSION
    assert schema.CURRENT_SCHEMA_VERSION >= 2
