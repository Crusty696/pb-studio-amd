"""
Tests for 3-Band Waveform Analyzer

Tests waveform extraction, filtering, caching, and downsampling.
"""
import pytest
import numpy as np
from pathlib import Path
from pb_studio.audio.waveform_analyzer import WaveformAnalyzer
from pb_studio.audio.waveform_cache import WaveformCache


class TestWaveformAnalyzer:
    """Test cases for WaveformAnalyzer."""

    def test_init(self):
        """Test analyzer initialization."""
        analyzer = WaveformAnalyzer(sr=44100, filter_order=4)
        assert analyzer.sr == 44100
        assert analyzer.filter_order == 4
        assert 'low' in analyzer.bands
        assert 'mid' in analyzer.bands
        assert 'high' in analyzer.bands

    def test_band_frequencies(self):
        """Test frequency band ranges."""
        analyzer = WaveformAnalyzer()

        # Verify Rekordbox-style frequency ranges
        assert analyzer.bands['low'] == (20, 200)
        assert analyzer.bands['mid'] == (200, 2000)
        assert analyzer.bands['high'] == (2000, 20000)

    def test_empty_waveform(self):
        """Test empty waveform structure."""
        analyzer = WaveformAnalyzer()
        empty = analyzer._empty_waveform()

        assert 'low' in empty
        assert 'mid' in empty
        assert 'high' in empty
        assert len(empty['low']) == 0
        assert len(empty['mid']) == 0
        assert len(empty['high']) == 0

    def test_rms_envelope(self):
        """Test RMS envelope computation."""
        analyzer = WaveformAnalyzer()

        # Generate test signal (1 second, 440Hz sine wave)
        duration = 1.0
        t = np.linspace(0, duration, int(analyzer.sr * duration))
        y = np.sin(2 * np.pi * 440 * t)

        rms = analyzer._compute_rms_envelope(y, hop_length=512)

        # RMS should be non-empty
        assert len(rms) > 0

        # RMS should be normalized to 0-1 range
        assert np.max(rms) <= 1.0
        assert np.min(rms) >= 0.0

    def test_bandpass_filter(self):
        """Test bandpass filtering."""
        analyzer = WaveformAnalyzer()

        # Generate test signal with multiple frequencies
        duration = 1.0
        t = np.linspace(0, duration, int(analyzer.sr * duration))
        y = (
            np.sin(2 * np.pi * 100 * t) +  # Low freq
            np.sin(2 * np.pi * 1000 * t) +  # Mid freq
            np.sin(2 * np.pi * 5000 * t)    # High freq
        )

        # Filter low band (should preserve 100Hz)
        y_low = analyzer._bandpass_filter(y, 20, 200, analyzer.sr)

        # Filtered signal should exist and have data
        assert len(y_low) == len(y)
        assert np.max(np.abs(y_low)) > 0

    def test_time_axis(self):
        """Test time axis generation."""
        analyzer = WaveformAnalyzer()

        num_frames = 100
        hop_length = 512

        time_axis = analyzer.get_time_axis(num_frames, hop_length)

        assert len(time_axis) == num_frames
        assert time_axis[0] >= 0
        assert time_axis[-1] > time_axis[0]  # Monotonically increasing

    @pytest.mark.skipif(not Path("tests/fixtures/test_audio.mp3").exists(),
                        reason="Test audio file not available")
    def test_extract_3band_waveform(self):
        """Test full 3-band extraction from audio file."""
        analyzer = WaveformAnalyzer()

        test_file = "tests/fixtures/test_audio.mp3"
        waveform = analyzer.extract_3band_waveform(test_file)

        # Check structure
        assert 'low' in waveform
        assert 'mid' in waveform
        assert 'high' in waveform

        # Check data exists
        assert len(waveform['low']) > 0
        assert len(waveform['mid']) > 0
        assert len(waveform['high']) > 0

        # All bands should have same length
        assert len(waveform['low']) == len(waveform['mid'])
        assert len(waveform['mid']) == len(waveform['high'])

    @pytest.mark.skipif(not Path("tests/fixtures/test_audio.mp3").exists(),
                        reason="Test audio file not available")
    def test_downsampled_waveform(self):
        """Test downsampled waveform for GUI display."""
        analyzer = WaveformAnalyzer()

        test_file = "tests/fixtures/test_audio.mp3"
        target_points = 500

        waveform = analyzer.get_downsampled_waveform(test_file, target_points)

        # Check structure
        assert 'low' in waveform
        assert 'mid' in waveform
        assert 'high' in waveform

        # Check downsampling
        for band_data in waveform.values():
            # Should be downsampled to approximately target_points
            assert len(band_data) <= target_points * 1.1  # Allow 10% margin

    @pytest.mark.skipif(not Path("tests/fixtures/test_audio.mp3").exists(),
                        reason="Test audio file not available")
    def test_frequency_content_analysis(self):
        """Test overall frequency content distribution."""
        analyzer = WaveformAnalyzer()

        test_file = "tests/fixtures/test_audio.mp3"
        content = analyzer.analyze_frequency_content(test_file)

        # Check structure
        assert 'low_pct' in content
        assert 'mid_pct' in content
        assert 'high_pct' in content

        # Percentages should sum to ~100%
        total = content['low_pct'] + content['mid_pct'] + content['high_pct']
        assert 99.0 <= total <= 101.0  # Allow small floating point error


class TestWaveformCache:
    """Test cases for WaveformCache."""

    def test_init(self):
        """Test cache initialization."""
        cache = WaveformCache(max_size=50, use_file_hash=True)
        assert cache.max_size == 50
        assert cache.use_file_hash is True
        assert len(cache) == 0

    def test_empty_cache(self):
        """Test cache miss on empty cache."""
        cache = WaveformCache()

        result = cache.get("nonexistent.mp3")
        assert result is None
        assert cache.misses == 1
        assert cache.hits == 0

    def test_put_and_get(self):
        """Test basic put and get operations."""
        cache = WaveformCache(use_file_hash=False)  # Disable hash for testing

        # Create fake waveform
        waveform = {
            'low': np.random.rand(100),
            'mid': np.random.rand(100),
            'high': np.random.rand(100)
        }

        # Put in cache
        cache.put("test_file.mp3", waveform)

        # Get from cache
        retrieved = cache.get("test_file.mp3")

        assert retrieved is not None
        assert 'low' in retrieved
        assert len(retrieved['low']) == 100
        assert cache.hits == 1

    def test_lru_eviction(self):
        """Test LRU eviction policy."""
        cache = WaveformCache(max_size=3, use_file_hash=False)

        waveform = {
            'low': np.random.rand(100),
            'mid': np.random.rand(100),
            'high': np.random.rand(100)
        }

        # Fill cache
        cache.put("file1.mp3", waveform)
        cache.put("file2.mp3", waveform)
        cache.put("file3.mp3", waveform)

        assert len(cache) == 3

        # Add 4th item - should evict oldest (file1)
        cache.put("file4.mp3", waveform)

        assert len(cache) == 3
        assert cache.evictions == 1

        # file1 should be evicted
        assert cache.get("file1.mp3") is None  # Cache miss
        assert cache.get("file2.mp3") is not None  # Still cached

    def test_remove(self):
        """Test manual removal."""
        cache = WaveformCache(use_file_hash=False)

        waveform = {
            'low': np.random.rand(100),
            'mid': np.random.rand(100),
            'high': np.random.rand(100)
        }

        cache.put("test.mp3", waveform)
        assert len(cache) == 1

        # Remove entry
        removed = cache.remove("test.mp3")
        assert removed is True
        assert len(cache) == 0

        # Try to remove non-existent
        removed = cache.remove("nonexistent.mp3")
        assert removed is False

    def test_clear(self):
        """Test cache clear."""
        cache = WaveformCache(use_file_hash=False)

        waveform = {
            'low': np.random.rand(100),
            'mid': np.random.rand(100),
            'high': np.random.rand(100)
        }

        cache.put("file1.mp3", waveform)
        cache.put("file2.mp3", waveform)

        assert len(cache) == 2

        cache.clear()
        assert len(cache) == 0

    def test_stats(self):
        """Test cache statistics."""
        cache = WaveformCache(use_file_hash=False)

        waveform = {
            'low': np.random.rand(100),
            'mid': np.random.rand(100),
            'high': np.random.rand(100)
        }

        # Perform operations
        cache.put("file1.mp3", waveform)
        cache.get("file1.mp3")  # Hit
        cache.get("nonexistent.mp3")  # Miss

        stats = cache.get_stats()

        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['size'] == 1
        assert stats['max_size'] == 50
        assert 0 <= stats['hit_rate'] <= 100

    def test_contains(self):
        """Test __contains__ method."""
        cache = WaveformCache(use_file_hash=False)

        waveform = {
            'low': np.random.rand(100),
            'mid': np.random.rand(100),
            'high': np.random.rand(100)
        }

        cache.put("test.mp3", waveform)

        assert "test.mp3" in cache
        assert "nonexistent.mp3" not in cache

    def test_size_estimation(self):
        """Test memory size estimation."""
        cache = WaveformCache(use_file_hash=False)

        waveform = {
            'low': np.random.rand(100),
            'mid': np.random.rand(100),
            'high': np.random.rand(100)
        }

        size = cache._estimate_size(waveform)

        # 3 bands * 100 floats * 8 bytes per float = 2400 bytes
        expected_size = 3 * 100 * 8
        assert size == expected_size
