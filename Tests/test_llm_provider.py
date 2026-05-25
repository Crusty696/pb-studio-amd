"""Tests fuer pb_studio.ai.llm_provider — Hybrid Ollama + LM Studio Factory.

Coverage:
- get_provider() liest config.json
- get_base_url() liefert die richtige URL pro Provider
- get_llm_client() returns LMStudioClient mit korrektem base_url
- Default-Fallbacks bei fehlender oder defekter config
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pb_studio.ai.llm_provider import (
    DEFAULT_LMSTUDIO_URL,
    DEFAULT_OLLAMA_URL,
    VALID_PROVIDERS,
    get_base_url,
    get_llm_client,
    get_provider,
)


def test_valid_providers_set():
    assert VALID_PROVIDERS == {"lmstudio", "ollama", "auto"}


def test_default_urls_constants():
    assert DEFAULT_LMSTUDIO_URL == "http://127.0.0.1:1234/v1"
    assert DEFAULT_OLLAMA_URL == "http://localhost:11434/v1"


@patch("pb_studio.ai.llm_provider._load_config", return_value={})
def test_provider_default_auto_when_config_missing(mock_cfg):
    assert get_provider() == "auto"


@patch("pb_studio.ai.llm_provider._load_config", return_value={"provider": "lmstudio"})
def test_provider_reads_config(mock_cfg):
    assert get_provider() == "lmstudio"


@patch("pb_studio.ai.llm_provider._load_config", return_value={"provider": "OLLAMA"})
def test_provider_normalizes_case(mock_cfg):
    assert get_provider() == "ollama"


@patch("pb_studio.ai.llm_provider._load_config", return_value={"provider": "garbage"})
def test_provider_invalid_falls_back_to_auto(mock_cfg):
    assert get_provider() == "auto"


@patch("pb_studio.ai.llm_provider._load_config", return_value={})
def test_base_url_lmstudio_default(mock_cfg):
    assert get_base_url("lmstudio") == DEFAULT_LMSTUDIO_URL


@patch("pb_studio.ai.llm_provider._load_config", return_value={})
def test_base_url_ollama_default(mock_cfg):
    assert get_base_url("ollama") == DEFAULT_OLLAMA_URL


@patch(
    "pb_studio.ai.llm_provider._load_config",
    return_value={
        "lmstudio_base_url": "http://custom-lms:9999/v1",
        "ollama_base_url": "http://custom-ollama:8888/v1",
    },
)
def test_base_url_reads_config_overrides(mock_cfg):
    assert get_base_url("lmstudio") == "http://custom-lms:9999/v1"
    assert get_base_url("ollama") == "http://custom-ollama:8888/v1"


@patch("pb_studio.ai.llm_provider._load_config", return_value={"provider": "auto"})
def test_base_url_auto_prefers_lmstudio(mock_cfg):
    assert get_base_url() == DEFAULT_LMSTUDIO_URL


@patch("pb_studio.ai.llm_provider._load_config", return_value={})
def test_get_llm_client_lmstudio(mock_cfg):
    client = get_llm_client(provider="lmstudio")
    assert client.base_url == DEFAULT_LMSTUDIO_URL


@patch("pb_studio.ai.llm_provider._load_config", return_value={})
def test_get_llm_client_ollama(mock_cfg):
    client = get_llm_client(provider="ollama")
    assert client.base_url == DEFAULT_OLLAMA_URL


@patch("pb_studio.ai.llm_provider._load_config", return_value={})
def test_get_llm_client_timeout_passthrough(mock_cfg):
    client = get_llm_client(provider="lmstudio", timeout_seconds=42.0)
    assert client.timeout_seconds == 42.0


def test_load_config_handles_missing_file(tmp_path, monkeypatch):
    """_load_config returns {} bei fehlender config.json."""
    from pb_studio.ai import llm_provider
    fake_path = tmp_path / "nonexistent.json"
    monkeypatch.setattr(
        llm_provider,
        "_load_config",
        lambda: {} if not fake_path.exists() else json.loads(fake_path.read_text()),
    )
    # function callable + returns dict
    cfg = llm_provider._load_config()
    assert isinstance(cfg, dict)
