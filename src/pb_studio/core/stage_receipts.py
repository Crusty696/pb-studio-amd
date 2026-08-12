"""Versioned analysis-stage receipts shared by audio and video pipelines.

The module is intentionally independent of FastAPI and persistence.  Routers
can therefore validate a complete receipt before committing it and before
publishing the corresponding SSE event.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
from uuid import UUID, uuid4


RECEIPT_VERSION = 1
LEGACY_RECEIPT_VERSION = 0

RECEIPT_FIELDS = frozenset(
    {
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
)

ATTEMPT_FIELDS = frozenset(
    {
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
)

_STATUSES = frozenset(
    {
        "pending",
        "running",
        "completed",
        "partial",
        "failed",
        "interrupted",
        "unavailable",
        "skipped",
        "missing",
    }
)
_TERMINAL_STATUSES = frozenset(
    {
        "completed",
        "partial",
        "failed",
        "interrupted",
        "unavailable",
        "skipped",
        "missing",
    }
)
_FAILED_STATUSES = frozenset(
    {"partial", "failed", "interrupted", "unavailable", "missing"}
)
_RETRY_STATUSES = frozenset({"missing", "failed", "interrupted"})
_ALLOWED_TRANSITIONS = {
    "pending": frozenset({"running", "failed", "interrupted", "unavailable"}),
    "running": frozenset(
        {"completed", "partial", "failed", "interrupted", "unavailable"}
    ),
}
_RFC3339_UTC_Z = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
_SHA256_LOWERCASE = re.compile(r"^[0-9a-f]{64}$")
_UNSET = object()


@dataclass(frozen=True, slots=True)
class StageAttemptReceipt:
    """One provider/model-selection attempt."""

    provider: str
    model_id: str
    task: str
    mode: str
    required_capabilities: tuple[str, ...]
    verified_capabilities: tuple[str, ...]
    source: str
    reason: str
    selected_at: str

    def __post_init__(self) -> None:
        _validate_attempt_instance(self)


@dataclass(frozen=True, slots=True)
class StageReceipt:
    """Persisted truth for one requested or explicitly skipped stage."""

    receipt_version: int
    stage_id: str
    requested: bool
    status: str
    input_fingerprint: str | None
    config_fingerprint: str | None
    artifact_ref: str | None
    artifact_sha256: str | None
    artifact_valid: bool | None
    started_at_utc: str | None
    finished_at_utc: str | None
    error_code: str | None
    error_message: str | None
    provider: str | None
    model_id: str | None
    attempts: tuple[StageAttemptReceipt, ...]
    correlation_id: str | None

    def __post_init__(self) -> None:
        _validate_stage_receipt_instance(self)


def utc_now_rfc3339() -> str:
    """Return the current UTC time in RFC3339 form with a literal ``Z``."""

    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _canonical_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _canonical_value(value.model_dump(mode="python"))
    if is_dataclass(value):
        return _canonical_value(asdict(value))
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("Canonical JSON mapping keys must be strings")
            normalized[key] = _canonical_value(item)
        return normalized
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized_items = [_canonical_value(item) for item in value]
        return sorted(
            normalized_items,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
        )
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Canonical timestamps must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, (UUID, Path)):
        return str(value)
    if isinstance(value, Enum):
        return _canonical_value(value.value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Canonical JSON rejects NaN and infinity")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported canonical JSON value: {type(value)!r}")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a value with stable ordering and no non-finite numbers."""

    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Hash canonical JSON using SHA-256."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def build_input_fingerprint(
    *,
    project_uuid: str,
    catalog_project_id: int,
    project_epoch: int,
    clip_id: int,
    media_sha256: str,
    stage_input_identity: Any,
) -> str:
    """Hash the immutable project/media/stage input identity."""

    return canonical_sha256(
        {
            "project_uuid": project_uuid,
            "catalog_project_id": catalog_project_id,
            "project_epoch": project_epoch,
            "clip_id": clip_id,
            "media_sha256": media_sha256,
            "stage_input_identity": stage_input_identity,
        }
    )


def build_config_fingerprint(
    *,
    stage_request_flags: Any,
    effective_config_identity: Any,
) -> str:
    """Hash the effective request/config/model-asset identity."""

    return canonical_sha256(
        {
            "stage_request_flags": stage_request_flags,
            "effective_config_identity": effective_config_identity,
        }
    )


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="python")
        if isinstance(dumped, Mapping):
            return dumped
    if is_dataclass(value):
        dumped = asdict(value)
        if isinstance(dumped, Mapping):
            return dumped
    raise TypeError(f"Expected mapping, Pydantic model or dataclass, got {type(value)!r}")


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must be non-empty")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _capability_tuple(value: Any, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TypeError(f"{field} must be a sequence of strings")
    return tuple(_required_text(item, field) for item in value)


def normalize_attempt(value: Any) -> StageAttemptReceipt:
    """Normalize a ModelSelectionReceipt-compatible attempt."""

    data = _as_mapping(value)
    missing = ATTEMPT_FIELDS.difference(data)
    extra = set(data).difference(ATTEMPT_FIELDS)
    if missing or extra:
        raise ValueError(
            f"Attempt fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    return StageAttemptReceipt(
        provider=_required_text(data["provider"], "provider"),
        model_id=_required_text(data["model_id"], "model_id"),
        task=_required_text(data["task"], "task"),
        mode=_required_text(data["mode"], "mode"),
        required_capabilities=_capability_tuple(
            data["required_capabilities"], "required_capabilities"
        ),
        verified_capabilities=_capability_tuple(
            data["verified_capabilities"], "verified_capabilities"
        ),
        source=_required_text(data["source"], "source"),
        reason=_required_text(data["reason"], "reason"),
        selected_at=_normalize_attempt_timestamp(data["selected_at"]),
    )


def _validate_attempt_instance(attempt: StageAttemptReceipt) -> None:
    for field in ("provider", "model_id", "task", "mode", "source", "reason"):
        if not isinstance(getattr(attempt, field), str):
            raise TypeError(f"{field} must be a string")
    if not isinstance(attempt.required_capabilities, tuple):
        raise TypeError("required_capabilities must be a tuple")
    if not isinstance(attempt.verified_capabilities, tuple):
        raise TypeError("verified_capabilities must be a tuple")
    _required_text(attempt.provider, "provider")
    _required_text(attempt.model_id, "model_id")
    _required_text(attempt.task, "task")
    _required_text(attempt.mode, "mode")
    _capability_tuple(attempt.required_capabilities, "required_capabilities")
    _capability_tuple(attempt.verified_capabilities, "verified_capabilities")
    _required_text(attempt.source, "source")
    _required_text(attempt.reason, "reason")
    _normalize_attempt_timestamp(attempt.selected_at)


def normalize_attempts(values: Iterable[Any] | None) -> tuple[StageAttemptReceipt, ...]:
    return tuple(normalize_attempt(value) for value in (values or ()))


def _normalize_timestamp(value: Any, field: str) -> str:
    text = _required_text(value, field)
    if _RFC3339_UTC_Z.fullmatch(text) is None:
        raise ValueError(f"{field} must be UTC RFC3339 with Z")
    try:
        datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be UTC RFC3339 with Z") from exc
    return text


def _normalize_attempt_timestamp(value: Any) -> str:
    """Accept the registry's ``+00:00`` form and persist canonical UTC ``Z``."""

    text = _required_text(value, "selected_at")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("selected_at must be timezone-aware RFC3339") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("selected_at must be timezone-aware RFC3339")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_optional_timestamp(value: str | None, field: str) -> None:
    if value is not None:
        _normalize_timestamp(value, field)


def _validate_sha256(value: str | None, field: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or _SHA256_LOWERCASE.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")


def _validate_uuid(value: str | None) -> None:
    if value is None:
        return
    try:
        UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("correlation_id must be a UUID") from exc


def coerce_stage_receipt(value: Any) -> StageReceipt:
    """Normalize any serialized receipt without changing its semantic fields."""

    data = _as_mapping(value)
    missing = RECEIPT_FIELDS.difference(data)
    extra = set(data).difference(RECEIPT_FIELDS)
    if missing or extra:
        raise ValueError(
            f"Receipt fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    if type(data["receipt_version"]) is not int:
        raise TypeError("receipt_version must be an exact int")
    if type(data["requested"]) is not bool:
        raise TypeError("requested must be an exact bool")
    return StageReceipt(
        receipt_version=data["receipt_version"],
        stage_id=_required_text(data["stage_id"], "stage_id"),
        requested=data["requested"],
        status=_required_text(data["status"], "status").lower(),
        input_fingerprint=_optional_text(data["input_fingerprint"]),
        config_fingerprint=_optional_text(data["config_fingerprint"]),
        artifact_ref=_optional_text(data["artifact_ref"]),
        artifact_sha256=_optional_text(data["artifact_sha256"]),
        artifact_valid=data["artifact_valid"],
        started_at_utc=_optional_text(data["started_at_utc"]),
        finished_at_utc=_optional_text(data["finished_at_utc"]),
        error_code=_optional_text(data["error_code"]),
        error_message=_optional_text(data["error_message"]),
        provider=_optional_text(data["provider"]),
        model_id=_optional_text(data["model_id"]),
        attempts=normalize_attempts(data["attempts"]),
        correlation_id=_optional_text(data["correlation_id"]),
    )


def validate_stage_receipt(value: Any) -> StageReceipt:
    """Reject internally inconsistent V1 receipts; allow nullable V0 legacy data."""

    return coerce_stage_receipt(value)


def _validate_stage_receipt_instance(receipt: StageReceipt) -> None:
    if type(receipt.receipt_version) is not int:
        raise TypeError("receipt_version must be an exact int")
    if type(receipt.requested) is not bool:
        raise TypeError("requested must be an exact bool")
    if not isinstance(receipt.stage_id, str) or not receipt.stage_id.strip():
        raise TypeError("stage_id must be a non-empty string")
    if not isinstance(receipt.status, str):
        raise TypeError("status must be a string")
    if not isinstance(receipt.attempts, tuple) or not all(
        isinstance(attempt, StageAttemptReceipt) for attempt in receipt.attempts
    ):
        raise TypeError("attempts must be a tuple of StageAttemptReceipt values")
    if receipt.receipt_version not in {LEGACY_RECEIPT_VERSION, RECEIPT_VERSION}:
        raise ValueError(f"Unsupported receipt_version={receipt.receipt_version}")
    if receipt.status not in _STATUSES:
        raise ValueError(f"Unsupported stage status: {receipt.status}")
    if receipt.artifact_valid is not None and not isinstance(receipt.artifact_valid, bool):
        raise TypeError("artifact_valid must be bool or None")
    _validate_sha256(receipt.input_fingerprint, "input_fingerprint")
    _validate_sha256(receipt.config_fingerprint, "config_fingerprint")
    _validate_sha256(receipt.artifact_sha256, "artifact_sha256")
    _validate_optional_timestamp(receipt.started_at_utc, "started_at_utc")
    _validate_optional_timestamp(receipt.finished_at_utc, "finished_at_utc")
    if receipt.started_at_utc is not None and receipt.finished_at_utc is not None:
        started = datetime.fromisoformat(receipt.started_at_utc[:-1] + "+00:00")
        finished = datetime.fromisoformat(receipt.finished_at_utc[:-1] + "+00:00")
        if finished < started:
            raise ValueError("finished_at_utc cannot be before started_at_utc")
    _validate_uuid(receipt.correlation_id)

    if receipt.receipt_version == LEGACY_RECEIPT_VERSION:
        return

    if receipt.status == "running":
        if receipt.started_at_utc is None:
            raise ValueError("running receipt requires started_at_utc")
        if receipt.finished_at_utc is not None:
            raise ValueError("running receipt cannot have finished_at_utc")
    elif receipt.status == "pending":
        if receipt.finished_at_utc is not None:
            raise ValueError(f"{receipt.status} receipt cannot have finished_at_utc")
    elif receipt.status in _TERMINAL_STATUSES and receipt.finished_at_utc is None:
        raise ValueError(f"terminal status {receipt.status} requires finished_at_utc")

    if receipt.requested and receipt.status == "unavailable":
        if not receipt.error_code or not receipt.error_message:
            raise ValueError(
                "requested unavailable receipt requires error_code and error_message"
            )
    if receipt.requested and receipt.status == "skipped":
        raise ValueError("requested V1 receipt cannot be skipped")
    if not receipt.requested and receipt.status not in {"skipped", "unavailable"}:
        raise ValueError("unrequested V1 receipt must be skipped or unavailable")

    if receipt.artifact_valid is True and (
        receipt.artifact_ref is None or receipt.artifact_sha256 is None
    ):
        raise ValueError("artifact_valid requires artifact_ref and artifact_sha256")
    if receipt.status == "completed" and (
        receipt.artifact_valid is not True
        or receipt.artifact_ref is None
        or receipt.artifact_sha256 is None
    ):
        raise ValueError(
            "completed receipt requires a valid artifact_ref and artifact_sha256"
        )


def receipt_to_dict(value: Any) -> dict[str, Any]:
    """Return the JSON transport representation of one validated receipt."""

    receipt = coerce_stage_receipt(value)
    data = asdict(receipt)
    data["attempts"] = [asdict(attempt) for attempt in receipt.attempts]
    for attempt in data["attempts"]:
        attempt["required_capabilities"] = list(attempt["required_capabilities"])
        attempt["verified_capabilities"] = list(attempt["verified_capabilities"])
    return data


def create_stage_receipt(
    stage_id: str,
    *,
    requested: bool,
    input_identity: Any | None = None,
    config_identity: Any | None = None,
    input_fingerprint: str | None = None,
    config_fingerprint: str | None = None,
    correlation_id: str | None = None,
    provider: str | None = None,
    model_id: str | None = None,
    attempts: Iterable[Any] | None = None,
) -> StageReceipt:
    """Create a pending requested receipt or a terminal skipped receipt."""

    if input_identity is not None and input_fingerprint is not None:
        raise ValueError("Provide input_identity or input_fingerprint, not both")
    if config_identity is not None and config_fingerprint is not None:
        raise ValueError("Provide config_identity or config_fingerprint, not both")
    now = utc_now_rfc3339() if not requested else None
    receipt = StageReceipt(
        receipt_version=RECEIPT_VERSION,
        stage_id=_required_text(stage_id, "stage_id"),
        requested=requested,
        status="pending" if requested else "skipped",
        input_fingerprint=(
            canonical_sha256(input_identity)
            if input_identity is not None
            else input_fingerprint
        ),
        config_fingerprint=(
            canonical_sha256(config_identity)
            if config_identity is not None
            else config_fingerprint
        ),
        artifact_ref=None,
        artifact_sha256=None,
        artifact_valid=None,
        started_at_utc=None,
        finished_at_utc=now,
        error_code=None,
        error_message=None,
        provider=_optional_text(provider),
        model_id=_optional_text(model_id),
        attempts=normalize_attempts(attempts),
        correlation_id=correlation_id or str(uuid4()),
    )
    return validate_stage_receipt(receipt)


def transition_stage_receipt(
    value: Any,
    status: str,
    *,
    artifact_ref: str | None = None,
    artifact: Any = _UNSET,
    artifact_sha256: str | None = None,
    artifact_valid: bool | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    provider: str | None = None,
    model_id: str | None = None,
    attempts: Iterable[Any] | None = None,
    timestamp_utc: str | None = None,
) -> StageReceipt:
    """Create and validate the next immutable state of a V1 receipt."""

    receipt = coerce_stage_receipt(value)
    if receipt.receipt_version != RECEIPT_VERSION:
        raise ValueError("Legacy V0 receipts must be replaced, not transitioned")
    next_status = _required_text(status, "status").lower()
    if next_status not in _STATUSES:
        raise ValueError(f"Unsupported stage status: {next_status}")
    allowed = _ALLOWED_TRANSITIONS.get(receipt.status, frozenset())
    if next_status not in allowed:
        if receipt.status in _TERMINAL_STATUSES:
            raise ValueError(f"terminal receipt {receipt.status} is immutable")
        raise ValueError(
            f"illegal StageReceipt transition {receipt.status} -> {next_status}"
        )

    when = timestamp_utc or utc_now_rfc3339()
    _normalize_timestamp(when, "timestamp_utc")
    next_started = receipt.started_at_utc
    next_finished: str | None = None
    if next_status == "running":
        next_started = next_started or when
    elif next_status in _TERMINAL_STATUSES:
        next_started = next_started or when
        next_finished = when

    next_artifact_sha = artifact_sha256
    next_artifact_valid = artifact_valid
    if artifact is not _UNSET:
        computed = canonical_sha256(artifact)
        if next_artifact_sha is not None and next_artifact_sha != computed:
            raise ValueError("artifact_sha256 does not match the provided artifact")
        next_artifact_sha = computed
        next_artifact_valid = True
    if next_status == "completed" and artifact is _UNSET:
        raise ValueError("completed transition requires the validated artifact payload")

    transitioned = replace(
        receipt,
        status=next_status,
        artifact_ref=artifact_ref if artifact_ref is not None else receipt.artifact_ref,
        artifact_sha256=(
            next_artifact_sha
            if next_artifact_sha is not None
            else receipt.artifact_sha256
        ),
        artifact_valid=(
            next_artifact_valid
            if next_artifact_valid is not None
            else receipt.artifact_valid
        ),
        started_at_utc=next_started,
        finished_at_utc=next_finished,
        error_code=_optional_text(error_code),
        error_message=_optional_text(error_message),
        provider=_optional_text(provider) if provider is not None else receipt.provider,
        model_id=_optional_text(model_id) if model_id is not None else receipt.model_id,
        attempts=(
            normalize_attempts(attempts) if attempts is not None else receipt.attempts
        ),
    )
    return validate_stage_receipt(transitioned)


def _resolve_artifact(root: Mapping[str, Any], artifact_ref: str) -> Any:
    path = artifact_ref.strip()
    for prefix in ("ai_data_json.", "metadata_json.", "$." ):
        if path.startswith(prefix):
            path = path[len(prefix) :]
            break
    if not path:
        return root
    current: Any = root
    for segment in path.split("."):
        if isinstance(current, Mapping) and segment in current:
            current = current[segment]
            continue
        if isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
            try:
                current = current[int(segment)]
                continue
            except (ValueError, IndexError):
                pass
        raise KeyError(artifact_ref)
    return current


def validate_receipt_artifact(value: Any, payload_root: Mapping[str, Any]) -> bool:
    """Verify that the referenced persisted payload exists and matches its hash."""

    receipt = coerce_stage_receipt(value)
    if not receipt.artifact_ref or not receipt.artifact_sha256:
        return False
    try:
        artifact = _resolve_artifact(payload_root, receipt.artifact_ref)
        return canonical_sha256(artifact) == receipt.artifact_sha256
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def validate_receipt_map(receipts: Mapping[str, Any]) -> dict[str, StageReceipt]:
    """Normalize receipts and enforce dictionary-key/stage identity."""

    normalized: dict[str, StageReceipt] = {}
    for key, value in receipts.items():
        stage_key = _required_text(key, "receipt dictionary key")
        receipt = coerce_stage_receipt(value)
        if receipt.stage_id != stage_key:
            raise ValueError(
                f"Receipt dictionary key {stage_key!r} does not match stage_id "
                f"{receipt.stage_id!r}"
            )
        normalized[stage_key] = receipt
    return normalized


def project_legacy_stage_receipts(
    *,
    stage_status: Mapping[str, Any] | None,
    stage_errors: Mapping[str, Any] | None = None,
) -> dict[str, StageReceipt]:
    """Project flat legacy truth into nullable V0 receipts without mutation."""

    errors = dict(stage_errors or {})
    projected: dict[str, StageReceipt] = {}
    for raw_stage_id, raw_status in dict(stage_status or {}).items():
        stage_id = _required_text(raw_stage_id, "stage_id")
        status = _required_text(raw_status, "status").lower()
        requested = status not in {"skipped", "not_requested"}
        if status == "not_requested":
            status = "skipped"
        if status not in _STATUSES:
            status = "failed"
        message = _optional_text(errors.get(stage_id))
        projected[stage_id] = StageReceipt(
            receipt_version=LEGACY_RECEIPT_VERSION,
            stage_id=stage_id,
            requested=requested,
            status=status,
            input_fingerprint=None,
            config_fingerprint=None,
            artifact_ref=None,
            artifact_sha256=None,
            artifact_valid=None,
            started_at_utc=None,
            finished_at_utc=None,
            error_code="legacy_stage_error" if message else None,
            error_message=message,
            provider=None,
            model_id=None,
            attempts=(),
            correlation_id=None,
        )
    return projected


def derive_analysis_status(receipts: Mapping[str, Any]) -> str:
    """Derive aggregate truth from requested receipts only."""

    normalized = validate_receipt_map(receipts)
    requested = [receipt for receipt in normalized.values() if receipt.requested]
    if not requested:
        return "unavailable"

    completed_count = sum(
        receipt.status == "completed"
        and (
            receipt.artifact_valid is True
            or (
                receipt.receipt_version == LEGACY_RECEIPT_VERSION
                and receipt.artifact_valid is not False
            )
        )
        for receipt in requested
    )
    if completed_count == len(requested):
        return "completed"

    has_failure = any(receipt.status in _FAILED_STATUSES for receipt in requested)
    if has_failure:
        return "partial" if completed_count else "failed"
    if any(receipt.status in {"pending", "running"} for receipt in requested):
        return "running"
    return "unavailable"


def select_retry_stage_ids(
    receipts: Mapping[str, Any],
    *,
    requested_stage_ids: Iterable[str],
    newly_requested_unavailable: Iterable[str] = (),
) -> list[str]:
    """Return only missing/failed/interrupted/newly-unavailable stage IDs."""

    normalized = validate_receipt_map(receipts)
    newly_unavailable = set(newly_requested_unavailable)
    selected: list[str] = []
    for stage_id in sorted(set(requested_stage_ids)):
        receipt = normalized.get(stage_id)
        if receipt is None or not receipt.requested:
            selected.append(stage_id)
        elif receipt.status in _RETRY_STATUSES:
            selected.append(stage_id)
        elif receipt.status == "unavailable" and stage_id in newly_unavailable:
            selected.append(stage_id)
    return selected


__all__ = [
    "ATTEMPT_FIELDS",
    "LEGACY_RECEIPT_VERSION",
    "RECEIPT_FIELDS",
    "RECEIPT_VERSION",
    "StageAttemptReceipt",
    "StageReceipt",
    "build_config_fingerprint",
    "build_input_fingerprint",
    "canonical_json_bytes",
    "canonical_sha256",
    "coerce_stage_receipt",
    "create_stage_receipt",
    "derive_analysis_status",
    "normalize_attempt",
    "normalize_attempts",
    "project_legacy_stage_receipts",
    "receipt_to_dict",
    "select_retry_stage_ids",
    "transition_stage_receipt",
    "utc_now_rfc3339",
    "validate_receipt_artifact",
    "validate_receipt_map",
    "validate_stage_receipt",
]
