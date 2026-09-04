"""Hash-bound Beat This! inference; callers must hold the shared GPU lock.

The source graph contains dynamic shape/rotary-position calculations assigned
to CPU by ORT 1.19.2. Fixing the actual input shape in memory lets ORT fold them
away, so the existing strict DirectML contract remains enabled. Source assets
are never rewritten. Short inputs retain their actual length, not 1500-frame
padding that would change attention and therefore predictions.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

import numpy as np
import onnx
import onnxruntime as ort
import scipy.ndimage as ndi
import soundfile as sf
import soxr
import torch
from onnxruntime.tools.onnx_model_utils import fix_output_shapes, make_input_shape_fixed

from pb_studio.audio.downbeat_alignment import BeatThisUnavailable

from pb_studio.core.directml_adapter import (
    configure_directml_session_options,
    enforce_directml_session,
    get_directml_provider,
)

SAMPLE_RATE = 22050
N_FFT = 1024
HOP_LENGTH = 441
MEL_BINS = 128
FPS = 50.0
CHUNK_FRAMES = 1500
BORDER_FRAMES = 6
PEAK_KERNEL = 7
LOG_MULTIPLIER = 1000.0
FILE_WINDOW_SECONDS = 120.0
FILE_CONTEXT_SECONDS = 30.0
ASSET_NAMES = frozenset({"beat_this.onnx", "config.json", "mel-filterbank.bin"})
REPO_ROOT = Path(__file__).resolve().parents[3]


def validate_assets(model_dir: Path, manifest_path: Path) -> dict:
    """Verify all bytes before parsing config or opening ONNX."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest["files"]
        if manifest["schema_version"] != 1 or set(files) != ASSET_NAMES:
            raise ValueError("unsupported Beat This asset manifest")
        for name in sorted(ASSET_NAMES):
            path = model_dir / name
            expected = files[name]
            if path.stat().st_size != expected["size"]:
                raise ValueError(f"Beat This asset size mismatch: {name}")
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != expected["sha256"]:
                raise ValueError(f"Beat This asset SHA-256 mismatch: {name}")
        return manifest
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise BeatThisUnavailable(str(exc)) from exc


def deduplicate_peaks(peaks: np.ndarray) -> np.ndarray:
    """Reference plateau handling: merge peaks at most one frame apart."""
    result: list[float] = []
    for raw in peaks:
        value = float(raw)
        if not result or value - result[-1] > 1.0:
            result.append(value)
            count = 1
        else:
            count += 1
            result[-1] += (value - result[-1]) / count
    return np.asarray(result, dtype=np.float64)


def postprocess(beat_logits: np.ndarray, downbeat_logits: np.ndarray):
    """Reference minimal peak picking; downbeats are a subset of beats."""
    times = []
    for logits in (beat_logits, downbeat_logits):
        maxima = ndi.maximum_filter1d(
            logits, size=PEAK_KERNEL, mode="constant", cval=-np.inf
        )
        indices = np.flatnonzero((logits == maxima) & (logits > 0.0))
        times.append(deduplicate_peaks(indices) / FPS)
    beats, downbeats = times
    if not len(beats):
        return beats, np.empty(0, dtype=np.float64)
    downbeats = np.unique([
        beats[int(np.argmin(np.abs(beats - time)))] for time in downbeats
    ])
    return beats, downbeats


class BeatThisTracker:
    """One task-owned session; no persistent model cache or implicit fallback."""

    def __init__(
        self,
        model_dir: Path | None = None,
        manifest_path: Path | None = None,
    ) -> None:
        self.model_dir = model_dir or REPO_ROOT / "models" / "beat_this"
        self.manifest = validate_assets(
            self.model_dir,
            manifest_path or REPO_ROOT / "config" / "beat-this-assets.json",
        )
        if "DmlExecutionProvider" not in ort.get_available_providers():
            raise BeatThisUnavailable("DmlExecutionProvider unavailable")
        self._provider = get_directml_provider()
        self._session = None
        self._session_frames = 0
        self._filterbank = torch.from_numpy(
            np.fromfile(self.model_dir / "mel-filterbank.bin", dtype="<f4")
            .reshape(N_FFT // 2 + 1, MEL_BINS)
        )
        self._window = torch.hann_window(N_FFT)

    def close(self) -> None:
        self._session = None
        self._session_frames = 0

    def _get_session(self, frames: int):
        if self._session is not None and self._session_frames == frames:
            return self._session
        self.close()
        model = onnx.load(self.model_dir / "beat_this.onnx")
        make_input_shape_fixed(model.graph, "spect", [1, frames, MEL_BINS])
        fix_output_shapes(model)
        options = configure_directml_session_options(ort.SessionOptions())
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        session = ort.InferenceSession(
            model.SerializeToString(), sess_options=options,
            providers=[self._provider],
        )
        self._session = enforce_directml_session(session)
        self._session_frames = frames
        return self._session

    def log_mel(self, signal: np.ndarray) -> np.ndarray:
        signal = np.asarray(signal, dtype=np.float32)
        if signal.ndim != 1 or not np.isfinite(signal).all():
            raise ValueError("Beat This expects finite mono audio")
        if len(signal) <= N_FFT // 2:
            return np.empty((0, MEL_BINS), dtype=np.float32)
        with torch.inference_mode():
            magnitude = torch.stft(
                torch.from_numpy(signal), N_FFT, hop_length=HOP_LENGTH,
                window=self._window, center=True, pad_mode="reflect",
                normalized=True, return_complex=True,
            ).abs().T
            return torch.log1p(LOG_MULTIPLIER * (magnitude @ self._filterbank)).numpy()

    def track_signal(
        self, signal: np.ndarray, check_cancelled: Callable[[], None] | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        spect = self.log_mel(signal)
        size = len(spect)
        if not size:
            return np.empty(0), np.empty(0)
        stride = CHUNK_FRAMES - 2 * BORDER_FRAMES
        starts = np.arange(-BORDER_FRAMES, size - BORDER_FRAMES, stride)
        if size > stride:
            starts[-1] = size - (CHUNK_FRAMES - BORDER_FRAMES)
        beat = np.full(size, -1000.0, dtype=np.float32)
        downbeat = beat.copy()
        written = 0
        for start in starts:
            if check_cancelled is not None:
                check_cancelled()
            piece = spect[max(start, 0):min(start + CHUNK_FRAMES, size)]
            left = max(0, -start)
            right = max(0, min(BORDER_FRAMES, start + CHUNK_FRAMES - size))
            piece = np.pad(piece, ((left, right), (0, 0)))
            session = self._get_session(len(piece))
            predictions = session.run(
                ["beat", "downbeat"], {"spect": piece[None].astype(np.float32)}
            )
            lo = max(written, start + BORDER_FRAMES)
            hi = min(size, start + len(piece) - BORDER_FRAMES)
            offset = lo - (start + BORDER_FRAMES)
            for target, values in zip((beat, downbeat), predictions):
                values = values[0, BORDER_FRAMES:-BORDER_FRAMES]
                target[lo:hi] = values[offset:offset + hi - lo]
            written = max(written, hi)
        return postprocess(beat, downbeat)

    def track_file(
        self, path: str | Path,
        check_cancelled: Callable[[], None] | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> tuple[list[float], list[float]]:
        """Bounded decoding with context; no writes to media or analysis stores.

        Long-file window seams are an explicit host policy, not a claim of
        bit-parity with whole-file reference chunking. Context predictions are
        discarded; only each disjoint core interval contributes timestamps.
        """
        info = sf.info(str(path))
        duration = info.frames / info.samplerate
        collected: tuple[list[float], list[float]] = ([], [])
        for core_start in np.arange(0.0, duration, FILE_WINDOW_SECONDS):
            if check_cancelled is not None:
                check_cancelled()
            core_end = min(duration, core_start + FILE_WINDOW_SECONDS)
            start = max(0.0, core_start - FILE_CONTEXT_SECONDS)
            end = min(duration, core_end + FILE_CONTEXT_SECONDS)
            first_sample = round(start * info.samplerate)
            signal, rate = sf.read(
                str(path), start=first_sample,
                frames=round(end * info.samplerate) - first_sample,
                dtype="float64", always_2d=True,
            )
            signal = signal.mean(axis=1)
            if rate != SAMPLE_RATE:
                signal = soxr.resample(signal, rate, SAMPLE_RATE)
            predictions = self.track_signal(signal, check_cancelled)
            for target, times in zip(collected, predictions):
                target.extend(
                    float(t + start) for t in times
                    if core_start <= t + start < core_end
                )
            if on_progress is not None:
                on_progress(100.0 * core_end / duration)
        return sorted(set(collected[0])), sorted(set(collected[1]))
