"""Test: motion_curve consumer in clip_selector (L-M3)."""
import pytest


def test_motion_curve_score_high_motion_high_intensity():
    from pb_studio.pacing.clip_selector import ClipSelector
    selector = ClipSelector()
    if not hasattr(selector, "_motion_curve_score"):
        pytest.skip("Helper nicht implementiert (Plan-M3 nicht aktiv)")
    score = selector._motion_curve_score([25.0, 28.0, 30.0], 1.0, 1.0)
    # high motion (~mean 28/30=0.93), high intensity 1.0 → diff ~0.07 → score ~0.93
    assert score > 0.7


def test_motion_curve_score_no_curve_returns_neutral():
    from pb_studio.pacing.clip_selector import ClipSelector
    selector = ClipSelector()
    if not hasattr(selector, "_motion_curve_score"):
        pytest.skip("Helper nicht implementiert")
    score = selector._motion_curve_score([], 1.0, 0.5)
    assert 0.4 <= score <= 0.6


def test_motion_curve_score_mismatch_low_score():
    from pb_studio.pacing.clip_selector import ClipSelector
    selector = ClipSelector()
    if not hasattr(selector, "_motion_curve_score"):
        pytest.skip("Helper nicht implementiert")
    # high motion 30, low intensity 0.0 → diff ~1.0 → score ~0.0
    score = selector._motion_curve_score([30.0, 30.0], 1.0, 0.0)
    assert score < 0.2


def test_motion_curve_consumer_integration_in_select_by_motion():
    """L-M3: Verifies motion_curve influences clip selection in _select_by_motion."""
    from pb_studio.pacing.clip_selector import ClipSelector
    selector = ClipSelector(strategy="motion")
    if not hasattr(selector, "_motion_curve_score"):
        pytest.skip("Helper nicht implementiert")

    # Two clips with same motion_score but different motion_curves.
    # At high trigger_strength, the high-motion-curve clip should win.
    clips = [
        {
            "id": "low_curve",
            "file_path": "/x/low.mp4",
            "duration": 1.0,
            "motion_score": 0.5,
            "motion_curve": [1.0, 2.0, 1.5],  # mean ~1.5/30 = 0.05 (calm)
        },
        {
            "id": "high_curve",
            "file_path": "/x/high.mp4",
            "duration": 1.0,
            "motion_score": 0.5,
            "motion_curve": [28.0, 29.0, 30.0],  # mean ~29/30 = 0.97 (action)
        },
    ]
    # Trigger strength 1.0 (kick-like high intensity) should prefer high-curve clip.
    selected = selector.select_clip(
        available_clips=clips,
        trigger_strength=1.0,
        trigger_type="kick",
    )
    assert selected.clip_id == "high_curve", (
        f"Expected high_curve clip but got {selected.clip_id} "
        f"— motion_curve consumer not influencing selection"
    )
