"""
Tests for SmartDirector integration with GenerationService.

Tests cover:
- SmartDirector data classes (AudioAnalysis, ClipAnalysis, Timeline, etc.)
- Mood classification logic
- Match matrix computation
- GenerationService smart/basic routing
- VideoGenerator.generate_from_timeline method
- UI config propagation (use_smart_director flag)
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

from pb_studio.ai.smart_director import (
    SmartDirector,
    AudioAnalysis,
    ClipAnalysis,
    Timeline,
    TimelineClip,
    MoodCategory,
)


# =============================================================================
# Data Class Tests
# =============================================================================

class TestDataClasses:
    """Test SmartDirector data structures."""

    def test_audio_analysis_creation(self):
        aa = AudioAnalysis(
            file_path="test.mp3",
            duration_sec=180.0,
            bpm=128.0,
            beat_times=[0.0, 0.47, 0.94],
            downbeat_times=[0.0, 0.94],
            mood_tags=["energetic", "bright"],
            mood_scores={"energetic": 0.8, "bright": 0.6},
            energy_curve=np.array([0.5, 0.7, 0.9], dtype=np.float32),
            energy_timestamps=np.array([0.0, 1.0, 2.0], dtype=np.float32),
            dominant_mood=MoodCategory.ENERGETIC,
        )
        assert aa.bpm == 128.0
        assert aa.dominant_mood == MoodCategory.ENERGETIC
        assert len(aa.beat_times) == 3

    def test_clip_analysis_creation(self):
        ca = ClipAnalysis(
            file_path="clip.mp4",
            duration_sec=10.0,
            embedding=np.zeros(1152, dtype=np.float32),
            content_tags=["nature scenery"],
            content_scores={"nature scenery": 0.9},
            motion_score=0.3,
            brightness=0.7,
            dominant_colors=[(128, 200, 100)],
        )
        assert ca.file_path == "clip.mp4"
        assert ca.embedding.shape == (1152,)
        assert ca.motion_score == 0.3

    def test_timeline_clip_defaults(self):
        tc = TimelineClip(
            source_path="clip.mp4",
            start_time=0.0,
            duration=3.0,
            source_start=0.0,
            source_end=3.0,
        )
        assert tc.transition_in == "cut"
        assert tc.speed_factor == 1.0
        assert tc.match_score == 0.0

    def test_timeline_creation(self):
        clips = [
            TimelineClip("a.mp4", 0.0, 3.0, 0.0, 3.0),
            TimelineClip("b.mp4", 3.0, 2.0, 1.0, 3.0),
        ]
        tl = Timeline(
            audio_path="track.mp3",
            duration_sec=5.0,
            clips=clips,
            cut_points=[0.0, 3.0, 5.0],
            total_clips=2,
            average_clip_duration=2.5,
            cuts_per_minute=24.0,
        )
        assert tl.total_clips == 2
        assert len(tl.cut_points) == 3

    def test_mood_category_values(self):
        assert MoodCategory.ENERGETIC.value == "energetic"
        assert MoodCategory.CALM.value == "calm"
        assert MoodCategory.NEUTRAL.value == "neutral"


# =============================================================================
# SmartDirector Logic Tests (mocked dependencies)
# =============================================================================

class TestSmartDirectorLogic:
    """Test SmartDirector internal algorithms without real models."""

    @patch("pb_studio.ai.smart_director.SmartDirector._register_models_with_vram_manager")
    @patch("pb_studio.config_manager.ConfigManager")
    @patch("pb_studio.core.get_vram_manager")
    def _make_director(self, mock_vram, mock_config, mock_register):
        """Helper to create SmartDirector with mocked heavy deps."""
        mock_vram.return_value = MagicMock()
        mock_config.return_value = MagicMock()
        director = SmartDirector.__new__(SmartDirector)
        director.config = MagicMock()
        director.vram_manager = MagicMock()
        director._clap = None
        director._siglip = None
        director._pacing_engine = None
        director._active_model = None
        director._clap_budget = 600
        director._siglip_budget = 900
        director._mood_visual_mapping = director._build_mood_visual_mapping()
        director._content_prompts = director._build_content_prompts()
        return director

    def test_classify_dominant_mood_energetic(self):
        d = self._make_director()
        mood = d._classify_dominant_mood({"energetic": 0.9, "calm": 0.1})
        assert mood == MoodCategory.ENERGETIC

    def test_classify_dominant_mood_empty(self):
        d = self._make_director()
        mood = d._classify_dominant_mood({})
        assert mood == MoodCategory.NEUTRAL

    def test_classify_dominant_mood_dark(self):
        d = self._make_director()
        mood = d._classify_dominant_mood({"dark": 0.7, "mysterious": 0.5})
        assert mood == MoodCategory.DARK

    def test_mood_visual_mapping_complete(self):
        d = self._make_director()
        mapping = d._mood_visual_mapping
        # All MoodCategory values (except neutral) should have a mapping
        for cat in MoodCategory:
            if cat != MoodCategory.NEUTRAL:
                assert cat.value in mapping, f"Missing mapping for {cat.value}"

    def test_content_prompts_not_empty(self):
        d = self._make_director()
        prompts = d._content_prompts
        assert len(prompts) > 5

    def test_calculate_mood_clip_match_energetic_high_motion(self):
        d = self._make_director()
        clip = ClipAnalysis(
            file_path="action.mp4",
            duration_sec=5.0,
            embedding=np.zeros(1152),
            content_tags=["sports action", "fast movement"],
            content_scores={"sports action": 0.9},
            motion_score=0.9,
            brightness=0.5,
            dominant_colors=[(128, 128, 128)],
        )
        score = d._calculate_mood_clip_match("energetic", clip)
        # High motion + "action"/"sports" keywords should score high
        assert score > 0.7

    def test_calculate_mood_clip_match_calm_low_motion(self):
        d = self._make_director()
        clip = ClipAnalysis(
            file_path="nature.mp4",
            duration_sec=10.0,
            embedding=np.zeros(1152),
            content_tags=["nature scenery", "water"],
            content_scores={"nature scenery": 0.8},
            motion_score=0.1,
            brightness=0.6,
            dominant_colors=[(100, 180, 100)],
        )
        score = d._calculate_mood_clip_match("calm", clip)
        assert score > 0.7

    def test_mood_to_visual_prompt(self):
        d = self._make_director()
        prompt = d._mood_to_visual_prompt("energetic")
        assert "fast" in prompt or "action" in prompt or "vibrant" in prompt

    def test_mood_to_visual_prompt_unknown(self):
        d = self._make_director()
        prompt = d._mood_to_visual_prompt("unknown_mood")
        assert prompt == "unknown_mood"

    def test_is_ready_always_true(self):
        d = self._make_director()
        assert d.is_ready is True

    def test_vram_usage_no_model(self):
        d = self._make_director()
        usage = d.get_vram_usage()
        assert usage["total"] == 0

    def test_vram_usage_clap_active(self):
        d = self._make_director()
        d._active_model = "clap"
        usage = d.get_vram_usage()
        assert usage["total"] == 600
        assert usage["clap"] == 600


# =============================================================================
# GenerationService Routing Tests
# =============================================================================

class TestGenerationServiceRouting:
    """Test that GenerationService correctly routes to smart/basic pipelines."""

    @patch("pb_studio.services.generation_service.Worker")
    @patch("pb_studio.services.generation_service.VideoGenerator")
    @patch("pb_studio.services.generation_service.ThreadPoolManager")
    def test_basic_generation_when_no_flag(self, mock_pool, mock_engine, mock_worker):
        from pb_studio.services.generation_service import GenerationService

        svc = GenerationService()
        config = {"master_audio": "a.mp3", "source_videos": ["v.mp4"], "output_path": "out.mp4"}

        on_progress = MagicMock()
        on_complete = MagicMock()
        on_error = MagicMock()

        svc.start_generation(config, on_progress, on_complete, on_error)

        # Worker should be started
        mock_pool.return_value.start.assert_called_once()
        mock_engine.return_value.reset_cancel.assert_called_once_with()

    @patch("pb_studio.services.generation_service.Worker")
    @patch("pb_studio.services.generation_service.VideoGenerator")
    @patch("pb_studio.services.generation_service.ThreadPoolManager")
    def test_smart_director_flag_set(self, mock_pool, mock_engine, mock_worker):
        from pb_studio.services.generation_service import GenerationService

        svc = GenerationService()
        config = {
            "master_audio": "a.mp3",
            "source_videos": ["v.mp4"],
            "output_path": "out.mp4",
            "use_smart_director": True,
        }

        on_progress = MagicMock()
        on_complete = MagicMock()
        on_error = MagicMock()

        svc.start_generation(config, on_progress, on_complete, on_error)

        # Worker should still be started (in background thread)
        mock_pool.return_value.start.assert_called_once()
        mock_engine.return_value.reset_cancel.assert_called_once_with()

    @patch("pb_studio.services.generation_service.VideoGenerator")
    @patch("pb_studio.services.generation_service.ThreadPoolManager")
    def test_unload_models(self, mock_pool, mock_engine):
        from pb_studio.services.generation_service import GenerationService

        svc = GenerationService()
        mock_director = MagicMock()
        svc._smart_director = mock_director

        svc.unload_models()

        mock_director.unload_all.assert_called_once()
        assert svc._smart_director is None

    @patch("pb_studio.services.generation_service.VideoGenerator")
    @patch("pb_studio.services.generation_service.ThreadPoolManager")
    def test_unload_models_when_none(self, mock_pool, mock_engine):
        from pb_studio.services.generation_service import GenerationService

        svc = GenerationService()
        # Should not raise when _smart_director is None
        svc.unload_models()


# =============================================================================
# VideoGenerator.generate_from_timeline Tests
# =============================================================================

class TestGenerateFromTimeline:
    """Test VideoGenerator.generate_from_timeline method."""

    @pytest.mark.skipif(
        not __import__("sys").platform.startswith("win"),
        reason="Temp-Dir Cleanup schlaegt auf Linux-gemountetm Windows-FS fehl (NTFS rmdir)"
    )
    @patch("pb_studio.video.engine.get_encoder_info")
    @patch("pb_studio.video.engine.check_amf_available")
    def test_generate_from_timeline_renders_all_clips(self, mock_amf, mock_info):
        mock_info.return_value = {"amf_available": True}
        mock_amf.return_value = True

        from pb_studio.video.engine import VideoGenerator

        gen = VideoGenerator()

        # Create a minimal timeline
        clips = [
            TimelineClip("a.mp4", 0.0, 3.0, 0.0, 3.0),
            TimelineClip("b.mp4", 3.0, 2.0, 1.0, 3.0),
        ]
        timeline = Timeline(
            audio_path="track.mp3",
            duration_sec=5.0,
            clips=clips,
            cut_points=[0.0, 3.0, 5.0],
            total_clips=2,
        )

        config = {
            "master_audio": "track.mp3",
            "output_path": "out.mp4",
            "use_hardware_encoding": True,
        }

        progress_calls = []

        def cb(step, pct):
            progress_calls.append((step, pct))

        # Mock ffmpeg calls
        with patch.object(gen, "_ffmpeg_extract") as mock_extract, \
             patch.object(gen, "_concat_segments") as mock_concat:

            result = gen.generate_from_timeline(config, timeline, callback=cb)

            # Should extract exactly 2 segments
            assert mock_extract.call_count == 2

            # First call: a.mp4, start=0.0, dur=3.0
            first_call = mock_extract.call_args_list[0]
            assert first_call[0][0] == "a.mp4"
            assert first_call[0][1] == 0.0
            assert first_call[0][2] == 3.0

            # Second call: b.mp4, start=1.0, dur=2.0
            second_call = mock_extract.call_args_list[1]
            assert second_call[0][0] == "b.mp4"
            assert second_call[0][1] == 1.0
            assert second_call[0][2] == 2.0

            # Should concatenate
            mock_concat.assert_called_once()

            # Should report done
            assert any("Done" in s for s, _ in progress_calls)

    @pytest.mark.skipif(
        not __import__("sys").platform.startswith("win"),
        reason="Temp-Dir Cleanup schlaegt auf Linux-gemountetm Windows-FS fehl (NTFS rmdir)"
    )
    @patch("pb_studio.video.engine.get_encoder_info")
    @patch("pb_studio.video.engine.check_amf_available")
    def test_generate_from_timeline_cancel(self, mock_amf, mock_info):
        mock_info.return_value = {"amf_available": False}
        mock_amf.return_value = False

        from pb_studio.video.engine import VideoGenerator

        gen = VideoGenerator()
        gen.cancel_flag = True  # Pre-set cancel

        clips = [TimelineClip("a.mp4", 0.0, 3.0, 0.0, 3.0)]
        timeline = Timeline("t.mp3", 3.0, clips, [0.0, 3.0], total_clips=1)
        config = {"master_audio": "t.mp3", "output_path": "out.mp4"}

        with patch.object(gen, "_ffmpeg_extract"), \
             patch.object(gen, "_concat_segments"):
            result = gen.generate_from_timeline(config, timeline)
            assert result.get("cancelled") is True

    @patch("pb_studio.video.engine.get_encoder_info")
    @patch("pb_studio.video.engine.check_amf_available")
    def test_basic_generate_respects_pre_set_cancel(self, mock_amf, mock_info):
        mock_info.return_value = {"amf_available": True}
        mock_amf.return_value = True

        from pb_studio.video.engine import VideoGenerator

        gen = VideoGenerator()
        gen.cancel()

        result = gen.generate(
            {
                "master_audio": "missing.mp3",
                "source_videos": ["missing.mp4"],
                "output_path": "out.mp4",
            }
        )

        assert result.get("cancelled") is True
