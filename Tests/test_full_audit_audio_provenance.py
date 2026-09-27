"""Regressions for full-audit audio findings 30–34."""

from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def test_suspect_beat_grid_segment_keeps_aggregate_suspect():
    from pb_studio.audio.beat_grid_segments import GridSegment, segments_as_payload

    rows = [
        GridSegment(0, 30, 120.0, 0.0, 4.0, "plausible", 1),
        GridSegment(30, 60, 120.0, 30.0, 0.1, "suspect", 1),
    ]
    payload = segments_as_payload(rows)
    assert payload["status"] == "suspect"
    assert payload["suspect_count"] == 1


def test_long_grid_covers_tail_and_reports_window_cap(monkeypatch):
    from pb_studio.audio import beat_grid_segments as module

    fake_librosa = SimpleNamespace(
        get_duration=lambda **_: 65.0,
        load=lambda *_, offset, duration, **__: (np.ones(int(22050 * duration)), 22050),
        onset=SimpleNamespace(onset_strength=lambda **__: np.ones(5)),
        times_like=lambda values, **__: np.arange(len(values), dtype=float),
    )
    monkeypatch.setitem(sys.modules, "librosa", fake_librosa)
    monkeypatch.setattr(
        module, "estimate_beat_grid",
        lambda chunk, sr, kick_times=None: module.BeatGrid(
            120.0, 0.0, 4.0, "test", "plausible"
        ),
    )
    rows = module.segment_beat_grids_from_file("fixture", max_windows=3)
    coverage = module.segments_as_payload(rows)["coverage"]
    assert coverage["successful_windows"] == 3
    assert coverage["covered_until_seconds"] == 65.0
    assert module.segments_as_payload(rows)["status"] == "plausible"

    capped = module.segment_beat_grids_from_file("fixture", max_windows=1)
    payload = module.segments_as_payload(capped)
    assert payload["coverage"]["capped"] is True
    assert payload["status"] == "suspect"


def test_streaming_key_feature_coverage_is_explicit_after_chunk_errors():
    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer

    analyzer = StreamingAudioAnalyzer(window_sec=10.0, overlap_sec=0.0)
    analyzer._load_chunk = lambda *_: np.ones(100, dtype=np.float32)
    analyzer._process_beats = lambda *_: None
    analyzer._process_triggers = lambda *_: None
    analyzer._process_energy = lambda chunk, is_first, overlap_frames, energy_agg: (
        energy_agg.add_chunk_rms(np.ones(8), is_first, overlap_frames) or None
    )
    calls = 0

    def representative(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated feature chunk failure")
        from pb_studio.audio.spectral_analyzer import FREQUENCY_BANDS
        return {
            "times": [0.5], "bands": {name: [1.0] for name in FREQUENCY_BANDS},
            "centroids": [100.0], "chroma_mean": [1.0] * 12,
            "chroma_weight": 1,
        }

    analyzer._extract_representative_features = representative
    result = analyzer._analyze_streaming_prepared(
        Path("unused"), 20.0, None, False, 44100
    )
    assert result.feature_covered_seconds == 10.0
    assert result.feature_coverage == 0.5


def test_streaming_structure_confidence_reflects_measured_evidence():
    from pb_studio.audio.structure_analyzer import StructureAnalyzer

    segments = StructureAnalyzer().analyze_streaming_energy(
        [0.1] * 20 + [0.9] * 20 + [0.2] * 20, 180.0, segment_seconds=60.0
    )["segments"]
    confidences = [segment["confidence"] for segment in segments]
    assert len(set(confidences)) > 1
    assert all(0.0 <= value <= 1.0 for value in confidences)


def test_router_distinguishes_mix_feature_source_from_beat_source():
    from backend.routers.audio_router import _same_audio_source

    assert _same_audio_source(ROOT / "fixture.wav", ROOT / "." / "fixture.wav")
    assert not _same_audio_source(ROOT / "drums.wav", ROOT / "mix.wav")
