"""Pacing-Service: letzter Cut wird auf audio_duration gestreckt."""
import pytest
from unittest.mock import patch, MagicMock

from pb_studio.services.pacing_service import PacingService
from pb_studio.pacing.pacing_models import CutListEntry


def _fake_cut(start: float, end: float, clip_id: str = "clip_1") -> CutListEntry:
    return CutListEntry(
        clip_id=clip_id,
        start_time=start,
        end_time=end,
        metadata={"file_path": "/x.mp4", "clip_name": "x", "clip_start": 0.0,
                  "trigger_type": "beat", "trigger_strength": 1.0},
    )


def test_last_cut_stretched_to_audio_duration():
    """Wenn last_cut.end_time < audio_duration, wird er auf audio_duration gestreckt."""
    svc = PacingService()
    cuts = [_fake_cut(0.0, 5.0), _fake_cut(5.0, 9.5)]
    audio_dur = 12.0

    out = svc._stretch_last_cut_to_audio(cuts, audio_duration=audio_dur)

    assert len(out) == 2
    assert out[-1].end_time == pytest.approx(audio_dur, abs=0.001)
    # Vorherige Cuts unveraendert
    assert out[0].end_time == pytest.approx(5.0)


def test_last_cut_not_shortened_if_already_long_enough():
    svc = PacingService()
    cuts = [_fake_cut(0.0, 5.0), _fake_cut(5.0, 12.0)]
    out = svc._stretch_last_cut_to_audio(cuts, audio_duration=12.0)
    assert out[-1].end_time == pytest.approx(12.0)


def test_no_op_on_empty_cuts():
    svc = PacingService()
    out = svc._stretch_last_cut_to_audio([], audio_duration=12.0)
    assert out == []


def test_no_op_when_audio_duration_zero():
    svc = PacingService()
    cuts = [_fake_cut(0.0, 5.0)]
    out = svc._stretch_last_cut_to_audio(cuts, audio_duration=0.0)
    assert out[-1].end_time == pytest.approx(5.0)
