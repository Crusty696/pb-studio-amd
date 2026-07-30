"""C-01 regressions for DirectML-only Semantic Audio."""

import inspect
import threading
from unittest.mock import MagicMock, patch

import pytest

from pb_studio.ai.clap_wrapper import CLAPAnalyzer
from pb_studio.ai.smart_director import (
    SemanticAudioUnavailableError,
    SmartDirector,
)
from pb_studio.services.pacing_service import PacingService


def _director_without_models() -> SmartDirector:
    director = SmartDirector.__new__(SmartDirector)
    director._clap = None
    director._siglip = None
    director._active_model = None
    director._semantic_audio_unavailable_reason = None
    director._inference_lock = threading.RLock()
    director.vram_manager = MagicMock()
    return director


def test_runtime_semantic_path_has_no_clap_pytorch_import():
    assert "clap_pytorch" not in inspect.getsource(CLAPAnalyzer)
    assert "clap_pytorch" not in inspect.getsource(SmartDirector._load_clap)


def test_missing_registered_clap_onnx_is_explicitly_unavailable():
    analyzer = CLAPAnalyzer(lazy_load=True)

    with (
        patch.object(analyzer, "_get_providers", return_value=["DmlExecutionProvider"]),
        patch("pb_studio.core.model_loader.ModelLoader") as loader_cls,
    ):
        loader_cls.return_value.load_model.return_value = None

        assert analyzer.load() is False

    assert analyzer.is_ready is False
    assert analyzer.is_semantic_ready is False
    assert "Registrierte CLAP-ONNX-Modelle fehlen" in analyzer.unavailable_reason


def test_clap_rejects_session_without_cpu_fallback_guard():
    analyzer = CLAPAnalyzer(lazy_load=True)
    session = MagicMock()
    session.get_providers.return_value = [
        "DmlExecutionProvider",
        "CPUExecutionProvider",
    ]
    session.get_session_options.return_value.get_session_config_entry.return_value = "0"

    with pytest.raises(RuntimeError, match="CPU EP fallback"):
        analyzer._validate_dml_session(session)


def test_smart_director_exposes_unavailable_semantic_audio_state():
    director = _director_without_models()
    analyzer = MagicMock()
    analyzer.load.return_value = True
    analyzer.is_semantic_ready = False
    analyzer.unavailable_reason = "classification missing"

    with patch("pb_studio.ai.clap_wrapper.CLAPAnalyzer", return_value=analyzer):
        assert director._load_clap() is False

    assert director.semantic_audio_status == {
        "available": False,
        "provider": None,
        "reason": "classification missing",
    }
    analyzer.unload.assert_called_once_with()


def test_smart_director_never_returns_neutral_when_clap_is_missing():
    director = _director_without_models()
    director._semantic_audio_unavailable_reason = "CLAP ONNX unavailable"

    with pytest.raises(SemanticAudioUnavailableError, match="CLAP ONNX"):
        director._analyze_mood("track.wav")


def test_pacing_disables_semantic_matching_when_clap_is_unavailable():
    service = PacingService()
    director = MagicMock()
    director.get_dominant_mood.side_effect = SemanticAudioUnavailableError(
        "CLAP ONNX unavailable"
    )

    with patch(
        "pb_studio.ai.smart_director.SmartDirector.get_instance",
        return_value=director,
    ):
        enabled, prompt = service._resolve_semantic_audio("track.wav", True)

    assert enabled is False
    assert prompt is None


def test_pacing_uses_semantic_prompt_only_when_clap_classification_works():
    service = PacingService()
    director = MagicMock()
    director.get_dominant_mood.return_value = "uplifting music"

    with patch(
        "pb_studio.ai.smart_director.SmartDirector.get_instance",
        return_value=director,
    ):
        enabled, prompt = service._resolve_semantic_audio("track.wav", True)

    assert enabled is True
    assert prompt == "uplifting music"
