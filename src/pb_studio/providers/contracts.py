"""T008: pure analysis boundary; consumers opt in through later packages."""
from __future__ import annotations

from dataclasses import dataclass, fields
import math
import re
from typing import Any
from uuid import UUID


_HASH = re.compile(r"[0-9a-f]{64}\Z")
_STATUSES = {"completed", "partial", "failed", "unavailable", "not_requested", "interrupted"}
_PRESENT = {"completed", "partial"}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    issues: tuple[ValidationIssue, ...] = ()


@dataclass(frozen=True)
class QualityProfile:
    """Only structural obligations; quality thresholds require a qualified T002 profile."""
    mandatory_stage_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class InputArtifact:
    role: str
    artifact_uuid: str
    content_sha256: str
    source_range: tuple[float, float] | None
    timebase: tuple[int, int]


@dataclass(frozen=True)
class StageResult:
    stage_id: str
    status: str
    payload_schema_version: int
    payload: dict[str, Any] | None = None
    reason_code: str | None = None
    dependencies: tuple[tuple[str, str], ...] = ()
    measurement_origin: str = "measured"
    confidence_method: str | None = None
    coverage_intervals: tuple[tuple[float, float], ...] = ()
    uncovered_intervals: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class AnalysisRun:
    result_uuid: str
    project_uuid: str
    execution_kind: str
    capability: str
    provider_id: str
    provider_version: str
    request_fingerprint: str
    source_sha256: str | None
    source_range: tuple[float, float] | None
    schema_version: int = 1
    input_artifacts: tuple[InputArtifact, ...] = ()
    produced_artifact_uuids: tuple[str, ...] = ()
    algorithm_id: str | None = None
    code_sha256: str | None = None
    processor_id: str | None = None
    config_revision: str | None = None
    result_adapter_revision: str | None = None
    model_bundle_sha256: str | None = None
    model_based: bool = False
    job_uuid: str | None = None
    attempt_uuid: str | None = None
    remote_prompt_uuid: str | None = None
    workflow_revision: str | None = None
    effective_prompt_sha256: str | None = None
    origin_generation_job_uuid: str | None = None
    origin_generation_attempt_uuid: str | None = None
    media_id: int | None = None
    stages: tuple[StageResult, ...] = ()
    started_at: float | None = None
    completed_at: float | None = None

    @property
    def aggregate_status(self) -> str:
        return self.aggregate_status_for(QualityProfile(tuple(stage.stage_id for stage in self.stages)))

    def aggregate_status_for(self, profile: QualityProfile) -> str:
        by_id = {stage.stage_id: stage.status for stage in self.stages}
        if not by_id or any(stage_id not in by_id for stage_id in profile.mandatory_stage_ids):
            return "unavailable"
        required = [by_id[stage_id] for stage_id in profile.mandatory_stage_ids]
        if "failed" in required:
            return "failed"
        if "interrupted" in required:
            return "interrupted"
        if any(status in ("unavailable", "not_requested") for status in required):
            return "unavailable"
        if "partial" in required or any(status != "completed" for status in by_id.values()):
            return "partial"
        return "completed"


@dataclass(frozen=True)
class ResultEnvelope(AnalysisRun):
    """The execution context also used by the persisted AnalysisRun projection."""

    @classmethod
    def from_run(cls, run: AnalysisRun) -> ResultEnvelope:
        return cls(**{item.name: getattr(run, item.name) for item in fields(AnalysisRun)})


@dataclass(frozen=True)
class EmbeddingPayload:
    embedding_space_id: str
    model_sha256: str
    processor_sha256: str
    output_layer: str
    pooling: str
    normalization: str
    dimension: int
    dtype: str
    granularity: str
    source_range: tuple[float, float] | None
    vector_artifact_sha256: str


def _uuid(value: Any) -> bool:
    try:
        return isinstance(value, str) and bool(UUID(value).version)
    except (ValueError, TypeError, AttributeError):
        return False


def _hash(value: Any) -> bool:
    return isinstance(value, str) and _HASH.fullmatch(value) is not None


def _range(value: Any) -> bool:
    return (isinstance(value, (tuple, list)) and len(value) == 2
            and all(type(x) in (int, float) and math.isfinite(x) for x in value)
            and 0 <= value[0] < value[1])


def _finite(value: Any) -> bool:
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is int or value is None or type(value) in (str, bool):
        return True
    if isinstance(value, dict):
        return all(_finite(x) for x in value.values())
    if isinstance(value, (tuple, list)):
        return all(_finite(x) for x in value)
    return False


def validate_result(run: AnalysisRun, profile: Any = None) -> ValidationReport:
    """Validate source-relative seconds and provenance before persistence/consumption.

    QualityProfile thresholds are a later T002/T038 gate; no implicit quality pass.
    """
    issues: list[ValidationIssue] = []

    def add(code: str, path: str) -> None:
        issues.append(ValidationIssue(code, path))

    if type(run.schema_version) is not int or run.schema_version != 1:
        add("schema_version_invalid", "schema_version")
    if not _uuid(run.result_uuid) or not _uuid(run.project_uuid):
        add("execution_identity_missing", "result/project")
    if not run.capability or not run.provider_id or not run.provider_version or not run.config_revision or not _hash(run.request_fingerprint):
        add("execution_identity_missing", "capability/provider/request")
    if run.execution_kind not in ("native", "comfy"):
        add("execution_kind_invalid", "execution_kind")
    for field_name in ("job_uuid", "origin_generation_job_uuid", "origin_generation_attempt_uuid"):
        value = getattr(run, field_name)
        if value is not None and not _uuid(value):
            add("execution_identity_invalid", field_name)
    if run.capability.startswith("media.video_generation."):
        if run.source_sha256 is not None and not _hash(run.source_sha256):
            add("source_identity_invalid", "source_sha256")
        if run.source_range is not None and not _range(run.source_range):
            add("source_range_invalid", "source_range")
    elif not _hash(run.source_sha256) or not _range(run.source_range):
        add("analysis_source_missing", "source")
    for index, artifact in enumerate(run.input_artifacts):
        if (not isinstance(artifact, InputArtifact) or not artifact.role or not _uuid(artifact.artifact_uuid)
                or not _hash(artifact.content_sha256)
                or (artifact.source_range is not None and not _range(artifact.source_range))
                or not isinstance(artifact.timebase, tuple) or len(artifact.timebase) != 2
                or any(type(value) is not int or value <= 0 for value in artifact.timebase)):
            add("input_artifact_invalid", f"input_artifacts.{index}")
    if any(not _uuid(value) for value in run.produced_artifact_uuids) or len(set(run.produced_artifact_uuids)) != len(run.produced_artifact_uuids):
        add("produced_artifact_invalid", "produced_artifact_uuids")
    if run.execution_kind == "native":
        if any(getattr(run, name) is not None for name in ("attempt_uuid", "remote_prompt_uuid", "workflow_revision", "effective_prompt_sha256")):
            add("native_remote_identity", "remote")
        if not all((run.algorithm_id, _hash(run.code_sha256), run.processor_id,
                    run.config_revision, run.result_adapter_revision)):
            add("native_identity_missing", "native")
        model_required = run.model_based or run.capability.startswith(("video.embedding.", "video.caption."))
        if ((model_required and not _hash(run.model_bundle_sha256)) or
                (not run.model_based and run.model_bundle_sha256 != "not_applicable" and not _hash(run.model_bundle_sha256))):
            add("model_identity_missing", "model_bundle_sha256")
    if run.execution_kind == "comfy":
        if not (_uuid(run.attempt_uuid) and _uuid(run.remote_prompt_uuid)
                and run.workflow_revision and _hash(run.effective_prompt_sha256)
                and _hash(run.model_bundle_sha256)):
            add("comfy_identity_missing", "remote")
    if not run.stages:
        add("stages_missing", "stages")
    if (type(run.started_at) not in (int, float) or type(run.completed_at) not in (int, float)
            or (type(run.started_at) in (int, float) and not math.isfinite(run.started_at))
            or (type(run.completed_at) in (int, float) and not math.isfinite(run.completed_at))
            or (type(run.started_at) in (int, float) and type(run.completed_at) in (int, float) and run.completed_at < run.started_at)):
        add("run_time_invalid", "timestamps")
    stage_ids: set[str] = set()
    declared_stage_ids = {stage.stage_id for stage in run.stages if isinstance(stage, StageResult)}
    for stage in run.stages:
        path = f"stages.{stage.stage_id}"
        if not stage.stage_id or stage.stage_id in stage_ids or type(stage.payload_schema_version) is not int or stage.payload_schema_version < 1:
            add("stage_identity_invalid", path)
        stage_ids.add(stage.stage_id)
        for dependency in stage.dependencies:
            if not isinstance(dependency, (tuple, list)) or len(dependency) != 2:
                add("stage_dependency_invalid", path)
                continue
            result_id, dependency_stage = dependency
            if not _uuid(result_id) or not isinstance(dependency_stage, str) or not dependency_stage or (result_id == run.result_uuid and dependency_stage not in declared_stage_ids):
                add("stage_dependency_invalid", path)
        if stage.status not in _STATUSES:
            add("stage_status_invalid", path)
        if stage.status in _PRESENT and not isinstance(stage.payload, dict):
            add("stage_payload_missing", path)
        if stage.status not in _PRESENT and stage.payload is not None:
            add("unavailable_payload", path)
        if stage.status in ("partial", "failed", "unavailable", "interrupted") and not stage.reason_code:
            add("failed_without_reason", path)
        if stage.status == "partial" and (not stage.coverage_intervals or not stage.uncovered_intervals):
            add("partial_coverage_missing", path)
        if stage.measurement_origin not in ("measured", "derived", "synthetic"):
            add("measurement_origin_invalid", path)
        if not _finite(stage.payload):
            add("nonfinite_number", path)
        intervals = (*stage.coverage_intervals, *stage.uncovered_intervals)
        valid_intervals = [interval for interval in intervals if _range(interval)]
        if len(valid_intervals) != len(intervals) or any(run.source_range is not None and (interval[0] < run.source_range[0] or interval[1] > run.source_range[1]) for interval in valid_intervals):
            add("coverage_out_of_range", path)
        ordered = sorted(valid_intervals)
        if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
            add("coverage_overlap", path)
        payload = stage.payload
        if not isinstance(payload, dict):
            continue
        if "confidence" in payload and (type(payload["confidence"]) not in (int, float) or not math.isfinite(payload["confidence"]) or not 0 <= payload["confidence"] <= 1):
            add("confidence_out_of_range", path)
        if "motion_curve" in payload and not payload.get("calibration_revision"):
            add("motion_uncalibrated", path)
        if "times" in payload:
            times = payload["times"]
            if payload.get("time_unit") != "seconds":
                add("invalid_time_unit", path)
            if not isinstance(times, (tuple, list)) or any(type(t) not in (float, int) or not math.isfinite(t) for t in times):
                add("nonfinite_number", path)
            else:
                if any(a >= b for a, b in zip(times, times[1:])):
                    add("nonmonotonic_time", path)
                origin = payload.get("time_origin", "source")
                if "chunk_start" in payload and "time_origin" not in payload:
                    add("chunk_offset_missing", path)
                if (origin not in ("source", "chunk")
                        or (origin == "source" and "chunk_start" in payload)
                        or (origin == "chunk" and ("chunk_start" not in payload or type(payload["chunk_start"]) not in (int, float)))):
                    add("time_origin_invalid", path)
                else:
                    offset = payload.get("chunk_start", 0) if origin == "chunk" else 0
                    if type(offset) in (int, float) and math.isfinite(offset):
                        absolute = [t + offset for t in times]
                        if run.source_range is not None and any(t < run.source_range[0] or t >= run.source_range[1] for t in absolute):
                            add("time_out_of_range", path)
    if profile is not None:
        if not isinstance(profile, QualityProfile):
            add("quality_profile_invalid", "profile")
        else:
            for mandatory in profile.mandatory_stage_ids:
                if mandatory not in stage_ids:
                    add("mandatory_stage_missing", f"stages.{mandatory}")
    return ValidationReport(not issues, tuple(issues))


def validate_embedding(payload: EmbeddingPayload, expected_space: str) -> ValidationReport:
    issues: list[ValidationIssue] = []
    if payload.embedding_space_id != expected_space:
        issues.append(ValidationIssue("embedding_space_mismatch", "embedding_space_id"))
    if not (payload.embedding_space_id and _hash(payload.model_sha256) and _hash(payload.processor_sha256)
            and payload.output_layer and payload.pooling and payload.normalization
            and payload.granularity and _hash(payload.vector_artifact_sha256)):
        issues.append(ValidationIssue("embedding_identity_missing", "identity"))
    if type(payload.dimension) is not int or payload.dimension <= 0:
        issues.append(ValidationIssue("embedding_dimension_invalid", "dimension"))
    if payload.dtype not in ("float16", "float32", "float64"):
        issues.append(ValidationIssue("embedding_dtype_invalid", "dtype"))
    if payload.source_range is not None and not _range(payload.source_range):
        issues.append(ValidationIssue("embedding_range_invalid", "source_range"))
    return ValidationReport(not issues, tuple(issues))
