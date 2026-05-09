"""Moondream-Wrapper fuer Video-Frame Captioning + dominante Farb-Extraktion.

Standalone Funktionen + Fallback (KMeans fuer Color-Clustering wenn sklearn
fehlt). DirectML-Pfad fuer ONNX-Modell. Diese Wrapper-Modul wird von
backend.routers.video_router._run_video_analysis (Phase 4 / L-K2) aufgerufen
um result["dominant_colors"] und result["tags"] zu befuellen — vorher waren
diese Felder NIE gesetzt und Audit E4 Pacing-Helper (tags_overlap_score,
color_similarity) liefen ins Leere.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def extract_dominant_colors(frame_rgb: Optional[np.ndarray], k: int = 5) -> list[str]:
    """Extrahiert k dominante Farben aus Frame als Hex-Strings.

    KMeans-Clustering im RGB-Raum (sklearn). 100% pure NumPy-Fallback wenn
    sklearn fehlt (Histogram-Quantization mit 32er-Bins).

    Args:
        frame_rgb: Frame als (H, W, 3) uint8 RGB-Array. None oder leer -> [].
        k: Anzahl der dominanten Farben.

    Returns:
        Liste von k Hex-Strings im Format "#RRGGBB".
    """
    if frame_rgb is None:
        return []
    try:
        if frame_rgb.size == 0:
            return []
    except AttributeError:
        return []

    pixels = frame_rgb.reshape(-1, 3).astype(np.float32)

    # Sub-sampling fuer Performance bei grossen Frames (4K hat ~8M Pixel)
    if len(pixels) > 10000:
        rng = np.random.default_rng(seed=42)
        idx = rng.choice(len(pixels), 10000, replace=False)
        pixels = pixels[idx]

    try:
        from sklearn.cluster import KMeans
        kmeans = KMeans(n_clusters=k, n_init=3, random_state=42)
        kmeans.fit(pixels)
        # Sortiere Cluster nach Groesse (haeufigste Farbe zuerst)
        labels = kmeans.labels_
        counts = np.bincount(labels, minlength=k)
        order = np.argsort(counts)[::-1]
        centers = kmeans.cluster_centers_[order].astype(int)
    except ImportError:
        # Pure-NumPy Fallback: Histogram-Quantization
        quantized = (pixels // 32).astype(int) * 32
        unique, counts = np.unique(quantized, axis=0, return_counts=True)
        top_idx = np.argsort(counts)[::-1][:k]
        centers = unique[top_idx]
    except Exception as e:
        logger.debug(f"KMeans fehlgeschlagen (unkritisch): {e}")
        return []

    return [
        f"#{int(np.clip(c[0], 0, 255)):02X}"
        f"{int(np.clip(c[1], 0, 255)):02X}"
        f"{int(np.clip(c[2], 0, 255)):02X}"
        for c in centers
    ]


# Stopwords fuer Tag-Extraktion aus Captions (Englisch — Moondream2 spricht EN).
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "of", "in", "on", "at", "to", "with", "and", "or",
    "this", "that", "are", "was", "were", "be", "been", "being", "has", "have",
    "had", "for", "from", "by", "as", "it", "its", "their", "they", "them",
    "there", "here", "where", "when", "what", "which", "who", "whom", "how",
    "image", "picture", "photo", "shows", "showing", "depicts", "displays",
    "scene", "view", "appears",
})


def extract_tags_via_moondream(frame_rgb: Optional[np.ndarray]) -> list[str]:
    """Moondream-Captioning + Tag-Extraktion. Lazy ONNX/DirectML.

    Falls Moondream-ONNX nicht verfuegbar (kein Modell, kein DirectML, etc.)
    -> leere Liste (kein Crash, kein Log-Spam).

    Args:
        frame_rgb: Frame als (H, W, 3) uint8 RGB-Array.

    Returns:
        Liste von max 10 Tags (lowercased, Stopwords + kurze Woerter gefiltert).
    """
    if frame_rgb is None:
        return []
    try:
        if frame_rgb.size == 0:
            return []
    except AttributeError:
        return []

    try:
        from PIL import Image
        from pb_studio.video.moondream import MoondreamAnalyzer
    except ImportError as e:
        logger.debug(f"Moondream-Imports nicht verfuegbar: {e}")
        return []

    try:
        analyzer = MoondreamAnalyzer(lazy_load=True)
        # is_ready triggert lazy init; bei fehlendem Modell -> False, kein Crash
        analyzer._init_model()
        if not analyzer.is_ready:
            logger.debug("Moondream nicht ready (kein ONNX-Modell oder kein DirectML)")
            return []

        pil_img = Image.fromarray(frame_rgb)
        caption = analyzer.generate_caption(
            pil_img,
            prompt="Describe this image in one sentence.",
            max_tokens=64,
        )
        # Defensive: Moondream gibt bei Fehlern "[...]"-Marker zurueck
        if not caption or caption.startswith("["):
            return []

        words = caption.lower().split()
        tags = []
        seen = set()
        for w in words:
            cleaned = w.strip(".,!?\"'();:")
            if (
                len(cleaned) > 3
                and cleaned not in _STOPWORDS
                and cleaned not in seen
                and cleaned.isalpha()
            ):
                tags.append(cleaned)
                seen.add(cleaned)
            if len(tags) >= 10:
                break
        return tags
    except Exception as e:
        logger.debug(f"Moondream tagging fehlgeschlagen (unkritisch): {e}")
        return []
