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


def _bounded_duration(
    total_frames: int,
    fps: float,
    duration_seconds: Optional[float] = None,
) -> float:
    decoded_duration = total_frames / fps if total_frames > 0 and fps > 0 else 0.0
    if duration_seconds is None or duration_seconds <= 0:
        return decoded_duration
    if decoded_duration <= 0:
        return duration_seconds
    return min(decoded_duration, duration_seconds)


class FrameGrabber:
    """Extrahiert Frames aus Videos mittels OpenCV."""

    def __init__(self, default_count: int = 10):
        self.default_count = default_count

    def extract_batch(
        self, video_path: str, start_time: float, end_time: float,
        count: Optional[int] = None,
        duration_seconds: Optional[float] = None,
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
            duration = _bounded_duration(total_frames, fps, duration_seconds)

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

    def extract_thumbnail_strip(
        self,
        video_path: str,
        n: int = 8,
        size: tuple = (160, 90),
        duration_seconds: Optional[float] = None,
    ) -> list:
        """Extract N evenly-spaced thumbnails across the full video.

        Returns list of PIL.Image (length == n) or [] if video unreadable.
        Used by the timeline clip template to show a frame strip a la Premiere.
        """
        from PIL import Image
        import cv2

        if n <= 0:
            return []
        if not Path(video_path).exists():
            return []

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        try:
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            duration = _bounded_duration(total, fps, duration_seconds)
            if total <= 0 or duration <= 0:
                return []

            # Pick n evenly-spaced time points; clamp to [0, duration-1/fps]
            step = duration / max(1, n)
            offsets = [min(duration - 1.0 / fps, step * i + step / 2.0) for i in range(n)]

            out = []
            for t in offsets:
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
                ret, frame = cap.read()
                if not ret or frame is None:
                    if out:
                        out.append(out[-1])  # duplicate previous to keep length == n
                    continue
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb).resize(size, Image.LANCZOS)
                out.append(img)
            return out
        finally:
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
