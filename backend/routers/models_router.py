"""Models Router — Ollama-Modell-Management fuer PB Studio.

Endpoints:
  GET    /models/list             — installierte Ollama-Modelle
  GET    /models/available        — kuratierte Vision-Modelle (+ installed-Flag)
  POST   /models/pull             — Pull mit SSE-Stream (Progress-Events)
  DELETE /models/{name}           — Modell loeschen
  GET    /models/recommendations  — beste Modell-Empfehlung fuer Task/Mode

Ollama-Verbindung defaultet auf ``http://localhost:11434``. Overrides via
``PBSTUDIO_OLLAMA_URL`` Environment-Variable.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["Models (Ollama)"])


# ----------------------------------------------------------------------
# Curated list of Vision-capable models PB Studio understands.
# Mirrors the defaults in pb_studio.ai.model_registry but exposes a
# human-friendly description + suggested mode label.
# ----------------------------------------------------------------------
CURATED_VISION_MODELS: list[dict[str, Any]] = [
    {
        "name": "moondream:latest",
        "description": "Klein & sehr schnell (~2GB). Englisch only, basale Tags.",
        "suggested_mode": "speed",
        "size_estimate_gb": 1.8,
        "vision": True,
    },
    {
        "name": "minicpm-v:8b-q4",
        "description": "Quantisiertes Mini-CPM Vision-Modell. Schnell, mehrsprachig.",
        "suggested_mode": "speed",
        "size_estimate_gb": 5.5,
        "vision": True,
    },
    {
        "name": "gemma4:latest",
        "description": "Google Gemma 4 (Vision). Default fuer Balance-Mode.",
        "suggested_mode": "balance",
        "size_estimate_gb": 9.6,
        "vision": True,
    },
    {
        "name": "llava:13b",
        "description": "Llava 13B Vision-Modell. Solider Allrounder.",
        "suggested_mode": "balance",
        "size_estimate_gb": 8.0,
        "vision": True,
    },
    {
        "name": "llava:34b",
        "description": "Llava 34B Vision. Hohe Qualitaet, ~20GB VRAM noetig.",
        "suggested_mode": "quality",
        "size_estimate_gb": 20.0,
        "vision": True,
    },
    {
        "name": "qwen2-vl:7b",
        "description": "Qwen2-VL 7B. Sehr stark bei Detailbeschreibung.",
        "suggested_mode": "quality",
        "size_estimate_gb": 8.5,
        "vision": True,
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


class ModelListResponse(BaseModel):
    ollama_available: bool
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
    base_url: str
    available: list[AvailableModelEntry] = Field(default_factory=list)


class PullRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Ollama-Modellname (z.B. gemma4:latest)")


class RecommendationResponse(BaseModel):
    task: str
    mode: str
    model: Optional[str] = None
    reason: str
    preference_list: list[str] = Field(default_factory=list)
    override: Optional[str] = None
    installed: list[str] = Field(default_factory=list)


# ----------------------------------------------------------------------
# Helper: Ollama-Client + AI-Config-Reader
# ----------------------------------------------------------------------
def _get_base_url() -> str:
    return os.environ.get("PBSTUDIO_OLLAMA_URL", "http://localhost:11434")


def _make_client():
    """Erzeugt einen frischen ``OllamaClient`` mit Default-Settings."""
    from pb_studio.ai.ollama_client import OllamaClient

    return OllamaClient(base_url=_get_base_url())


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
    """Liefert alle installierten Ollama-Modelle."""
    from pb_studio.ai.ollama_client import OllamaError

    base_url = _get_base_url()
    try:
        async with _make_client() as client:
            models = await client.list_models()
        entries = [ModelListEntry(**m.to_dict()) for m in models]
        return ModelListResponse(
            ollama_available=True,
            base_url=base_url,
            models=entries,
        )
    except OllamaError as exc:
        logger.warning("Ollama list_models fehlgeschlagen: %s", exc)
        return ModelListResponse(
            ollama_available=False,
            base_url=base_url,
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
    from pb_studio.ai.ollama_client import OllamaError

    base_url = _get_base_url()
    installed_names: list[str] = []
    ollama_ok = True
    try:
        async with _make_client() as client:
            models = await client.list_models()
        installed_names = [m.name for m in models]
    except OllamaError as exc:
        logger.warning("Ollama list_models fehlgeschlagen (/available): %s", exc)
        ollama_ok = False

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
        base_url=base_url,
        available=entries,
    )


# ----------------------------------------------------------------------
# POST /models/pull  — SSE Stream
# ----------------------------------------------------------------------
@router.post("/pull")
async def pull_model(request: PullRequest) -> StreamingResponse:
    """Streamt Progress-Events bis der Pull abgeschlossen ist."""

    async def _generator():
        from pb_studio.ai.ollama_client import OllamaError

        try:
            async with _make_client() as client:
                async for event in client.pull_model(request.name):
                    payload = json.dumps(event, ensure_ascii=False)
                    yield f"event: pull_progress\ndata: {payload}\n\n"
                    if event.get("status") in {"success", "error"}:
                        break
        except OllamaError as exc:
            err_payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
            yield f"event: pull_error\ndata: {err_payload}\n\n"

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ----------------------------------------------------------------------
# DELETE /models/{name}
# ----------------------------------------------------------------------
@router.delete("/{name:path}")
async def delete_model(name: str) -> dict[str, Any]:
    """Loescht ein installiertes Modell."""
    from pb_studio.ai.ollama_client import OllamaError

    if not name.strip():
        raise HTTPException(status_code=400, detail="Leerer Modellname")
    try:
        async with _make_client() as client:
            deleted = await client.delete_model(name)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Modell {name!r} nicht gefunden")
        return {"deleted": True, "name": name}
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=f"Ollama-Fehler: {exc}") from exc


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
    from pb_studio.ai.ollama_client import OllamaError

    ai_cfg = _load_ai_config()
    try:
        async with _make_client() as client:
            registry = ModelRegistry(ai_cfg, client=client)
            try:
                await registry.refresh()
            except OllamaError as exc:
                return RecommendationResponse(
                    task=task,
                    mode=mode,
                    model=None,
                    reason=f"Ollama nicht erreichbar: {exc}",
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


__all__ = ["router"]
