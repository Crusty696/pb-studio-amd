from pathlib import Path

import numpy as np


def test_softmax_sanitizes_invalid_logits():
    from pb_studio.video.moondream import MoondreamAnalyzer

    probs = MoondreamAnalyzer._softmax(np.array([np.nan, np.inf, -np.inf, 0.0], dtype=np.float32))

    assert np.all(np.isfinite(probs))
    assert np.all(probs >= 0)
    assert np.isclose(float(probs.sum()), 1.0)


def test_vision_ready_does_not_claim_caption_pipeline():
    from pb_studio.video.moondream import MoondreamAnalyzer

    analyzer = MoondreamAnalyzer(lazy_load=True)
    analyzer._initialized = True
    analyzer.encoder_session = object()

    assert analyzer.is_vision_ready is True
    assert analyzer.is_ready is False


def test_tokenizer_initialization_has_no_vulnerable_save_pretrained_sink():
    source = (
        Path(__file__).resolve().parents[1]
        / "src" / "pb_studio" / "video" / "moondream.py"
    ).read_text(encoding="utf-8")

    assert ".save_pretrained(" not in source
