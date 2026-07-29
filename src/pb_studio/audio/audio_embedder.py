"""Legacy Brain cache identity for the registered CLAP ONNX encoder.

Modell: laion/larger_clap_music
Window: 10s, Hop: 5s (50% overlap), 48 kHz Eingang.
Aggregation: window -> section -> mix-level (Mean-Pool).

The historical Hugging Face/Torch producer is intentionally unavailable.
Production semantic inference uses ``pb_studio.ai.clap_wrapper.CLAPAnalyzer``
and fails closed when registered ONNX assets or DirectML are unavailable.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

CURRENT_MODEL_NAME = "clap_audio"
CURRENT_MODEL_VERSION = "onnx-dml-v1"
EMBED_DIM = 512
TARGET_SR = 48000
WINDOW_SEC = 10.0
HOP_SEC = 5.0


@dataclass
class AudioEmbeddingResult:
    mix_embedding: np.ndarray  # (512,)
    section_embeddings: list[np.ndarray] = field(default_factory=list)
    window_embeddings: list[np.ndarray] = field(default_factory=list)
    window_starts: list[float] = field(default_factory=list)
    cached: bool = False


_singleton: Optional["AudioEmbedder"] = None
_singleton_lock = threading.Lock()


def get_audio_embedder(*, prefer_directml: bool = True) -> "AudioEmbedder":
    if not prefer_directml:
        raise ValueError("Audio embeddings require the DirectML-only ONNX path")
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = AudioEmbedder(prefer_directml=prefer_directml)
    return _singleton


class AudioEmbedder:
    """Fail-closed compatibility surface for the removed Torch producer."""

    def __init__(self, *, prefer_directml: bool = True):
        if not prefer_directml:
            raise ValueError(
                "Audio embeddings require the DirectML-only ONNX path"
            )
        self.prefer_directml = prefer_directml
        self.model_name = CURRENT_MODEL_NAME
        self.model_version = CURRENT_MODEL_VERSION
        self._model = None
        self._processor = None
        self._device = None
        self._load_lock = threading.Lock()

    def _ensure_loaded(self) -> None:
        raise RuntimeError(
            "Legacy AudioEmbedder is unavailable. Use registered CLAP ONNX "
            "through CLAPAnalyzer; missing semantic assets remain unavailable."
        )

    def embed_audio(
        self,
        audio_path: str | Path,
        *,
        section_segments: Optional[list[tuple[float, float]]] = None,
    ) -> AudioEmbeddingResult:
        """Berechnet window/section/mix-Embeddings für eine Audio-Datei.

        Args:
            audio_path: Pfad zur Audio-Datei
            section_segments: optional, Sub-Track-Segments [(start,end), ...]
                              fuer Section-Level. Default: keine Sections.
        """
        self._ensure_loaded()
        raise AssertionError("unreachable")

    @staticmethod
    def _load_audio(path: str) -> tuple[np.ndarray, int]:
        import librosa
        wav, sr = librosa.load(path, sr=TARGET_SR, mono=True)
        return wav.astype(np.float32), int(sr)


def _pad_to(arr: np.ndarray, target_len: int) -> np.ndarray:
    if arr.size >= target_len:
        return arr[:target_len]
    out = np.zeros(target_len, dtype=arr.dtype)
    out[: arr.size] = arr
    return out
