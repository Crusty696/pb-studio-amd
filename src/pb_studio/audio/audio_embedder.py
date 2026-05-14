"""CLAP audio embedder via torch-directml (Plan Phase 2 + Decision #15).

Modell: laion/larger_clap_music
Window: 10s, Hop: 5s (50% overlap), 48 kHz Eingang.
Aggregation: window -> section -> mix-level (Mean-Pool).

Singleton-Pattern, respektiert GPULockMiddleware (best-effort: pro Aufruf
kein eigener Lock, aber Caller MUSS with_gpu_task verwenden).

Cache: hash-basiert via EmbeddingCache (cross-project).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

CURRENT_MODEL_NAME = "laion/larger_clap_music"
CURRENT_MODEL_VERSION = "1.0"
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
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = AudioEmbedder(prefer_directml=prefer_directml)
    return _singleton


class AudioEmbedder:
    """Lazy-loaded CLAP-Audio-Tower auf torch-directml."""

    def __init__(self, *, prefer_directml: bool = True):
        self.prefer_directml = prefer_directml
        self.model_name = CURRENT_MODEL_NAME
        self.model_version = CURRENT_MODEL_VERSION
        self._model = None
        self._processor = None
        self._device = None
        self._load_lock = threading.Lock()

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            import torch
            from transformers import ClapModel, ClapProcessor

            if self.prefer_directml:
                # IRC-2 / IRON RULE 1: AMD DirectML ONLY — kein silent CPU-Fallback.
                # CLAP versteckt ohne DML ~600MB VRAM vor VRAMBudgetManager.
                try:
                    import torch_directml
                    self._device = torch_directml.device()
                    logger.info("AudioEmbedder using torch-directml device")
                except Exception as e:
                    raise RuntimeError(
                        f"torch-directml nicht verfuegbar: {e}. "
                        "IRON RULE 1: AMD DirectML ONLY. Bitte torch-directml installieren."
                    ) from e
            else:
                self._device = torch.device("cpu")

            self._processor = ClapProcessor.from_pretrained(self.model_name)
            self._model = ClapModel.from_pretrained(self.model_name)
            self._model.eval()
            try:
                self._model.to(self._device)
            except Exception as e:
                # IRC-2: Im DirectML-Mode hart failen statt silent zu CPU schwenken.
                if self.prefer_directml:
                    raise RuntimeError(
                        f"CLAP .to(directml) failed: {e}. IRON RULE 1: kein CPU-Fallback."
                    ) from e
                logger.warning("CLAP .to(device) failed: %s - staying on CPU (CPU-Mode)", e)
                self._device = torch.device("cpu")
                self._model.to(self._device)

            # Z1 / GPU-F3: CLAP-VRAM beim VRAMBudgetManager registrieren —
            # vorher waren ~600MB DML-VRAM unsichtbar fuer den Manager und
            # konnten bei Stem-Separation/Render-OOM-Fehler verursachen.
            if self.prefer_directml:
                try:
                    from pb_studio.core.vram_budget_manager import get_vram_manager
                    mgr = get_vram_manager()
                    mgr.reserve("brain_clap", force=False)
                except Exception as ve:
                    logger.warning("VRAM-Manager-Registrierung fehlgeschlagen (unkritisch): %s", ve)

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
        import torch

        self._ensure_loaded()

        wav, sr = self._load_audio(str(audio_path))
        if wav.size == 0:
            return AudioEmbeddingResult(
                mix_embedding=np.zeros(EMBED_DIM, dtype=np.float32),
            )

        win_samples = int(WINDOW_SEC * sr)
        hop_samples = int(HOP_SEC * sr)
        windows: list[np.ndarray] = []
        starts: list[float] = []
        if wav.size <= win_samples:
            windows.append(_pad_to(wav, win_samples))
            starts.append(0.0)
        else:
            for s in range(0, wav.size - win_samples + 1, hop_samples):
                windows.append(wav[s : s + win_samples])
                starts.append(s / sr)
            tail = wav.size - win_samples
            if tail > 0 and (tail % hop_samples) != 0:
                windows.append(_pad_to(wav[-win_samples:], win_samples))
                starts.append((wav.size - win_samples) / sr)

        win_embeddings: list[np.ndarray] = []
        with torch.no_grad():
            for w in windows:
                inputs = self._processor(
                    audios=[w], sampling_rate=sr, return_tensors="pt"
                )
                inputs = {k: v.to(self._device) for k, v in inputs.items()}
                feats = self._model.get_audio_features(**inputs)
                emb = feats.detach().cpu().numpy().reshape(-1).astype(np.float32)
                if emb.size != EMBED_DIM:
                    emb = emb[:EMBED_DIM]
                win_embeddings.append(emb)

        section_embeddings: list[np.ndarray] = []
        if section_segments:
            for (s_start, s_end) in section_segments:
                idxs = [
                    i for i, t in enumerate(starts)
                    if s_start <= t < s_end
                ]
                if idxs:
                    section_embeddings.append(
                        np.mean([win_embeddings[i] for i in idxs], axis=0)
                    )

        mix_embedding = (
            np.mean(win_embeddings, axis=0)
            if win_embeddings
            else np.zeros(EMBED_DIM, dtype=np.float32)
        )

        return AudioEmbeddingResult(
            mix_embedding=mix_embedding.astype(np.float32),
            section_embeddings=section_embeddings,
            window_embeddings=win_embeddings,
            window_starts=starts,
            cached=False,
        )

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
