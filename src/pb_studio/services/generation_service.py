import logging
from src.pb_studio.core.thread_pool import ThreadPoolManager, Worker
from src.pb_studio.video.engine import VideoGenerator

logger = logging.getLogger(__name__)


class GenerationService:
    def __init__(self):
        self.engine = VideoGenerator()
        self.thread_pool = ThreadPoolManager()
        self._smart_director = None

    def start_generation(self, config: dict, on_progress, on_complete, on_error):
        """Starts generation in background thread.

        If config contains "use_smart_director": True, the SmartDirector
        AI pipeline is used for audio mood analysis, clip matching,
        and intelligent timeline generation before rendering.
        """
        use_ai = config.get("use_smart_director", False)

        if use_ai:
            run_fn = self._run_smart_generation
        else:
            run_fn = self._run_basic_generation

        def run_job(progress_callback):
            def engine_cb(step, pct):
                progress_callback.emit({"status": step, "progress": pct})
            return run_fn(config, engine_cb)

        worker = Worker(run_job)
        worker.signals.progress.connect(on_progress)
        worker.signals.result.connect(on_complete)
        worker.signals.error.connect(on_error)

        self.thread_pool.start(worker)
        logger.info("Generation job started (smart_director=%s).", use_ai)

    def _run_basic_generation(self, config: dict, callback):
        """Run the standard VideoGenerator pipeline."""
        return self.engine.generate(config, callback=callback)

    def _run_smart_generation(self, config: dict, callback):
        """Run SmartDirector-enhanced generation pipeline.

        Steps:
          1. Analyze audio with CLAP (mood, energy, beats)
          2. Analyze video clips with SigLIP (content, motion)
          3. Generate AI-optimized timeline (semantic matching)
          4. Render segments using VideoGenerator
        """
        from src.pb_studio.ai.smart_director import SmartDirector

        master_audio = config["master_audio"]
        source_videos = config["source_videos"]

        # Step 1: Initialize SmartDirector (lazy-loads models on demand)
        if callback:
            callback("Initializing AI Director...", 0)

        if self._smart_director is None:
            self._smart_director = SmartDirector(lazy_load=True)

        director = self._smart_director

        # Step 2: Analyze audio (BeatNet + CLAP mood classification)
        if callback:
            callback("Analyzing Audio (AI)...", 5)
        audio_analysis = director.analyze_audio(master_audio)
        logger.info(
            "Audio analyzed: %.1fs, %.0f BPM, mood=%s",
            audio_analysis.duration_sec,
            audio_analysis.bpm,
            audio_analysis.dominant_mood.value,
        )

        # Step 3: Analyze video clips (SigLIP embeddings + content tags)
        if callback:
            callback("Analyzing Video Clips (AI)...", 15)
        clip_analyses = director.analyze_clips(source_videos)
        logger.info("Analyzed %d clips", len(clip_analyses))

        # Step 4: Generate intelligent timeline
        if callback:
            callback("Generating AI Timeline...", 30)
        timeline = director.generate_timeline(audio_analysis, clip_analyses)
        logger.info(
            "Timeline: %d clips, %.1f cuts/min",
            timeline.total_clips,
            timeline.cuts_per_minute,
        )

        # Step 5: Render using VideoGenerator with the AI timeline
        if callback:
            callback("Rendering Segments...", 35)

        # Convert SmartDirector Timeline to engine-compatible format
        config_for_engine = dict(config)
        config_for_engine["_smart_timeline"] = timeline

        return self.engine.generate_from_timeline(
            config_for_engine, timeline, callback=callback
        )

    def cancel(self):
        self.engine.cancel()

    def unload_models(self):
        """Free VRAM by unloading SmartDirector models."""
        if self._smart_director is not None:
            self._smart_director.unload_all()
            self._smart_director = None
            logger.info("SmartDirector models unloaded")
