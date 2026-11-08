"""Strict, offline PB job DTO fixtures; not an API or Comfy transport adapter."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .models import _JOB, _JOB_TERMINAL, _MAX_INT64, _uuid


def _required(data: Mapping[str, object], name: str) -> object:
    if name not in data or data[name] is None:
        raise ValueError(f"required wire field: {name}")
    return data[name]


def _wire_uuid(data: Mapping[str, object], name: str) -> str:
    value = _required(data, name)
    if not isinstance(value, str):
        raise ValueError(f"UUID string required: {name}")
    return _uuid(value)


def _wire_int64(data: Mapping[str, object], name: str) -> int:
    value = _required(data, name)
    if type(value) is not int or not 0 <= value <= _MAX_INT64:
        raise ValueError(f"nonnegative int64 required: {name}")
    return value


def _version(data: Mapping[str, object]) -> None:
    if type(_required(data, "schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("incompatible job wire schema")


@dataclass(frozen=True)
class JobReceiptWire:
    request_id: str
    client_request_id: str
    project_uuid: str
    job_uuid: str
    state: str
    state_revision: int
    store_generation_uuid: str


def parse_job_receipt(data: Mapping[str, object]) -> JobReceiptWire:
    _version(data)
    state = _required(data, "state")
    if type(state) is not str or state not in _JOB and state not in _JOB_TERMINAL:
        raise ValueError("incompatible job state")
    return JobReceiptWire(
        request_id=_wire_uuid(data, "request_id"),
        client_request_id=_wire_uuid(data, "client_request_id"),
        project_uuid=_wire_uuid(data, "project_uuid"),
        job_uuid=_wire_uuid(data, "job_uuid"),
        state=state,
        state_revision=_wire_int64(data, "state_revision"),
        store_generation_uuid=_wire_uuid(data, "store_generation_uuid"),
    )


@dataclass(frozen=True)
class ProviderJobEventWire:
    event_uuid: str
    store_generation_uuid: str
    job_change_seq: int
    project_uuid: str
    entity_kind: str
    entity_uuid: str
    entity_revision: int
    job_uuid: str | None
    attempt_uuid: str | None
    state_revision: int | None


def parse_provider_job_event(data: Mapping[str, object]) -> ProviderJobEventWire:
    _version(data)
    kind = _required(data, "entity_kind")
    if kind not in ("job", "batch"):
        raise ValueError("incompatible entity kind")
    entity_uuid = _wire_uuid(data, "entity_uuid")
    job_uuid = None
    attempt_uuid = None
    state_revision = None
    if kind == "job":
        job_uuid = _wire_uuid(data, "job_uuid")
        if job_uuid != entity_uuid:
            raise ValueError("job/entity identity mismatch")
        if "attempt_uuid" not in data:
            raise ValueError("attempt_uuid must be explicit nullable")
        if data["attempt_uuid"] is not None:
            attempt_uuid = _wire_uuid(data, "attempt_uuid")
        state_revision = _wire_int64(data, "state_revision")
    return ProviderJobEventWire(
        event_uuid=_wire_uuid(data, "event_uuid"),
        store_generation_uuid=_wire_uuid(data, "store_generation_uuid"),
        job_change_seq=_wire_int64(data, "job_change_seq"),
        project_uuid=_wire_uuid(data, "project_uuid"),
        entity_kind=kind,
        entity_uuid=entity_uuid,
        entity_revision=_wire_int64(data, "entity_revision"),
        job_uuid=job_uuid,
        attempt_uuid=attempt_uuid,
        state_revision=state_revision,
    )
