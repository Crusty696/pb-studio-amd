from __future__ import annotations

import importlib

import pytest


def _contract():
    try:
        return importlib.import_module("pb_studio.core.stage_receipts")
    except ModuleNotFoundError as exc:
        if exc.name == "pb_studio.core.stage_receipts":
            pytest.fail("Wave-1 status engine is missing: pb_studio.core.stage_receipts")
        raise


def _receipt(
    stage_id: str,
    status: str,
    *,
    requested: bool = True,
    artifact_valid: bool | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict[str, object]:
    return {
        "receipt_version": 1,
        "stage_id": stage_id,
        "requested": requested,
        "status": status,
        "input_fingerprint": None,
        "config_fingerprint": None,
        "artifact_ref": f"ai_data_json.{stage_id}" if artifact_valid else None,
        "artifact_sha256": "a" * 64 if artifact_valid else None,
        "artifact_valid": artifact_valid,
        "started_at_utc": "2026-08-12T10:00:00Z",
        "finished_at_utc": None if status == "running" else "2026-08-12T10:00:01Z",
        "error_code": error_code,
        "error_message": error_message,
        "provider": None,
        "model_id": None,
        "attempts": [],
        "correlation_id": "8c47ee26-cd59-4f61-bb3d-a7aa68c399eb",
    }


@pytest.mark.parametrize(
    ("receipts", "expected"),
    [
        ({"beats": _receipt("beats", "completed", artifact_valid=True)}, "completed"),
        (
            {
                "beats": _receipt("beats", "completed", artifact_valid=True),
                "structure": _receipt(
                    "structure",
                    "failed",
                    artifact_valid=False,
                    error_code="analysis_failed",
                    error_message="boom",
                ),
            },
            "partial",
        ),
        (
            {
                "captions": _receipt(
                    "captions",
                    "unavailable",
                    error_code="capability_unavailable",
                    error_message="no model",
                ),
                "motion": _receipt(
                    "motion",
                    "interrupted",
                    error_code="startup_recovery",
                    error_message="worker stopped",
                ),
            },
            "failed",
        ),
        (
            {
                "beats": _receipt("beats", "completed", artifact_valid=True),
                "captions": _receipt(
                    "captions",
                    "unavailable",
                    requested=False,
                    error_code="capability_unavailable",
                    error_message="no model",
                ),
            },
            "completed",
        ),
    ],
)
def test_requested_only_aggregate_status(receipts: dict[str, dict], expected: str):
    derive = getattr(_contract(), "derive_analysis_status", None)
    assert callable(derive), "derive_analysis_status is missing"
    assert derive(receipts) == expected


def test_requested_unavailable_requires_typed_reason():
    derive = getattr(_contract(), "derive_analysis_status", None)
    assert callable(derive), "derive_analysis_status is missing"
    receipts = {"captions": _receipt("captions", "unavailable")}

    with pytest.raises(ValueError, match="unavailable|error_code|error_message"):
        derive(receipts)


def test_retry_selects_only_missing_failed_interrupted_and_new_unavailable():
    select_retry = getattr(_contract(), "select_retry_stage_ids", None)
    assert callable(select_retry), "select_retry_stage_ids is missing"
    receipts = {
        "beats": _receipt("beats", "completed", artifact_valid=True),
        "structure": _receipt(
            "structure",
            "failed",
            error_code="analysis_failed",
            error_message="boom",
        ),
        "spectral": _receipt(
            "spectral",
            "interrupted",
            error_code="startup_recovery",
            error_message="worker stopped",
        ),
        "captions": _receipt(
            "captions",
            "unavailable",
            error_code="capability_unavailable",
            error_message="no model",
        ),
        "colors": _receipt("colors", "skipped", requested=False),
    }
    requested = {"beats", "structure", "spectral", "captions", "motion"}

    ordinary_retry = set(select_retry(receipts, requested_stage_ids=requested))
    newly_requested_retry = set(
        select_retry(
            receipts,
            requested_stage_ids=requested,
            newly_requested_unavailable={"captions"},
        )
    )

    assert ordinary_retry == {"structure", "spectral", "motion"}
    assert newly_requested_retry == {"structure", "spectral", "captions", "motion"}
    assert "beats" not in newly_requested_retry
    assert "colors" not in newly_requested_retry


def test_receipt_dictionary_key_must_match_stage_id():
    derive = getattr(_contract(), "derive_analysis_status", None)
    assert callable(derive), "derive_analysis_status is missing"

    with pytest.raises(ValueError, match="stage_id|key"):
        derive({"beats": _receipt("motion", "completed", artifact_valid=True)})
