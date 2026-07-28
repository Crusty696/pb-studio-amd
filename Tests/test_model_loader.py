"""Test coverage for core/model_loader.py (P3.1 Test-Coverage-Gap-Filler).

Spec: PLAN_OPEN_TASKS_2026-05-15.md P3.1 — model_loader.py hat 13 defs ohne Tests.
Hier: ModelSpec + ModelType + register_model + is_loaded + get_stats + unload_all
+ singleton accessor. Echtes Loading wird gemockt (ORT-Session = Magic-Mock).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pb_studio.core.model_loader import (
    ModelType,
    ModelSpec,
    ModelLoader,
    get_model_loader,
    MODEL_SPECS,
)
from pb_studio.core.vram_budget_manager import ModelPriority


# ---------- Enum + Dataclass ----------

def test_model_type_enum_values():
    assert ModelType.ONNX.value == "onnx"
    assert ModelType.ONNX_SPLIT.value == "onnx_split"
    assert ModelType.PYTORCH_CPU.value == "pytorch"


def test_model_spec_construction_minimal():
    spec = ModelSpec(
        model_id="test_model",
        name="Test Model",
        model_type=ModelType.ONNX,
        vram_mb=500,
        model_path="test.onnx",
    )
    assert spec.model_id == "test_model"
    assert spec.priority == ModelPriority.MEDIUM  # default
    assert spec.encoder_path is None
    assert spec.decoder_path is None


def test_model_spec_split_model():
    spec = ModelSpec(
        model_id="split",
        name="Split Model",
        model_type=ModelType.ONNX_SPLIT,
        vram_mb=1000,
        model_path="main.onnx",
        encoder_path="enc.onnx",
        decoder_path="dec.onnx",
    )
    assert spec.model_type == ModelType.ONNX_SPLIT
    assert spec.encoder_path == "enc.onnx"
    assert spec.decoder_path == "dec.onnx"


# ---------- Predefined Specs ----------

def test_predefined_specs_present():
    assert "moondream_fp16" in MODEL_SPECS
    assert "raft_standard" in MODEL_SPECS
    assert "mdx_net_inst" in MODEL_SPECS


def test_moondream_is_split_model():
    spec = MODEL_SPECS["moondream_fp16"]
    assert spec.model_type == ModelType.ONNX_SPLIT
    assert spec.encoder_path is not None
    assert spec.decoder_path is not None


# ---------- ModelLoader register/is_loaded/stats ----------

@pytest.fixture
def loader():
    """Fresh ModelLoader with mocked VRAM manager."""
    with patch("pb_studio.core.model_loader.get_vram_manager") as mock_vm:
        mock_manager = MagicMock()
        mock_manager.can_fit.return_value = True
        mock_manager.register_model.return_value = None
        mock_manager.touch_model.return_value = None
        mock_manager.release.return_value = None
        mock_manager.get_stats.return_value = {"total_committed_mb": 0}
        mock_vm.return_value = mock_manager
        loader = ModelLoader()
        loader.vram_manager = mock_manager
        yield loader


def test_register_custom_model(loader):
    custom = ModelSpec(
        model_id="custom_test",
        name="Custom Test",
        model_type=ModelType.ONNX,
        vram_mb=100,
        model_path="custom.onnx",
    )
    loader.register_model(custom)
    assert "custom_test" in loader._specs
    assert loader._specs["custom_test"].name == "Custom Test"


def test_is_loaded_false_for_unloaded(loader):
    assert loader.is_loaded("never_loaded") is False


def test_is_loaded_true_after_session_inserted(loader):
    loader._sessions["mocked"] = MagicMock()
    assert loader.is_loaded("mocked") is True


def test_get_stats_returns_dict(loader):
    stats = loader.get_stats()
    assert "loaded_models" in stats
    assert "registered_models" in stats
    assert "vram_stats" in stats
    assert isinstance(stats["loaded_models"], list)


def test_unload_all_clears_sessions(loader):
    loader._sessions["m1"] = MagicMock()
    loader._sessions["m2"] = MagicMock()
    loader.unload_all()
    assert len(loader._sessions) == 0


def test_can_load_unknown_model_returns_false(loader):
    assert loader.can_load("nonexistent_model_xyz") is False


# ---------- DirectML contract ----------

def test_session_options_disable_both_directml_memory_optimizations(loader):
    options = loader._create_session_options()

    assert options.enable_mem_pattern is False
    assert options.enable_cpu_mem_arena is False


def test_get_providers_is_directml_only(loader):
    with patch(
        "pb_studio.core.model_loader.ort.get_available_providers",
        return_value=["DmlExecutionProvider", "CPUExecutionProvider"],
    ):
        providers = loader._get_providers()

    assert providers == [("DmlExecutionProvider", {"device_id": 0})]


def test_get_providers_fails_when_directml_is_unavailable(loader):
    with patch(
        "pb_studio.core.model_loader.ort.get_available_providers",
        return_value=["CPUExecutionProvider"],
    ):
        with pytest.raises(RuntimeError, match="DmlExecutionProvider"):
            loader._get_providers()


# ---------- Singleton ----------

def test_get_model_loader_returns_same_instance():
    """Singleton: get_model_loader() returns identical instance on repeat calls."""
    a = get_model_loader()
    b = get_model_loader()
    assert a is b
