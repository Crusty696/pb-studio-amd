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

import asyncio
import logging
from typing import Optional

from .lmstudio_client import LMStudioClient, LMStudioConnectionError

logger = logging.getLogger(__name__)

DEFAULT_LMSTUDIO_URL = "http://127.0.0.1:1234/v1"
DEFAULT_OLLAMA_URL = "http://localhost:11434/v1"

VALID_PROVIDERS = frozenset({"lmstudio", "ollama", "auto"})

# Read-Timeout fuer echte Chat-Generierung. Reasoning-Modelle (deepseek-r1,
# phi-4-reasoning) "denken" viele Sekunden bevor Tokens kommen — ein kurzer
# Probe-Timeout (5s) wuerde jede Generierung mit ReadTimeout abbrechen.
DEFAULT_GENERATION_TIMEOUT = 180.0


def _load_config() -> dict:
    """Liefert die ai-Sektion aus config.json, leeres dict bei Fehler."""
    try:
        from pb_studio.config_manager import ConfigManager

        config = ConfigManager().get("ai") or {}
        return config if isinstance(config, dict) else {}
    except Exception as exc:
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
    configured_provider = (
        str(provider or get_provider()).strip().lower()
    )
    resolved_provider = (
        configured_provider
        if configured_provider in {"lmstudio", "ollama"}
        else "lmstudio"
    )
    base_url = get_base_url(resolved_provider)
    return LMStudioClient(
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        provider=resolved_provider,
        **client_kwargs,
    )


async def get_alive_client(
    timeout_seconds: float = 5.0,
    *,
    client_timeout_seconds: float = DEFAULT_GENERATION_TIMEOUT,
    required_capability: str = "chat",
) -> Optional[LMStudioClient]:
    """Auto-Mode mit Fallback: LM Studio first, Ollama wenn LM Studio down.

    Liefert einen frischen Client mit Generierungs-Timeout
    (``client_timeout_seconds``) oder None wenn beide Provider unerreichbar
    sind. Caller ist verantwortlich fuer ``async with`` Eintritt und Schliessen.

    Die Erreichbarkeits-Pruefung laeuft auf einem separaten Probe-Client mit
    kurzem ``timeout_seconds`` — der zurueckgegebene Client bekommt aber den
    laengeren Generierungs-Timeout, sonst wuerde jede echte Chat-Generierung
    mit ReadTimeout abbrechen (Reasoning-Modelle denken laenger als 5s).
    """
    provider = get_provider()
    candidates: list[str]
    if provider == "auto":
        candidates = ["lmstudio", "ollama"]
    else:
        candidates = [provider]

    async def _probe(candidate: str) -> tuple[str, bool]:
        probe = get_llm_client(
            provider=candidate,
            timeout_seconds=timeout_seconds,
            retry_attempts=1,
        )
        try:
            suitable = await asyncio.wait_for(
                probe.supports_capability(required_capability),
                timeout=timeout_seconds,
            )
            return candidate, suitable
        except (LMStudioConnectionError, asyncio.TimeoutError):
            logger.debug(
                "Provider %s nicht erreichbar oder Probe-Deadline erreicht",
                candidate,
            )
            return candidate, False
        except Exception as exc:  # noqa: BLE001 - Probe darf Fallback nicht abbrechen
            logger.debug("Provider-Probe %s fehlgeschlagen: %s", candidate, exc)
            return candidate, False
        finally:
            await probe.aclose()

    probe_results = dict(await asyncio.gather(*(_probe(name) for name in candidates)))
    for candidate in candidates:
        if probe_results.get(candidate, False):
            logger.info(
                "LLM-Provider aktiv: %s (Capability: %s)",
                candidate,
                required_capability,
            )
            # Frischer Client mit Generierungs-Timeout (Probe war nur kurz).
            return get_llm_client(provider=candidate, timeout_seconds=client_timeout_seconds)
    logger.warning(
        "Kein LLM-Provider mit Capability %s (geprueft: %s)",
        required_capability,
        ", ".join(candidates),
    )
    return None
