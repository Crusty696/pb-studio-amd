from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_obj77_ground_truth import (
    DEFAULT_AUDIO_ROOT,
    DEFAULT_VIDEO_ROOT,
    main,
    validate_annotation,
    validate_corpus,
    validate_corpus_metadata,
    validate_media_path,
    validate_media_snapshot,
)


@pytest.fixture
def valid_annotation() -> dict:
    return {
        "schema_version": 1,
        "media_id": "audio-mix-001",
        "media_sha256": "a" * 64,
        "annotation_version": "1.0.0",
        "annotation_status": "approved",
        "annotator_id": "annotator-a",
        "reviewer_id": "reviewer-b",
        "independent_labeling": {
            "attested": True,
            "annotator_attestor_id": "annotator-a",
            "reviewer_attestor_id": "reviewer-b",
            "source_system": "independent_of_pb_studio",
        },
        "downbeats": [{"time": 0.0, "bar_number": 1}],
        "subtracks": [],
        "song_sections": [],
        "scene_boundaries": [],
        "tags": {"required": [], "allowed": [], "forbidden": []},
        "pacing_cases": [],
    }


def test_rejects_same_annotator_and_reviewer(valid_annotation: dict) -> None:
    valid_annotation["reviewer_id"] = valid_annotation["annotator_id"]
    assert validate_annotation(valid_annotation, duration_seconds=3600.0) == [
        "annotator_id and reviewer_id must differ"
    ]


def test_rejects_non_contiguous_bar_numbers(valid_annotation: dict) -> None:
    valid_annotation["downbeats"] = [
        {"time": 0.0, "bar_number": 1},
        {"time": 1.875, "bar_number": 3},
    ]
    assert validate_annotation(valid_annotation, duration_seconds=3600.0) == [
        "bar_number must increase contiguously"
    ]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_rejects_non_finite_times(valid_annotation: dict, value: float) -> None:
    valid_annotation["downbeats"] = [{"time": value, "bar_number": 1}]
    assert validate_annotation(valid_annotation, duration_seconds=3600.0) == [
        "downbeats[0].time must be finite"
    ]


def test_rejects_out_of_range_times(valid_annotation: dict) -> None:
    valid_annotation["downbeats"] = [{"time": 3600.1, "bar_number": 1}]
    assert validate_annotation(valid_annotation, duration_seconds=3600.0) == [
        "downbeats[0].time outside media duration"
    ]


def test_rejects_unsorted_and_overlapping_segments(valid_annotation: dict) -> None:
    valid_annotation["song_sections"] = [
        {"start_time": 20.0, "end_time": 40.0, "label": "verse"},
        {"start_time": 10.0, "end_time": 30.0, "label": "chorus"},
    ]
    assert validate_annotation(valid_annotation, duration_seconds=3600.0) == [
        "song_sections must be sorted by start_time",
        "song_sections must not overlap",
    ]


def test_rejects_unknown_controlled_labels(valid_annotation: dict) -> None:
    valid_annotation["song_sections"] = [
        {"start_time": 0.0, "end_time": 10.0, "label": "build"}
    ]
    valid_annotation["scene_boundaries"] = [
        {"time": 5.0, "transition_type": "wipe"}
    ]
    valid_annotation["tags"] = {"required": ["unknown-tag"], "allowed": [], "forbidden": []}
    assert validate_annotation(valid_annotation, duration_seconds=3600.0) == [
        "song_sections[0].label is not allowed",
        "scene_boundaries[0].transition_type is not allowed",
        "tags.required[0] is not allowed",
    ]


def test_rejects_unapproved_annotation(valid_annotation: dict) -> None:
    valid_annotation["annotation_status"] = "draft"
    assert validate_annotation(valid_annotation, duration_seconds=3600.0) == [
        "annotation_status must be approved"
    ]


def test_rejects_media_hash_duration_and_stream_drift() -> None:
    entry = {
        "media_id": "audio-mix-001",
        "sha256": "a" * 64,
        "duration_seconds": 3600.0,
        "stream": {"codec_type": "audio", "codec_name": "mp3"},
    }
    assert validate_media_snapshot(
        entry,
        observed_sha256="b" * 64,
        observed_duration_seconds=3599.0,
        observed_stream={"codec_type": "audio", "codec_name": "aac"},
    ) == [
        "audio-mix-001 hash drift",
        "audio-mix-001 duration drift",
        "audio-mix-001 stream drift",
    ]


def test_rejects_media_path_outside_approved_root(tmp_path: Path) -> None:
    approved_root = tmp_path / "audio"
    assert validate_media_path(tmp_path / "outside.mp3", approved_root, "audio-mix-001") == [
        "audio-mix-001 path is outside the approved root"
    ]


def test_rejects_missing_rights_evidence_and_kpi_roles() -> None:
    payload = {
        "schema_version": 1,
        "objective": "OBJ-77",
        "kpi_definitions": {
            "section_alignment": {"formula": "matches / total"},
            "cut_accuracy": {"formula": "matches / total"},
            "sync_drift_under_10ms": {"formula": "count / total"},
        },
        "media": [
            {
                "media_id": "audio-mix-001",
                "media_type": "audio",
                "relative_path": "mix.mp3",
                "sha256": "a" * 64,
                "duration_seconds": 3600.0,
                "stream": {"codec_type": "audio", "codec_name": "mp3"},
                "rights_evidence": {},
            }
        ],
        "annotations": [],
    }
    errors = validate_corpus_metadata(payload)
    assert {
        "audio-mix-001 rights evidence is incomplete",
        "kpi_definitions.section_alignment roles are incomplete",
        "kpi_definitions.cut_accuracy roles are incomplete",
        "kpi_definitions.sync_drift_under_10ms roles are incomplete",
    }.issubset(errors)


def test_rejects_annotation_mutation_without_version_increase() -> None:
    payload = {
        "schema_version": 1,
        "objective": "OBJ-77",
        "corpus_version": "1.1.0",
        "previous_corpus_sha256": "c" * 64,
        "previous_corpus_version": "1.0.0",
        "corpus_policy": {
            "mode": "update",
            "audio_duration_slots": [],
            "video_coverage": {"required_markers": [], "approval_id": "approval", "approver_id": "reviewer"},
        },
        "kpi_definitions": {
            name: {"formula": "frozen", "owner_id": "kpi-owner", "reviewer_id": "kpi-reviewer"}
            for name in ("section_alignment", "cut_accuracy", "sync_drift_under_10ms")
        },
        "media": [],
        "annotations": [
            {
                "media_id": "audio-mix-001",
                "relative_path": "audio-mix-001.json",
                "sha256": "a" * 64,
                "annotation_version": "1.0.0",
                "previous_sha256": "b" * 64,
                "previous_annotation_version": "1.0.0",
            }
        ],
    }
    prior_registration = {
        "schema_version": 1,
        "registration_kind": "OBJ-77-ground-truth-prior",
        "corpus_sha256": "c" * 64,
        "corpus_version": "1.0.0",
        "annotations": [{"media_id": "audio-mix-001", "sha256": "b" * 64, "annotation_version": "1.0.0"}],
    }
    assert "audio-mix-001 annotation mutation without a version increase" in validate_corpus_metadata(
        payload,
        prior_registration,
    )


def test_metadata_only_documents_do_not_close_the_live_gate(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    assert json.loads(corpus.read_text(encoding="utf-8")) == {"schema_version": 1}


def _valid_corpus() -> dict:
    slots = [
        ("mix-1h", 3500.0, 3700.0),
        ("mix-2h-a", 7100.0, 7300.0),
        ("mix-2h-b", 7100.0, 7300.0),
        ("mix-3h", 10700.0, 10900.0),
        ("mix-4h", 14300.0, 14500.0),
    ]
    media: list[dict] = []
    for index, (slot_id, minimum, maximum) in enumerate(slots):
        media.append(
            {
                "media_id": f"audio-mix-{index + 1:03d}",
                "media_type": "audio",
                "relative_path": f"mix-{index + 1}.mp3",
                "sha256": f"{index + 1:064x}",
                "duration_seconds": (minimum + maximum) / 2,
                "stream": {"codec_type": "audio", "codec_name": "mp3"},
                "rights_evidence": {
                    "approval_id": f"rights-audio-{index + 1}",
                    "approver_id": "rights-reviewer",
                    "approved": True,
                    "provenance": "licensed test corpus",
                    "source_type": "licensed",
                    "real_media": True,
                },
                "profile_slot": slot_id,
            }
        )
    markers = ("continuous", "cut", "fade", "dissolve")
    for index in range(10):
        media.append(
            {
                "media_id": f"video-{index + 1:03d}",
                "media_type": "video",
                "relative_path": f"video-{index + 1}.mp4",
                "sha256": f"{index + 6:064x}",
                "duration_seconds": 120.0,
                "stream": {"codec_type": "video", "codec_name": "h264"},
                "rights_evidence": {
                    "approval_id": f"rights-video-{index + 1}",
                    "approver_id": "rights-reviewer",
                    "approved": True,
                    "provenance": "licensed test corpus",
                    "source_type": "licensed",
                    "real_media": True,
                },
                "coverage_markers": [markers[index % len(markers)]],
            }
        )
    return {
        "schema_version": 1,
        "objective": "OBJ-77",
        "corpus_version": "1.0.0",
        "corpus_policy": {
            "mode": "initial",
            "audio_duration_slots": [
                {"slot_id": slot_id, "min_duration_seconds": minimum, "max_duration_seconds": maximum}
                for slot_id, minimum, maximum in slots
            ],
            "video_coverage": {
                "required_markers": list(markers),
                "approval_id": "coverage-approval-1",
                "approver_id": "coverage-reviewer",
            },
        },
        "kpi_definitions": {
            name: {"formula": "frozen formula", "owner_id": "kpi-owner", "reviewer_id": "kpi-reviewer"}
            for name in ("section_alignment", "cut_accuracy", "sync_drift_under_10ms")
        },
        "media": media,
        "annotations": [
            {
                "media_id": entry["media_id"],
                "relative_path": f"annotations/{entry['media_id']}.json",
                "sha256": entry["sha256"],
                "annotation_version": "1.0.0",
            }
            for entry in media
        ],
    }


def _write_corpus(tmp_path: Path, payload: dict) -> Path:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps(payload), encoding="utf-8")
    return corpus


def test_validate_corpus_rejects_annotation_free_corpus(tmp_path: Path) -> None:
    payload = _valid_corpus()
    payload["annotations"] = []
    errors = validate_corpus(_write_corpus(tmp_path, payload), tmp_path / "audio", tmp_path / "video")
    assert "missing annotation registration for audio-mix-001" in errors


def test_validate_corpus_rejects_duplicate_media_metadata(tmp_path: Path) -> None:
    payload = _valid_corpus()
    payload["media"].append(payload["media"][0].copy())
    errors = validate_corpus(_write_corpus(tmp_path, payload), tmp_path / "audio", tmp_path / "video")
    assert "duplicate media_id: audio-mix-001" in errors
    assert "duplicate media relative_path: mix-1.mp3" in errors
    assert "duplicate media sha256" in errors


def test_validate_corpus_rejects_duplicate_resolved_paths(tmp_path: Path) -> None:
    payload = _valid_corpus()
    payload["media"][1]["relative_path"] = "nested/../mix-1.mp3"
    payload["annotations"][1]["relative_path"] = "annotations/nested/../audio-mix-001.json"
    errors = validate_corpus(_write_corpus(tmp_path, payload), tmp_path / "audio", tmp_path / "video")
    assert any(error.startswith("duplicate resolved media path:") for error in errors)
    assert any(error.startswith("duplicate resolved annotation path:") for error in errors)


def test_validate_corpus_requires_frozen_audio_profile_policy(tmp_path: Path) -> None:
    payload = _valid_corpus()
    payload["corpus_policy"]["audio_duration_slots"] = []
    errors = validate_corpus(_write_corpus(tmp_path, payload), tmp_path / "audio", tmp_path / "video")
    assert "corpus_policy must define exactly five audio duration slots" in errors


def test_validate_corpus_requires_human_approved_video_coverage(tmp_path: Path) -> None:
    payload = _valid_corpus()
    payload["corpus_policy"]["video_coverage"].pop("approver_id")
    errors = validate_corpus(_write_corpus(tmp_path, payload), tmp_path / "audio", tmp_path / "video")
    assert "corpus_policy.video_coverage approval is incomplete" in errors


def test_annotation_structure_rejects_missing_and_unexpected_fields(valid_annotation: dict) -> None:
    valid_annotation.pop("tags")
    valid_annotation["unexpected"] = True
    errors = validate_annotation(valid_annotation, duration_seconds=3600.0)
    assert "annotation missing required field: tags" in errors
    assert "annotation has unexpected field: unexpected" in errors


def test_annotation_independence_normalizes_case_and_whitespace(valid_annotation: dict) -> None:
    valid_annotation["reviewer_id"] = " ANNOTATOR-A "
    assert "annotator_id and reviewer_id must differ" in validate_annotation(
        valid_annotation,
        duration_seconds=3600.0,
    )


def test_validate_corpus_update_requires_separate_prior_registration(tmp_path: Path) -> None:
    payload = _valid_corpus()
    payload["corpus_policy"]["mode"] = "update"
    payload["previous_corpus_sha256"] = "f" * 64
    payload["previous_corpus_version"] = "1.0.0"
    errors = validate_corpus(_write_corpus(tmp_path, payload), tmp_path / "audio", tmp_path / "video")
    assert "update mode requires --prior-registration" in errors


@pytest.mark.parametrize("marker", [{}, [], None])
def test_coverage_policy_rejects_malformed_marker_without_exception(marker: object) -> None:
    payload = _valid_corpus()
    payload["corpus_policy"]["video_coverage"]["required_markers"] = [marker]
    errors = validate_corpus_metadata(payload)
    assert "corpus_policy.video_coverage required_markers must contain strings" in errors


def test_video_coverage_rejects_malformed_marker_without_exception() -> None:
    payload = _valid_corpus()
    payload["media"][5]["coverage_markers"] = [{}]
    errors = validate_corpus_metadata(payload)
    assert "video-001 coverage_markers are invalid" in errors


@pytest.mark.parametrize(
    "prior_annotation",
    [
        None,
        {"media_id": "audio-mix-001", "sha256": "a" * 64},
        {"media_id": {}, "sha256": "a" * 64, "annotation_version": "1.0.0"},
        {"media_id": "audio-mix-001", "sha256": "invalid", "annotation_version": "1.0.0"},
        {"media_id": "audio-mix-001", "sha256": "a" * 64, "annotation_version": "invalid"},
    ],
)
def test_update_rejects_malformed_prior_annotation_without_exception(prior_annotation: object) -> None:
    payload = _valid_corpus()
    payload["corpus_policy"]["mode"] = "update"
    payload["corpus_version"] = "1.1.0"
    payload["previous_corpus_sha256"] = "b" * 64
    payload["previous_corpus_version"] = "1.0.0"
    prior = {
        "schema_version": 1,
        "registration_kind": "OBJ-77-ground-truth-prior",
        "corpus_sha256": "b" * 64,
        "corpus_version": "1.0.0",
        "annotations": [prior_annotation],
    }
    errors = validate_corpus_metadata(payload, prior)
    assert "prior registration is invalid" in errors


def test_update_rejects_duplicate_prior_annotation_media_ids_without_exception() -> None:
    payload = _valid_corpus()
    payload["corpus_policy"]["mode"] = "update"
    payload["corpus_version"] = "1.1.0"
    payload["previous_corpus_sha256"] = "b" * 64
    payload["previous_corpus_version"] = "1.0.0"
    prior = {
        "schema_version": 1,
        "registration_kind": "OBJ-77-ground-truth-prior",
        "corpus_sha256": "b" * 64,
        "corpus_version": "1.0.0",
        "annotations": [
            {"media_id": "audio-mix-001", "sha256": "a" * 64, "annotation_version": "1.0.0"},
            {"media_id": "audio-mix-001", "sha256": "c" * 64, "annotation_version": "1.0.0"},
        ],
    }
    errors = validate_corpus_metadata(payload, prior)
    assert "prior registration annotation media_id values must be unique" in errors


def test_strict_cli_rejects_approved_root_override(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        [
            "--corpus",
            str(tmp_path / "absent.json"),
            "--audio-root",
            str(tmp_path / "override-audio"),
            "--video-root",
            str(DEFAULT_VIDEO_ROOT),
            "--strict",
        ]
    )
    assert exit_code == 1
    assert "--audio-root must equal the approved root in strict mode" in capsys.readouterr().err
