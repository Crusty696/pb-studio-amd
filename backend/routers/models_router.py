"""Models Router — LM-Studio-Modell-Management fuer PB Studio.

Endpoints:
  GET    /models/list             — geladene / verfuegbare LM-Studio-Modelle
  GET    /models/available        — kuratierte Vision-Modelle (+ installed-Flag)
  POST   /models/pull             — NICHT mehr unterstuetzt (HTTP 501)
  DELETE /models/{name}           — NICHT mehr unterstuetzt (HTTP 501)
  GET    /models/recommendations  — beste Modell-Empfehlung fuer Task/Mode

LM-Studio-Verbindung defaultet auf ``http://localhost:1234/v1``. Overrides via
``PBSTUDIO_LMSTUDIO_URL`` Environment-Variable. Legacy
``PBSTUDIO_OLLAMA_URL`` wird (mit deprecation-Hinweis im Log) noch akzeptiert.

LM Studio Refactor 2026-05-17: Drop-in von ``OllamaClient`` auf
``LMStudioClient``. LM Studio managed Downloads ueber seine UI — die
``pull``- und ``delete``-Endpoints existieren nur fuer Backwards-Compat
und antworten mit HTTP 501 + Hinweis.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["Models (LM Studio)"])


# ----------------------------------------------------------------------
# Curated list of Vision-capable models PB Studio understands.
# Mirrors the defaults in pb_studio.ai.model_registry. Modell-Identifier
# entsprechen denen, die LM Studio in GET /v1/models liefert.
# ----------------------------------------------------------------------
CURATED_VISION_MODELS: list[dict[str, Any]] = [
    {
        "name": "qwen/qwen3-vl-8b",
        "description": "Qwen 3 VL 8B — primaeres Vision-Modell (DE/EN, schnell, ~8 GB VRAM).",
        "suggested_mode": "balance",
        "size_estimate_gb": 8.0,
        "vision": True,
    },
    {
        "name": "google/gemma-4-e4b",
        "description": "Google Gemma 4 E4B — kompakter Allrounder (Text + Vision), schnell.",
        "suggested_mode": "speed",
        "size_estimate_gb": 4.0,
        "vision": True,
    },
    {
        "name": "gemma-4-26b-a4b-it-ultra-uncensored-heretic",
        "description": "Gemma 4 26B Ultra — sehr hohe Qualitaet (Vision + Text), ~26 GB VRAM.",
        "suggested_mode": "quality",
        "size_estimate_gb": 26.0,
        "vision": True,
    },
    {
        "name": "gemma-4-31b-it-uncensored",
        "description": "Gemma 4 31B — premium Vision + Text, ~31 GB VRAM.",
        "suggested_mode": "quality",
        "size_estimate_gb": 31.0,
        "vision": True,
    },
    {
        "name": "qwen3.5-9b-uncensored-hauhaucs-aggressive",
        "description": "Qwen 3.5 9B — balance-class Chat + Tool-Use (text-only).",
        "suggested_mode": "balance",
        "size_estimate_gb": 9.0,
        "vision": False,
    },
    {
        "name": "raw-uncensored-qwen3-14b-heretic-recovered",
        "description": "Qwen 3 14B — Chat + Tool-Use (quality, text-only).",
        "suggested_mode": "quality",
        "size_estimate_gb": 14.0,
        "vision": False,
    },
]


# ----------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------
class ModelListEntry(BaseModel):
    name: str
    size_bytes: int = 0
    size_mb: float = 0.0
    size_gb: float = 0.0
    modified_at: str = ""
    family: Optional[str] = None
    parameter_size: Optional[str] = None
    quantization_level: Optional[str] = None
    description: str = ""
    is_active: bool = False
    active_tasks: list[str] = Field(default_factory=list)
    vision: bool = False


class ModelListResponse(BaseModel):
    # Feldname bleibt fuer Frontend-Compat — ``ollama_available`` ist jetzt
    # tatsaechlich ``lmstudio_available``, wir behalten den Namen damit das
    # WPF-Frontend nicht sofort brechen muss. Alias-Field gibt LM-Studio-Status.
    ollama_available: bool
    lmstudio_available: bool = False
    base_url: str
    models: list[ModelListEntry] = Field(default_factory=list)
    error: Optional[str] = None


class AvailableModelEntry(BaseModel):
    name: str
    description: str
    suggested_mode: str
    size_estimate_gb: float
    vision: bool
    installed: bool


class AvailableModelsResponse(BaseModel):
    ollama_available: bool
    lmstudio_available: bool = False
    base_url: str
    available: list[AvailableModelEntry] = Field(default_factory=list)


class PullRequest(BaseModel):
    name: str = Field(..., min_length=1, description="LM-Studio-Modellname (z.B. qwen/qwen3-vl-8b)")


class RecommendationResponse(BaseModel):
    task: str
    mode: str
    model: Optional[str] = None
    reason: str
    preference_list: list[str] = Field(default_factory=list)
    override: Optional[str] = None
    installed: list[str] = Field(default_factory=list)


class ActivateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="LM-Studio-Modellname zur Aktivierung")


class TestRequest(BaseModel):
    name: str = Field(..., min_length=1, description="LM-Studio-Modellname zum Testen")


class ModelTestResponse(BaseModel):
    success: bool
    latency_ms: float = 0.0
    response: str = ""
    error: Optional[str] = None


def _enrich_model_entry(entry: ModelListEntry, registry: "ModelRegistry") -> ModelListEntry:
    from pb_studio.ai.model_registry import _name_matches

    # 1. Abgleich mit Kuratierten Modellen
    curated = None
    for c_model in CURATED_VISION_MODELS:
        if _name_matches(c_model["name"], entry.name):
            curated = c_model
            break

    # 2. Parsing von Parameter-Größe aus dem Namen
    parsed_param = None
    # Regex-Suche nach Zahl vor B/b, z.B. 8b, 35b, 1.5b
    param_match = re.search(r'(?:\b|[-_])([0-9]+(?:\.[0-9]+)?)[bB](?:\b|[-_]|\d)', entry.name)
    if param_match:
        parsed_param = param_match.group(1)
        entry.parameter_size = f"{parsed_param}B"

    # 3. Parsing von Quantisierung
    parsed_quant = None
    # Suche nach GGUF-Quantisierungscodes wie q4_k_m, q8_0, fp16
    quant_match = re.search(r'(?:\b|[-_])(q[0-9]+_[kK]_[mMsSlL]|q[0-9]+_[0-9]|[qQ][0-9]_[kK]|[qQ][0-9]_[0-9a-zA-Z]|[fF][pP]16|[fF]16|[fF][pP]8|[gG][gG][uU][fF])(?:\b|[-_])', entry.name)
    if quant_match:
        parsed_quant = quant_match.group(1).upper()
        entry.quantization_level = parsed_quant
    elif "fp16" in entry.name.lower() or "f16" in entry.name.lower():
        entry.quantization_level = "FP16"
    elif "fp8" in entry.name.lower() or "f8" in entry.name.lower():
        entry.quantization_level = "FP8"

    # 4. Schätzung der Dateigröße, falls 0
    if entry.size_bytes == 0:
        param_val = 7.0 # Standardwert
        if parsed_param:
            try:
                param_val = float(parsed_param)
            except ValueError:
                pass
        elif curated:
            param_val = curated["size_estimate_gb"] / 0.58 # rückgerechnet

        quant_factor = 0.58 # Standard Q4
        q_lower = (entry.quantization_level or "").lower()
        if "fp16" in q_lower or "f16" in q_lower:
            quant_factor = 2.0
        elif "q8" in q_lower:
            quant_factor = 1.0
        elif "q6" in q_lower:
            quant_factor = 0.8
        elif "q5" in q_lower:
            quant_factor = 0.68
        elif "q4" in q_lower:
            quant_factor = 0.58
        elif "q3" in q_lower:
            quant_factor = 0.48
        elif "q2" in q_lower:
            quant_factor = 0.38

        est_gb = param_val * quant_factor
        entry.size_gb = round(est_gb, 2)
        entry.size_mb = round(est_gb * 1024, 1)
        entry.size_bytes = int(est_gb * 1024 * 1024 * 1024)

    # 5. Vision-Fähigkeit erkennen
    entry.vision = False
    if curated:
        entry.vision = curated["vision"]
    else:
        # Vision-Keywords im Namen suchen
        vision_keywords = ["vl", "vision", "moondream", "llava", "multimodal", "clip"]
        name_lower = entry.name.lower()
        if any(kw in name_lower for kw in vision_keywords):
            entry.vision = True

    # 6. Aktive Tasks bestimmen
    entry.active_tasks = []
    # Standardmäßige Tasks:
    tasks_to_check = {
        "video_captioning": "Video-Analyse",
        "image_captioning": "Bild-Analyse",
        "chat": "Chat (Haupt)",
        "chat_general": "Chat",
        "chat_tool_use": "Tool-Ausführung",
        "brain_explanation": "KI-Director"
    }
    for t_key, t_name in tasks_to_check.items():
        try:
            selected = registry.select_best_for_task(t_key, mode="balance")
            if _name_matches(selected, entry.name):
                entry.active_tasks.append(t_name)
        except Exception:
            pass

    entry.is_active = len(entry.active_tasks) > 0

    # 7. Deutsche Beschreibung generieren
    if curated:
        entry.description = curated["description"]
    else:
        # Dynamische Beschreibung
        family_name = "LLM"
        for fam in ["Gemma", "Qwen", "Llama", "Phi", "Mistral", "DeepSeek", "Gemma-4", "Phi-4"]:
            if fam.lower() in entry.name.lower():
                family_name = fam
                break

        type_str = "Vision- und Text-Modell" if entry.vision else "reines Textmodell"
        desc_parts = [
            f"Lokales {family_name} ({type_str}).",
            f"Parametergröße: {entry.parameter_size or 'Unbekannt'}, Quantisierung: {entry.quantization_level or 'Unbekannt'}."
        ]
        if entry.vision:
            desc_parts.append("Eignet sich hervorragend zur Bildbeschreibung und Video-Szenen-Analyse.")
        else:
            desc_parts.append("Optimiert für Textgenerierung, logisches Denken und interaktive Chats.")

        entry.description = " ".join(desc_parts)

    return entry


# ----------------------------------------------------------------------
# Helper: LM-Studio-Client + AI-Config-Reader
# ----------------------------------------------------------------------
def _get_base_url() -> str:
    explicit = os.environ.get("PBSTUDIO_LMSTUDIO_URL")
    if explicit:
        return explicit
    legacy = os.environ.get("PBSTUDIO_OLLAMA_URL")
    if legacy:
        logger.warning(
            "PBSTUDIO_OLLAMA_URL=%s ist deprecated — bitte PBSTUDIO_LMSTUDIO_URL setzen",
            legacy,
        )
        # Auto-rewrite 11434 -> 1234/v1 nur fuer den haeufigsten Ollama-Default
        if "11434" in legacy:
            return "http://127.0.0.1:1234/v1"
        return legacy
    return "http://127.0.0.1:1234/v1"


def _make_client():
    """Erzeugt einen frischen ``LMStudioClient`` mit Default-Settings.

    W-QA-2 (2026-05-22): respektiert config.ai.provider — bei "ollama" wird
    der Ollama-Base-URL gewaehlt. Bei "auto" greift get_alive_client_url() ein
    um Live-Verfuegbarkeit zu pruefen. Env-Override hat hoechste Prio.
    """
    from pb_studio.ai.lmstudio_client import LMStudioClient

    return LMStudioClient(base_url=_get_base_url())


async def _make_alive_client():
    """W-QA-2 (2026-05-22): Auto-Fallback Client.

    Bei provider="auto" + LM-Studio down + Ollama up → Ollama-Client.
    Returns (client, lmstudio_ok, ollama_ok). Caller schliesst client via
    ``async with``. Wenn beide down: client ist None.
    """
    # Env-Override hat Vorrang — kein Fallback wenn explizit gesetzt
    explicit = os.environ.get("PBSTUDIO_LMSTUDIO_URL") or os.environ.get("PBSTUDIO_OLLAMA_URL")
    if explicit:
        return _make_client(), True, False  # uns ist die Pruefung egal, env weist auf gewollten Server

    from pb_studio.ai.llm_provider import get_provider, get_llm_client, DEFAULT_LMSTUDIO_URL, DEFAULT_OLLAMA_URL
    from pb_studio.ai.lmstudio_client import LMStudioConnectionError

    provider = get_provider()
    lmstudio_ok = False
    ollama_ok = False

    async def _probe(p: str) -> bool:
        c = get_llm_client(provider=p, timeout_seconds=3.0)
        try:
            return await c.is_alive()
        except LMStudioConnectionError:
            return False
        finally:
            try:
                await c.aclose()
            except Exception:
                pass

    if provider in ("auto", "lmstudio"):
        lmstudio_ok = await _probe("lmstudio")
    if provider in ("auto", "ollama"):
        ollama_ok = await _probe("ollama")

    # Provider-Wahl
    if provider == "lmstudio":
        chosen = "lmstudio" if lmstudio_ok else None
    elif provider == "ollama":
        chosen = "ollama" if ollama_ok else None
    else:  # auto
        chosen = "lmstudio" if lmstudio_ok else ("ollama" if ollama_ok else None)

    client = get_llm_client(provider=chosen) if chosen else None
    return client, lmstudio_ok, ollama_ok


def _load_ai_config() -> dict[str, Any]:
    try:
        from pb_studio.config_manager import ConfigManager

        ai = ConfigManager().get("ai") or {}
        if isinstance(ai, dict):
            return ai
    except Exception as exc:
        logger.debug("AI-Config nicht ladbar: %s", exc)
    return {}


# ----------------------------------------------------------------------
# GET /models/list
# ----------------------------------------------------------------------
@router.get("/list", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    """Liefert alle in LM Studio ODER Ollama verfuegbaren / geladenen Modelle.

    W-QA-2 (2026-05-22): respektiert config.ai.provider mit Auto-Fallback.
    Reportet ``ollama_available`` und ``lmstudio_available`` korrekt.
    """
    from pb_studio.ai.lmstudio_client import LMStudioError

    client, lmstudio_ok, ollama_ok = await _make_alive_client()
    if client is None:
        return ModelListResponse(
            ollama_available=ollama_ok,
            lmstudio_available=lmstudio_ok,
            base_url=_get_base_url(),
            models=[],
            error="Kein LLM-Provider erreichbar (weder LM Studio noch Ollama)",
        )

    try:
        from pb_studio.ai.model_registry import ModelRegistry
        ai_cfg = _load_ai_config()

        async with client as c:
            models = await c.list_models()
            active_base = c.base_url
            # Bereite Registry vor, um aktive Zuweisungen zu ermitteln
            registry = ModelRegistry(ai_cfg, client=c)
            registry._installed = models
            registry._loaded = True

        entries = []
        for m in models:
            entry = ModelListEntry(**m.to_dict())
            enriched = _enrich_model_entry(entry, registry)
            entries.append(enriched)

        return ModelListResponse(
            ollama_available=ollama_ok,
            lmstudio_available=lmstudio_ok,
            base_url=active_base,
            models=entries,
        )
    except LMStudioError as exc:
        logger.warning("list_models fehlgeschlagen: %s", exc)
        return ModelListResponse(
            ollama_available=ollama_ok,
            lmstudio_available=lmstudio_ok,
            base_url=_get_base_url(),
            models=[],
            error=str(exc),
        )


# ----------------------------------------------------------------------
# GET /models/available
# ----------------------------------------------------------------------
@router.get("/available", response_model=AvailableModelsResponse)
async def list_available_models() -> AvailableModelsResponse:
    """Kuratierte Vision-Modelle + Installations-Status."""
    from pb_studio.ai.model_registry import _name_matches  # type: ignore
    from pb_studio.ai.lmstudio_client import LMStudioError

    # W-QA-2 (2026-05-22): Hybrid-Auto-Fallback statt hard-coded LM-Studio.
    client, lmstudio_ok, ollama_ok = await _make_alive_client()
    installed_names: list[str] = []
    active_base = _get_base_url()
    if client is not None:
        try:
            async with client as c:
                models = await c.list_models()
                active_base = c.base_url
            installed_names = [m.name for m in models]
        except LMStudioError as exc:
            logger.warning("list_models fehlgeschlagen (/available): %s", exc)

    entries: list[AvailableModelEntry] = []
    for spec in CURATED_VISION_MODELS:
        is_installed = any(_name_matches(spec["name"], n) for n in installed_names)
        entries.append(
            AvailableModelEntry(
                name=spec["name"],
                description=spec["description"],
                suggested_mode=spec["suggested_mode"],
                size_estimate_gb=spec["size_estimate_gb"],
                vision=spec["vision"],
                installed=is_installed,
            )
        )
    return AvailableModelsResponse(
        ollama_available=ollama_ok,
        lmstudio_available=lmstudio_ok,
        base_url=active_base,
        available=entries,
    )


# ----------------------------------------------------------------------
# POST /models/pull  — NICHT unterstuetzt (LM Studio managed Downloads)
# ----------------------------------------------------------------------
_LMSTUDIO_MANAGEMENT_HINT = (
    "LM Studio managed Modell-Downloads und -Loeschungen ueber die Desktop-App. "
    "Bitte oeffne LM Studio -> Discover-Tab um ein neues Modell zu laden, oder "
    "-> My Models um eines zu entfernen."
)


@router.post("/pull", status_code=501)
async def pull_model(request: PullRequest) -> JSONResponse:
    """LM Studio managed Downloads ueber UI — HTTP 501 + Hinweis."""
    return JSONResponse(
        status_code=501,
        content={
            "error": "not_implemented",
            "message": _LMSTUDIO_MANAGEMENT_HINT,
            "requested_model": request.name,
            "hint": "Open LM Studio -> Discover tab to download models.",
        },
    )


# ----------------------------------------------------------------------
# DELETE /models/{name}  — NICHT unterstuetzt (LM Studio managed)
# ----------------------------------------------------------------------
@router.delete("/{name:path}", status_code=501)
async def delete_model(name: str) -> JSONResponse:
    """LM Studio managed Modelle ueber UI — HTTP 501 + Hinweis."""
    if not name.strip():
        raise HTTPException(status_code=400, detail="Leerer Modellname")
    return JSONResponse(
        status_code=501,
        content={
            "error": "not_implemented",
            "message": _LMSTUDIO_MANAGEMENT_HINT,
            "requested_model": name,
            "hint": "Open LM Studio -> My Models tab to remove models.",
        },
    )


# ----------------------------------------------------------------------
# GET /models/recommendations
# ----------------------------------------------------------------------
@router.get("/recommendations", response_model=RecommendationResponse)
async def recommend_model(
    task: str = Query(default="video_captioning", description="Task-Schluessel"),
    mode: str = Query(default="balance", description="speed|balance|quality"),
) -> RecommendationResponse:
    """Liefert das Modell, das die Auto-Selection fuer Task/Mode auswaehlen wuerde."""
    from pb_studio.ai.model_registry import ModelRegistry, ModelRegistryError
    from pb_studio.ai.lmstudio_client import LMStudioError

    ai_cfg = _load_ai_config()
    # W-QA-2 (2026-05-22): Hybrid-Auto-Fallback statt hard-coded LM Studio.
    client, lmstudio_ok, ollama_ok = await _make_alive_client()
    if client is None:
        registry_stub = ModelRegistry(ai_cfg)
        return RecommendationResponse(
            task=task,
            mode=mode,
            model=None,
            reason="Kein LLM-Provider erreichbar (weder LM Studio noch Ollama)",
            preference_list=registry_stub.get_preference_list(task, mode) if mode in {"speed", "balance", "quality"} else [],
            override=registry_stub.get_user_override(task),
            installed=[],
        )
    try:
        async with client as c:
            registry = ModelRegistry(ai_cfg, client=c)
            try:
                await registry.refresh()
            except LMStudioError as exc:
                return RecommendationResponse(
                    task=task,
                    mode=mode,
                    model=None,
                    reason=f"LLM-Provider nicht erreichbar: {exc}",
                    preference_list=registry.get_preference_list(task, mode) if mode in {"speed", "balance", "quality"} else [],
                    override=registry.get_user_override(task),
                    installed=[],
                )
            try:
                data = registry.recommendation_with_reason(task, mode)
            except ModelRegistryError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RecommendationResponse(**data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("recommend_model fehlgeschlagen: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/activate")
async def activate_model(request: ActivateRequest) -> JSONResponse:
    """Aktiviert ein Modell fuer die passenden AI-Tasks in PB Studio und persistiert dies in der Konfiguration."""
    try:
        from pb_studio.config_manager import ConfigManager

        # 1. Ermitteln, ob das Modell vision-faehig ist
        vision_keywords = ["vl", "vision", "moondream", "llava", "multimodal", "clip"]
        name_lower = request.name.lower()
        is_vision = any(kw in name_lower for kw in vision_keywords)
        
        from pb_studio.ai.model_registry import _name_matches
        for c_model in CURATED_VISION_MODELS:
            if _name_matches(c_model["name"], request.name):
                is_vision = c_model["vision"]
                break

        # 2. Config laden und task_overrides anpassen
        cfg_manager = ConfigManager()
        ai_cfg = cfg_manager.get("ai") or {}
        if not isinstance(ai_cfg, dict):
            ai_cfg = {}

        overrides = ai_cfg.get("task_overrides") or {}
        if not isinstance(overrides, dict):
            overrides = {}

        # Text-Tasks überschreiben wir immer
        text_tasks = ["chat", "chat_general", "chat_tool_use", "brain_explanation"]
        for t in text_tasks:
            overrides[t] = request.name

        # Vision-Tasks nur bei vision-faehigen Modellen überschreiben
        vision_tasks = ["video_captioning", "image_captioning"]
        if is_vision:
            for t in vision_tasks:
                overrides[t] = request.name
        else:
            # Falls ein nicht-vision-faehiges Modell aktiviert wird, loeschen wir die Overrides fuer Vision-Tasks,
            # damit dort das standardmaessige Vision-Modell aktiv bleibt!
            for t in vision_tasks:
                if t in overrides:
                    del overrides[t]

        ai_cfg["task_overrides"] = overrides

        if is_vision:
            ai_cfg["vision_model"] = request.name

        cfg_manager.set("ai", ai_cfg)

        logger.info("Modell '%s' erfolgreich fuer Tasks aktiviert (Vision: %s)", request.name, is_vision)
        return JSONResponse(
            status_code=200,
            content={
                "message": f"Modell '{request.name}' erfolgreich aktiviert.",
                "vision_enabled": is_vision,
                "activated_tasks": text_tasks + (vision_tasks if is_vision else [])
            }
        )
    except Exception as exc:
        logger.error("Aktivierung von Modell '%s' fehlgeschlagen: %s", request.name, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/test", response_model=ModelTestResponse)
async def test_model(request: TestRequest) -> ModelTestResponse:
    """Fuehrt einen minimalen Inferenz-Smoke-Test (max_tokens=1) auf der AMD-GPU durch, um die Funktion zu pruefen."""
    import time
    
    client, lmstudio_ok, ollama_ok = await _make_alive_client()
    if client is None:
        return ModelTestResponse(
            success=False,
            error="Kein LLM-Provider erreichbar (weder LM Studio noch Ollama)."
        )

    start_time = time.perf_counter()
    try:
        async with client as c:
            # Minimaler Prompt, nur 1 Token generieren um VRAM und Zeit zu sparen
            result = await c.generate(
                model=request.name,
                prompt="Say 'ok'",
                options={"max_tokens": 1, "temperature": 0.0}
            )
            response_text = result.get("response") or ""

        latency = (time.perf_counter() - start_time) * 1000.0
        return ModelTestResponse(
            success=True,
            latency_ms=round(latency, 1),
            response=response_text.strip() or "OK"
        )
    except Exception as exc:
        latency = (time.perf_counter() - start_time) * 1000.0
        logger.warning("GPU-Smoke-Test fuer Modell '%s' fehlgeschlagen: %s", request.name, exc)
        return ModelTestResponse(
            success=False,
            latency_ms=round(latency, 1),
            error=str(exc)
        )


__all__ = ["router"]
