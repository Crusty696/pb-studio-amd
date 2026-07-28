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
PROVIDER_PROBE_DEADLINE_SECONDS = 3.0


# ----------------------------------------------------------------------
# Curated list of Vision-capable models PB Studio understands.
# Mirrors the defaults in pb_studio.ai.model_registry. Modell-Identifier
# entsprechen denen, die LM Studio in GET /v1/models liefert.
# ----------------------------------------------------------------------
CURATED_VISION_MODELS: list[dict[str, Any]] = [
    # Review-Fix MEDIUM (2026-07-09): "qwen3.6-vision"/"qwen3.5-vl" waren
    # erfundene Ids — reale LM-Studio-Katalog-Ids verifiziert via
    # GET /v1/models + lmstudio.ai/models (Qwen3.5/3.6 sind Vision-faehig).
    {
        "name": "qwen/qwen3.6-27b",
        "description": "Qwen 3.6 27B — neuestes Vision+Reasoning-Modell, beste Qualitaet fuer Bild-/Video-Captioning (~16 GB VRAM, q4).",
        "suggested_mode": "quality",
        "size_estimate_gb": 16.0,
        "vision": True,
    },
    {
        "name": "qwen/qwen3.5-9b",
        "description": "Qwen 3.5 9B — schnelles Vision-Reasoning-Modell der 3.5er Generation (~6 GB VRAM).",
        "suggested_mode": "balance",
        "size_estimate_gb": 6.0,
        "vision": True,
    },
    {
        "name": "qwen/qwen3-vl-8b",
        "description": "Qwen 3 VL 8B — Vision-Modell (DE/EN, schnell, ~8 GB VRAM).",
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
    provider: str = "lmstudio"


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


class ModeRequest(BaseModel):
    mode: str = Field(..., min_length=1, description="KI-Modus: speed|balance|quality")


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

    # 2. Parsing von Parameter-Größe aus dem Namen (nur wenn nicht bereits belegt)
    if not entry.parameter_size:
        parsed_param = None
        # Regex-Suche nach Zahl vor B/b, z.B. 8b, 35b, 1.5b
        param_match = re.search(r'(?:\b|[-_])([0-9]+(?:\.[0-9]+)?)[bB](?:\b|[-_]|\d)', entry.name)
        if param_match:
            parsed_param = param_match.group(1)
            entry.parameter_size = f"{parsed_param}B"

    # 3. Parsing von Quantisierung (nur wenn nicht bereits belegt)
    if not entry.quantization_level:
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
        if entry.parameter_size:
            param_match = re.search(r'([0-9]+(?:\.[0-9]+)?)', entry.parameter_size)
            if param_match:
                try:
                    param_val = float(param_match.group(1))
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
    else:
        # Falls Größe bereits bekannt (z.B. von Ollama), rechnen wir GB und MB korrekt aus!
        entry.size_gb = round(entry.size_bytes / (1024 * 1024 * 1024), 2)
        entry.size_mb = round(entry.size_bytes / (1024 * 1024), 1)

    # 5. Vision-Fähigkeit erkennen
    entry.vision = registry._is_vision_capable(entry.name)

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
    from pb_studio.config_manager import ConfigManager
    current_mode = ConfigManager().get("ai", {}).get("default_mode", "balance")
    for t_key, t_name in tasks_to_check.items():
        try:
            selected = registry.select_best_for_task(t_key, mode=current_mode)
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
        if "11434" in legacy:
            from pb_studio.ai.llm_provider import get_base_url
            return get_base_url(provider="lmstudio")
        return legacy
    from pb_studio.ai.llm_provider import get_base_url
    return get_base_url(provider="lmstudio")


def _make_client():
    """Erzeugt einen frischen ``LMStudioClient`` mit Default-Settings.

    W-QA-2 (2026-05-22): respektiert config.ai.provider — bei "ollama" wird
    der Ollama-Base-URL gewaehlt. Bei "auto" greift get_alive_client_url() ein
    um Live-Verfuegbarkeit zu pruefen. Env-Override hat hoechste Prio.
    """
    from pb_studio.ai.lmstudio_client import LMStudioClient

    return LMStudioClient(base_url=_get_base_url())


async def _make_alive_client(required_capability: Optional[str] = None):
    """W-QA-2 (2026-05-22): Auto-Fallback Client.

    Bei provider="auto" + LM-Studio down + Ollama up → Ollama-Client.
    Returns (client, lmstudio_ok, ollama_ok). Caller schliesst client via
    ``async with``. Wenn beide down: client ist None.
    """
    # Env-Override hat Vorrang — kein Fallback wenn explizit gesetzt
    explicit = os.environ.get("PBSTUDIO_LMSTUDIO_URL") or os.environ.get("PBSTUDIO_OLLAMA_URL")
    if explicit:
        explicit_client = _make_client()
        try:
            probe_call = (
                explicit_client.supports_capability(required_capability)
                if required_capability
                else explicit_client.is_alive()
            )
            available = await asyncio.wait_for(
                probe_call,
                timeout=PROVIDER_PROBE_DEADLINE_SECONDS,
            )
        except Exception:
            available = False
        if not available:
            await explicit_client.aclose()
            return None, False, False
        is_ollama = "11434" in explicit_client.base_url
        return explicit_client, not is_ollama, is_ollama

    from pb_studio.ai.llm_provider import get_provider, get_llm_client, DEFAULT_LMSTUDIO_URL, DEFAULT_OLLAMA_URL
    from pb_studio.ai.lmstudio_client import LMStudioConnectionError

    provider = get_provider()
    lmstudio_ok = False
    ollama_ok = False

    async def _probe(p: str) -> bool:
        c = get_llm_client(
            provider=p,
            timeout_seconds=PROVIDER_PROBE_DEADLINE_SECONDS,
            retry_attempts=1,
        )
        try:
            probe_call = (
                c.supports_capability(required_capability)
                if required_capability
                else c.is_alive()
            )
            return await asyncio.wait_for(
                probe_call,
                timeout=PROVIDER_PROBE_DEADLINE_SECONDS,
            )
        except (LMStudioConnectionError, asyncio.TimeoutError):
            return False
        except Exception as exc:  # noqa: BLE001 - Provider-Fallback bleibt aktiv
            logger.debug("Provider-Probe %s fehlgeschlagen: %s", p, exc)
            return False
        finally:
            try:
                await c.aclose()
            except Exception:
                pass

    probe_names = [
        name
        for name in ("lmstudio", "ollama")
        if provider in ("auto", name)
    ]
    probe_values = await asyncio.gather(*(_probe(name) for name in probe_names))
    probe_results = dict(zip(probe_names, probe_values))
    lmstudio_ok = probe_results.get("lmstudio", False)
    ollama_ok = probe_results.get("ollama", False)

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
    """Liefert alle verfuegbaren Modelle aus LM Studio UND Ollama (Hybrid-Merge)."""
    from pb_studio.ai.lmstudio_client import LMStudioClient, LMStudioError
    from pb_studio.ai.llm_provider import get_llm_client
    
    lmstudio_ok = False
    ollama_ok = False
    
    lmstudio_client = get_llm_client(
        provider="lmstudio",
        timeout_seconds=PROVIDER_PROBE_DEADLINE_SECONDS,
        retry_attempts=1,
    )
    ollama_client = get_llm_client(
        provider="ollama",
        timeout_seconds=PROVIDER_PROBE_DEADLINE_SECONDS,
        retry_attempts=1,
    )

    async def _bounded_alive(provider_client) -> bool:
        try:
            return await asyncio.wait_for(
                provider_client.is_alive(),
                timeout=PROVIDER_PROBE_DEADLINE_SECONDS,
            )
        except Exception:
            return False

    lmstudio_ok, ollama_ok = await asyncio.gather(
        _bounded_alive(lmstudio_client),
        _bounded_alive(ollama_client),
    )

    if not lmstudio_ok and not ollama_ok:
        try:
            await lmstudio_client.aclose()
        except Exception:
            pass
        try:
            await ollama_client.aclose()
        except Exception:
            pass
        return ModelListResponse(
            ollama_available=False,
            lmstudio_available=False,
            base_url=_get_base_url(),
            models=[],
            error="Kein LLM-Provider erreichbar (weder LM Studio noch Ollama)",
        )

    merged_models = []
    seen_names = set()
    
    async def _fetch_from_provider(p_client, p_ok):
        if not p_ok:
            return []
        try:
            async with p_client as c:
                return await c.list_models()
        except Exception as exc:
            logger.warning("Fehler beim Laden der Modelle von %s: %s", p_client.base_url, exc)
            return []

    lms_models, oll_models = await asyncio.gather(
        _fetch_from_provider(lmstudio_client, lmstudio_ok),
        _fetch_from_provider(ollama_client, ollama_ok),
    )

    lms_names = {m.name for m in lms_models}
    oll_names = {m.name for m in oll_models}

    for m in lms_models + oll_models:
        m_name = m.name
        if m_name not in seen_names:
            seen_names.add(m_name)
            merged_models.append(m)

    async def _fetch_capabilities(provider_client, provider_ok):
        if not provider_ok:
            return {}
        try:
            async with provider_client as c:
                return await asyncio.wait_for(
                    c.get_model_capabilities(),
                    timeout=PROVIDER_PROBE_DEADLINE_SECONDS,
                )
        except Exception as exc:
            logger.debug("Konnte Modell-Capabilities nicht abfragen: %s", exc)
            return {}

    lms_capabilities, oll_capabilities = await asyncio.gather(
        _fetch_capabilities(lmstudio_client, lmstudio_ok),
        _fetch_capabilities(ollama_client, ollama_ok),
    )
    capabilities_by_name: dict[str, frozenset[str]] = {}
    for provider_capabilities in (lms_capabilities, oll_capabilities):
        for name, capabilities in provider_capabilities.items():
            capabilities_by_name[name] = frozenset(
                set(capabilities_by_name.get(name, frozenset())) | set(capabilities)
            )

    from pb_studio.ai.model_registry import ModelRegistry
    ai_cfg = _load_ai_config()
    
    registry = ModelRegistry(ai_cfg, client=None)
    registry._installed = merged_models
    registry._model_capabilities = capabilities_by_name
    registry._vision_models = {
        name
        for name, capabilities in capabilities_by_name.items()
        if "vision" in capabilities
    }
    registry._loaded = True

    entries = []
    for m in merged_models:
        entry = ModelListEntry(**m.to_dict())
        
        # Provider-Zuweisung
        is_lms = m.name in lms_names
        is_oll = m.name in oll_names
        if is_lms and is_oll:
            entry.provider = "both"
        elif is_oll:
            entry.provider = "ollama"
        else:
            entry.provider = "lmstudio"

        enriched = _enrich_model_entry(entry, registry)
        entries.append(enriched)

    active_base = lmstudio_client.base_url if lmstudio_ok else ollama_client.base_url

    return ModelListResponse(
        ollama_available=ollama_ok,
        lmstudio_available=lmstudio_ok,
        base_url=active_base,
        models=entries,
    )


# ----------------------------------------------------------------------
# GET /models/available
# ----------------------------------------------------------------------
@router.get("/available", response_model=AvailableModelsResponse)
async def list_available_models() -> AvailableModelsResponse:
    """Kuratierte Vision-Modelle + Installations-Status (Hybrid-Merge)."""
    from pb_studio.ai.model_registry import _name_matches  # type: ignore
    from pb_studio.ai.lmstudio_client import LMStudioError
    from pb_studio.ai.llm_provider import get_llm_client

    lmstudio_ok = False
    ollama_ok = False
    
    lmstudio_client = get_llm_client(
        provider="lmstudio",
        timeout_seconds=PROVIDER_PROBE_DEADLINE_SECONDS,
        retry_attempts=1,
    )
    ollama_client = get_llm_client(
        provider="ollama",
        timeout_seconds=PROVIDER_PROBE_DEADLINE_SECONDS,
        retry_attempts=1,
    )

    async def _bounded_alive(provider_client) -> bool:
        try:
            return await asyncio.wait_for(
                provider_client.is_alive(),
                timeout=PROVIDER_PROBE_DEADLINE_SECONDS,
            )
        except Exception:
            return False

    lmstudio_ok, ollama_ok = await asyncio.gather(
        _bounded_alive(lmstudio_client),
        _bounded_alive(ollama_client),
    )

    installed_names: list[str] = []
    
    async def _fetch_names(p_client, p_ok):
        if not p_ok:
            return []
        try:
            async with p_client as c:
                models = await c.list_models()
                return [m.name for m in models]
        except Exception:
            return []

    lms_names, oll_names = await asyncio.gather(
        _fetch_names(lmstudio_client, lmstudio_ok),
        _fetch_names(ollama_client, ollama_ok),
    )
    installed_names = list(set(lms_names + oll_names))

    active_base = lmstudio_client.base_url if lmstudio_ok else ollama_client.base_url

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


async def ollama_pull_generator(model_name: str, ollama_url: str):
    import httpx
    # Rewrite base_url from OpenAI compat (e.g. /v1) to native Ollama api /api/pull
    pull_url = ollama_url
    if pull_url.endswith("/v1"):
        pull_url = pull_url[:-3]
    pull_url = f"{pull_url.rstrip('/')}/api/pull"
    
    logger.info(f"Ollama native pull starting for model {model_name} via {pull_url}")
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", pull_url, json={"name": model_name, "stream": True}) as response:
                if response.status_code != 200:
                    err_msg = f"Ollama HTTP {response.status_code}"
                    yield f"event: pull_progress\ndata: {json.dumps({'status': 'error', 'error': err_msg})}\n\n"
                    return
                
                async for line in response.aiter_lines():
                    if line.strip():
                        yield f"event: pull_progress\ndata: {line.strip()}\n\n"
    except Exception as exc:
        logger.error(f"Ollama pull failed: {exc}")
        yield f"event: pull_progress\ndata: {json.dumps({'status': 'error', 'error': str(exc)})}\n\n"


@router.post("/pull")
async def pull_model(request: PullRequest):
    """LM Studio managed Downloads ueber UI — oder native Weiterleitung an Ollama."""
    client, lmstudio_ok, ollama_ok = await _make_alive_client()
    
    # Universal Ollama-Download-Bypass: Wenn Ollama online ist, leiten wir alle Downloads an Ollama weiter!
    if ollama_ok:
        from pb_studio.ai.llm_provider import DEFAULT_OLLAMA_URL
        return StreamingResponse(
            ollama_pull_generator(request.name, DEFAULT_OLLAMA_URL),
            media_type="text/event-stream"
        )

    return JSONResponse(
        status_code=501,
        content={
            "error": "not_implemented",
            "message": _LMSTUDIO_MANAGEMENT_HINT,
            "requested_model": request.name,
            "hint": "Open LM Studio -> Discover tab to download models, or start Ollama to enable universal downloads.",
        },
    )


# ----------------------------------------------------------------------
# DELETE /models/{name}  — NICHT unterstuetzt (LM Studio managed) oder Ollama DELETE
# ----------------------------------------------------------------------
@router.delete("/{name:path}")
async def delete_model(name: str) -> JSONResponse:
    """LM Studio managed Modelle ueber UI — oder native Loeschung via Ollama."""
    if not name.strip():
        raise HTTPException(status_code=400, detail="Leerer Modellname")
    
    client, lmstudio_ok, ollama_ok = await _make_alive_client()
    
    # Universal Ollama-Delete-Bypass: Wenn Ollama online ist, können wir das Modell dort löschen!
    if ollama_ok:
        from pb_studio.ai.llm_provider import DEFAULT_OLLAMA_URL
        import httpx
        delete_url = DEFAULT_OLLAMA_URL
        if delete_url.endswith("/v1"):
            delete_url = delete_url[:-3]
        delete_url = f"{delete_url.rstrip('/')}/api/delete"
        
        logger.info(f"Ollama native delete starting for model {name} via {delete_url}")
        try:
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                response = await http_client.request("DELETE", delete_url, json={"name": name})
                if response.status_code == 200:
                    return JSONResponse(content={"status": "success", "message": f"Model {name} deleted."})
        except Exception as exc:
            logger.error(f"Ollama delete failed: {exc}")

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
    required_capability = (
        "vision"
        if task in {"video_captioning", "image_captioning"}
        else "chat"
    )
    client, lmstudio_ok, ollama_ok = await _make_alive_client(required_capability)
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


@router.post("/mode")
async def update_ki_mode(request: ModeRequest) -> JSONResponse:
    """Aktualisiert den standardmaessigen KI-Modus (speed|balance|quality) in der Konfiguration."""
    if request.mode not in ("speed", "balance", "quality"):
        raise HTTPException(status_code=400, detail="Ungueltiger Modus. Erlaubt sind: speed, balance, quality.")
    try:
        from pb_studio.config_manager import ConfigManager
        cfg_manager = ConfigManager()
        ai_cfg = cfg_manager.get("ai") or {}
        if not isinstance(ai_cfg, dict):
            ai_cfg = {}
        
        ai_cfg["default_mode"] = request.mode
        cfg_manager.set("ai", ai_cfg)
        
        logger.info("KI-Modus erfolgreich auf '%s' aktualisiert", request.mode)
        return JSONResponse(
            status_code=200,
            content={
                "message": f"KI-Modus erfolgreich auf '{request.mode}' aktualisiert.",
                "mode": request.mode
            }
        )
    except Exception as exc:
        logger.error("Aktualisierung des KI-Modus fehlgeschlagen: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/test", response_model=ModelTestResponse)
async def test_model(request: TestRequest) -> ModelTestResponse:
    """Fuehrt einen minimalen Inferenz-Smoke-Test (max_tokens=1) auf der AMD-GPU durch, um die Funktion zu pruefen."""
    import time
    
    client, lmstudio_ok, ollama_ok = await _make_alive_client("chat")
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
