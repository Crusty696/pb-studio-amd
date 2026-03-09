"""Thumbnail Generator - Erstellt Thumbnails für Video-Clips.

Extrahiert Frame 0 und speichert als JPEG in proxy_cache/.
AMD-Version: Identisch (rein OpenCV, kein GPU).
"""

import logging
from pathlib import Path

import cv2

logger = logging.getLogger(__name__)


def generate_clip_thumbnail(
    video_path: str, clip_id: int, project_root: str | None = None
) -> str | None:
    """Generiert Thumbnail für Video-Clip.

    Returns:
        Pfad zum Thumbnail oder None bei Fehler
    """
    try:
        if project_root:
            thumbnail_dir = Path(project_root) / "proxy_cache"
        else:
            thumbnail_dir = Path(video_path).parent / "proxy_cache"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)

        thumbnail_path = thumbnail_dir / f"clip_{clip_id}_thumb.jpg"

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Thumbnail: Kann Video nicht öffnen: {video_path}")
            return None

        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.error(f"Thumbnail: Kann Frame 0 nicht lesen: {video_path}")
                return None

            height, width = frame.shape[:2]
            if height == 0 or width == 0:
                return None

            target_w, target_h = 320, 240
            aspect = width / height
            if aspect > (target_w / target_h):
                new_w = target_w
                new_h = int(target_w / aspect)
            else:
                new_h = target_h
                new_w = int(target_h * aspect)

            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(thumbnail_path), resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
            logger.debug(f"Thumbnail erstellt: {thumbnail_path.name}")
            return str(thumbnail_path)
        finally:
            cap.release()

    except Exception as e:
        logger.error(f"Thumbnail Fehler für {Path(video_path).name}: {e}")
        return None


def batch_generate_thumbnails(
    video_clips: list[dict], project_root: str | None = None
) -> dict[int, str]:
    """Generiert Thumbnails für mehrere Clips.

    Args:
        video_clips: Liste von {id, file_path}

    Returns:
        Dict {clip_id: thumbnail_path}
    """
    results = {}
    for clip in video_clips:
        clip_id = clip.get("id")
        file_path = clip.get("file_path")
        if not clip_id or not file_path:
            continue
        tp = generate_clip_thumbnail(file_path, clip_id, project_root)
        if tp:
            results[clip_id] = tp

    logger.info(f"Batch-Thumbnails: {len(results)}/{len(video_clips)} OK")
    return results
