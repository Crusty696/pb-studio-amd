"""T008: isolated result boundary tests; no backend, database or remote runtime."""
from dataclasses import replace
from uuid import uuid4

from pb_studio.providers.contracts import (
    AnalysisRun, EmbeddingPayload, InputArtifact, ResultEnvelope, StageResult,
    QualityProfile, validate_embedding, validate_result,
)


def run(*, kind="native", capability="audio.beats.v1", stages=None, **changes):
    base = AnalysisRun(
        result_uuid=str(uuid4()), project_uuid=str(uuid4()), execution_kind=kind,
        capability=capability, provider_id="native.beats" if kind == "native" else "comfy.beats",
        provider_version="1", request_fingerprint="a" * 64,
        started_at=1.0, completed_at=2.0,
        source_sha256="b" * 64, source_range=(30.0, 60.0),
        algorithm_id="beat-detector-v1" if kind == "native" else None,
        code_sha256="c" * 64 if kind == "native" else None,
        processor_id="not_applicable" if kind == "native" else None,
        config_revision="1", result_adapter_revision="1",
        model_bundle_sha256="not_applicable" if kind == "native" else "d" * 64,
        attempt_uuid=str(uuid4()) if kind == "comfy" else None,
        remote_prompt_uuid=str(uuid4()) if kind == "comfy" else None,
        workflow_revision="fixture:1" if kind == "comfy" else None,
        effective_prompt_sha256="e" * 64 if kind == "comfy" else None,
        stages=tuple(stages if stages is not None else [StageResult(
            stage_id="beats", status="completed", payload_schema_version=1,
            payload={"times": [31.0, 31.5], "time_unit": "seconds"},
            coverage_intervals=((30.0, 60.0),),
        )]),
    )
    return replace(base, **changes)


def codes(report):
    return {issue.code for issue in report.issues}


def test_native_dsp_without_remote_or_model_and_shared_envelope():
    native = run()
    assert validate_result(native).valid
    assert validate_result(ResultEnvelope.from_run(native)).valid
    assert validate_result(replace(native, origin_generation_attempt_uuid=str(uuid4()))).valid


def test_remote_execution_identity_is_discriminated():
    native = run()
    assert "native_remote_identity" in codes(validate_result(replace(native, attempt_uuid=str(uuid4()))))
    comfy = run(kind="comfy")
    assert validate_result(comfy).valid
    for field in ("attempt_uuid", "remote_prompt_uuid", "workflow_revision", "effective_prompt_sha256"):
        assert not validate_result(replace(comfy, **{field: None})).valid, field
    assert "execution_identity_missing" in codes(validate_result(replace(native, provider_id="")))


def test_text_to_video_can_have_no_source_but_analysis_cannot():
    generated = run(kind="comfy", capability="media.video_generation.v1",
                    source_sha256=None, source_range=None,
                    stages=(StageResult("video", "completed", 1, payload={"artifact_uuid": str(uuid4())}),))
    assert validate_result(generated).valid
    assert "analysis_source_missing" in codes(validate_result(replace(run(), source_sha256=None)))


def test_partial_caption_preserves_tags_and_uncovered_range():
    stage = StageResult("caption", "partial", 1,
                        payload={"tags": ["forest"]}, reason_code="frame_failed",
                        coverage_intervals=((0.0, 1.0),), uncovered_intervals=((1.0, 2.0),))
    report = validate_result(run(capability="video.caption.v1", stages=(stage,), source_range=(0.0, 2.0),
                                 model_bundle_sha256="f" * 64))
    assert report.valid
    assert stage.payload["tags"] == ["forest"]
    assert validate_result(run(stages=(StageResult("caption", "completed", 1, payload={"tags": []}),))).valid
    assert "failed_without_reason" in codes(validate_result(run(stages=(StageResult("caption", "failed", 1),))))


def test_time_units_chunk_offset_and_finite_range():
    base = run()
    for payload, expected in (
        ({"times": [31000.0], "time_unit": "milliseconds"}, "invalid_time_unit"),
        ({"times": [31.0, 30.0], "time_unit": "seconds"}, "nonmonotonic_time"),
        ({"times": [61.0], "time_unit": "seconds"}, "time_out_of_range"),
        ({"times": [float("nan")], "time_unit": "seconds"}, "nonfinite_number"),
        ({"times": [1.0], "time_unit": "seconds", "chunk_start": 30.0}, "chunk_offset_missing"),
    ):
        changed = replace(base, stages=(StageResult("beats", "completed", 1, payload=payload),))
        assert expected in codes(validate_result(changed)), expected


def test_unavailable_empty_and_uncalibrated_motion_are_distinct():
    empty = run(stages=(StageResult("beats", "completed", 1, payload={"times": [], "time_unit": "seconds"}),))
    assert validate_result(empty).valid
    assert "unavailable_payload" in codes(validate_result(run(stages=(StageResult("beats", "unavailable", 1, payload={"times": []}, reason_code="no_model"),))))
    motion = run(capability="video.motion.v1", stages=(StageResult("motion", "completed", 1, payload={"motion_curve": [0.5]}),))
    assert "motion_uncalibrated" in codes(validate_result(motion))


def test_embedding_space_and_identity_even_at_same_dimension():
    payload = EmbeddingPayload("siglip_vision/onnx-dml-v2", "a" * 64, "b" * 64,
                               "vision-output", "mean", "unit_l2", 768, "float32", "frame",
                               (0.0, 1.0), "c" * 64)
    assert validate_embedding(payload, "siglip_vision/onnx-dml-v2").valid
    assert "embedding_space_mismatch" in codes(validate_embedding(payload, "siglip_vision/onnx-dml-v1"))
    assert "embedding_identity_missing" in codes(validate_embedding(replace(payload, processor_sha256=""), payload.embedding_space_id))
    assert "embedding_dimension_invalid" in codes(validate_embedding(replace(payload, dimension=0), payload.embedding_space_id))


def test_chunk_times_are_mapped_once_and_half_open_range_is_enforced():
    correct = StageResult("beats", "completed", 1,
                          payload={"times": [0.0, 0.5], "time_unit": "seconds",
                                   "time_origin": "chunk", "chunk_start": 30.0})
    assert validate_result(run(stages=(correct,))).valid
    out = replace(correct, payload={**correct.payload, "times": [30.0]})
    assert "time_out_of_range" in codes(validate_result(run(stages=(out,))))
    end = replace(correct, payload={"times": [30.0], "time_unit": "seconds", "time_origin": "source"})
    assert validate_result(run(stages=(end,))).valid
    ambiguous = replace(correct, payload={**correct.payload, "times": [31.0], "time_origin": "source"})
    assert "time_origin_invalid" in codes(validate_result(run(stages=(ambiguous,))))


def test_partial_coverage_must_not_overlap_and_source_must_be_real():
    partial = StageResult("caption", "partial", 1, payload={"tags": ["forest"]},
                          reason_code="one_frame_failed", coverage_intervals=((30.0, 40.0),),
                          uncovered_intervals=((39.0, 60.0),))
    assert "coverage_overlap" in codes(validate_result(run(stages=(partial,))))
    assert "analysis_source_missing" in codes(validate_result(run(source_sha256="x")))


def test_partial_requires_both_valid_and_missing_coverage():
    partial = StageResult("caption", "partial", 1, payload={"tags": ["forest"]},
                          reason_code="frame_failed")
    assert "partial_coverage_missing" in codes(validate_result(run(stages=(partial,))))


def test_model_based_native_run_cannot_claim_no_model():
    assert "model_identity_missing" in codes(validate_result(run(model_based=True)))
    assert validate_result(run(model_based=True, model_bundle_sha256="f" * 64)).valid
    assert "model_identity_missing" in codes(validate_result(run(capability="video.embedding.v1")))


def test_profile_requires_named_stages_and_partial_is_not_completed():
    profile = QualityProfile(mandatory_stage_ids=("beats", "energy"))
    assert "mandatory_stage_missing" in codes(validate_result(run(), profile))
    partial = StageResult("beats", "partial", 1, payload={"times": [31.0], "time_unit": "seconds"},
                          reason_code="short_window", coverage_intervals=((30.0, 40.0),),
                          uncovered_intervals=((40.0, 60.0),))
    result = run(stages=(partial,))
    assert result.aggregate_status == "partial"
    assert validate_result(result, QualityProfile(mandatory_stage_ids=("beats",))).valid


def test_run_timestamps_and_identity_are_checked():
    assert "run_time_invalid" in codes(validate_result(run(started_at=20.0, completed_at=10.0)))
    assert "run_time_invalid" in codes(validate_result(run(started_at=None)))
    assert "execution_identity_missing" in codes(validate_result(run(result_uuid="bad")))
    assert "execution_identity_missing" in codes(validate_result(run(config_revision=None)))


def test_envelope_schema_artifacts_and_timebase_are_bound():
    artifact = InputArtifact("source", str(uuid4()), "f" * 64, (30.0, 60.0), (1, 48000))
    result = run(input_artifacts=(artifact,), produced_artifact_uuids=(str(uuid4()),),
                 schema_version=1, started_at=1.0, completed_at=2.0)
    assert validate_result(result).valid
    assert "schema_version_invalid" in codes(validate_result(replace(result, schema_version=2)))
    assert "input_artifact_invalid" in codes(validate_result(replace(result, input_artifacts=(
        replace(artifact, timebase=(1, 0)),))))
    assert "produced_artifact_invalid" in codes(validate_result(replace(result, produced_artifact_uuids=("wrong",))))


def test_bad_coverage_and_dependency_are_reported_without_crashing():
    malformed = StageResult("caption", "completed", 1, payload={"tags": []},
                            coverage_intervals=(("bad",), (30.0, 60.0)),
                            dependencies=(("wrong-result", "missing-stage"),))
    result = validate_result(run(stages=(malformed,)))
    assert "coverage_out_of_range" in codes(result)
    assert "stage_dependency_invalid" in codes(result)


def test_aggregate_status_uses_required_and_optional_stages():
    beats = StageResult("beats", "completed", 1, payload={"times": [], "time_unit": "seconds"})
    caption = StageResult("caption", "failed", 1, reason_code="frame_failed")
    result = run(stages=(beats, caption))
    assert result.aggregate_status_for(QualityProfile(mandatory_stage_ids=("beats",))) == "partial"
    assert result.aggregate_status_for(QualityProfile(mandatory_stage_ids=("beats", "caption"))) == "failed"


def test_unexpected_stage_dependencies_and_duplicate_ids_are_rejected():
    one = StageResult("beats", "completed", 1, payload={"times": [], "time_unit": "seconds"})
    two = replace(one, dependencies=((str(uuid4()), ""),))
    report = validate_result(run(stages=(one, two)))
    assert "stage_identity_invalid" in codes(report)
    assert "stage_dependency_invalid" in codes(report)


def test_malformed_dependency_is_rejected_without_exception():
    stage = StageResult("beats", "completed", 1,
                        payload={"times": [], "time_unit": "seconds"},
                        dependencies=(("wrong",),))
    assert "stage_dependency_invalid" in codes(validate_result(run(stages=(stage,))))
