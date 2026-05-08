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


# ----------------------------------------------------------------------------
# R-Brain-01/02/09: Tests fuer die neuen Helper (centroid Normalisierung,
# nearest-scene-distance, NaN-guard cosine, weight-store variance defensiv)
# ----------------------------------------------------------------------------

def test_normalize_centroid_curve_handles_empty_and_nan():
    from pb_studio.brain.post_processor import _normalize_centroid_curve

    assert _normalize_centroid_curve([]) == []
    assert _normalize_centroid_curve(None) == []
    # all-zero -> empty (kein Signal)
    assert _normalize_centroid_curve([0.0, 0.0, 0.0]) == []
    # NaN/Inf werden zu 0.0
    arr = [float("nan"), float("inf"), 4000.0, 8000.0]
    out = _normalize_centroid_curve(arr)
    assert all(0.0 <= v <= 1.0 for v in out)
    # Cap auf [0,1] gilt fuer alle Werte
    out = _normalize_centroid_curve([1000.0] * 20 + [99999.0])
    assert max(out) == 1.0


def test_nearest_scene_distance_dict_and_tuple():
    from pb_studio.brain.post_processor import _nearest_scene_distance

    # leere Liste
    assert _nearest_scene_distance(5.0, []) == 1.0

    # dict mit start_time/end_time
    scenes_dict = [
        {"start_time": 0.0, "end_time": 2.5},
        {"start_time": 2.5, "end_time": 5.0},
        {"start_time": 5.0, "end_time": 7.5},
    ]
    # cut bei 2.6 -> naechste scene-grenze ist 2.5 (dist 0.1)
    assert abs(_nearest_scene_distance(2.6, scenes_dict) - 0.1) < 0.001

    # tuple-Format (start, end)
    scenes_tup = [(0.0, 1.0), (3.0, 4.5)]
    assert abs(_nearest_scene_distance(0.5, scenes_tup) - 0.5) < 0.001

    # Cap auf 10.0 fuer absurd weite Distanzen
    assert _nearest_scene_distance(1000.0, [{"start_time": 0.0}]) == 10.0


def test_cosine_zero_one_handles_nan_inf_inputs():
    """R-Brain-09: NaN/Inf in embeddings darf nicht NaN propagieren."""
    from pb_studio.brain.bridge_dimensions import _cosine_zero_one
    import numpy as np

    a = np.array([1.0, 0.0, float("nan"), 1.0], dtype=np.float32)
    b = np.array([1.0, 0.0, 0.0, 1.0], dtype=np.float32)
    val = _cosine_zero_one(a, b)
    assert val == val  # nicht NaN
    assert 0.0 <= val <= 1.0

    # Empty
    assert _cosine_zero_one(np.array([]), np.array([])) == 0.5


def test_weight_store_variance_zero_alpha_beta(tmp_path):
    """R-Brain-07: defensiv -- get_variance bei (0,0) gibt Cold-Start variance."""
    from pb_studio.brain.weight_store import WeightStore

    db = tmp_path / "wt.db"
    ws = WeightStore.from_path(str(db))
    # explicit (0, 0) bucket einfuegen via direct UPDATE
    ws.update("beat_weight", 0, "", alpha_delta=0.0, beta_delta=0.0)
    var = ws.get_variance("beat_weight", [""])
    assert 0.0 <= var <= 0.5
    # NaN nicht propagiert
    assert var == var
