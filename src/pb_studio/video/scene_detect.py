import logging
from scenedetect import open_video, SceneManager, ContentDetector

logger = logging.getLogger(__name__)

class SceneDetector:
    def __init__(self, threshold=8.0):
        self.threshold = threshold

    def detect_scenes(self, video_path: str, duration_seconds: float | None = None):
        """
        Detects scenes in a video.
        Returns list of (start_sec, end_sec) tuples.
        """
        logger.info(f"Detecting scenes for: {video_path} (Threshold: {self.threshold})")
        scene_list = []
        
        video = None
        try:
            video = open_video(video_path)
            scene_manager = SceneManager()
            
            # ADAPTIVE: Use AdaptiveDetector to ignore gradual light changes and motion
            try:
                from scenedetect.detectors import AdaptiveDetector
                # adaptive_threshold scale is slightly different from content threshold
                scene_manager.add_detector(AdaptiveDetector(adaptive_threshold=self.threshold, min_scene_len=15))
            except ImportError:
                scene_manager.add_detector(ContentDetector(threshold=self.threshold))

            # Detect
            scene_manager.detect_scenes(video, show_progress=False)
            scenes = scene_manager.get_scene_list()

            # Convert FrameTimecodes to seconds
            for scene in scenes:
                start, end = scene
                start_seconds = max(0.0, start.get_seconds())
                end_seconds = end.get_seconds()
                if duration_seconds is not None and duration_seconds > 0:
                    start_seconds = min(start_seconds, duration_seconds)
                    end_seconds = min(end_seconds, duration_seconds)
                if end_seconds > start_seconds:
                    scene_list.append((start_seconds, end_seconds))

            if not scene_list:
                logger.warning(f"No scenes detected for {video_path}, adding full clip as single scene.")
                duration = duration_seconds or 0.0
                if duration <= 0:
                    # OpenCV duration is only a fallback when no authoritative
                    # ffprobe duration was supplied by the caller.
                    import cv2
                    cap = None
                    try:
                        cap = cv2.VideoCapture(video_path)
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                        duration = frame_count / fps if fps > 0 else 0.0
                    finally:
                        if cap is not None:
                            cap.release()
                if duration > 0:
                    scene_list.append((0.0, duration))

            logger.info(f"Found {len(scene_list)} scenes.")
            return scene_list

        except FileNotFoundError:
            logger.error(f"Video file not found: {video_path}")
            raise
        except Exception as e:
            logger.error(f"Scene detection failed: {e}")
            raise
        finally:
            # Video-Handle schliessen um File-Locks zu vermeiden
            if video is not None:
                try:
                    if hasattr(video, 'release'):
                        video.release()
                    elif hasattr(video, 'close'):
                        video.close()
                except Exception as release_err:
                    logger.warning("Failed to release video handle for %s: %s", video_path, release_err)
