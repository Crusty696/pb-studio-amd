"""Tests für visual_curves (Plan Phase 1)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pb_studio.video.visual_curves import compute_visual_curves


def _write_video(path: Path, frames: list[np.ndarray], fps: float = 24.0) -> None:
    """Schreibt ein simples MP4 mit gegebenen BGR-Frames."""
    import cv2
    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (w, h))
    if not writer.isOpened():
        pytest.skip("cv2 VideoWriter cannot encode mp4v on this system")
    try:
        for f in frames:
            writer.write(f)
    finally:
        writer.release()


def test_visual_curves_uniform_gray(tmp_path: Path):
    gray = np.full((48, 64, 3), 128, dtype=np.uint8)
    frames = [gray.copy() for _ in range(48)]  # 2 sec @ 24 fps
    p = tmp_path / "gray.mp4"
    _write_video(p, frames, fps=24.0)

    res = compute_visual_curves(p, samples_per_sec=1.0)
    assert len(res.brightness) == len(res.saturation) == len(res.color_temp)
    assert len(res.brightness) >= 1
    # Uniform gray -> brightness ~ 0.5, saturation ~ 0
    for b in res.brightness:
        assert 0.4 < b < 0.6
    for s in res.saturation:
        assert s < 0.05


def test_visual_curves_warm_vs_cool(tmp_path: Path):
    """Warmer (rot) Frame -> color_temp > 0; kühler (blau) Frame -> color_temp < 0."""
    h, w = 48, 64
    red = np.zeros((h, w, 3), dtype=np.uint8); red[..., 2] = 200  # BGR red channel
    blue = np.zeros((h, w, 3), dtype=np.uint8); blue[..., 0] = 200  # BGR blue channel

    p_red = tmp_path / "red.mp4"
    p_blue = tmp_path / "blue.mp4"
    _write_video(p_red, [red] * 24, fps=24.0)
    _write_video(p_blue, [blue] * 24, fps=24.0)

    res_red = compute_visual_curves(p_red, samples_per_sec=1.0)
    res_blue = compute_visual_curves(p_blue, samples_per_sec=1.0)

    if res_red.color_temp:
        assert res_red.color_temp[0] > 0
    if res_blue.color_temp:
        assert res_blue.color_temp[0] < 0


def test_visual_curves_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        compute_visual_curves(tmp_path / "ghost.mp4")
