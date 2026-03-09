"""
Unit Tests for StemSeparator

Tests:
- DirectML provider detection and patching
- Separator initialization
- Model listing
- Separation process
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestStemSeparatorSeparation:
    """Tests for stem separation functionality."""

    def test_separate_returns_error_when_not_initialized(self, reset_config_singleton):
        """Verify separate() returns error when separator is None."""
        from pb_studio.audio.separator import StemSeparator

        sep = StemSeparator.__new__(StemSeparator)
        sep.separator = None

        result = sep.separate("test.wav")

        assert "error" in result
        assert "not initialized" in result["error"].lower()

    def test_separate_returns_error_for_missing_file(self, reset_config_singleton):
        """Verify separate() returns error for non-existent file."""
        from pb_studio.audio.separator import StemSeparator

        sep = StemSeparator.__new__(StemSeparator)
        sep.separator = MagicMock()

        result = sep.separate("nonexistent_file.wav")

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_separate_returns_stems_on_success(self, reset_config_singleton, temp_dir):
        """Verify separate() returns stems list on success."""
        from pb_studio.audio.separator import StemSeparator

        # Create dummy file
        test_file = temp_dir / "test.wav"
        test_file.touch()

        sep = StemSeparator.__new__(StemSeparator)
        mock_sep = MagicMock()
        mock_sep.separate.return_value = [
            str(temp_dir / "vocals.wav"),
            str(temp_dir / "instrumental.wav")
        ]
        mock_sep.onnx_execution_provider = ["DmlExecutionProvider"]
        sep.separator = mock_sep

        result = sep.separate(str(test_file))

        assert "stems" in result
        assert len(result["stems"]) == 2


class TestStemSeparatorModelListing:
    """Tests for model listing."""

    def test_list_models_returns_empty_when_not_initialized(self, reset_config_singleton):
        """Verify list_models() returns empty dict when separator is None."""
        from pb_studio.audio.separator import StemSeparator

        sep = StemSeparator.__new__(StemSeparator)
        sep.separator = None

        result = sep.list_models()

        assert result == {}

    def test_list_models_returns_available_models(self, reset_config_singleton):
        """Verify list_models() returns model list."""
        from pb_studio.audio.separator import StemSeparator

        sep = StemSeparator.__new__(StemSeparator)
        mock_sep = MagicMock()
        mock_sep.list_supported_model_files.return_value = {
            "mdx": ["model1.onnx", "model2.onnx"],
            "demucs": ["htdemucs.pt"]
        }
        sep.separator = mock_sep

        result = sep.list_models()

        assert "mdx" in result
        assert len(result["mdx"]) == 2
