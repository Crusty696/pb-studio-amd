from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_obj77_ground_truth import (
    validate_annotation,
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
    assert validate_corpus_metadata(payload) == [
        "audio-mix-001 rights evidence is incomplete",
        "kpi_definitions.section_alignment roles are incomplete",
        "kpi_definitions.cut_accuracy roles are incomplete",
        "kpi_definitions.sync_drift_under_10ms roles are incomplete",
    ]


def test_rejects_annotation_mutation_without_version_increase() -> None:
    payload = {
        "schema_version": 1,
        "objective": "OBJ-77",
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
                "registered_sha256": "b" * 64,
                "registered_annotation_version": "1.0.0",
            }
        ],
    }
    assert validate_corpus_metadata(payload) == [
        "audio-mix-001 annotation mutation without a version increase"
    ]


def test_metadata_only_documents_do_not_close_the_live_gate(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    assert json.loads(corpus.read_text(encoding="utf-8")) == {"schema_version": 1}
