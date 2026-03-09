"""
Unit Tests for AudioAnalyzer

Tests:
- BeatNet initialization
- BPM detection
- Error handling for missing files
- Audio conversion fallback
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestAudioAnalyzerAnalysis:
    """Tests for audio analysis functionality."""

    def test_analyze_returns_error_when_model_not_loaded(self):
        """Verify analyze_file returns error dict when model unavailable."""
        from pb_studio.audio.analyzer import AudioAnalyzer

        analyzer = AudioAnalyzer.__new__(AudioAnalyzer)
        analyzer.model_loaded = False

        result = analyzer.analyze_file("test.wav")

        assert "error" in result
        assert "not loaded" in result["error"].lower()

    def test_analyze_returns_bpm_structure(self):
        """Verify analyze_file returns correct result structure."""
        mock_output = np.array([[0.5, 1], [1.0, 2], [1.5, 1], [2.0, 2]])

        from pb_studio.audio.analyzer import AudioAnalyzer

        analyzer = AudioAnalyzer.__new__(AudioAnalyzer)
        analyzer.model_loaded = True
        analyzer.estimator = MagicMock()
        analyzer.estimator.process.return_value = mock_output

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=1000):
                    with patch("os.remove"):
                        result = analyzer.analyze_file("test.wav")

        assert "bpm" in result
        assert "count" in result
        assert isinstance(result["bpm"], (int, float))

    def test_analyze_calculates_correct_bpm(self):
        """Verify BPM calculation from beat intervals."""
        # Beats at 0.5s intervals = 120 BPM
        mock_output = np.array([
            [0.0, 1], [0.5, 2], [1.0, 1], [1.5, 2], [2.0, 1]
        ])

        from pb_studio.audio.analyzer import AudioAnalyzer

        analyzer = AudioAnalyzer.__new__(AudioAnalyzer)
        analyzer.model_loaded = True
        analyzer.estimator = MagicMock()
        analyzer.estimator.process.return_value = mock_output

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=1000):
                    with patch("os.remove"):
                        result = analyzer.analyze_file("test.wav")

        # 0.5s intervals = 120 BPM
        assert 115 <= result["bpm"] <= 125

    def test_analyze_handles_empty_output(self):
        """Verify graceful handling of empty BeatNet output."""
        from pb_studio.audio.analyzer import AudioAnalyzer

        analyzer = AudioAnalyzer.__new__(AudioAnalyzer)
        analyzer.model_loaded = True
        analyzer.estimator = MagicMock()
        analyzer.estimator.process.return_value = np.array([])

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=1000):
                    with patch("os.remove"):
                        result = analyzer.analyze_file("test.wav")

        assert result["bpm"] == 0

    def test_analyze_returns_warning_for_silent_video(self):
        """Verify warning for videos without audio stream."""
        from pb_studio.audio.analyzer import AudioAnalyzer

        analyzer = AudioAnalyzer.__new__(AudioAnalyzer)
        analyzer.model_loaded = True
        analyzer.ffmpeg_path = "ffmpeg"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="does not contain any stream"
            )
            result = analyzer.analyze_file("silent_video.mp4")

        assert result["bpm"] == 0
        assert "warning" in result
