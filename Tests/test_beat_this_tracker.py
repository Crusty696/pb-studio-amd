"""Deterministic contracts; model inference is checked separately on real GPU."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch
import torchaudio

from pb_studio.audio import beat_this_tracker as tracker


def _assets(tmp_path):
    files = {}
    for name in tracker.ASSET_NAMES:
        payload = name.encode()
        (tmp_path / name).write_bytes(payload)
        files[name] = {"size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": 1, "files": files}))
    return manifest


def test_assets_require_all_exact_bytes(tmp_path):
    manifest = _assets(tmp_path)
    assert tracker.validate_assets(tmp_path, manifest)["schema_version"] == 1
    path = tmp_path / "beat_this.onnx"
    path.write_bytes(b"x" * path.stat().st_size)
    with pytest.raises(tracker.BeatThisUnavailable, match="SHA-256"):
        tracker.validate_assets(tmp_path, manifest)


def test_missing_assets_are_unavailable(tmp_path):
    manifest = _assets(tmp_path)
    with pytest.raises(tracker.BeatThisUnavailable):
        tracker.validate_assets(tmp_path / "missing", manifest)


def test_manifest_cannot_supply_extra_paths(tmp_path):
    manifest = _assets(tmp_path)
    payload = json.loads(manifest.read_text())
    payload["files"]["../outside"] = {}
    manifest.write_text(json.dumps(payload))
    with pytest.raises(tracker.BeatThisUnavailable, match="manifest"):
        tracker.validate_assets(tmp_path, manifest)


def test_downbeats_are_unique_subset_and_empty_beats_mean_empty_downbeats():
    beats = np.full(50, -1.0, dtype=np.float32)
    downbeats = beats.copy()
    beats[[10, 30]] = 2
    downbeats[[8, 12, 32]] = 2
    b, d = tracker.postprocess(beats, downbeats)
    assert b.tolist() == [0.2, 0.6]
    assert d.tolist() == [0.2, 0.6]
    assert tracker.postprocess(np.full(50, -1.0), downbeats)[1].size == 0


def test_plateau_dedup_matches_reference_centroid():
    assert tracker.deduplicate_peaks(np.array([1, 2, 8, 9])).tolist() == [1.5, 8.5]


def _frontend():
    instance = object.__new__(tracker.BeatThisTracker)
    mel = torchaudio.transforms.MelSpectrogram(
        sample_rate=22050, n_fft=1024, hop_length=441, f_min=30,
        f_max=11000, n_mels=128, mel_scale="slaney",
        normalized="frame_length", power=1,
    )
    instance._window = torch.hann_window(1024)
    instance._filterbank = mel.mel_scale.fb
    return instance, mel


def test_frontend_matches_reference_torchaudio():
    instance, mel = _frontend()
    signal = np.random.default_rng(42).normal(size=44100).astype(np.float32)
    actual = instance.log_mel(signal)
    expected = torch.log1p(1000 * mel(torch.from_numpy(signal)).T).numpy()
    np.testing.assert_allclose(actual, expected, atol=1e-6, rtol=1e-6)


def test_frontend_rejects_nonfinite_and_handles_tiny_audio():
    instance, _ = _frontend()
    assert instance.log_mel(np.zeros(10)).shape == (0, 128)
    with pytest.raises(ValueError, match="finite mono"):
        instance.log_mel(np.array([np.nan] * 1024))


@pytest.mark.parametrize("size", [30, 1488, 1490, 1500, 3100])
def test_chunk_aggregation_keeps_first_without_gaps(size):
    instance = object.__new__(tracker.BeatThisTracker)
    spect = np.repeat(np.arange(size, dtype=np.float32)[:, None], 128, axis=1)
    instance.log_mel = lambda _: spect

    class Session:
        def run(self, outputs, feeds):
            values = feeds["spect"][:, :, 0]
            return [values, values]

    instance._get_session = lambda frames: Session()
    # A strictly increasing sequence leaves exactly the final peak. A gap or
    # duplicated overlap introduces additional peaks or moves that final peak.
    beats, downbeats = instance.track_signal(np.zeros(1))
    assert beats.tolist() == [(size - 1) / tracker.FPS]
    assert downbeats.tolist() == beats.tolist()


def test_cancel_checked_before_model_session():
    instance = object.__new__(tracker.BeatThisTracker)
    instance.log_mel = lambda _: np.zeros((100, 128), np.float32)
    def cancel():
        raise InterruptedError("cancelled")
    with pytest.raises(InterruptedError):
        instance.track_signal(np.zeros(1), cancel)


def test_file_decoding_bounded_and_seams_disjoint(monkeypatch):
    instance = object.__new__(tracker.BeatThisTracker)
    reads = []
    monkeypatch.setattr(tracker.sf, "info", lambda _: type("Info", (), {"frames": 300 * 22050, "samplerate": 22050})())
    def read(path, **kwargs):
        reads.append(kwargs)
        return np.zeros((kwargs["frames"], 1)), 22050
    monkeypatch.setattr(tracker.sf, "read", read)
    instance.track_signal = lambda signal, cancel: (np.arange(0, len(signal) / 22050, 1.0), np.arange(0, len(signal) / 22050, 4.0))
    beats, downbeats = instance.track_file(Path("fixture.wav"))
    assert beats == list(range(300))
    assert len(beats) == len(set(beats))
    assert set(downbeats).issubset(beats)
    assert max(row["frames"] for row in reads) <= 180 * 22050
