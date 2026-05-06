"""Tests for brain post-processor (Plan Phase 4)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from pb_studio.brain import BRIDGE_AXES
from pb_studio.brain.brain_service import BrainService
from pb_studio.brain.post_processor import annotate_cuts_with_brain
from pb_studio.storage.migration_runner import migrate
from pb_studio.storage.sqlite_init import init_connection


def _make_state_conn(tmp_path: Path) -> sqlite3.Connection:
    p = tmp_path / "state.db"
    mig = (
        Path(__file__).resolve().parent.parent
        / "src" / "pb_studio" / "storage" / "migrations" / "state"
    )
    migrate(p, mig)
    conn = sqlite3.connect(str(p), isolation_level=None, check_same_thread=False)
    init_connection(conn)
    return conn


@pytest.fixture
def brain_svc(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    BrainService.reset_singleton()
    yield BrainService.get()
    BrainService.reset_singleton()


def test_annotate_attaches_brain_scores(brain_svc, tmp_path: Path):
    state = _make_state_conn(tmp_path)
    try:
        cuts = [
            {
                "clip_id": "clip_1",
                "start_time": 0.0,
                "end_time": 1.0,
                "metadata": {
                    "trigger_type": "kick",
                    "trigger_strength": 1.0,
                    "segment_type": "drop",
                },
            },
            {
                "clip_id": "clip_2",
                "start_time": 1.0,
                "end_time": 2.5,
                "metadata": {
                    "trigger_type": "snare",
                    "trigger_strength": 0.6,
                },
            },
        ]
        out = annotate_cuts_with_brain(
            cuts,
            weight_store=brain_svc.weights,
            audio_analysis={"mood_tags": ["dark"], "energy_curve": [0.4, 0.7], "duration_seconds": 2.5},
            video_analysis_by_clip={
                "clip_1": {"avg_motion": 0.6, "motion_category": "high",
                           "avg_brightness": 0.5, "avg_color_temp": 0.1},
                "clip_2": {"avg_motion": 0.3, "motion_category": "low"},
            },
            audio_clip_id=1,
            persist_to_state_conn=state,
        )
        assert len(out) == 2
        for c in out:
            scores = c["metadata"]["brain_scores"]
            assert set(scores.keys()) == set(BRIDGE_AXES)
            ck = c["metadata"]["context_keys"]
            assert len(ck) == 6

        # Check db persistence
        rows = state.execute(
            "SELECT id, clip_id, brain_scores_json, metadata_json "
            "FROM timeline_cuts ORDER BY position_idx"
        ).fetchall()
        assert len(rows) == 2
        meta = json.loads(rows[0][3])
        assert "context_keys" in meta
    finally:
        state.close()


def test_min_confidence_filters_low_scores(brain_svc, tmp_path: Path):
    state = _make_state_conn(tmp_path)
    try:
        cuts = [{"clip_id": "x", "start_time": 0.0, "end_time": 1.0, "metadata": {}}]
        out = annotate_cuts_with_brain(
            cuts,
            weight_store=brain_svc.weights,
            min_confidence=0.99,
            persist_to_state_conn=state,
        )
        assert out == []
    finally:
        state.close()
