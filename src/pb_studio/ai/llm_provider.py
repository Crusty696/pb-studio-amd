"""LLM-Provider-Factory fuer Hybrid Ollama + LM Studio Setup.

Beide Backends sprechen OpenAI-kompatible APIs:
- LM Studio: http://localhost:1234/v1  (Default)
- Ollama 0.5+: http://localhost:11434/v1

Der gemeinsame Client ist ``LMStudioClient`` — er funktioniert via base_url
gegen beide Backends. Die Factory waehlt anhand der Config-Direktive
``config.ai.provider`` zwischen den base_urls und unterstuetzt einen
"auto"-Modus mit Fallback (LM Studio first, Ollama bei Connection-Error).

Usage::

    from pb_studio.ai.llm_provider import get_llm_client

    async with get_llm_client() as client:
        models = await client.list_models()

Config-Keys (config.json::ai):
- provider: "lmstudio" | "ollama" | "auto"  (default: "auto")
- lmstudio_base_url: str  (default: http://localhost:1234/v1)
- ollama_base_url: str  (default: http://localhost:11434/v1)

User-Direktive 2026-05-19: "ollama und lmStudio nutzen koennen" — private app,
hybrid Modus default-on.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from .lmstudio_client import LMStudioClient, LMStudioConnectionError

logger = logging.getLogger(__name__)

DEFAULT_LMSTUDIO_URL = "http://localhost:1234/v1"
DEFAULT_OLLAMA_URL = "http://localhost:11434/v1"

VALID_PROVIDERS = frozenset({"lmstudio", "ollama", "auto"})


def _load_config() -> dict:
    """Liefert die ai-Sektion aus config.json, leeres dict bei Fehler."""
    cfg_path = Path(__file__).resolve().parents[3] / "config.json"
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8")).get("ai", {})
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("config.json nicht lesbar (%s) — Defaults werden verwendet", exc)
        return {}


def get_provider() -> str:
    """Liefert konfigurierten Provider — auto/lmstudio/ollama."""
    p = _load_config().get("provider", "auto").lower().strip()
    return p if p in VALID_PROVIDERS else "auto"


def get_base_url(provider: Optional[str] = None) -> str:
    """Liefert base_url fuer den gewaehlten Provider (oder Config-Default)."""
    cfg = _load_config()
    chosen = provider or cfg.get("provider", "auto").lower().strip()
    if chosen not in VALID_PROVIDERS:
        chosen = "auto"
    if chosen == "ollama":
        return cfg.get("ollama_base_url", DEFAULT_OLLAMA_URL)
    if chosen == "lmstudio":
        return cfg.get("lmstudio_base_url", DEFAULT_LMSTUDIO_URL)
    # auto → LM Studio bevorzugt, Fallback in get_llm_client
    return cfg.get("lmstudio_base_url", DEFAULT_LMSTUDIO_URL)


def get_llm_client(
    *,
    provider: Optional[str] = None,
    timeout_seconds: float = 60.0,
    **client_kwargs,
) -> LMStudioClient:
    """Erstellt LMStudioClient gegen den gewaehlten Provider.

    Bei provider="auto" wird LM Studio default-base_url genutzt — fuer Fallback
    auf Ollama sollten Caller ``is_alive()`` pruefen und bei False
    ``get_llm_client(provider="ollama")`` erneut aufrufen.

    Args:
        provider: Override fuer Config — "lmstudio" | "ollama" | "auto".
        timeout_seconds: HTTP-Timeout fuer Requests.
        **client_kwargs: Zusaetzliche Args fuer LMStudioClient (z.B. max_retries).
    """
    base_url = get_base_url(provider)
    return LMStudioClient(
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        **client_kwargs,
    )


async def get_alive_client(timeout_seconds: float = 5.0) -> Optional[LMStudioClient]:
    """Auto-Mode mit Fallback: LM Studio first, Ollama wenn LM Studio down.

    Liefert eingesteckten Client (async-context geoeffnet noch nicht) oder
    None wenn beide Provider unerreichbar sind. Caller ist verantwortlich
    fuer ``async with`` Eintritt und Schliessen.

    Pruefung erfolgt via ``is_alive()`` (kurzer Timeout).
    """
    provider = get_provider()
    candidates: list[str]
    if provider == "auto":
        candidates = ["lmstudio", "ollama"]
    else:
        candidates = [provider]

    for candidate in candidates:
        client = get_llm_client(provider=candidate, timeout_seconds=timeout_seconds)
        try:
            if await client.is_alive():
                logger.info("LLM-Provider aktiv: %s (%s)", candidate, client.base_url)
                return client
        except LMStudioConnectionError:
            logger.debug("Provider %s nicht erreichbar — naechster Kandidat", candidate)
        finally:
            # bei Mismatch close, sonst returnen wir den lebenden client
            if client is not None and not await client.is_alive():
                await client.aclose()
    logger.warning("Kein LLM-Provider erreichbar (geprueft: %s)", ", ".join(candidates))
    return None
