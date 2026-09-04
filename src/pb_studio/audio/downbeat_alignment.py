"""Neural event validation and diagnostic comparison with legacy beat grids."""

import numpy as np

MAX_OFFSET_SECONDS = 0.070
MAX_OFFSET_FRACTION = 0.15
MIN_MATCH_RATIO = 0.90
MAX_TEMPO_RELATIVE_ERROR = 0.08


class BeatThisUnavailable(RuntimeError):
    """Required assets or the mandatory DirectML provider are unavailable."""


def validate_neural_events(neural_beats, neural_downbeats, duration):
    """Validate model output before atomically replacing any legacy values."""
    beats = np.asarray(neural_beats, dtype=float)
    downbeats = np.asarray(neural_downbeats, dtype=float)
    for values in (beats, downbeats):
        if (values.ndim != 1 or not np.isfinite(values).all()
                or np.any(values < 0) or np.any(values >= duration)
                or np.any(np.diff(values) <= 0)):
            raise ValueError("Invalid Beat This event times")
    if len(beats) < 2:
        raise BeatThisUnavailable("Insufficient Beat This events")
    if not np.isin(downbeats, beats).all():
        raise ValueError("Beat This downbeats are not a beat subset")
    return beats.tolist(), downbeats.tolist(), float(60.0 / np.median(np.diff(beats)))


def align_downbeats(beats, neural_beats, neural_downbeats):
    """Reject incompatible grids; never invent a periodic bar sequence.

    Preserve exact neural times in provenance. Accepted product markers use
    existing grid times, with an explicit, bounded alignment error.
    """
    grid = np.asarray([row["time"] for row in beats], dtype=float)
    neural = np.asarray(neural_beats, dtype=float)
    down = np.asarray(neural_downbeats, dtype=float)
    provenance = {
        "status": "unavailable", "method": "beat_this_onnx_aligned",
        "synthetic": False, "measured_count": 0,
        "neural_downbeat_count": len(down),
    }
    for values in (grid, neural, down):
        if (values.ndim != 1 or not np.isfinite(values).all()
                or np.any(values < 0) or np.any(np.diff(values) <= 0)):
            return [], {**provenance, "reason": "invalid_or_unsorted_times"}
    if len(grid) < 2 or len(neural) < 2 or not len(down):
        return [], {**provenance, "reason": "insufficient_events"}
    if not np.isin(down, neural).all():
        return [], {**provenance, "reason": "downbeats_not_neural_subset"}
    interval = float(np.median(np.diff(grid)))
    neural_interval = float(np.median(np.diff(neural)))
    tempo_error = abs(interval / neural_interval - 1.0)
    tolerance = min(MAX_OFFSET_SECONDS, MAX_OFFSET_FRACTION * interval)
    provenance.update(tolerance_seconds=tolerance, tempo_relative_error=tempo_error)
    if tempo_error > MAX_TEMPO_RELATIVE_ERROR:
        return [], {**provenance, "reason": "incompatible_tempo"}
    right = np.clip(np.searchsorted(grid, down), 0, len(grid) - 1)
    left = np.maximum(0, right - 1)
    indices = np.where(abs(grid[left] - down) <= abs(grid[right] - down), left, right)
    offsets = abs(grid[indices] - down)
    accepted = offsets <= tolerance
    ratio = float(np.mean(accepted))
    provenance["match_ratio"] = ratio
    if ratio < MIN_MATCH_RATIO or len(set(indices[accepted])) != int(sum(accepted)):
        return [], {**provenance, "reason": "incompatible_phase_or_duplicates"}
    mapped = grid[indices[accepted]].tolist()
    provenance.update(
        status="measured", measured_count=len(mapped),
        raw_downbeats=down[accepted].tolist(),
        max_alignment_error_seconds=float(np.max(offsets[accepted])),
        rejected_count=int(sum(~accepted)),
    )
    return mapped, provenance
