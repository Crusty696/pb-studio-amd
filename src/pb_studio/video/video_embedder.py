"""Legacy Brain cache identity for the registered SigLIP ONNX encoder.

The historical Hugging Face/Torch producer is intentionally unavailable.
Production embeddings are created by ``pb_studio.ai.siglip_wrapper`` and have
1152 dimensions. Missing registered assets remain explicitly unavailable.

LEGACY — kein Produktionsaufrufer (Zustandsaufnahme 2026-08-30, E-3).

Abgeloest durch den registrierten SigLIP-ONNX-Pfad. Produktiv gelesen werden
aus diesem Modul nur noch die drei Konstanten (`video_router.py:476-477`,
`scripts/backfill_brain_embedding_cache.py`); Klasse und Zugangsfunktion
haben null Aufrufer, auch in Tests nicht.

Bewacht von `Tests/test_legacy_symbols_have_no_production_callers.py`.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

CURRENT_MODEL_NAME = "siglip_vision"
CURRENT_MODEL_VERSION = "onnx-dml-v1"
EMBED_DIM = 1152


@dataclass
class VideoEmbeddingResult:
    clip_embedding: np.ndarray  # (1152,)
    scene_embeddings: list[np.ndarray] = field(default_factory=list)
    scene_times: list[tuple[float, float]] = field(default_factory=list)
    cached: bool = False


_singleton: Optional["VideoEmbedder"] = None
_singleton_lock = threading.Lock()


def get_video_embedder(*, prefer_directml: bool = True) -> "VideoEmbedder":
    if not prefer_directml:
        raise ValueError("Video embeddings require the DirectML-only ONNX path")
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = VideoEmbedder(prefer_directml=prefer_directml)
    return _singleton


class VideoEmbedder:
    """Fail-closed compatibility surface for the removed Torch producer."""

    def __init__(self, *, prefer_directml: bool = True):
        if not prefer_directml:
            raise ValueError(
                "Video embeddings require the DirectML-only ONNX path"
            )
        self.prefer_directml = prefer_directml
        self.model_name = CURRENT_MODEL_NAME
        self.model_version = CURRENT_MODEL_VERSION
        self._model = None
        self._processor = None
        self._device = None
        self._dtype = None
        self._load_lock = threading.Lock()

    def _ensure_loaded(self) -> None:
        raise RuntimeError(
            "Legacy VideoEmbedder is unavailable. Use registered SigLIP ONNX "
            "through SigLIPWrapper; missing semantic assets remain unavailable."
        )

    def unload(self) -> None:
        """Compatibility no-op; this class owns no model session."""
        self._model = None

    def embed_scenes(
        self,
        video_path: str | Path,
        *,
        scenes: list[tuple[float, float]],
        batch_size: int = 8,
    ) -> VideoEmbeddingResult:
        """Sampelt 1 Frame pro Scene-Mitte und embeddet sie.

        Args:
            video_path: Pfad zum Video
            scenes: [(start, end), ...] Scene-Cuts
            batch_size: SigLIP-2 batch (auto-halve bei OOM)
        """
        self._ensure_loaded()
        raise AssertionError("unreachable")

    def _embed_batched(
        self, frames: list[np.ndarray], batch_size: int
    ) -> list[np.ndarray]:
        self._ensure_loaded()
        raise AssertionError("unreachable")

    @staticmethod
    def _extract_pooled(outputs):
        for attr in ("pooler_output", "image_embeds", "last_hidden_state"):
            v = getattr(outputs, attr, None)
            if v is not None:
                if attr == "last_hidden_state":
                    # mean-pool über Token-Dim
                    return v.mean(dim=1)
                return v
        # tuple fallback
        return outputs[0].mean(dim=1)


def _resize_emb(emb: np.ndarray, dim: int) -> np.ndarray:
    if emb.size >= dim:
        return emb[:dim].astype(np.float32)
    out = np.zeros(dim, dtype=np.float32)
    out[: emb.size] = emb
    return out
