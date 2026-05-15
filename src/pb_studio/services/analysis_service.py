import logging
from pb_studio.audio.analyzer import AudioAnalyzer
from pb_studio.video.scene_detect import SceneDetector
from pb_studio.data.repositories.media_repository import MediaRepository
from pb_studio.core.thread_pool import ThreadPoolManager, Worker

logger = logging.getLogger(__name__)

class AnalysisService:
    def __init__(self):
        self.audio_analyzer = AudioAnalyzer()
        self.scene_detector = SceneDetector()
        self.media_repo = MediaRepository()
        self.pool = ThreadPoolManager()

    def analyze_media(self, media_id: int, file_path: str, on_complete=None, on_error=None):
        """
        Starts analysis in background thread.
        Calls on_complete(result_dict) when done.
        """
        # P3.4 vulture-clarification: status_callback ist PyQt-Legacy-Signal-Param, API-Stability.
        def run_analysis(progress_callback=None, status_callback=None):  # noqa: ARG002
            results = {}

            # Zwischenstatus setzen (verhindert Re-Analyse bei Crash)
            try:
                self.media_repo.update_status(media_id, "analyzing")
            except Exception as e:
                logger.warning(f"Could not update status to analyzing: {e}")

            # Determine type by extension
            ext = file_path.lower().rsplit(".", 1)[-1] if "." in file_path else ""
            is_audio = ext in ["mp3", "wav", "flac", "ogg", "aac"]
            is_video = ext in ["mp4", "mov", "avi", "mkv", "webm"]

            if is_audio or is_video:
                # Audio Analysis (BPM)
                try:
                    logger.info(f"Running Audio Analysis on {file_path}")
                    audio_result = self.audio_analyzer.analyze_file(file_path)
                    logger.debug(f"RAW AUDIO RESULT: {str(audio_result)[:200]}...")
                    results["bpm"] = audio_result.get("bpm", 0)
                    results["beats"] = audio_result.get("beat_data", [])
                except Exception as e:
                    logger.error(f"Audio analysis failed: {e}")
                    results["audio_error"] = str(e)

            if is_video:
                # Scene Detection
                try:
                    logger.info(f"Running Scene Detection on {file_path}")
                    scenes = self.scene_detector.detect_scenes(file_path)
                    results["scenes"] = scenes
                except Exception as e:
                    logger.error(f"Scene detection failed: {e}")
                    results["scene_error"] = str(e)

            # Status basierend auf Ergebnis setzen
            has_errors = "audio_error" in results or "scene_error" in results
            has_results = "bpm" in results or "scenes" in results

            try:
                if has_errors and not has_results:
                    self.media_repo.update_status(media_id, "error", results)
                else:
                    self.media_repo.update_status(media_id, "ready", results)
            except Exception as e:
                logger.error(f"Could not update media status: {e}")

            return results

        worker = Worker(run_analysis)

        if on_complete:
            worker.signals.result.connect(on_complete)
        if on_error:
            worker.signals.error.connect(on_error)

        self.pool.start(worker)
        logger.info(f"Analysis queued for media_id={media_id}")
