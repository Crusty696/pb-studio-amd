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


def _extract_dominant_color_clusters(
    frame_rgb: Optional[np.ndarray],
    k: int,
) -> tuple[list[str], list[float]]:
    """Return dominant color centers and their normalized populations."""
    if frame_rgb is None:
        return [], []
    try:
        if frame_rgb.size == 0:
            return [], []
    except AttributeError:
        return [], []

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
        labels = kmeans.labels_
        counts = np.bincount(labels, minlength=k)
        order = np.argsort(counts)[::-1]
        centers = kmeans.cluster_centers_[order].astype(int)
        populations = counts[order]
    except ImportError:
        # Pure-NumPy Fallback: Histogram-Quantization
        quantized = (pixels // 32).astype(int) * 32
        unique, counts = np.unique(quantized, axis=0, return_counts=True)
        top_idx = np.argsort(counts)[::-1][:k]
        centers = unique[top_idx]
        populations = counts[top_idx]
    except Exception as e:
        logger.debug(f"KMeans fehlgeschlagen (unkritisch): {e}")
        return [], []

    colors = [
        f"#{int(np.clip(c[0], 0, 255)):02X}"
        f"{int(np.clip(c[1], 0, 255)):02X}"
        f"{int(np.clip(c[2], 0, 255)):02X}"
        for c in centers
    ]
    total_population = float(np.sum(populations))
    if total_population <= 0.0:
        return colors, []
    weights = [float(value) / total_population for value in populations]
    return colors, weights


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
    colors, _weights = _extract_dominant_color_clusters(frame_rgb, k)
    return colors


def extract_dominant_colors_with_weights(
    frame_rgb: Optional[np.ndarray],
    k: int = 5,
) -> tuple[list[str], list[float]]:
    """Extrahiert dominante Farben plus ausgerichtete Clusteranteile."""
    return _extract_dominant_color_clusters(frame_rgb, k)


def compute_color_features(
    hex_colors: list[str],
    weights: Optional[list[float]] = None,
) -> dict:
    """Berechnet Brightness/Saturation/Color-Temp/Mood-Tags aus dominanten Farben.

    Audit-Fix 2026-07-10 (Sweep-Finding HIGH-10): die Brain-Bridge-Achsen
    ``mood_match_weight``/``color_temp_match_weight`` (bridge_dimensions.py)
    waren strukturell tot, weil kein Producer ``avg_saturation``/
    ``avg_color_temp``/``mood_tags`` in der Video-Pipeline je befuellte.
    LM-Studio-Vision-Tags sind freies Deutsch und koennen nicht direkt gegen
    das feste englische Audio-Mood-Vokabular (``_audio_mood_score``:
    dark/cold/cool/moody/uplifting/warm/happy/energetic) matchen — daher
    deterministische Ableitung aus den bereits vorhandenen dominanten Farben,
    im selben Vokabular wie die Audio-Seite.

    Args:
        hex_colors: Liste von Hex-Farbstrings ("#RRGGBB"), z.B. aus
            ``extract_dominant_colors``.
        weights: Optionale, zu ``hex_colors`` ausgerichtete Clusteranteile.

    Returns:
        Dict mit ``avg_brightness``/``avg_saturation`` (0..1) und
        ``avg_color_temp`` (-1 kuehl .. +1 warm, passend zu
        ``_audio_mood_score``) und ``mood_tags`` (Liste aus dem Audio-
        Mood-Vokabular).
    """
    import colorsys

    default = {"avg_brightness": 0.5, "avg_saturation": 0.5, "avg_color_temp": 0.0, "mood_tags": []}
    if not hex_colors:
        return default

    brightness_vals: list[float] = []
    saturation_vals: list[float] = []
    warmth_vals: list[float] = []  # -1 (kuehl/blau) .. +1 (warm/rot)
    feature_weights: list[float] = []
    aligned_weights = (
        weights
        if weights is not None and len(weights) == len(hex_colors)
        else [1.0] * len(hex_colors)
    )
    for hex_str, raw_weight in zip(hex_colors, aligned_weights):
        h = (hex_str or "").lstrip("#")
        if len(h) != 6:
            continue
        try:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            weight = float(raw_weight)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(weight) or weight <= 0.0:
            continue
        _hue, sat, val = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        brightness_vals.append(val)
        saturation_vals.append(sat)
        warmth_vals.append((r - b) / 255.0)
        feature_weights.append(weight)

    total_weight = sum(feature_weights)
    if not brightness_vals or total_weight <= 0.0:
        return default

    avg_brightness = sum(
        value * weight for value, weight in zip(brightness_vals, feature_weights)
    ) / total_weight
    avg_saturation = sum(
        value * weight for value, weight in zip(saturation_vals, feature_weights)
    ) / total_weight
    avg_color_temp = sum(
        value * weight for value, weight in zip(warmth_vals, feature_weights)
    ) / total_weight

    mood_tags: list[str] = []
    if avg_color_temp > 0.15:
        mood_tags.append("warm")
    elif avg_color_temp < -0.15:
        mood_tags.append("cool")
    if avg_brightness < 0.3:
        mood_tags.append("dark")
    if avg_brightness > 0.35 and avg_saturation > 0.4 and avg_color_temp > 0.0:
        mood_tags.append("happy")

    return {
        "avg_brightness": avg_brightness,
        "avg_saturation": avg_saturation,
        "avg_color_temp": avg_color_temp,
        "mood_tags": mood_tags,
    }


# Stopwords fuer Tag-Extraktion aus Captions (Englisch — Moondream2 spricht EN).
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "of", "in", "on", "at", "to", "with", "and", "or",
    "this", "that", "are", "was", "were", "be", "been", "being", "has", "have",
    "had", "for", "from", "by", "as", "it", "its", "their", "they", "them",
    "there", "here", "where", "when", "what", "which", "who", "whom", "how",
    "image", "picture", "photo", "shows", "showing", "depicts", "displays",
    "scene", "view", "appears",
})


def extract_tags_via_moondream(frame_rgb: Optional[np.ndarray], analyzer: Optional[object] = None) -> list[str]:
    """Moondream-Captioning + Tag-Extraktion. Lazy ONNX/DirectML.

    Falls Moondream-ONNX nicht verfuegbar (kein Modell, kein DirectML, etc.)
    -> leere Liste (kein Crash, kein Log-Spam).

    Args:
        frame_rgb: Frame als (H, W, 3) uint8 RGB-Array.
        analyzer: Optionaler pre-initialisierter MoondreamAnalyzer zur Vermeidung von Model-Thrashing.

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

    local_analyzer = False
    try:
        if analyzer is None:
            analyzer = MoondreamAnalyzer(lazy_load=True)
            local_analyzer = True

        # is_ready triggert lazy init; bei fehlendem Modell -> False, kein Crash
        if hasattr(analyzer, '_init_model'):
            analyzer._init_model()
        if not getattr(analyzer, 'is_ready', False):
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
    finally:
        if local_analyzer and analyzer is not None:
            try:
                analyzer.unload()
            except Exception as ex:
                logger.debug(f"Fehler beim Entladen des MoondreamAnalyzers: {ex}")
