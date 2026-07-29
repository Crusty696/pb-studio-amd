"""R-Brain-01/02/07/09 Tests: Helper functions for post_processor + bridge + weight_store."""
from __future__ import annotations
import numpy as np


def test_normalize_centroid_curve_handles_empty_and_nan():
    from pb_studio.brain.feature_adapter import (
        _normalize_percentile_curve as _normalize_centroid_curve,
    )
    assert _normalize_centroid_curve([]) == []
    assert _normalize_centroid_curve(None) == []
    assert _normalize_centroid_curve([0.0, 0.0, 0.0]) == []
    arr = [float("nan"), float("inf"), 4000.0, 8000.0]
    out = _normalize_centroid_curve(arr)
    assert all(0.0 <= v <= 1.0 for v in out)
    out = _normalize_centroid_curve([1000.0] * 20 + [99999.0])
    assert max(out) == 1.0


def test_nearest_scene_distance_dict_and_tuple():
    from pb_studio.brain.feature_adapter import _nearest_scene_distance
    assert _nearest_scene_distance(5.0, []) == 1.0
    scenes_dict = [
        {"start_time": 0.0, "end_time": 2.5},
        {"start_time": 2.5, "end_time": 5.0},
        {"start_time": 5.0, "end_time": 7.5},
    ]
    assert abs(_nearest_scene_distance(2.6, scenes_dict) - 0.1) < 0.001
    scenes_tup = [(0.0, 1.0), (3.0, 4.5)]
    assert _nearest_scene_distance(0.5, scenes_tup) == 1.0
    assert _nearest_scene_distance(1000.0, [{"start_time": 0.0}]) == 1000.0


def test_cosine_zero_one_handles_nan_inf_inputs():
    """R-Brain-09: NaN/Inf in embeddings darf nicht NaN propagieren."""
    from pb_studio.brain.bridge_dimensions import _cosine_zero_one
    a = np.array([1.0, 0.0, float("nan"), 1.0], dtype=np.float32)
    b = np.array([1.0, 0.0, 0.0, 1.0], dtype=np.float32)
    val = _cosine_zero_one(a, b)
    assert val == val
    assert -1e-6 <= val <= 1.0 + 1e-6
    assert _cosine_zero_one(np.array([]), np.array([])) is None


def test_weight_store_variance_zero_alpha_beta(tmp_path):
    """R-Brain-07: bei alpha+beta == 0 Cold-Start variance."""
    from pb_studio.brain.weight_store import WeightStore
    db = tmp_path / "wt.db"
    ws = WeightStore.from_path(str(db))
    ws.update("beat_weight", 0, "", alpha_delta=0.0, beta_delta=0.0)
    var = ws.get_variance("beat_weight", [""])
    assert 0.0 <= var <= 0.5
    assert var == var
