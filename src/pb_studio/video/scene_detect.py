import logging
from scenedetect import open_video, SceneManager, ContentDetector

logger = logging.getLogger(__name__)

class SceneDetector:
    def __init__(self, threshold=8.0):
        self.threshold = threshold

    def detect_scenes(self, video_path: str):
        """
        Detects scenes in a video.
        Returns list of (start_sec, end_sec) tuples.
        """
        logger.info(f"Detecting scenes for: {video_path} (Threshold: {self.threshold})")
        scene_list = []
        
        try:
            video = open_video(video_path)
            scene_manager = SceneManager()
            scene_manager.add_detector(ContentDetector(threshold=self.threshold))
            
            # Detect
            scene_manager.detect_scenes(video, show_progress=False)
            scenes = scene_manager.get_scene_list()
            
            # Convert FrameTimecodes to seconds
            for scene in scenes:
                start, end = scene
                scene_list.append((start.get_seconds(), end.get_seconds()))
                
            logger.info(f"Found {len(scene_list)} scenes.")
            return scene_list
            
        except Exception as e:
            logger.error(f"Scene detection failed: {e}")
            return []
