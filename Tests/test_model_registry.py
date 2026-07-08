"""Tests fuer pb_studio.ai.model_registry (LM-Studio-Variante)."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from pb_studio.ai.lmstudio_client import LMStudioClient
from pb_studio.ai.model_registry import (
    DEFAULT_TASK_PREFERENCES,
    ModelRegistry,
    ModelRegistryError,
    NoSuitableModelError,
    _name_matches,
)


def _run(coro):
    return asyncio.run(coro)


def _client_with_models(model_names: list[str]) -> LMStudioClient:
    """Erzeugt einen LMStudioClient, der via MockTransport ``model_names`` zurueckgibt."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models") and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": n, "object": "model", "owned_by": "test"}
                        for n in model_names
                    ],
                    "object": "list",
                },
            )
        return httpx.Response(404)

    return LMStudioClient(transport=httpx.MockTransport(handler))


# ======================================================================
# _name_matches helper — angepasst auf LM-Studio-Tags
# ======================================================================
def test_name_matches_exact():
    assert _name_matches("qwen/qwen3-vl-8b", "qwen/qwen3-vl-8b")


def test_name_matches_suffix_after_slash():
    # LM Studio: 'qwen3-vl-8b' matched 'qwen/qwen3-vl-8b'
    assert _name_matches("qwen3-vl-8b", "qwen/qwen3-vl-8b")
    assert _name_matches("qwen/qwen3-vl-8b", "qwen3-vl-8b")


def test_name_matches_legacy_ollama_tag():
    # Backward-Compat fuer Ollama-Style ':latest'-Tags
    assert _name_matches("gemma4", "gemma4:9b")
    assert _name_matches("gemma4:latest", "gemma4")


def test_name_matches_different_models():
    assert not _name_matches("qwen3-vl-8b", "gemma-4-31b-it-uncensored")


# ======================================================================
# refresh()
# ======================================================================
def test_registry_refresh_populates_installed_models():
    async def go():
        async with _client_with_models(["qwen/qwen3-vl-8b", "google/gemma-4-e4b"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
        return reg

    reg = _run(go())
    assert reg.is_loaded
    names = [m.name for m in reg.installed_models]
    assert names == ["qwen/qwen3-vl-8b", "google/gemma-4-e4b"]


def test_select_before_refresh_raises():
    reg = ModelRegistry()
    with pytest.raises(ModelRegistryError):
        reg.select_best_for_task("video_captioning", "balance")


# ======================================================================
# Preference list resolution
# ======================================================================
def test_get_preference_list_returns_defaults_when_no_config():
    reg = ModelRegistry()
    prefs = reg.get_preference_list("video_captioning", "balance")
    assert prefs == DEFAULT_TASK_PREFERENCES["video_captioning"]["balance"]
    assert "qwen/qwen3-vl-8b" in prefs


def test_get_preference_list_user_overrides_defaults():
    cfg = {
        "task_preferences": {
            "video_captioning": {
                "balance": ["my-custom-model"],
            }
        }
    }
    reg = ModelRegistry(cfg)
    prefs = reg.get_preference_list("video_captioning", "balance")
    assert prefs == ["my-custom-model"]


def test_get_preference_list_invalid_mode_raises():
    reg = ModelRegistry()
    with pytest.raises(ModelRegistryError):
        reg.get_preference_list("video_captioning", "ultra")


# ======================================================================
# Auto-selection happy paths
# ======================================================================
def test_select_first_installed_pref():
    async def go():
        # balance: ["qwen/qwen3-vl-8b"] — soll qwen3-vl-8b waehlen
        async with _client_with_models(["google/gemma-4-e4b", "qwen/qwen3-vl-8b"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.select_best_for_task("video_captioning", "balance")

    assert _run(go()) == "qwen/qwen3-vl-8b"


def test_select_falls_back_when_first_missing():
    async def go():
        # chat_tool_use speed: ["qwen3.5-9b-...", "google/gemma-4-e4b"]
        # nur gemma installiert — fallback nimmt es
        async with _client_with_models(["google/gemma-4-e4b"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.select_best_for_task("chat_tool_use", "speed")

    assert _run(go()) == "google/gemma-4-e4b"


def test_select_speed_mode_picks_speed_pref():
    async def go():
        # video_captioning speed: ["qwen/qwen3-vl-8b", "google/gemma-4-e4b"]
        async with _client_with_models(["google/gemma-4-e4b"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.select_best_for_task("video_captioning", "speed")

    assert _run(go()) == "google/gemma-4-e4b"


# ======================================================================
# User override
# ======================================================================
def test_user_override_takes_precedence_if_installed():
    cfg = {"task_overrides": {"video_captioning": "google/gemma-4-e4b"}}

    async def go():
        async with _client_with_models(
            ["google/gemma-4-e4b", "qwen/qwen3-vl-8b"]
        ) as client:
            reg = ModelRegistry(cfg, client=client)
            await reg.refresh()
            return reg.select_best_for_task("video_captioning", "balance")

    assert _run(go()) == "google/gemma-4-e4b"


def test_user_override_ignored_if_not_installed_falls_back():
    cfg = {"task_overrides": {"video_captioning": "not-installed-model"}}

    async def go():
        async with _client_with_models(["qwen/qwen3-vl-8b"]) as client:
            reg = ModelRegistry(cfg, client=client)
            await reg.refresh()
            return reg.select_best_for_task("video_captioning", "balance")

    assert _run(go()) == "qwen/qwen3-vl-8b"


# ======================================================================
# No suitable model
# ======================================================================
def test_no_suitable_model_raises():
    async def go():
        async with _client_with_models(["unrelated-tiny-model"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.select_best_for_task("video_captioning", "balance", allow_any_installed=False)

    with pytest.raises(NoSuitableModelError):
        _run(go())



def test_vision_task_skips_text_qwen_model():
    """Regression: 'qwen' im Namen eines TEXT-Modells (deepseek-r1-qwen3) darf
    nicht als Vision-Modell fuer Captioning gewaehlt werden. Der echte vlm
    (google/gemma-4-e4b, via 'e4b'-Token) muss gewaehlt werden."""
    async def go():
        async with _client_with_models(
            ["deepseek/deepseek-r1-0528-qwen3-8b", "google/gemma-4-e4b"]
        ) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.select_best_for_task("video_captioning", "balance")

    chosen = _run(go())
    assert chosen == "google/gemma-4-e4b", f"erwartete vlm, bekam {chosen!r}"


def test_vision_task_authoritative_vlm_set_overrides_keywords():
    """Wenn /api/v0/models ein vlm meldet das KEIN Vision-Token im Namen hat,
    muss es trotzdem als vision-faehig gelten (autoritativ)."""
    async def go():
        async with _client_with_models(["mystery-captioner-7b", "phi-4-reasoning"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            # Simuliere /api/v0/models type==vlm fuer das sonst token-lose Modell.
            reg._vision_models = {"mystery-captioner-7b"}
            return reg.select_best_for_task("video_captioning", "balance")

    assert _run(go()) == "mystery-captioner-7b"


def test_vision_task_no_vision_model_raises_when_vlm_known():
    """Nur Text-Modelle installiert, aber es sind vlm-Modelle bekannt -> klarer Fehler
    statt ein Text-Modell zu waehlen das 'does not support images' wirft."""
    async def go():
        async with _client_with_models(["phi-4-reasoning", "deepseek-r1"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            reg._vision_models = {"some-vlm-not-installed"}
            return reg.select_best_for_task("video_captioning", "balance")

    with pytest.raises(NoSuitableModelError):
        _run(go())


def test_no_suitable_with_allow_any_picks_first_installed():
    async def go():
        async with _client_with_models(["unrelated-tiny-vl-model"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.select_best_for_task(
                "video_captioning", "balance", allow_any_installed=True
            )

    assert _run(go()) == "unrelated-tiny-vl-model"


def test_no_suitable_with_allow_any_but_empty_still_raises():
    async def go():
        async with _client_with_models([]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.select_best_for_task(
                "video_captioning", "balance", allow_any_installed=True
            )

    with pytest.raises(NoSuitableModelError):
        _run(go())


# ======================================================================
# recommendation_with_reason
# ======================================================================
def test_recommendation_reports_top_preference():
    async def go():
        async with _client_with_models(["qwen3.6-vision"]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.recommendation_with_reason("video_captioning", "balance")

    out = _run(go())
    assert out["model"] == "qwen3.6-vision"
    assert "top preference" in out["reason"]
    assert out["installed"] == ["qwen3.6-vision"]


def test_recommendation_reports_fallback_index():
    async def go():
        # chat_general speed: ["google/gemma-4-e4b", "gemma-3-1b-..."]
        # nur das zweite installiert — fallback #1
        async with _client_with_models(
            ["gemma-3-1b-it-glm-4.7-flash-heretic-uncensored-thinking_gguf"]
        ) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.recommendation_with_reason("chat_general", "speed")

    out = _run(go())
    assert "gemma-3-1b" in out["model"]
    assert "fallback" in out["reason"]


def test_recommendation_reports_override():
    cfg = {"task_overrides": {"video_captioning": "qwen/qwen3-vl-8b"}}

    async def go():
        async with _client_with_models(["qwen/qwen3-vl-8b"]) as client:
            reg = ModelRegistry(cfg, client=client)
            await reg.refresh()
            return reg.recommendation_with_reason("video_captioning", "balance")

    out = _run(go())
    assert out["model"] == "qwen/qwen3-vl-8b"
    assert "override" in out["reason"]


def test_recommendation_when_none_installed():
    async def go():
        async with _client_with_models([]) as client:
            reg = ModelRegistry(client=client)
            await reg.refresh()
            return reg.recommendation_with_reason("video_captioning", "balance")

    out = _run(go())
    assert out["model"] is None
    assert out["installed"] == []
