"""
Unit tests for the Pacing Engine module.

Tests cover:
- PacingConfig creation and validation
- AdvancedPacingEngine timeline generation
- ClipSelector filtering and ranking
- Integration with audio analysis data
"""

import pytest
import numpy as np
from pb_studio.pacing import (
    AdvancedPacingEngine,
    PacingConfig,
    CutPoint,
    ClipSelector
)
from pb_studio.pacing.advanced_pacing_engine import SyncMode, TransitionType
from pb_studio.pacing.clip_selector import ClipMetadata


class TestPacingConfig:
    """Test PacingConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PacingConfig()

        assert config.pacing == 3
        assert config.precision == 8
        assert config.energy_react == 5
        assert config.chaos == 2
        assert config.min_clip_length == 2.0
        assert config.max_clip_length == 8.0
        assert config.sync_mode == SyncMode.HYBRID

    def test_custom_config(self):
        """Test custom configuration."""
        config = PacingConfig(
            pacing=5,
            precision=10,
            energy_react=8,
            chaos=5,
            min_clip_length=1.0,
            max_clip_length=10.0,
            sync_mode=SyncMode.BEAT_SYNC
        )

        assert config.pacing == 5
        assert config.sync_mode == SyncMode.BEAT_SYNC

    def test_legacy_conversion(self):
        """Test conversion to VideoGenerator format."""
        config = PacingConfig(pacing=4, precision=9)
        legacy = config.to_legacy_dict()

        assert "pacing" in legacy
        assert "precision" in legacy
        assert legacy["min_dur"] == 2.0
        assert legacy["max_dur"] == 8.0


class TestAdvancedPacingEngine:
    """Test AdvancedPacingEngine timeline generation."""

    @pytest.fixture
    def mock_audio_analysis(self):
        """Create mock audio analysis data."""
        # Generate 120 BPM beats (0.5s interval)
        beats = [[i * 0.5, 1 if i % 4 == 0 else 2] for i in range(40)]  # 20 seconds

        return {
            "bpm": 120,
            "beat_data": beats,
            "count": len(beats)
        }

    @pytest.fixture
    def mock_energy_curve(self):
        """Create mock energy curve."""
        times = np.linspace(0, 20, 100)
        # Sine wave energy curve
        energy = 0.5 + 0.5 * np.sin(2 * np.pi * 0.2 * times)
        return energy, times

    def test_engine_initialization(self):
        """Test engine initialization."""
        engine = AdvancedPacingEngine()

        assert engine.config is not None
        assert engine.timeline == []
        assert engine.audio_analysis is None

    def test_audio_structure_analysis(self, mock_audio_analysis, mock_energy_curve):
        """Test audio structure analysis."""
        engine = AdvancedPacingEngine()
        rms, times = mock_energy_curve

        engine.analyze_audio_structure(mock_audio_analysis, rms, times)

        assert engine.audio_analysis == mock_audio_analysis
        assert engine.energy_curve is not None
        assert len(engine.energy_curve) == len(rms)

    def test_hybrid_sync_planning(self, mock_audio_analysis, mock_energy_curve):
        """Test hybrid sync mode."""
        config = PacingConfig(sync_mode=SyncMode.HYBRID, pacing=3)
        engine = AdvancedPacingEngine(config)

        rms, times = mock_energy_curve
        engine.analyze_audio_structure(mock_audio_analysis, rms, times)

        cuts = engine.plan_cuts(total_duration=20.0)

        assert len(cuts) > 0
        assert all(isinstance(cut, CutPoint) for cut in cuts)
        assert all(cut.duration >= config.min_clip_length for cut in cuts)
        assert all(cut.duration <= config.max_clip_length for cut in cuts)

    def test_beat_sync_planning(self, mock_audio_analysis, mock_energy_curve):
        """Test pure beat sync mode."""
        config = PacingConfig(sync_mode=SyncMode.BEAT_SYNC)
        engine = AdvancedPacingEngine(config)

        rms, times = mock_energy_curve
        engine.analyze_audio_structure(mock_audio_analysis, rms, times)

        cuts = engine.plan_cuts(total_duration=20.0)

        # All cuts should be beat-aligned
        assert all(cut.beat_aligned for cut in cuts)

    def test_energy_sync_planning(self, mock_audio_analysis, mock_energy_curve):
        """Test energy-based sync mode."""
        config = PacingConfig(sync_mode=SyncMode.ENERGY_SYNC)
        engine = AdvancedPacingEngine(config)

        rms, times = mock_energy_curve
        engine.analyze_audio_structure(mock_audio_analysis, rms, times)

        cuts = engine.plan_cuts(total_duration=20.0)

        assert len(cuts) > 0

    def test_pacing_speed_effect(self, mock_audio_analysis, mock_energy_curve):
        """Test that pacing level affects cut frequency."""
        rms, times = mock_energy_curve

        # Fast pacing (5)
        fast_config = PacingConfig(pacing=5, chaos=0)
        fast_engine = AdvancedPacingEngine(fast_config)
        fast_engine.analyze_audio_structure(mock_audio_analysis, rms, times)
        fast_cuts = fast_engine.plan_cuts(20.0)

        # Slow pacing (1)
        slow_config = PacingConfig(pacing=1, chaos=0)
        slow_engine = AdvancedPacingEngine(slow_config)
        slow_engine.analyze_audio_structure(mock_audio_analysis, rms, times)
        slow_cuts = slow_engine.plan_cuts(20.0)

        # Fast pacing should generate more cuts (shorter clips)
        assert len(fast_cuts) > len(slow_cuts)

    def test_generate_edl(self, mock_audio_analysis, mock_energy_curve):
        """Test EDL generation."""
        engine = AdvancedPacingEngine()
        rms, times = mock_energy_curve

        engine.analyze_audio_structure(mock_audio_analysis, rms, times)
        engine.plan_cuts(20.0)

        edl = engine.generate_edit_decision_list()

        assert isinstance(edl, list)
        assert len(edl) == len(engine.timeline)
        assert all("time" in entry for entry in edl)
        assert all("duration" in entry for entry in edl)

    def test_statistics(self, mock_audio_analysis, mock_energy_curve):
        """Test statistics generation."""
        engine = AdvancedPacingEngine()
        rms, times = mock_energy_curve

        engine.analyze_audio_structure(mock_audio_analysis, rms, times)
        engine.plan_cuts(20.0)

        stats = engine.get_statistics()

        assert "total_cuts" in stats
        assert "beat_aligned_cuts" in stats
        assert "avg_cut_duration" in stats
        assert stats["total_cuts"] > 0

    def test_no_beats_fallback(self):
        """Test fallback when no beats detected."""
        engine = AdvancedPacingEngine()

        # Empty beat data
        empty_analysis = {"bpm": 0, "beat_data": [], "count": 0}
        rms = np.random.random(100)
        times = np.linspace(0, 20, 100)

        engine.analyze_audio_structure(empty_analysis, rms, times)
        cuts = engine.plan_cuts(20.0)

        # Should still generate cuts (time-based fallback)
        assert len(cuts) > 0


class TestClipSelector:
    """Test ClipSelector filtering and ranking."""

    @pytest.fixture
    def sample_clips(self):
        """Create sample clip metadata."""
        clips = [
            ClipMetadata(
                video_id=1,
                file_path="video1.mp4",
                start_time=0.0,
                duration=5.0,
                motion_score=0.8,
                energy_score=0.7,
                tags=["action", "outdoor"],
                embedding=np.random.random(768)
            ),
            ClipMetadata(
                video_id=2,
                file_path="video2.mp4",
                start_time=0.0,
                duration=5.0,
                motion_score=0.3,
                energy_score=0.4,
                tags=["calm", "indoor"],
                embedding=np.random.random(768)
            ),
            ClipMetadata(
                video_id=3,
                file_path="video3.mp4",
                start_time=0.0,
                duration=5.0,
                motion_score=0.9,
                energy_score=0.9,
                tags=["action", "fast"],
                embedding=np.random.random(768)
            )
        ]
        return clips

    def test_selector_initialization(self):
        """Test ClipSelector initialization."""
        selector = ClipSelector()

        assert selector.clip_cache == {}
        assert selector.vector_store is None

    def test_add_clips(self, sample_clips):
        """Test adding clips to selector."""
        selector = ClipSelector()

        for clip in sample_clips:
            clip_id = selector.add_clip(clip)
            assert clip_id in selector.clip_cache

        assert len(selector.clip_cache) == len(sample_clips)

    def test_select_by_motion(self, sample_clips):
        """Test motion-based filtering."""
        selector = ClipSelector()

        for clip in sample_clips:
            selector.add_clip(clip)

        # Select high motion clips
        high_motion = selector.select_by_motion(0.7, operator="greater", k=5)

        assert len(high_motion) == 2  # Two clips have motion > 0.7
        assert all(clip.motion_score > 0.7 for clip in high_motion)

    def test_select_by_energy(self, sample_clips):
        """Test energy-based selection."""
        selector = ClipSelector()

        for clip in sample_clips:
            selector.add_clip(clip)

        # Select medium energy clips
        medium_energy = selector.select_by_energy(0.5, tolerance=0.2, k=5)

        assert len(medium_energy) >= 1
        assert all(abs(clip.energy_score - 0.5) <= 0.2 for clip in medium_energy)

    def test_select_by_tags(self, sample_clips):
        """Test tag-based filtering."""
        selector = ClipSelector()

        for clip in sample_clips:
            selector.add_clip(clip)

        # Select action clips
        action_clips = selector.select_by_tags(["action"], any_match=True, k=5)

        assert len(action_clips) == 2
        assert all("action" in clip.tags for clip in action_clips)

    def test_hybrid_selection(self, sample_clips):
        """Test hybrid selection combining multiple criteria."""
        selector = ClipSelector()

        for clip in sample_clips:
            selector.add_clip(clip)

        # Search for high-energy, high-motion clips
        results = selector.select_hybrid(
            energy_target=0.8,
            motion_threshold=0.5,
            weights={"energy": 0.5, "motion": 0.5},
            k=3
        )

        assert len(results) > 0
        assert all(isinstance(item, tuple) for item in results)
        assert all(isinstance(item[0], ClipMetadata) for item in results)
        assert all(isinstance(item[1], float) for item in results)

    def test_statistics(self, sample_clips):
        """Test statistics generation."""
        selector = ClipSelector()

        for clip in sample_clips:
            selector.add_clip(clip)

        stats = selector.get_statistics()

        assert stats["total_clips"] == 3
        assert "avg_motion" in stats
        assert "avg_energy" in stats
        assert len(stats["unique_tags"]) > 0

    def test_clear_cache(self, sample_clips):
        """Test cache clearing."""
        selector = ClipSelector()

        for clip in sample_clips:
            selector.add_clip(clip)

        assert len(selector.clip_cache) > 0

        selector.clear_cache()

        assert len(selector.clip_cache) == 0


class TestIntegration:
    """Integration tests for pacing engine with video generation."""

    def test_full_pipeline_simulation(self):
        """Simulate full pipeline: analysis -> planning -> EDL generation."""
        # 1. Create mock audio analysis
        beats = [[i * 0.5, 1 if i % 4 == 0 else 2] for i in range(80)]  # 40s
        analysis = {
            "bpm": 120,
            "beat_data": beats,
            "count": len(beats)
        }

        # 2. Create mock energy curve
        times = np.linspace(0, 40, 200)
        rms = 0.5 + 0.3 * np.sin(2 * np.pi * 0.1 * times)

        # 3. Initialize pacing engine
        config = PacingConfig(
            pacing=4,
            precision=8,
            energy_react=6,
            chaos=3
        )
        engine = AdvancedPacingEngine(config)

        # 4. Analyze and plan
        engine.analyze_audio_structure(analysis, rms, times)
        cuts = engine.plan_cuts(40.0)

        # 5. Generate EDL
        edl = engine.generate_edit_decision_list()

        # Verify pipeline output
        assert len(cuts) > 0
        assert len(edl) == len(cuts)
        assert cuts[0].time == 0.0
        # Last cut start time should be within duration, end_time can exceed slightly due to duration
        assert cuts[-1].time <= 40.0

        # Verify statistics
        stats = engine.get_statistics()
        assert stats["total_cuts"] > 0
        assert 0.0 <= stats["beat_alignment_ratio"] <= 1.0

    def test_compatibility_with_video_generator(self):
        """Test that EDL format matches VideoGenerator expectations."""
        config = PacingConfig()
        engine = AdvancedPacingEngine(config)

        # Mock data
        analysis = {
            "bpm": 120,
            "beat_data": [[i * 0.5, 1] for i in range(40)],
            "count": 40
        }
        rms = np.random.random(100)
        times = np.linspace(0, 20, 100)

        engine.analyze_audio_structure(analysis, rms, times)
        engine.plan_cuts(20.0)
        edl = engine.generate_edit_decision_list()

        # Verify format
        for entry in edl:
            assert "time" in entry
            assert "duration" in entry
            assert "energy" in entry
            assert isinstance(entry["time"], float)
            assert isinstance(entry["duration"], float)
            assert 0.0 <= entry["energy"] <= 1.0
