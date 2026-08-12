"""Pydantic transport models for the additive StageReceipt contract."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

from pb_studio.core.stage_receipts import (
    RECEIPT_VERSION,
    validate_receipt_map,
    validate_stage_receipt,
)


StageStatus = Literal[
    "pending",
    "running",
    "completed",
    "partial",
    "failed",
    "interrupted",
    "unavailable",
    "skipped",
    "missing",
]


class StageAttemptReceipt(BaseModel):
    """One typed model/provider attempt, field-compatible with the registry."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model_id: str
    task: str
    mode: str
    required_capabilities: list[str] = Field(default_factory=list)
    verified_capabilities: list[str] = Field(default_factory=list)
    source: str
    reason: str
    selected_at: str

    @field_validator("selected_at")
    @classmethod
    def normalize_selected_at(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise ValueError("selected_at must be timezone-aware RFC3339") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("selected_at must be timezone-aware RFC3339")
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        from pb_studio.core.stage_receipts import normalize_attempt

        normalize_attempt(self.model_dump(mode="python"))
        return self


class StageReceipt(BaseModel):
    """Serializable V1 receipt or nullable projected V0 legacy receipt."""

    model_config = ConfigDict(extra="forbid")

    receipt_version: StrictInt = RECEIPT_VERSION
    stage_id: str
    requested: StrictBool
    status: StageStatus
    input_fingerprint: str | None = None
    config_fingerprint: str | None = None
    artifact_ref: str | None = None
    artifact_sha256: str | None = None
    artifact_valid: bool | None = None
    started_at_utc: str | None = None
    finished_at_utc: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    provider: str | None = None
    model_id: str | None = None
    attempts: list[StageAttemptReceipt] = Field(default_factory=list)
    correlation_id: str | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        validate_stage_receipt(self.model_dump(mode="python"))
        return self


def validate_stage_receipt_mapping(
    receipts: dict[str, StageReceipt],
) -> dict[str, StageReceipt]:
    """Pydantic field validator shared by audio and video transport records."""

    validate_receipt_map(
        {stage_id: receipt.model_dump(mode="python") for stage_id, receipt in receipts.items()}
    )
    return receipts


__all__ = [
    "StageAttemptReceipt",
    "StageReceipt",
    "StageStatus",
    "validate_stage_receipt_mapping",
]
