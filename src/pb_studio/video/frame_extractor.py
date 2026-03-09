"""
Frame Extractor - Extrahiert Frames aus Videos mittels OpenCV.

Optimiert für schnellen Random Access mit äquidistanten Frames pro Szene.
AMD-Version: Identisch mit NVIDIA (rein CPU/OpenCV).
"""

import logging
from pathlib import Path
from typing import List, Optional

import cv2
from PIL import Image

logger = logging.getLogger(__name__)


class FrameGrabber:
    """Extrahiert Frames aus Videos mittels OpenCV."""

    def __init__(self, default_count: int = 10):
        self.default_count = default_count

    def extract_batch(
        self, video_path: str, start_time: float, end_time: float,
        count: Optional[int] = None
    ) -> List[Image.Image]:
        video_path = Path(video_path)
        count = count or self.default_count

        if not video_path.exists():
            raise FileNotFoundError(f"Video nicht gefunden: {video_path}")
        if start_time >= end_time:
            raise ValueError(f"start_time ({start_time}) >= end_time ({end_time})")

        cap = None
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise RuntimeError(f"Konnte Video nicht öffnen: {video_path}")

            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0

            if end_time > duration:
                logger.warning(f"end_time ({end_time:.2f}s) > Dauer ({duration:.2f}s)")
                end_time = duration

            time_points = self._calculate_time_points(start_time, end_time, count)
            frames = []
            for tp in time_points:
                frame = self._grab_frame_at(cap, tp)
                if frame is not None:
                    frames.append(frame)

            logger.debug(f"Extrahiert: {len(frames)}/{count} Frames aus {video_path.name}")
            return frames
        except Exception as e:
            logger.error(f"Frame-Extraktion Fehler: {e}")
            raise RuntimeError(f"Frame-Extraktion fehlgeschlagen: {e}") from e
        finally:
            if cap is not None:
                cap.release()

    def _calculate_time_points(self, start: float, end: float, count: int) -> List[float]:
        if count == 1:
            return [(start + end) / 2]
        step = (end - start) / (count - 1)
        return [start + i * step for i in range(count)]

    def _grab_frame_at(self, cap: cv2.VideoCapture, time_seconds: float) -> Optional[Image.Image]:
        cap.set(cv2.CAP_PROP_POS_MSEC, time_seconds * 1000)
        ret, frame = cap.read()
        if not ret or frame is None:
            return None
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    def extract_middle_frame(self, video_path: str, start_time: float, end_time: float) -> Optional[Image.Image]:
        frames = self.extract_batch(video_path, start_time, end_time, count=1)
        return frames[0] if frames else None

    def extract_thumbnail(self, video_path: str, time_seconds: float = 0.0, size: tuple = (320, 180)) -> Optional[Image.Image]:
        video_path = Path(video_path)
        if not video_path.exists():
            return None
        cap = None
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                return None
            frame = self._grab_frame_at(cap, time_seconds)
            if frame is None:
                return None
            frame.thumbnail(size, Image.Resampling.LANCZOS)
            return frame
        except Exception as e:
            logger.error(f"Thumbnail fehlgeschlagen: {e}")
            return None
        finally:
            if cap is not None:
                cap.release()

    def get_video_info(self, video_path: str) -> dict:
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video nicht gefunden: {video_path}")
        cap = None
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise RuntimeError(f"Konnte Video nicht öffnen: {video_path}")
            fps = cap.get(cv2.CAP_PROP_FPS)
            fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            return {
                "fps": fps, "frame_count": fc,
                "duration": fc / fps if fps > 0 else 0,
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            }
        finally:
            if cap is not None:
                cap.release()
