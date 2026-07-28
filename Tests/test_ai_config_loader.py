"""Regression tests for the shared AI configuration reader."""

import importlib
import json
import warnings

import pytest

from pb_studio.ai.config_loader import load_ai_config


def _patch_config_manager(monkeypatch, value=None, error=None):
    import pb_studio.config_manager as config_module

    class FakeConfigManager:
        def __init__(self):
            if error is not None:
                raise error

        def get(self, key):
            assert key == "ai"
            return value

    monkeypatch.setattr(config_module, "ConfigManager", FakeConfigManager)


def test_config_manager_dict_wins_over_disk(monkeypatch, tmp_path):
    _patch_config_manager(monkeypatch, {"provider": "lmstudio"})
    fallback = tmp_path / "config.json"
    fallback.write_text(
        json.dumps({"ai": {"provider": "ollama"}}),
        encoding="utf-8",
    )

    assert load_ai_config(fallback_path=fallback) == {"provider": "lmstudio"}


@pytest.mark.parametrize("manager_value", [[1], "invalid"])
def test_non_dict_config_manager_value_uses_disk(
    monkeypatch,
    tmp_path,
    manager_value,
):
    _patch_config_manager(monkeypatch, manager_value)
    fallback = tmp_path / "config.json"
    fallback.write_text(
        json.dumps({"ai": {"provider": "auto"}}),
        encoding="utf-8",
    )

    assert load_ai_config(fallback_path=fallback) == {"provider": "auto"}


@pytest.mark.parametrize("manager_value", [None, [], ""])
def test_falsy_config_manager_value_preserves_empty_result(
    monkeypatch,
    tmp_path,
    manager_value,
):
    _patch_config_manager(monkeypatch, manager_value)
    fallback = tmp_path / "config.json"
    fallback.write_text(
        json.dumps({"ai": {"provider": "ollama"}}),
        encoding="utf-8",
    )

    assert load_ai_config(fallback_path=fallback) == {}


def test_config_manager_error_uses_disk(monkeypatch, tmp_path):
    _patch_config_manager(monkeypatch, error=RuntimeError("forced"))
    fallback = tmp_path / "config.json"
    fallback.write_text(json.dumps({"ai": {"mode": "quality"}}), encoding="utf-8")

    assert load_ai_config(fallback_path=fallback) == {"mode": "quality"}


@pytest.mark.parametrize("payload", [None, "{broken", '{"ai": []}'])
def test_invalid_or_missing_disk_fallback_returns_empty(
    monkeypatch,
    tmp_path,
    payload,
):
    _patch_config_manager(monkeypatch, error=RuntimeError("forced"))
    fallback = tmp_path / "config.json"
    if payload is not None:
        fallback.write_text(payload, encoding="utf-8")

    assert load_ai_config(fallback_path=fallback) == {}


def test_brain_vision_and_ollama_shim_preserve_loader_alias():
    narrator = importlib.import_module("pb_studio.brain.llm_narrator")
    vision = importlib.import_module("pb_studio.video.lmstudio_vision_wrapper")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        shim = importlib.import_module("pb_studio.video.ollama_vision_wrapper")

    assert narrator._load_ai_config is load_ai_config
    assert vision._load_ai_config is load_ai_config
    assert shim._load_ai_config is load_ai_config
    assert shim.extract_tags_via_ollama is vision.extract_tags_via_lmstudio
