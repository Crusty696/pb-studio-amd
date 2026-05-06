"""Brightness / Saturation / Color-Temperature pro Frame.

Plan Phase 1 #5. CPU-only via OpenCV. Default: 1 sample/sec.

Color-Temp-Heuristik: relative R/B-Ratio, normalisiert auf [-1, 1]
(positiv = warm, negativ = kalt). Keine echte Kelvin-Schätzung —
Brücken-Achse nutzt es als kontinuierliches Feature, nicht absolut.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VisualCurveResult:
    timestamps: list[float]
    brightness: list[float]
    saturation: list[float]
    color_temp: list[float]


def compute_visual_curves(
    video_path: str | Path,
    samples_per_sec: float = 1.0,
) -> VisualCurveResult:
    """Sampelt Frames im gegebenen Intervall, berechnet B/S/CT-Kurven.

    Args:
        video_path: Pfad zum Video
        samples_per_sec: Sampling-Rate (1.0 = 1 Frame pro Sekunde)
    """
    import cv2

    p = Path(video_path)
    if not p.is_file():
        raise FileNotFoundError(f"Not a file: {p}")

    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {p}")

    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if fps <= 0 or total_frames <= 0:
            return VisualCurveResult([], [], [], [])

        step_frames = max(1, int(round(fps / max(samples_per_sec, 1e-3))))

        ts: list[float] = []
        b: list[float] = []
        s: list[float] = []
        ct: list[float] = []

        frame_idx = 0
        while frame_idx < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            ts.append(frame_idx / fps)
            br, sa, te = _frame_metrics(frame)
            b.append(br)
            s.append(sa)
            ct.append(te)
            frame_idx += step_frames

        return VisualCurveResult(
            timestamps=ts, brightness=b, saturation=s, color_temp=ct
        )
    finally:
        cap.release()


def _frame_metrics(frame_bgr: np.ndarray) -> tuple[float, float, float]:
    """Liefert (brightness[0..1], saturation[0..1], color_temp[-1..1])."""
    import cv2

    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2].astype(np.float32) / 255.0
    s = hsv[:, :, 1].astype(np.float32) / 255.0
    brightness = float(np.mean(v))
    saturation = float(np.mean(s))

    b = frame_bgr[:, :, 0].astype(np.float32)
    g = frame_bgr[:, :, 1].astype(np.float32)
    r = frame_bgr[:, :, 2].astype(np.float32)
    r_mean = float(np.mean(r))
    b_mean = float(np.mean(b))
    g_mean = float(np.mean(g)) + 1e-6
    # warm/cool index: (R-B)/(R+B+G), bound to [-1, 1]
    color_temp = (r_mean - b_mean) / (r_mean + b_mean + g_mean)
    color_temp = max(-1.0, min(1.0, float(color_temp)))

    return brightness, saturation, color_temp
