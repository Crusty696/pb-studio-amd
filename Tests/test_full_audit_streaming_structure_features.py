"""Time-aligned evidence contracts for long-mix structure analysis."""

from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def test_streaming_structure_detects_harmonic_change_without_energy_change():
    from pb_studio.audio.structure_analyzer import StructureAnalyzer

    times = np.arange(180, dtype=np.float64).tolist()
    chroma = np.zeros((180, 12), dtype=np.float64)
    chroma[:60, 0] = 1.0
    chroma[60:120, 4] = 1.0
    chroma[120:, 7] = 1.0

    result = StructureAnalyzer().analyze_streaming_energy(
        [0.5] * 180,
        180.0,
        feature_times=times,
        chroma_features=chroma.tolist(),
    )

    interior = [segment["start_time"] for segment in result["segments"][1:]]
    assert len(interior) == 2
    assert interior[0] == pytest.approx(60.0, abs=2.0)
    assert interior[1] == pytest.approx(120.0, abs=2.0)
    assert all(segment["label"] == "section" for segment in result["segments"])
    assert all(0.0 <= segment["confidence"] <= 1.0 for segment in result["segments"])


def test_silent_chroma_does_not_create_phantom_structure_boundaries():
    from pb_studio.audio.structure_analyzer import StructureAnalyzer

    result = StructureAnalyzer().analyze_streaming_energy(
        [0.0] * 180,
        180.0,
        feature_times=np.arange(180, dtype=np.float64).tolist(),
        chroma_features=np.zeros((180, 12), dtype=np.float64).tolist(),
    )

    assert len(result["segments"]) == 1
    assert result["segments"][0]["label"] == "section"
    assert result["segments"][0]["confidence"] == 0.0


@pytest.mark.parametrize(
    ("feature_times", "chroma_features"),
    [
        ([0.0, 1.0], [[1.0] * 12]),
        ([0.0, 0.0], [[1.0] * 12, [1.0] * 12]),
        ([0.0, 1.0], [[float("nan")] * 12, [1.0] * 12]),
    ],
)
def test_streaming_structure_rejects_unaligned_or_invalid_chroma(
    feature_times, chroma_features
):
    from pb_studio.audio.structure_analyzer import StructureAnalyzer

    with pytest.raises(ValueError):
        StructureAnalyzer().analyze_streaming_energy(
            [0.5] * 20,
            20.0,
            feature_times=feature_times,
            chroma_features=chroma_features,
        )


def test_representative_streaming_features_include_timestamped_chroma():
    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer

    analyzer = StreamingAudioAnalyzer()
    sample_rate = analyzer.SR
    times = np.arange(sample_rate * 3, dtype=np.float32) / sample_rate
    chunk = (
        0.2 * np.sin(2 * np.pi * 220.0 * times)
        + 0.2 * np.sin(2 * np.pi * 440.0 * times)
    ).astype(np.float32)

    result = analyzer._extract_representative_features(chunk, 12.0, 1.0)

    assert len(result["times"]) == len(result["chroma_points"])
    assert len(result["chroma_points"]) == 3
    assert all(len(point) == 12 for point in result["chroma_points"])
    assert all(np.linalg.norm(point) == pytest.approx(1.0, abs=1e-6) for point in result["chroma_points"])
    assert result["times"][0] >= 13.0
    assert np.isfinite(np.asarray(result["chroma_points"])).all()


def test_chunk_chroma_mean_excludes_previously_covered_overlap(monkeypatch):
    import librosa

    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer

    analyzer = StreamingAudioAnalyzer()
    chunk = np.ones(analyzer.SR * 3, dtype=np.float32)
    frames_per_second = int(round(analyzer.SR / analyzer.HOP_LENGTH))
    chroma = np.zeros((12, 1 + analyzer.SR * 3 // analyzer.HOP_LENGTH))
    chroma[0, :frames_per_second] = 1.0
    chroma[4, frames_per_second : 2 * frames_per_second] = 1.0
    chroma[7, 2 * frames_per_second :] = 1.0

    monkeypatch.setattr(
        librosa,
        "stft",
        lambda *_args, **_kwargs: np.ones((1025, chroma.shape[1])),
    )
    monkeypatch.setattr(
        librosa.feature,
        "spectral_centroid",
        lambda S, **_kwargs: np.ones((1, S.shape[1])),
    )
    monkeypatch.setattr(
        librosa.feature,
        "chroma_stft",
        lambda **_kwargs: chroma,
    )

    result = analyzer._extract_representative_features(
        chunk,
        chunk_start=25.0,
        skip_seconds=1.0,
    )

    expected = np.mean(chroma[:, frames_per_second:], axis=1)
    np.testing.assert_allclose(result["chroma_mean"], expected)
    assert result["chroma_weight"] == chroma.shape[1] - frames_per_second


def test_resume_rejects_checkpoint_with_overlap_inclusive_key_weighting():
    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer

    analyzer = StreamingAudioAnalyzer()
    source = {"path": "mix.wav", "size": 1, "mtime_ns": 1}
    old_checkpoint = {
        "schema_version": 3,
        "source": source,
        "config": analyzer._checkpoint_config(False),
        "duration_seconds": 60.0,
        "window_count": 2,
        "chunks": [],
    }

    assert not analyzer._checkpoint_is_compatible(
        old_checkpoint,
        source_identity=source,
        duration=60.0,
        n_windows=2,
        energy_only=False,
    )
