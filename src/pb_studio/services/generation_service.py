import logging

try:
    from pb_studio.core.thread_pool import ThreadPoolManager, Worker
except ImportError:
    ThreadPoolManager = None  # type: ignore
    Worker = None  # type: ignore  # PyQt6 nicht verfügbar (Linux CI)

try:
    from pb_studio.video.engine import VideoGenerator
except ImportError:
    VideoGenerator = None  # type: ignore

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

        def run_job(progress_callback=None, status_callback=None):
            """Worker-Funktion - progress_callback ist ein PyQt Signal."""
            def engine_cb(step, pct):
                if progress_callback is not None:
                    try:
                        progress_callback.emit({"status": step, "progress": pct})
                    except Exception:
                        pass  # Signal kann fehlschlagen wenn UI geschlossen
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
        try:
            from pb_studio.ai.smart_director import SmartDirector

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

        except Exception as e:
            logger.error(f"Smart generation failed: {e}", exc_info=True)
            raise
        finally:
            # VRAM freigeben auch bei Fehler
            # (Nicht den SmartDirector selbst loeschen - nur Modelle entladen)
            if self._smart_director is not None:
                try:
                    self._smart_director.unload_all()
                    logger.info("SmartDirector models unloaded after generation")
                except Exception as cleanup_err:
                    logger.warning("Failed to unload SmartDirector models: %s", cleanup_err)

    def cancel(self):
        self.engine.cancel()

    def unload_models(self):
        """Free VRAM by unloading SmartDirector models and resetting singleton."""
        if self._smart_director is not None:
            try:
                self._smart_director.unload_all()
            except Exception as e:
                logger.warning(f"Error unloading SmartDirector models: {e}")
            self._smart_director = None
            logger.info("SmartDirector models unloaded")

        # Singleton zurücksetzen damit get_instance() frisch initialisiert
        try:
            from pb_studio.ai.smart_director import SmartDirector
            SmartDirector.reset_instance()
        except Exception as e:
            logger.debug(f"SmartDirector singleton reset skipped: {e}")
