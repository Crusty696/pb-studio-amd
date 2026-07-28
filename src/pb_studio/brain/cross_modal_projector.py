"""Cross-Modal Projector CLAP <-> SigLIP (R-Brain-04 + R-Brain-05 + R-Brain-08).

Audio (CLAP, 512-dim) und Video (SigLIP2-Base, 768-dim via video_embedder.py)
leben in unterschiedlichen Raeumen. Beide werden in einen gemeinsamen 256-dim
Raum projiziert. Initial random (Johnson-Lindenstrauss); spaeter aus
Brain-Feedback gelernt (R-Brain-05).

R-Brain-08: per-instance hash-keyed projection cache. Cleared bei _load_weights()
und nach fit_pairs().
R-Brain-05: SGD on cosine-MSE loss von audio<->video Bewertungs-Paaren.

IRON RULES: AMD DirectML only (NumPy CPU), NumPy 1.x kompatibel, pathlib.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

import numpy as np

from pb_studio.audio.audio_embedder import (
    CURRENT_MODEL_NAME as _AUDIO_MODEL_NAME,
    CURRENT_MODEL_VERSION as _AUDIO_MODEL_VERSION,
    EMBED_DIM as _AUDIO_EMBED_DIM,
)
from pb_studio.video.video_embedder import (
    CURRENT_MODEL_NAME as _VIDEO_MODEL_NAME,
    CURRENT_MODEL_VERSION as _VIDEO_MODEL_VERSION,
    EMBED_DIM as _VIDEO_EMBED_DIM,
)

logger = logging.getLogger(__name__)

DEFAULT_COMMON_DIM = 256
DEFAULT_AUDIO_DIM = _AUDIO_EMBED_DIM
DEFAULT_AUDIO_MODEL_NAME = _AUDIO_MODEL_NAME
DEFAULT_AUDIO_MODEL_VERSION = _AUDIO_MODEL_VERSION
# Korrektur (2026-07-10, selbst-korrigiert nach Sweep-Audit): faelschlich
# kurzzeitig auf 1152 gesetzt, weil siglip_wrapper.py (SO400M, 1152-dim,
# nur fuer FAISS/clip_selector-Suche) mit dem tatsaechlichen Brain-Feeder
# verwechselt wurde. post_processor.py._load_video_embedding() liest via
# CURRENT_MODEL_NAME/CURRENT_MODEL_VERSION aus video_embedder.py
# (google/siglip2-base-patch16-384, EMBED_DIM=768) - DAS ist die reale
# Quelle fuer Cross-Modal-Similarity. 768 war die ganze Zeit richtig.
DEFAULT_VIDEO_DIM = _VIDEO_EMBED_DIM
DEFAULT_VIDEO_MODEL_NAME = _VIDEO_MODEL_NAME
DEFAULT_VIDEO_MODEL_VERSION = _VIDEO_MODEL_VERSION
DEFAULT_SEED = 42
WEIGHTS_FILENAME = "cross_modal_projector.npz"


class CrossModalProjector:
    """Projects CLAP audio + SigLIP video embeddings into a common space."""

    def __init__(
        self,
        *,
        common_dim: int = DEFAULT_COMMON_DIM,
        audio_dim: int = DEFAULT_AUDIO_DIM,
        video_dim: int = DEFAULT_VIDEO_DIM,
        seed: int = DEFAULT_SEED,
        weights_path: Optional[Path] = None,
        audio_model_name: str = DEFAULT_AUDIO_MODEL_NAME,
        audio_model_version: str = DEFAULT_AUDIO_MODEL_VERSION,
        video_model_name: str = DEFAULT_VIDEO_MODEL_NAME,
        video_model_version: str = DEFAULT_VIDEO_MODEL_VERSION,
    ):
        self.common_dim = int(common_dim)
        self.audio_dim = int(audio_dim)
        self.video_dim = int(video_dim)
        self.seed = int(seed)
        self.weights_path = Path(weights_path) if weights_path else None
        self.audio_model_name = str(audio_model_name)
        self.audio_model_version = str(audio_model_version)
        self.video_model_name = str(video_model_name)
        self.video_model_version = str(video_model_version)

        self._init_random_matrices()
        # R-Brain-08
        self._projection_cache: dict[tuple[str, str], np.ndarray] = {}
        self._proj_cache_hits = 0
        self._proj_cache_misses = 0
        if self.weights_path and self.weights_path.is_file():
            self._load_weights()

    # ---------- public projection API ----------

    def project_audio(self, emb: Optional[np.ndarray]) -> Optional[np.ndarray]:
        return self._project(emb, self.W_audio, expected_dim=self.audio_dim)

    def project_video(self, emb: Optional[np.ndarray]) -> Optional[np.ndarray]:
        return self._project(emb, self.W_video, expected_dim=self.video_dim)

    # R-Brain-08: hash-keyed cached variants
    def project_audio_for_hash(
        self, media_hash: Optional[str], emb: Optional[np.ndarray]
    ) -> Optional[np.ndarray]:
        if not media_hash:
            return self.project_audio(emb)
        key = (media_hash, "audio")
        cached = self._projection_cache.get(key)
        if cached is not None:
            self._proj_cache_hits += 1
            return cached
        self._proj_cache_misses += 1
        out = self.project_audio(emb)
        if out is not None:
            self._projection_cache[key] = out
        return out

    def project_video_for_hash(
        self, media_hash: Optional[str], emb: Optional[np.ndarray]
    ) -> Optional[np.ndarray]:
        if not media_hash:
            return self.project_video(emb)
        key = (media_hash, "video")
        cached = self._projection_cache.get(key)
        if cached is not None:
            self._proj_cache_hits += 1
            return cached
        self._proj_cache_misses += 1
        out = self.project_video(emb)
        if out is not None:
            self._projection_cache[key] = out
        return out

    def projection_cache_stats(self) -> dict:
        return {
            "size": len(self._projection_cache),
            "hits": self._proj_cache_hits,
            "misses": self._proj_cache_misses,
        }

    def clear_projection_cache(self) -> None:
        self._projection_cache.clear()
        self._proj_cache_hits = 0
        self._proj_cache_misses = 0

    def cosine(self, a: np.ndarray, b: np.ndarray) -> float:
        """Convenience: cosine on already-projected vectors. Returns 0..1."""
        a = np.asarray(a, dtype=np.float32).reshape(-1)
        b = np.asarray(b, dtype=np.float32).reshape(-1)
        if a.size == 0 or b.size == 0 or a.size != b.size:
            return 0.5
        a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
        b = np.nan_to_num(b, nan=0.0, posinf=0.0, neginf=0.0)
        na = float(np.linalg.norm(a)) + 1e-9
        nb = float(np.linalg.norm(b)) + 1e-9
        cos = float(np.dot(a, b) / (na * nb))
        if cos != cos:
            return 0.5
        return float(max(0.0, min(1.0, (cos + 1.0) / 2.0)))

    # ---------- R-Brain-05: learned projection ----------

    def fit_pairs(
        self,
        pairs: list,
        *,
        lr: float = 0.01,
        steps: int = 1,
        max_grad_norm: float = 1.0,
    ) -> dict:
        """SGD on cosine-MSE loss using audio-video feedback pairs.

        loss = 0.5 * (cos(a_hat, v_hat) - label)^2

        Standard L2-normalized-projection gradient:
          p = W_a^T @ x;  a_hat = p / ||p||
          q = W_v^T @ y;  v_hat = q / ||q||
          dL/dp = (cos - label) * (v_hat - cos * a_hat) / ||p||
          dW_a = outer(x, dL/dp)

        Args:
            pairs: list of (audio_emb_raw, video_emb_raw, label).
                label in [-1, 1]: perfect=+1, fits=+0.5, not_quite=-0.5, no_match=-1.
            lr: learning rate.
            steps: full passes over the pair list.
            max_grad_norm: per-step gradient L2-norm clip.

        Returns:
            dict with loss_before, loss_after, n_pairs, n_steps.
        """
        if not pairs:
            return {"loss_before": 0.0, "loss_after": 0.0,
                    "n_pairs": 0, "n_steps": 0}

        prepared: list[tuple[np.ndarray, np.ndarray, float]] = []
        for a_raw, v_raw, label in pairs:
            a = self._prepare_input(a_raw, self.audio_dim)
            v = self._prepare_input(v_raw, self.video_dim)
            if a is None or v is None:
                continue
            label_f = float(np.clip(label, -1.0, 1.0))
            prepared.append((a, v, label_f))

        if not prepared:
            return {"loss_before": 0.0, "loss_after": 0.0,
                    "n_pairs": 0, "n_steps": 0}

        loss_before = self._compute_loss(prepared)

        for _ in range(int(steps)):
            for x, y, label in prepared:
                self._sgd_step(x, y, label, lr, max_grad_norm)

        loss_after = self._compute_loss(prepared)

        # R-Brain-08: invalidate projection cache (matrices changed)
        self._projection_cache.clear()
        self._proj_cache_hits = 0
        self._proj_cache_misses = 0

        return {
            "loss_before": loss_before,
            "loss_after": loss_after,
            "n_pairs": len(prepared),
            "n_steps": int(steps),
        }

    def save(self) -> bool:
        """Persist matrices to weights_path. Returns False when path not set."""
        if self.weights_path is None:
            return False
        try:
            self.weights_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez(
                self.weights_path,
                W_audio=self.W_audio,
                W_video=self.W_video,
                common_dim=np.int32(self.common_dim),
                audio_dim=np.int32(self.audio_dim),
                video_dim=np.int32(self.video_dim),
                seed=np.int32(self.seed),
                audio_model_name=np.str_(self.audio_model_name),
                audio_model_version=np.str_(self.audio_model_version),
                video_model_name=np.str_(self.video_model_name),
                video_model_version=np.str_(self.video_model_version),
            )
            return True
        except Exception as e:
            logger.warning("CrossModalProjector save failed: %s", e)
            return False

    # ---------- internals ----------

    def _init_random_matrices(self) -> None:
        rng = np.random.RandomState(self.seed)
        scale = 1.0 / np.sqrt(self.common_dim)
        self.W_audio = (
            rng.standard_normal((self.audio_dim, self.common_dim)) * scale
        ).astype(np.float32)
        self.W_video = (
            rng.standard_normal((self.video_dim, self.common_dim)) * scale
        ).astype(np.float32)

    def _load_weights(self) -> None:
        try:
            with np.load(self.weights_path, allow_pickle=False) as data:
                cd = int(data["common_dim"])
                ad = int(data["audio_dim"])
                vd = int(data["video_dim"])
                file_identity = (
                    str(data["audio_model_name"].item()),
                    str(data["audio_model_version"].item()),
                    str(data["video_model_name"].item()),
                    str(data["video_model_version"].item()),
                )
                expected_identity = (
                    self.audio_model_name,
                    self.audio_model_version,
                    self.video_model_name,
                    self.video_model_version,
                )
                if (cd, ad, vd) != (
                    self.common_dim, self.audio_dim, self.video_dim,
                ):
                    raise ValueError(
                        "CrossModalProjector dimension mismatch: "
                        f"file={ad}/{vd}->{cd}, expected="
                        f"{self.audio_dim}/{self.video_dim}->{self.common_dim}"
                    )
                if file_identity != expected_identity:
                    raise ValueError(
                        "CrossModalProjector model identity mismatch: "
                        f"file={file_identity}, expected={expected_identity}"
                    )
                wa = np.asarray(data["W_audio"], dtype=np.float32)
                wv = np.asarray(data["W_video"], dtype=np.float32)
            if wa.shape != (self.audio_dim, self.common_dim):
                raise ValueError(f"W_audio shape mismatch: {wa.shape}")
            if wv.shape != (self.video_dim, self.common_dim):
                raise ValueError(f"W_video shape mismatch: {wv.shape}")
            self.W_audio = wa
            self.W_video = wv
            self._projection_cache.clear()
            self._proj_cache_hits = 0
            self._proj_cache_misses = 0
            logger.info(
                "CrossModalProjector loaded from %s (audio %s, video %s)",
                self.weights_path, wa.shape, wv.shape,
            )
        except Exception as e:
            raise RuntimeError(
                f"CrossModalProjector weights rejected: {self.weights_path}: {e}"
            ) from e

    def _project(
        self, emb: Optional[np.ndarray], W: np.ndarray, *, expected_dim: int,
    ) -> Optional[np.ndarray]:
        if emb is None:
            return None
        x = np.asarray(emb, dtype=np.float32).reshape(-1)
        if x.size == 0:
            return None
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        if x.size != expected_dim:
            logger.warning(
                "CrossModalProjector rejected embedding dimension %d; expected %d",
                x.size,
                expected_dim,
            )
            return None
        n = float(np.linalg.norm(x)) + 1e-9
        if n < 1e-6:
            return None
        x = x / n
        out = x @ W
        n2 = float(np.linalg.norm(out)) + 1e-9
        if n2 < 1e-6:
            return None
        return (out / n2).astype(np.float32)

    def _prepare_input(
        self, emb: Optional[np.ndarray], expected_dim: int
    ) -> Optional[np.ndarray]:
        """Returns L2-normalized fixed-size float32 vector. None on bad input."""
        if emb is None:
            return None
        x = np.asarray(emb, dtype=np.float32).reshape(-1)
        if x.size == 0:
            return None
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        if x.size != expected_dim:
            logger.warning(
                "CrossModalProjector training rejected embedding dimension %d; "
                "expected %d",
                x.size,
                expected_dim,
            )
            return None
        n = float(np.linalg.norm(x)) + 1e-9
        if n < 1e-6:
            return None
        return (x / n).astype(np.float32)

    def _compute_loss(
        self, prepared: list[tuple[np.ndarray, np.ndarray, float]]
    ) -> float:
        """Mean MSE on cosine over prepared pairs (already L2-normalized)."""
        if not prepared:
            return 0.0
        total = 0.0
        for x, y, label in prepared:
            p = x @ self.W_audio
            q = y @ self.W_video
            np_ = float(np.linalg.norm(p)) + 1e-9
            nq = float(np.linalg.norm(q)) + 1e-9
            cos = float(np.dot(p, q) / (np_ * nq))
            if cos != cos:
                cos = 0.0
            total += 0.5 * (cos - label) ** 2
        return total / len(prepared)

    def _sgd_step(
        self,
        x: np.ndarray,
        y: np.ndarray,
        label: float,
        lr: float,
        max_grad_norm: float,
    ) -> None:
        """One SGD step on a single pair. x, y already L2-normalized."""
        p = x @ self.W_audio                      # (common_dim,)
        q = y @ self.W_video
        np_ = float(np.linalg.norm(p)) + 1e-9
        nq = float(np.linalg.norm(q)) + 1e-9
        a_hat = p / np_
        v_hat = q / nq
        cos = float(np.dot(a_hat, v_hat))
        if cos != cos:
            return  # NaN guard

        err = cos - float(label)               # scalar
        # dL/dp = err * (v_hat - cos*a_hat) / np_
        dp = err * (v_hat - cos * a_hat) / np_
        dq = err * (a_hat - cos * v_hat) / nq

        # Gradient w.r.t. weight matrices: outer products
        gW_a = np.outer(x, dp).astype(np.float32)
        gW_v = np.outer(y, dq).astype(np.float32)

        # Gradient clipping
        ga_norm = float(np.linalg.norm(gW_a))
        if ga_norm > max_grad_norm:
            gW_a *= max_grad_norm / (ga_norm + 1e-9)
        gv_norm = float(np.linalg.norm(gW_v))
        if gv_norm > max_grad_norm:
            gW_v *= max_grad_norm / (gv_norm + 1e-9)

        self.W_audio -= lr * gW_a
        self.W_video -= lr * gW_v


# ---------- Singleton accessor ----------

_singleton: Optional[CrossModalProjector] = None
_singleton_lock = threading.Lock()


def get_default_projector(
    *,
    weights_path: Optional[Path] = None,
    common_dim: int = DEFAULT_COMMON_DIM,
) -> CrossModalProjector:
    """Lazy thread-safe singleton."""
    global _singleton
    if (
        _singleton is not None
        and _singleton.common_dim == common_dim
        and (_singleton.weights_path == weights_path or weights_path is None)
    ):
        return _singleton
    with _singleton_lock:
        if (
            _singleton is None
            or _singleton.common_dim != common_dim
            or (weights_path is not None and _singleton.weights_path != weights_path)
        ):
            _singleton = CrossModalProjector(
                common_dim=common_dim,
                weights_path=weights_path,
            )
        return _singleton


def reset_default_projector() -> None:
    """Test helper: forces fresh singleton on next get_default_projector()."""
    global _singleton
    with _singleton_lock:
        _singleton = None
