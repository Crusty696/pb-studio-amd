"""Providerübergreifendes Modellinventar und Management für PB Studio.

Endpoints:
  GET    /models/list             — live verifiziertes Providerinventar
  GET    /models/available        — live verifizierte Downloads/Discovery
  POST   /models/pull             — exakt verifizierter Ollama-Pull
  DELETE /models/{name}           — exakt verifiziertes Ollama-Delete
  GET    /models/recommendations  — receiptgebundene Empfehlung
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from ..owner_capability import OWNER_CAPABILITY_HEADER, authorize_owner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["Models (LM Studio)"])


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
    installed: bool = True
    loaded: bool = False
    downloadable: bool = False
    usable: bool = False
    capabilities: list[str] = Field(default_factory=list)
    inventory_sources: list[str] = Field(default_factory=list)
    verified_at: str = ""
    status_reason: str = ""
    # Audit 2026-08-05 (H-3/T3.9): Diese vier Felder liefert LM Studio
    # nachweislich, sie wurden aber auf drei Schichten hintereinander
    # abgeschnitten und erreichten die Modell-Karte nie. Das Kontextfenster ist
    # dabei die praktisch wichtigste Zahl: der Chat-Agent verweist im Fehlerfall
    # selbst darauf ("Verlauf kuerzen oder groesseres Kontextfenster waehlen").
    context_length: Optional[int] = None
    architecture: Optional[str] = None
    publisher: Optional[str] = None
    runtime_state: Optional[str] = None


class ProviderStatusEntry(BaseModel):
    provider: str
    status: str
    base_url: str
    verified_at: str
    status_reason: str = ""
    catalog_status: str = "not_verified"
    discover_url: Optional[str] = None


class ModelListResponse(BaseModel):
    # Feldname bleibt fuer Frontend-Compat — ``ollama_available`` ist jetzt
    # tatsaechlich ``lmstudio_available``, wir behalten den Namen damit das
    # WPF-Frontend nicht sofort brechen muss. Alias-Field gibt LM-Studio-Status.
    ollama_available: bool
    lmstudio_available: bool = False
    base_url: str
    models: list[ModelListEntry] = Field(default_factory=list)
    providers: list[ProviderStatusEntry] = Field(default_factory=list)
    inventory_generation: int = 0
    verified_at: str = ""
    error: Optional[str] = None


class AvailableModelEntry(BaseModel):
    name: str
    description: str
    suggested_mode: str
    size_estimate_gb: float
    vision: bool
    installed: bool
    provider: str = "lmstudio"
    loaded: bool = False
    downloadable: bool = False
    usable: bool = False
    capabilities: list[str] = Field(default_factory=list)
    verified_at: str = ""
    status_reason: str = ""


class DiscoverAction(BaseModel):
    provider: str
    label: str
    url: str
    catalog_status: str


class AvailableModelsResponse(BaseModel):
    ollama_available: bool
    lmstudio_available: bool = False
    base_url: str
    available: list[AvailableModelEntry] = Field(default_factory=list)
    discover_actions: list[DiscoverAction] = Field(default_factory=list)
    inventory_generation: int = 0
    verified_at: str = ""


class PullRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Live-verifizierte Ollama-Modell-ID",
    )


class RecommendationResponse(BaseModel):
    task: str
    mode: str
    model: Optional[str] = None
    reason: str
    preference_list: list[str] = Field(default_factory=list)
    override: Optional[str] = None
    installed: list[str] = Field(default_factory=list)
    provider: Optional[str] = None
    required_capabilities: list[str] = Field(default_factory=list)
    verified_capabilities: list[str] = Field(default_factory=list)
    selection_source: Optional[str] = None
    selected_at: Optional[str] = None


class ModeRequest(BaseModel):
    mode: str = Field(..., min_length=1, description="KI-Modus: speed|balance|quality")


class ActivateRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Modell-ID zur Aktivierung",
    )
    provider: Optional[str] = Field(
        default=None,
        description="Optional: lmstudio|ollama; erforderlich bei mehrdeutiger Modell-ID",
    )
    task: Optional[str] = Field(
        default=None,
        description="Optionaler einzelner Aufgaben-Schlüssel",
    )


class TestRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Modell-ID zum Testen",
    )
    provider: Optional[str] = Field(default=None, description="lmstudio|ollama")


class ModelSelectionReceiptSchema(BaseModel):
    """
    Nachvollziehbarkeits-Beleg der Modellauswahl.

    Audit 2026-08-05 (H-2/T3.10): Der Receipt existierte als vollstaendig
    strukturiertes, frozen dataclass und wurde ausschliesslich per
    ``logger.info`` ausgegeben — nie persistiert, nie in einer Response, nie in
    der UI. Die Frage "welches Modell hat DIESE Antwort geliefert, mit welchen
    Capabilities, aus welcher Quelle" war damit nur ueber backend.log
    beantwortbar. IRON RULE 10 verlangt genau diese Nachvollziehbarkeit.
    """

    provider: str
    model_id: str
    task: str
    mode: str
    required_capabilities: list[str] = Field(default_factory=list)
    verified_capabilities: list[str] = Field(default_factory=list)
    source: str
    reason: str
    selected_at: str


class ModelTestResponse(BaseModel):
    success: bool
    latency_ms: float = 0.0
    response: str = ""
    error: Optional[str] = None
    # Audit 2026-08-05 (H-2/T3.10): Der Smoke-Test baut den Receipt bereits,
    # loggte ihn aber nur. Jetzt Teil der Antwort.
    selection_receipt: Optional[ModelSelectionReceiptSchema] = None


def _enrich_model_entry(entry: ModelListEntry) -> ModelListEntry:
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

    # 5. Deutsche Beschreibung generieren. Capability- und Aktivstatus werden
    # ausschließlich aus dem zentralen providergebundenen Inventar übernommen.
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


def _load_ai_config() -> dict[str, Any]:
    try:
        from pb_studio.config_manager import ConfigManager

        ai = ConfigManager().get("ai") or {}
        if isinstance(ai, dict):
            return ai
    except Exception as exc:
        logger.debug("AI-Config nicht ladbar: %s", exc)
    return {}


def _resolve_inventory_matches(
    models: list[Any],
    requested_name: str,
    *,
    provider: str = "",
) -> list[Any]:
    """Resolve an exact model ID, or one unambiguous legacy alias."""
    from pb_studio.ai.model_registry import _name_matches

    scoped = [
        model
        for model in models
        if not provider or model.provider == provider
    ]
    normalized = requested_name.strip().casefold()
    exact = [
        model
        for model in scoped
        if model.name.strip().casefold() == normalized
    ]
    if exact:
        return exact
    return [
        model
        for model in scoped
        if _name_matches(requested_name, model.name)
    ]


# ----------------------------------------------------------------------
# GET /models/list
# ----------------------------------------------------------------------
@router.get("/list", response_model=ModelListResponse)
async def list_models(
    refresh: bool = Query(default=False, description="Inventar einmal invalidieren"),
) -> ModelListResponse:
    """Liefert den zentralen, providergetrennten Inventar-Snapshot."""
    from pb_studio.ai.model_inventory import get_model_inventory_service

    service = get_model_inventory_service()
    if refresh:
        service.invalidate()
    snapshot = await service.refresh()
    provider_by_name = {
        provider.provider: provider for provider in snapshot.providers
    }
    lmstudio_status = provider_by_name.get("lmstudio")
    ollama_status = provider_by_name.get("ollama")
    lmstudio_ok = bool(
        lmstudio_status and lmstudio_status.status != "offline"
    )
    ollama_ok = bool(ollama_status and ollama_status.status != "offline")

    task_labels = {
        "video_captioning": "Video-Analyse",
        "image_captioning": "Bild-Analyse",
        "chat": "Chat (Haupt)",
        "chat_general": "Chat",
        "chat_tool_use": "Tool-Ausführung",
        "brain_explanation": "KI-Director",
    }
    ai_cfg = _load_ai_config()
    model_overrides = ai_cfg.get("task_overrides") or {}
    provider_overrides = ai_cfg.get("task_provider_overrides") or {}
    active_by_identity: dict[tuple[str, str], list[str]] = {}
    usable_models = [
        model
        for model in snapshot.models
        if model.installed and model.usable
    ]
    for task, label in task_labels.items():
        configured_model = model_overrides.get(task)
        if not configured_model:
            continue
        configured_provider = str(
            provider_overrides.get(task) or ""
        ).strip().lower()
        matches = _resolve_inventory_matches(
            usable_models,
            str(configured_model),
            provider=configured_provider,
        )
        if len(matches) != 1:
            continue
        selected = matches[0]
        active_by_identity.setdefault(
            (selected.provider, selected.name),
            [],
        ).append(label)

    entries: list[ModelListEntry] = []
    for model in snapshot.models:
        if not model.installed:
            continue
        entry = ModelListEntry(
            name=model.name,
            size_bytes=model.size_bytes,
            modified_at=model.modified_at,
            family=model.family,
            parameter_size=model.parameter_size,
            quantization_level=model.quantization_level,
            provider=model.provider,
            installed=model.installed,
            loaded=model.loaded,
            downloadable=model.downloadable,
            usable=model.usable,
            capabilities=list(model.capabilities),
            inventory_sources=list(model.inventory_sources),
            verified_at=model.verified_at,
            status_reason=model.status_reason,
            vision="vision" in model.capabilities,
            # Audit 2026-08-05 (H-3/T3.9)
            context_length=getattr(model, "context_length", None),
            architecture=getattr(model, "architecture", None),
            publisher=getattr(model, "publisher", None),
            runtime_state=getattr(model, "runtime_state", None),
        )
        enriched = _enrich_model_entry(entry)
        enriched.vision = "vision" in model.capabilities
        active_tasks = active_by_identity.get(
            (model.provider, model.name),
            [],
        )
        enriched.active_tasks = active_tasks
        enriched.is_active = bool(active_tasks)
        entries.append(enriched)

    active_provider = next(
        (
            provider
            for provider in snapshot.providers
            if provider.status in {"ready", "degraded", "online_empty"}
        ),
        None,
    )
    display_provider = active_provider or lmstudio_status or ollama_status
    return ModelListResponse(
        ollama_available=ollama_ok,
        lmstudio_available=lmstudio_ok,
        base_url=(
            display_provider.base_url
            if display_provider
            else "configured endpoint"
        ),
        models=entries,
        providers=[
            ProviderStatusEntry(**provider.__dict__)
            for provider in snapshot.providers
        ],
        inventory_generation=snapshot.generation,
        verified_at=snapshot.verified_at,
        error=(
            None
            if lmstudio_ok or ollama_ok
            else "Kein LLM-Provider erreichbar (weder LM Studio noch Ollama)"
        ),
    )


# ----------------------------------------------------------------------
# GET /models/available
# ----------------------------------------------------------------------
@router.get("/available", response_model=AvailableModelsResponse)
async def list_available_models() -> AvailableModelsResponse:
    """Expose only live-verified downloadable records and general discovery."""
    from pb_studio.ai.model_inventory import get_model_inventory_service

    snapshot = await get_model_inventory_service().refresh()
    provider_by_name = {
        provider.provider: provider for provider in snapshot.providers
    }
    lmstudio_status = provider_by_name.get("lmstudio")
    ollama_status = provider_by_name.get("ollama")
    lmstudio_ok = bool(
        lmstudio_status and lmstudio_status.status != "offline"
    )
    ollama_ok = bool(ollama_status and ollama_status.status != "offline")
    active_provider = next(
        (
            provider
            for provider in snapshot.providers
            if provider.status in {"ready", "degraded", "online_empty"}
        ),
        None,
    )
    display_provider = active_provider or lmstudio_status or ollama_status
    active_base = (
        display_provider.base_url
        if display_provider
        else "configured endpoint"
    )

    entries = [
        AvailableModelEntry(
            name=model.name,
            description=model.status_reason,
            suggested_mode="verified",
            size_estimate_gb=round(
                model.size_bytes / (1024 * 1024 * 1024),
                2,
            ),
            vision="vision" in model.capabilities,
            installed=model.installed,
            provider=model.provider,
            loaded=model.loaded,
            downloadable=model.downloadable,
            usable=model.usable,
            capabilities=list(model.capabilities),
            verified_at=model.verified_at,
            status_reason=model.status_reason,
        )
        for model in snapshot.models
        if model.downloadable and not model.installed
    ]
    discover_actions = [
        DiscoverAction(
            provider=provider.provider,
            label=(
                "LM Studio Discover"
                if provider.provider == "lmstudio"
                else "Ollama Library"
            ),
            url=provider.discover_url,
            catalog_status=provider.catalog_status,
        )
        for provider in snapshot.providers
        if provider.discover_url
    ]
    return AvailableModelsResponse(
        ollama_available=ollama_ok,
        lmstudio_available=lmstudio_ok,
        base_url=active_base,
        available=entries,
        discover_actions=discover_actions,
        inventory_generation=snapshot.generation,
        verified_at=snapshot.verified_at,
    )


# ----------------------------------------------------------------------
# POST /models/pull — exakt verifizierter Ollama-Download
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
        timeout = httpx.Timeout(
            connect=5.0,
            read=60.0,
            write=30.0,
            pool=5.0,
        )
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
        ) as client:
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
        error = {
            "status": "error",
            "error": f"Ollama-Download fehlgeschlagen ({type(exc).__name__}).",
        }
        yield f"event: pull_progress\ndata: {json.dumps(error)}\n\n"


@router.post("/pull")
async def pull_model(
    request: PullRequest,
    owner_capability: Optional[str] = Header(
        default=None,
        alias=OWNER_CAPABILITY_HEADER,
    ),
):
    """Download exactly one live-verified Ollama registry candidate."""
    authorize_owner(owner_capability, operation="Modell-Download")
    from pb_studio.ai.llm_provider import get_base_url
    from pb_studio.ai.model_inventory import get_model_inventory_service

    service = get_model_inventory_service()
    snapshot = await service.refresh()
    ollama = next(
        (
            provider
            for provider in snapshot.providers
            if provider.provider == "ollama"
        ),
        None,
    )
    candidate = await service.verify_downloadable_candidate(
        "ollama",
        request.name,
    )
    if ollama and ollama.status != "offline" and candidate is not None:
        return StreamingResponse(
            ollama_pull_generator(candidate.name, get_base_url("ollama")),
            media_type="text/event-stream",
        )

    return JSONResponse(
        status_code=400,
        content={
            "error": "not_verified",
            "message": (
                "Die Ollama-Modell-ID ist nicht live als herunterladbar "
                "verifiziert oder Ollama ist offline."
            ),
            "requested_model": request.name,
            "hint": _LMSTUDIO_MANAGEMENT_HINT,
        },
    )


# ----------------------------------------------------------------------
# DELETE /models/{name} — exakt verifiziertes Ollama-Modell
# ----------------------------------------------------------------------
@router.delete("/{name:path}")
async def delete_model(
    name: str,
    owner_capability: Optional[str] = Header(
        default=None,
        alias=OWNER_CAPABILITY_HEADER,
    ),
) -> JSONResponse:
    """Delete only an exact, live-inventoried Ollama model ID."""
    authorize_owner(owner_capability, operation="Modell-Löschung")
    if not name.strip():
        raise HTTPException(status_code=400, detail="Leerer Modellname")
    if len(name) > 256:
        raise HTTPException(status_code=400, detail="Modellname ist zu lang")

    from pb_studio.ai.llm_provider import get_base_url
    from pb_studio.ai.model_inventory import get_model_inventory_service

    service = get_model_inventory_service()
    snapshot = await service.refresh()
    exact_matches = [
        model
        for model in snapshot.models
        if model.provider == "ollama"
        and model.installed
        and model.name.casefold() == name.strip().casefold()
    ]
    if len(exact_matches) == 1:
        import httpx
        selected = exact_matches[0]
        delete_url = get_base_url("ollama")
        if delete_url.endswith("/v1"):
            delete_url = delete_url[:-3]
        delete_url = f"{delete_url.rstrip('/')}/api/delete"
        
        logger.info(
            "Ollama native delete starting for exact model %s",
            selected.name,
        )
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=False,
            ) as http_client:
                response = await http_client.request(
                    "DELETE",
                    delete_url,
                    json={"name": selected.name},
                )
                if response.status_code == 200:
                    service.invalidate()
                    return JSONResponse(
                        content={
                            "status": "success",
                            "message": f"Model {selected.name} deleted.",
                        }
                    )
        except Exception as exc:
            logger.error(f"Ollama delete failed: {exc}")

    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "message": (
                "Keine exakt passende installierte Ollama-Modell-ID "
                "live verifiziert."
            ),
            "requested_model": name,
            "hint": _LMSTUDIO_MANAGEMENT_HINT,
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
    from pb_studio.ai.model_inventory import get_model_inventory_service
    from pb_studio.ai.model_registry import (
        ModelRegistry,
        ModelRegistryError,
        NoSuitableModelError,
    )

    ai_cfg = _load_ai_config()
    registry = ModelRegistry(ai_cfg)
    snapshot = await get_model_inventory_service().refresh()
    try:
        receipt = registry.select_receipt_for_task(snapshot, task, mode)
    except NoSuitableModelError as exc:
        return RecommendationResponse(
            task=task,
            mode=mode,
            model=None,
            reason=str(exc),
            preference_list=registry.get_preference_list(task, mode)
            if mode in {"speed", "balance", "quality"}
            else [],
            override=registry.get_user_override(task),
            installed=[
                model.name for model in snapshot.models if model.installed
            ],
        )
    except ModelRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return RecommendationResponse(
            task=task,
            mode=mode,
            model=receipt.model_id,
            provider=receipt.provider,
            reason=receipt.reason,
            preference_list=registry.get_preference_list(task, mode),
            override=registry.get_user_override(task),
            installed=[
                model.name for model in snapshot.models if model.installed
            ],
            required_capabilities=list(receipt.required_capabilities),
            verified_capabilities=list(receipt.verified_capabilities),
            selection_source=receipt.source,
            selected_at=receipt.selected_at,
        )
    except ModelRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("recommend_model fehlgeschlagen: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Modell-Empfehlung fehlgeschlagen; Details im Backend-Log.",
        ) from exc


@router.post("/activate")
async def activate_model(
    request: ActivateRequest,
    owner_capability: Optional[str] = Header(
        default=None,
        alias=OWNER_CAPABILITY_HEADER,
    ),
) -> JSONResponse:
    """Persistiert eine live verifizierte Provider-/Modellwahl pro Aufgabe."""
    authorize_owner(owner_capability, operation="Modell-Aktivierung")
    try:
        from pb_studio.ai.model_inventory import get_model_inventory_service
        from pb_studio.config_manager import ConfigManager

        requested_provider = str(request.provider or "").strip().lower()
        if requested_provider and requested_provider not in {"lmstudio", "ollama"}:
            raise HTTPException(
                status_code=400,
                detail="provider muss 'lmstudio' oder 'ollama' sein",
            )
        service = get_model_inventory_service()
        snapshot = await service.refresh()
        eligible = [
            model
            for model in snapshot.models
            if model.installed
            and model.usable
        ]
        matches = _resolve_inventory_matches(
            eligible,
            request.name,
            provider=requested_provider,
        )
        if not matches:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Modell {request.name!r} ist beim angeforderten Provider "
                    "nicht live als installiert und nutzbar verifiziert."
                ),
            )
        if len(matches) > 1:
            identities = ", ".join(
                sorted(
                    f"{model.provider}:{model.name}"
                    for model in matches
                )
            )
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Modell {request.name!r} ist nicht eindeutig "
                    f"({identities}); exakte Modell-ID und Provider wählen."
                ),
            )
        selected = matches[0]
        capabilities = set(selected.capabilities)
        task_capabilities = {
            "video_captioning": "vision",
            "image_captioning": "vision",
            "chat": "chat",
            "chat_general": "chat",
            "chat_tool_use": "chat",
            "brain_explanation": "chat",
        }
        requested_task = str(request.task or "").strip()
        if requested_task and requested_task not in task_capabilities:
            raise HTTPException(
                status_code=400,
                detail=f"Unbekannter Aufgaben-Schlüssel: {requested_task!r}",
            )
        target_tasks = (
            [requested_task]
            if requested_task
            else [
                task
                for task, capability in task_capabilities.items()
                if capability in capabilities
            ]
        )
        incompatible = [
            task
            for task in target_tasks
            if task_capabilities[task] not in capabilities
        ]
        if incompatible:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Modell {selected.name!r} hat nicht die erforderliche "
                    f"Capability für: {', '.join(incompatible)}"
                ),
            )
        if not target_tasks:
            raise HTTPException(
                status_code=400,
                detail="Modell hat keine von PB Studio nutzbare Capability.",
            )

        cfg_manager = ConfigManager()
        ai_cfg = cfg_manager.get("ai") or {}
        if not isinstance(ai_cfg, dict):
            ai_cfg = {}
        overrides = ai_cfg.get("task_overrides") or {}
        if not isinstance(overrides, dict):
            overrides = {}
        provider_overrides = ai_cfg.get("task_provider_overrides") or {}
        if not isinstance(provider_overrides, dict):
            provider_overrides = {}
        for task in target_tasks:
            overrides[task] = selected.name
            provider_overrides[task] = selected.provider
        ai_cfg["task_overrides"] = overrides
        ai_cfg["task_provider_overrides"] = provider_overrides
        if "vision" in capabilities:
            ai_cfg["vision_model"] = selected.name
        cfg_manager.set("ai", ai_cfg)
        persisted = json.loads(
            cfg_manager.config_file.read_text(encoding="utf-8")
        ).get("ai") or {}
        persisted_models = persisted.get("task_overrides") or {}
        persisted_providers = persisted.get("task_provider_overrides") or {}
        if any(
            persisted_models.get(task) != selected.name
            or persisted_providers.get(task) != selected.provider
            for task in target_tasks
        ):
            raise RuntimeError(
                "Provider-/Modellwahl konnte nicht dauerhaft verifiziert werden."
            )
        service.invalidate()
        await service.refresh()
        logger.info(
            "Modell '%s' von %s fuer Tasks aktiviert: %s",
            selected.name,
            selected.provider,
            target_tasks,
        )
        return JSONResponse(
            status_code=200,
            content={
                "message": (
                    f"Modell '{selected.name}' von {selected.provider} "
                    "erfolgreich aktiviert."
                ),
                "provider": selected.provider,
                "model": selected.name,
                "vision_enabled": "vision" in capabilities,
                "activated_tasks": target_tasks,
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Aktivierung von Modell '%s' fehlgeschlagen: %s", request.name, exc)
        raise HTTPException(
            status_code=500,
            detail="Modell-Aktivierung fehlgeschlagen; Details im Backend-Log.",
        ) from exc


@router.post("/mode")
async def update_ki_mode(
    request: ModeRequest,
    owner_capability: Optional[str] = Header(
        default=None,
        alias=OWNER_CAPABILITY_HEADER,
    ),
) -> JSONResponse:
    """Aktualisiert den standardmaessigen KI-Modus (speed|balance|quality) in der Konfiguration."""
    authorize_owner(owner_capability, operation="KI-Modus-Aktualisierung")
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
        raise HTTPException(
            status_code=500,
            detail="KI-Modus konnte nicht gespeichert werden; Details im Backend-Log.",
        ) from exc


@router.post("/test", response_model=ModelTestResponse)
async def test_model(
    request: TestRequest,
    owner_capability: Optional[str] = Header(
        default=None,
        alias=OWNER_CAPABILITY_HEADER,
    ),
) -> ModelTestResponse:
    """Fuehrt einen minimalen Inferenz-Smoke-Test (max_tokens=1) auf der AMD-GPU durch, um die Funktion zu pruefen."""
    authorize_owner(owner_capability, operation="Modell-Smoke-Test")
    import time
    from datetime import datetime, timezone

    from pb_studio.ai.llm_provider import get_llm_client
    from pb_studio.ai.model_inventory import get_model_inventory_service
    from pb_studio.ai.model_registry import ModelSelectionReceipt
    provider = str(request.provider or "").strip().lower()
    snapshot = await get_model_inventory_service().refresh()
    eligible = [
        model
        for model in snapshot.models
        if model.installed
        and model.usable
        and "chat" in model.capabilities
    ]
    matches = _resolve_inventory_matches(
        eligible,
        request.name,
        provider=provider,
    )
    if len(matches) != 1:
        return ModelTestResponse(
            success=False,
            error=(
                "Modell/Provider ist nicht eindeutig als nutzbares "
                "Chat-Modell verifiziert."
            ),
        )
    selected = matches[0]
    receipt = ModelSelectionReceipt(
        provider=selected.provider,
        model_id=selected.name,
        task="model_smoke_test",
        mode="diagnostic",
        required_capabilities=("chat",),
        verified_capabilities=tuple(sorted(selected.capabilities)),
        source="explicit_smoke_test",
        reason="Explizit angeforderter, live verifizierter Modell-Smoke-Test.",
        selected_at=datetime.now(timezone.utc).isoformat(),
    )
    logger.info("ModelSelectionReceipt: %s", receipt.to_dict())
    # Audit 2026-08-05 (H-2/T3.10): Receipt in die Antwort heben, damit die
    # Auswahl nachvollziehbar wird statt nur im Log zu landen.
    receipt_schema = ModelSelectionReceiptSchema(
        provider=receipt.provider,
        model_id=receipt.model_id,
        task=receipt.task,
        mode=receipt.mode,
        required_capabilities=list(receipt.required_capabilities),
        verified_capabilities=list(receipt.verified_capabilities),
        source=receipt.source,
        reason=receipt.reason,
        selected_at=receipt.selected_at,
    )
    client = get_llm_client(provider=selected.provider)

    start_time = time.perf_counter()
    try:
        async with client as c:
            # Minimaler Prompt, nur 1 Token generieren um VRAM und Zeit zu sparen
            result = await c.generate(
                model=selected.name,
                prompt="Say 'ok'",
                options={"max_tokens": 1, "temperature": 0.0}
            )
            response_text = result.get("response") or ""

        latency = (time.perf_counter() - start_time) * 1000.0
        return ModelTestResponse(
            success=True,
            latency_ms=round(latency, 1),
            response=response_text.strip() or "OK",
            selection_receipt=receipt_schema,
        )
    except Exception as exc:
        latency = (time.perf_counter() - start_time) * 1000.0
        logger.warning("GPU-Smoke-Test fuer Modell '%s' fehlgeschlagen: %s", request.name, exc)
        return ModelTestResponse(
            success=False,
            latency_ms=round(latency, 1),
            error=f"Modell-Smoke-Test fehlgeschlagen ({type(exc).__name__}).",
            # Auch im Fehlerfall: gerade dann ist interessant, WELCHES Modell
            # mit welchen Capabilities ausgewaehlt wurde.
            selection_receipt=receipt_schema,
        )


__all__ = ["router"]
