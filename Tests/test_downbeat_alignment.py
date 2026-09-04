import numpy as np
import pytest

from pb_studio.audio.downbeat_alignment import align_downbeats


def grid(times):
    return [{"time": float(t), "strength": 0.5, "beat_type": "beat"} for t in times]


def test_alignment_preserves_times_and_records_raw_measurement():
    times = np.arange(0, 20, 0.5)
    beats = grid(times)
    mapped, provenance = align_downbeats(beats, times + 0.02, times[::4] + 0.02)
    assert mapped == times[::4].tolist()
    assert provenance["status"] == "measured"
    assert provenance["raw_downbeats"] == (times[::4] + 0.02).tolist()
    assert provenance["max_alignment_error_seconds"] == pytest.approx(0.02)
    assert beats == grid(times)


@pytest.mark.parametrize("offset,step,reason", [
    (0.25, 0.5, "incompatible_phase_or_duplicates"),
    (0, 1.0, "incompatible_tempo"),
    (0, 0.25, "incompatible_tempo"),
])
def test_alignment_rejects_phase_and_octave_errors(offset, step, reason):
    neural = np.arange(offset, 20, step)
    mapped, p = align_downbeats(grid(np.arange(0, 20, 0.5)), neural, neural[::4])
    assert mapped == []
    assert p["status"] == "unavailable"
    assert p["reason"] == reason


@pytest.mark.parametrize("downbeats", [[np.nan], [-1], [0, 0], [1, 0], [0.1]])
def test_alignment_rejects_invalid_or_unmeasured_times(downbeats):
    mapped, p = align_downbeats(grid([0, 0.5, 1]), [0, 0.5, 1], downbeats)
    assert not mapped
    assert p["status"] == "unavailable"
