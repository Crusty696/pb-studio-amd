"""Characterize the anchor file contract independently of HTTP endpoints."""

import json

import pytest

from backend.project_anchors import load_project_anchors


def test_legacy_router_import_remains_the_same_function():
    from backend.routers.project_router import load_project_anchors as legacy

    assert legacy is load_project_anchors


@pytest.mark.parametrize("payload", [None, {}, "broken", 12])
def test_non_list_anchor_payload_is_empty(tmp_path, payload):
    (tmp_path / "anchors.json").write_text(json.dumps(payload), encoding="utf-8")
    assert load_project_anchors(tmp_path) == []


def test_missing_and_unreadable_anchor_files_are_empty(tmp_path):
    assert load_project_anchors(tmp_path) == []
    (tmp_path / "anchors.json").write_text("{broken", encoding="utf-8")
    assert load_project_anchors(str(tmp_path)) == []


def test_anchor_normalization_sorting_and_filtering(tmp_path):
    payload = [
        {"time": "3.5", "label": "later", "video_clip_id": 8},
        None, {"time": -1}, {"time": "invalid"}, {},
        {"time": 1, "label": None},
        {"time": 1, "label": 42, "video_clip_id": 9},
    ]
    (tmp_path / "anchors.json").write_text(json.dumps(payload), encoding="utf-8")
    assert load_project_anchors(tmp_path) == [
        {"time": 1.0, "label": "", "video_clip_id": None},
        {"time": 1.0, "label": "42", "video_clip_id": 9},
        {"time": 3.5, "label": "later", "video_clip_id": 8},
    ]
