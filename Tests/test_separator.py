"""
Unit Tests for StemSeparator

Tests:
- DirectML provider detection and patching
- Separator initialization
- Model listing
- Separation process
"""

import threading

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
        sep._has_directml = True
        mock_sep.load_model.side_effect = lambda _name: setattr(
            sep,
            "_directml_session_created",
            True,
        )

        result = sep.separate(str(test_file))

        assert "stems" in result
        assert len(result["stems"]) == 2

    def test_onnx_separation_fails_before_model_load_without_directml(
        self, reset_config_singleton, temp_dir
    ):
        """ONNX models must never fall back to CPU when DML is unavailable."""
        from pb_studio.audio.separator import StemSeparator

        test_file = temp_dir / "test.wav"
        model_file = temp_dir / "model.onnx"
        test_file.touch()
        model_file.touch()

        sep = StemSeparator.__new__(StemSeparator)
        sep.separator = MagicMock()
        sep._has_directml = False
        sep.config = MagicMock()
        sep.config.get.return_value = {"models_dir": str(temp_dir)}

        result = sep.separate(str(test_file), model_name=model_file.name)

        assert "error" in result
        assert "directml" in result["error"].lower()
        sep.separator.load_model.assert_not_called()
        sep.separator.separate.assert_not_called()

    def test_demucs_cpu_path_remains_available_without_directml(
        self, reset_config_singleton, temp_dir
    ):
        """Demucs is an intentional PyTorch CPU path, not an ONNX fallback."""
        from pb_studio.audio.separator import StemSeparator

        test_file = temp_dir / "test.wav"
        model_file = temp_dir / "htdemucs.yaml"
        test_file.touch()
        model_file.touch()

        sep = StemSeparator.__new__(StemSeparator)
        sep.separator = MagicMock()
        sep.separator.separate.return_value = [str(temp_dir / "vocals.wav")]
        sep._has_directml = False
        sep.config = MagicMock()
        sep.config.get.return_value = {"models_dir": str(temp_dir)}

        result = sep.separate(str(test_file), model_name=model_file.name)

        assert result == {"stems": [str(temp_dir / "vocals.wav")]}
        sep.separator.load_model.assert_called_once_with(model_file.name)

    def test_onnx_reservation_failure_stops_before_model_load(
        self, reset_config_singleton, temp_dir
    ):
        """H-06: failed GPU reservation must stop the direct separator path."""
        from pb_studio.audio.separator import StemSeparator

        test_file = temp_dir / "test.wav"
        model_file = temp_dir / "model.onnx"
        test_file.touch()
        model_file.touch()

        sep = StemSeparator.__new__(StemSeparator)
        sep.separator = MagicMock()
        sep._has_directml = True
        sep.config = MagicMock()
        sep.config.get.return_value = {"models_dir": str(temp_dir)}
        manager = MagicMock()
        manager.reserve.return_value = False

        with patch(
            "pb_studio.core.vram_budget_manager.get_vram_manager",
            return_value=manager,
        ):
            result = sep.separate(str(test_file), model_name=model_file.name)

        assert "error" in result
        assert "reservation failed" in result["error"].lower()
        sep.separator.load_model.assert_not_called()
        sep.separator.separate.assert_not_called()
        manager.commit.assert_not_called()
        manager.release.assert_not_called()

    def test_demucs_cpu_path_does_not_reserve_gpu_budget(
        self, reset_config_singleton, temp_dir
    ):
        """H-05: documented PyTorch Demucs path has no GPU budget owner."""
        from pb_studio.audio.separator import StemSeparator

        test_file = temp_dir / "test.wav"
        model_file = temp_dir / "htdemucs.yaml"
        test_file.touch()
        model_file.touch()

        sep = StemSeparator.__new__(StemSeparator)
        sep.separator = MagicMock()
        sep.separator.separate.return_value = [str(temp_dir / "vocals.wav")]
        sep._has_directml = False
        sep.config = MagicMock()
        sep.config.get.return_value = {"models_dir": str(temp_dir)}

        with patch(
            "pb_studio.core.vram_budget_manager.get_vram_manager"
        ) as get_manager:
            result = sep.separate(str(test_file), model_name=model_file.name)

        assert "stems" in result
        get_manager.assert_not_called()


def test_separator_source_is_directml_only_for_onnx():
    """Static guard against reintroducing ORT CPU provider fallback."""
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "pb_studio"
        / "audio"
        / "separator.py"
    ).read_text(encoding="utf-8")

    assert '["DmlExecutionProvider", "CPUExecutionProvider"]' not in source
    assert "provider = get_directml_provider()" in source
    assert "self.separator.onnx_execution_provider = [provider]" in source


def test_directml_session_options_patch_is_serialized_across_instances():
    """A process-global ORT constructor patch must not overlap across separators."""
    import pb_studio.audio.separator as separator_module

    class FakeSessionOptions:
        def __init__(self):
            self.enable_mem_pattern = True
            self.enable_cpu_mem_arena = True

    original_init = FakeSessionOptions.__init__
    first = separator_module.StemSeparator.__new__(separator_module.StemSeparator)
    second = separator_module.StemSeparator.__new__(separator_module.StemSeparator)
    first._has_directml = True
    second._has_directml = True
    second_applied = threading.Event()
    release_second = threading.Event()

    def apply_and_restore_second():
        second._apply_directml_patch()
        second_applied.set()
        release_second.wait(timeout=2)
        second._restore_directml_patch()

    with patch.object(separator_module.ort, "SessionOptions", FakeSessionOptions):
        worker = None
        try:
            first._apply_directml_patch()
            worker = threading.Thread(target=apply_and_restore_second)
            worker.start()

            assert not second_applied.wait(timeout=0.1)
            first._restore_directml_patch()
            assert second_applied.wait(timeout=1)
        finally:
            first._restore_directml_patch()
            release_second.set()
            if worker is not None:
                worker.join(timeout=2)

        assert not worker.is_alive()
        assert FakeSessionOptions.__init__ is original_init


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
