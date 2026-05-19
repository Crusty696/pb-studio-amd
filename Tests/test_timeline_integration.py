"""Final integration test: timeline contiguous + no overlaps via validate_timeline."""
import pytest

from backend.schemas.common import validate_timeline


def test_validate_timeline_blocks_overlap():
    cuts = [
        {"start_time": 0.0, "end_time": 5.0, "metadata": {}},
        {"start_time": 4.0, "end_time": 8.0, "metadata": {}},  # overlaps prev
    ]
    warnings, errors = validate_timeline(cuts, audio_duration=12.0)
    assert any("berlappung" in e or "overlap" in e.lower() for e in errors), \
        f"Expected overlap error, got errors={errors}, warnings={warnings}"


def test_validate_timeline_no_overlaps_in_contiguous_output():
    cuts = [
        {"start_time": 0.0, "end_time": 5.0, "metadata": {}},
        {"start_time": 5.0, "end_time": 8.0, "metadata": {}},
        {"start_time": 8.0, "end_time": 12.0, "metadata": {}},
    ]
    warnings, errors = validate_timeline(cuts, audio_duration=12.0)
    assert errors == [], f"Contiguous timeline should validate; errors={errors}"


def test_validate_timeline_blocks_overflow():
    cuts = [
        {"start_time": 0.0, "end_time": 13.0, "metadata": {}},
    ]
    warnings, errors = validate_timeline(cuts, audio_duration=12.0)
    assert any("uberschreitet" in e.lower() or "berschreitet" in e or "audio" in e.lower() for e in errors), \
        f"Expected audio-overflow error, got errors={errors}"
