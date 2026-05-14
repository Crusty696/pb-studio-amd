"""SigLIP-2 Vision-Tower video embedder via torch-directml (Plan Phase 2 + Decision #16).

Modell: google/siglip2-base-patch16-384 (Vision-Tower only, 768-dim).
Frame-Sampling: 1 Frame pro Scene-Mitte. batch=8 + FP16, OOM-Fallback.

Aggregation: scene -> clip (gewichtet mit Scene-Dauer).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

CURRENT_MODEL_NAME = "google/siglip2-base-patch16-384"
CURRENT_MODEL_VERSION = "1.0"
EMBED_DIM = 768


@dataclass
class VideoEmbeddingResult:
    clip_embedding: np.ndarray  # (768,)
    scene_embeddings: list[np.ndarray] = field(default_factory=list)
    scene_times: list[tuple[float, float]] = field(default_factory=list)
    cached: bool = False


_singleton: Optional["VideoEmbedder"] = None
_singleton_lock = threading.Lock()


def get_video_embedder(*, prefer_directml: bool = True) -> "VideoEmbedder":
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = VideoEmbedder(prefer_directml=prefer_directml)
    return _singleton


class VideoEmbedder:
    """Lazy-loaded SigLIP-2 vision tower auf torch-directml."""

    def __init__(self, *, prefer_directml: bool = True):
        self.prefer_directml = prefer_directml
        self.model_name = CURRENT_MODEL_NAME
        self.model_version = CURRENT_MODEL_VERSION
        self._model = None
        self._processor = None
        self._device = None
        self._dtype = None
        self._load_lock = threading.Lock()

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            import torch
            # Vision-Tower only -> AutoImageProcessor avoids text tokenizer issues
            # (Siglip2Tokenizer registration not robust in transformers 4.49).
            from transformers import AutoImageProcessor, AutoModel

            if self.prefer_directml:
                # IRC-2 / IRON RULE 1: AMD DirectML ONLY — kein silent CPU-Fallback.
                # CPU-Mode versteckt VRAM-Druck vor VRAMBudgetManager und ist ca.
                # 10x langsamer als DML. Wenn torch-directml fehlt, loud failen.
                try:
                    import torch_directml
                    self._device = torch_directml.device()
                    self._dtype = torch.float16
                    logger.info("VideoEmbedder using torch-directml device (fp16)")
                except Exception as e:
                    raise RuntimeError(
                        f"torch-directml nicht verfuegbar: {e}. "
                        "IRON RULE 1: AMD DirectML ONLY. Bitte torch-directml installieren."
                    ) from e
            else:
                self._device = torch.device("cpu")
                self._dtype = torch.float32

            self._processor = AutoImageProcessor.from_pretrained(self.model_name)
            full = AutoModel.from_pretrained(self.model_name, torch_dtype=self._dtype)
            self._model = getattr(full, "vision_model", full)
            self._model.eval()
            try:
                self._model.to(self._device)
            except Exception as e:
                # IRC-2: Im DirectML-Mode hart failen statt silent zu CPU schwenken.
                if self.prefer_directml:
                    raise RuntimeError(
                        f"SigLIP .to(directml) failed: {e}. IRON RULE 1: kein CPU-Fallback."
                    ) from e
                logger.warning("SigLIP .to(device) failed: %s - CPU fallback (CPU-Mode)", e)
                self._device = __import__("torch").device("cpu")
                self._dtype = __import__("torch").float32
                self._model.to(self._device)

            # Z1 / GPU-F3: SigLIP-2-VRAM beim VRAMBudgetManager registrieren —
            # vorher waren ~1.1GB DML-VRAM unsichtbar fuer den Manager
            # (Brain-Embedder umging Reservation).
            if self.prefer_directml:
                try:
                    from pb_studio.core.vram_budget_manager import get_vram_manager
                    mgr = get_vram_manager()
                    mgr.reserve("brain_siglip2", force=False)
                except Exception as ve:
                    logger.warning("VRAM-Manager-Registrierung fehlgeschlagen (unkritisch): %s", ve)

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
        import cv2

        self._ensure_loaded()
        if not scenes:
            return VideoEmbeddingResult(
                clip_embedding=np.zeros(EMBED_DIM, dtype=np.float32),
            )

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        try:
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            if fps <= 0:
                return VideoEmbeddingResult(
                    clip_embedding=np.zeros(EMBED_DIM, dtype=np.float32),
                )

            frames = []
            for (s, e) in scenes:
                mid = (s + e) / 2.0
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(mid * fps)))
                ok, frame = cap.read()
                if not ok or frame is None:
                    frame = np.zeros((384, 384, 3), dtype=np.uint8)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(rgb)
        finally:
            cap.release()

        scene_embeddings = self._embed_batched(frames, batch_size)

        durations = np.asarray([max(e - s, 1e-6) for (s, e) in scenes], dtype=np.float32)
        weights = durations / durations.sum()
        clip_embedding = np.sum(
            np.stack(scene_embeddings, axis=0) * weights[:, None], axis=0
        ).astype(np.float32)

        return VideoEmbeddingResult(
            clip_embedding=clip_embedding,
            scene_embeddings=scene_embeddings,
            scene_times=list(scenes),
            cached=False,
        )

    def _embed_batched(
        self, frames: list[np.ndarray], batch_size: int
    ) -> list[np.ndarray]:
        import torch

        out: list[np.ndarray] = []
        i = 0
        bs = max(1, batch_size)
        while i < len(frames):
            batch = frames[i : i + bs]
            try:
                with torch.no_grad():
                    inputs = self._processor(images=batch, return_tensors="pt")
                    inputs = {
                        k: v.to(self._device, dtype=self._dtype)
                        if v.is_floating_point()
                        else v.to(self._device)
                        for k, v in inputs.items()
                    }
                    outputs = self._model(**inputs)
                    pooled = self._extract_pooled(outputs)
                    arr = pooled.detach().to("cpu").float().numpy()
                    for row in arr:
                        emb = row.reshape(-1).astype(np.float32)
                        if emb.size != EMBED_DIM:
                            emb = _resize_emb(emb, EMBED_DIM)
                        out.append(emb)
                i += bs
            except (RuntimeError, MemoryError) as e:
                msg = str(e).lower()
                if bs > 1 and (
                    "out of memory" in msg
                    or "oom" in msg
                    or "memory" in msg
                ):
                    logger.warning("VRAM-OOM bei batch_size=%d, halviere", bs)
                    bs = max(1, bs // 2)
                    continue
                raise
        return out

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
