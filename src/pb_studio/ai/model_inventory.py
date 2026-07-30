"""Truthful, provider-aware inventory for local AI models."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx

from .llm_provider import get_base_url, get_llm_client
from .lmstudio_client import LMStudioModelInfo
from .model_registry import _name_matches

logger = logging.getLogger(__name__)

PROVIDER_NAMES = ("lmstudio", "ollama")
PROVIDER_STATES = frozenset({"offline", "online_empty", "ready", "degraded"})
MODEL_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*"
    r"(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?"
    r"(?::[A-Za-z0-9][A-Za-z0-9._-]*)?$"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_base_url(value: str) -> str:
    """Return an endpoint label without credentials, query, or fragment."""
    try:
        parsed = urlsplit(str(value))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return "configured endpoint"
        hostname = parsed.hostname
        if ":" in hostname:
            hostname = f"[{hostname}]"
        netloc = hostname
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    except ValueError:
        return "configured endpoint"


def _public_probe_error(context: str, exc: Exception) -> str:
    """Keep UI diagnostics useful without reflecting provider-controlled text."""
    return f"{context} fehlgeschlagen ({type(exc).__name__})."


def _unique_matching_name(
    requested: str,
    candidates: Iterable[str],
) -> Optional[str]:
    """Resolve an exact ID, or one unambiguous legacy alias, fail closed."""
    candidate_list = [str(candidate) for candidate in candidates]
    normalized = str(requested).strip().casefold()
    exact = [
        candidate
        for candidate in candidate_list
        if candidate.strip().casefold() == normalized
    ]
    if len(exact) == 1:
        return exact[0]
    if exact:
        return None
    aliases = [
        candidate
        for candidate in candidate_list
        if _name_matches(requested, candidate)
    ]
    return aliases[0] if len(aliases) == 1 else None


@dataclass(frozen=True)
class ProviderInventory:
    provider: str
    status: str
    base_url: str
    verified_at: str
    status_reason: str = ""
    catalog_status: str = "not_verified"
    discover_url: Optional[str] = None


@dataclass(frozen=True)
class ModelInventoryEntry:
    provider: str
    name: str
    installed: bool
    loaded: bool
    downloadable: bool
    usable: bool
    capabilities: tuple[str, ...]
    inventory_sources: tuple[str, ...]
    verified_at: str
    status_reason: str
    size_bytes: int = 0
    modified_at: str = ""
    family: Optional[str] = None
    parameter_size: Optional[str] = None
    quantization_level: Optional[str] = None


@dataclass(frozen=True)
class ModelInventorySnapshot:
    providers: tuple[ProviderInventory, ...] = field(default_factory=tuple)
    models: tuple[ModelInventoryEntry, ...] = field(default_factory=tuple)
    verified_at: str = ""
    generation: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "providers": [asdict(provider) for provider in self.providers],
            "models": [asdict(model) for model in self.models],
            "verified_at": self.verified_at,
            "generation": self.generation,
        }


@dataclass(frozen=True)
class _LoadedProbe:
    names: frozenset[str]
    error: Optional[str] = None


class ModelInventoryService:
    """Collect installed and loaded state without private provider indexes."""

    def __init__(
        self,
        *,
        probe_timeout_seconds: float = 3.0,
        cache_ttl_seconds: float = 5.0,
    ) -> None:
        self._probe_timeout_seconds = max(0.5, float(probe_timeout_seconds))
        self._cache_ttl_seconds = max(0.0, float(cache_ttl_seconds))
        self._snapshot = ModelInventorySnapshot()
        self._generation = 0
        self._invalidated = True
        self._last_refresh_monotonic = 0.0
        self._refresh_lock = asyncio.Lock()

    @property
    def snapshot(self) -> ModelInventorySnapshot:
        return self._snapshot

    def invalidate(self) -> None:
        """Make the next caller perform one provider refresh."""
        self._invalidated = True

    def _cache_is_fresh(self) -> bool:
        return (
            not self._invalidated
            and bool(self._snapshot.verified_at)
            and time.monotonic() - self._last_refresh_monotonic
            <= self._cache_ttl_seconds
        )

    async def refresh(
        self,
        *,
        force: bool = False,
        downloadable_candidates: Optional[Mapping[str, Iterable[str]]] = None,
    ) -> ModelInventorySnapshot:
        """Refresh both providers once and publish one atomic snapshot.

        Concurrent view requests are coalesced by the lock and the second
        freshness check, so one UI refresh cannot create a provider storm.
        """
        if not force and self._cache_is_fresh():
            return self._snapshot
        async with self._refresh_lock:
            if not force and self._cache_is_fresh():
                return self._snapshot
            provider_results = await asyncio.gather(
                *(self._inventory_provider(name) for name in PROVIDER_NAMES)
            )
            providers: list[ProviderInventory] = []
            models: list[ModelInventoryEntry] = []
            for provider, provider_models in provider_results:
                providers.append(provider)
                models.extend(provider_models)

            candidates = downloadable_candidates or {}
            installed_keys = {
                (model.provider, model.name.lower())
                for model in models
                if model.installed
            }
            verification_jobs = [
                self._verify_downloadable(provider, name)
                for provider, names in candidates.items()
                if provider in PROVIDER_NAMES
                for name in names
                if (provider, str(name).lower()) not in installed_keys
            ]
            if verification_jobs:
                for candidate in await asyncio.gather(*verification_jobs):
                    if candidate is not None:
                        models.append(candidate)

            self._generation += 1
            verified_at = _utc_now()
            self._snapshot = ModelInventorySnapshot(
                providers=tuple(sorted(providers, key=lambda item: item.provider)),
                models=tuple(
                    sorted(models, key=lambda item: (item.provider, item.name.lower()))
                ),
                verified_at=verified_at,
                generation=self._generation,
            )
            self._invalidated = False
            self._last_refresh_monotonic = time.monotonic()
            return self._snapshot

    async def _inventory_provider(
        self,
        provider: str,
    ) -> tuple[ProviderInventory, list[ModelInventoryEntry]]:
        verified_at = _utc_now()
        base_url = get_base_url(provider)
        client = get_llm_client(
            provider=provider,
            timeout_seconds=self._probe_timeout_seconds,
            retry_attempts=1,
        )
        try:
            installed = await asyncio.wait_for(
                client.list_models(),
                timeout=self._probe_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - recorded as truthful offline state
            logger.debug(
                "Provider inventory probe failed for %s: %s",
                provider,
                exc,
            )
            await client.aclose()
            return (
                ProviderInventory(
                    provider=provider,
                    status="offline",
                    base_url=_public_base_url(base_url),
                    verified_at=verified_at,
                    status_reason=_public_probe_error(
                        "Provider-Inventarprobe",
                        exc,
                    ),
                    catalog_status=(
                        "discover_only" if provider == "lmstudio" else "not_verified"
                    ),
                    discover_url=(
                        "https://lmstudio.ai/models"
                        if provider == "lmstudio"
                        else "https://ollama.com/library"
                    ),
                ),
                [],
            )

        try:
            capabilities = await asyncio.wait_for(
                client.get_model_capabilities(),
                timeout=self._probe_timeout_seconds,
            )
            capability_error: Optional[str] = None
        except Exception as exc:  # noqa: BLE001 - degraded is part of the contract
            capabilities = {}
            logger.debug(
                "Provider capability probe failed for %s: %s",
                provider,
                exc,
            )
            capability_error = _public_probe_error(
                "Capability-Prüfung",
                exc,
            )
        finally:
            await client.aclose()

        loaded_probe = await (
            self._loaded_lmstudio(base_url)
            if provider == "lmstudio"
            else self._loaded_ollama(base_url)
        )
        unmatched_capabilities = [
            model.name
            for model in installed
            if _unique_matching_name(model.name, capabilities) is None
        ]
        auxiliary_errors = [
            error for error in (capability_error, loaded_probe.error) if error
        ]
        if installed and unmatched_capabilities:
            auxiliary_errors.append(
                "Keine verifizierte Capability für: "
                + ", ".join(unmatched_capabilities)
            )
        if not installed:
            status = "online_empty"
            reason = "Provider erreichbar, aber keine installierten Modelle gemeldet."
        elif auxiliary_errors:
            status = "degraded"
            reason = "; ".join(auxiliary_errors)
        else:
            status = "ready"
            reason = "Installierte, geladene und Capability-Zustände verifiziert."

        entries = [
            self._installed_entry(
                provider=provider,
                model=model,
                loaded_names=loaded_probe.names,
                capabilities_by_name=capabilities,
                verified_at=verified_at,
                provider_status=status,
                capability_error=capability_error,
            )
            for model in installed
        ]
        return (
            ProviderInventory(
                provider=provider,
                status=status,
                base_url=_public_base_url(base_url),
                verified_at=verified_at,
                status_reason=reason,
                catalog_status=(
                    "discover_only" if provider == "lmstudio" else "not_verified"
                ),
                discover_url=(
                    "https://lmstudio.ai/models"
                    if provider == "lmstudio"
                    else "https://ollama.com/library"
                ),
            ),
            entries,
        )

    @staticmethod
    def _installed_entry(
        *,
        provider: str,
        model: LMStudioModelInfo,
        loaded_names: frozenset[str],
        capabilities_by_name: Mapping[str, frozenset[str]],
        verified_at: str,
        provider_status: str,
        capability_error: Optional[str],
    ) -> ModelInventoryEntry:
        capability_name = _unique_matching_name(
            model.name,
            capabilities_by_name,
        )
        capabilities = (
            frozenset(capabilities_by_name[capability_name])
            if capability_name is not None
            else frozenset()
        )
        loaded = _unique_matching_name(model.name, loaded_names) is not None
        usable = provider_status in {"ready", "degraded"} and bool(capabilities)
        if capability_error:
            reason = f"Installiert; Capability-Prüfung fehlgeschlagen: {capability_error}"
        elif not capabilities:
            reason = "Installiert, aber keine verifizierte Capability gemeldet."
        elif loaded:
            reason = "Installiert, geladen und nutzbar."
        else:
            reason = "Installiert, nicht geladen und per JIT beziehungsweise Provider ladbar."
        return ModelInventoryEntry(
            provider=provider,
            name=model.name,
            installed=True,
            loaded=loaded,
            downloadable=False,
            usable=usable,
            capabilities=tuple(sorted(capabilities)),
            inventory_sources=(
                "/v1/models",
                "/api/v0/models",
                "/api/v0/models state",
            )
            if provider == "lmstudio"
            else ("/api/tags", "/api/ps"),
            verified_at=verified_at,
            status_reason=reason,
            size_bytes=model.size_bytes,
            modified_at=model.modified_at,
            family=model.family,
            parameter_size=model.parameter_size,
            quantization_level=model.quantization_level,
        )

    async def _loaded_lmstudio(self, base_url: str) -> _LoadedProbe:
        """Read loaded state from LM Studio's native HTTP inventory."""
        root = base_url.rstrip("/")
        if root.endswith("/v1"):
            root = root[:-3]
        try:
            async with httpx.AsyncClient(
                timeout=self._probe_timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = await client.get(f"{root}/api/v0/models")
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # noqa: BLE001 - captured as degraded state
            logger.debug("LM Studio loaded-state probe failed: %s", exc)
            return _LoadedProbe(
                frozenset(),
                _public_probe_error("LM Studio Loaded-State", exc),
            )
        names = {
            str(raw.get("id") or raw.get("name") or "").strip()
            for raw in (payload.get("data") or [])
            if isinstance(raw, dict)
            and str(raw.get("state") or "").strip().casefold() == "loaded"
        }
        return _LoadedProbe(frozenset(name for name in names if name))

    async def _loaded_ollama(self, base_url: str) -> _LoadedProbe:
        root = base_url.rstrip("/")
        if root.endswith("/v1"):
            root = root[:-3]
        try:
            async with httpx.AsyncClient(
                timeout=self._probe_timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = await client.get(f"{root}/api/ps")
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # noqa: BLE001 - captured as degraded state
            logger.debug("Ollama loaded-state probe failed: %s", exc)
            return _LoadedProbe(
                frozenset(),
                _public_probe_error("Ollama Loaded-State", exc),
            )
        names = {
            str(raw.get("name") or raw.get("model") or "").strip()
            for raw in (payload.get("models") or [])
            if isinstance(raw, dict)
        }
        return _LoadedProbe(frozenset(name for name in names if name))

    async def _verify_downloadable(
        self,
        provider: str,
        model_name: str,
    ) -> Optional[ModelInventoryEntry]:
        name = str(model_name).strip()
        if provider != "ollama" or not MODEL_ID_PATTERN.fullmatch(name):
            return None
        path_part, _, tag = name.partition(":")
        namespace, separator, repository = path_part.partition("/")
        if not separator:
            repository = namespace
            namespace = "library"
        if namespace in {".", ".."} or repository in {".", ".."}:
            return None
        manifest_tag = tag or "latest"
        url = (
            "https://registry.ollama.ai/v2/"
            f"{namespace}/{repository}/manifests/{manifest_tag}"
        )
        try:
            async with httpx.AsyncClient(
                timeout=self._probe_timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = await client.head(
                    url,
                    headers={
                        "Accept": (
                            "application/vnd.docker.distribution.manifest.v2+json,"
                            "application/vnd.oci.image.manifest.v1+json"
                        )
                    },
                )
            if response.status_code != 200:
                return None
        except httpx.HTTPError:
            return None
        verified_at = _utc_now()
        return ModelInventoryEntry(
            provider=provider,
            name=name,
            installed=False,
            loaded=False,
            downloadable=True,
            usable=False,
            capabilities=(),
            inventory_sources=("registry.ollama.ai manifest",),
            verified_at=verified_at,
            status_reason="Provider-Manifest live verifiziert; nicht installiert.",
        )

    async def verify_downloadable_candidate(
        self,
        provider: str,
        model_name: str,
    ) -> Optional[ModelInventoryEntry]:
        """Verify one provider/model candidate without relying on cache state."""
        return await self._verify_downloadable(provider, model_name)


_inventory_service: Optional[ModelInventoryService] = None


def get_model_inventory_service() -> ModelInventoryService:
    global _inventory_service
    if _inventory_service is None:
        _inventory_service = ModelInventoryService()
    return _inventory_service


__all__ = [
    "ModelInventoryEntry",
    "ModelInventoryService",
    "ModelInventorySnapshot",
    "ProviderInventory",
    "get_model_inventory_service",
]
