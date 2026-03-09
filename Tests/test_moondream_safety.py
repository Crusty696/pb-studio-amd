import numpy as np


def test_softmax_sanitizes_invalid_logits():
    from pb_studio.video.moondream import MoondreamAnalyzer

    probs = MoondreamAnalyzer._softmax(np.array([np.nan, np.inf, -np.inf, 0.0], dtype=np.float32))

    assert np.all(np.isfinite(probs))
    assert np.all(probs >= 0)
    assert np.isclose(float(probs.sum()), 1.0)

