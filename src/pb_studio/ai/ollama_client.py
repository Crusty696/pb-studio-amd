"""Ollama HTTP-Client fuer PB Studio (AMD Premium).

Reine HTTP-Schnittstelle auf den lokalen Ollama-Daemon (Standard:
``http://localhost:11434``). Wir benutzen bewusst ``httpx`` direkt und
verzichten auf das ``ollama`` Python-Paket, um Abhaengigkeits-Konflikte
mit dem PyTorch-/DirectML-Stack zu vermeiden.

Unterstuetzte Endpoints:
    * POST   /api/chat       — Chat-Completion inkl. Vision-Support (base64-images)
    * POST   /api/generate   — Single-Prompt-Completion
    * GET    /api/tags       — Liste installierter Modelle
    * POST   /api/pull       — Modell-Pull mit Streaming-Progress
    * DELETE /api/delete     — Modell deinstallieren

Iron Rule 10 (100% Honesty): Bei Fehlern wird ``OllamaError`` geworfen, niemals
silent ``None`` oder ``[]`` zurueckgegeben. Aufrufer entscheiden ueber Fallback.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Iterable, Optional

import httpx
import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 0.5


class OllamaError(RuntimeError):
    """Basis-Exception fuer alle Ollama-HTTP-Fehler."""


class OllamaConnectionError(OllamaError):
    """Ollama-Daemon nicht erreichbar (nach Retries)."""


class OllamaResponseError(OllamaError):
    """HTTP-Status != 2xx oder ungueltige Antwort."""


@dataclass(frozen=True)
class OllamaModelInfo:
    """Metadaten eines installierten Ollama-Modells.

    Felder gemappt aus ``/api/tags`` (modifizierter Standard von Ollama).
    """

    name: str
    size_bytes: int
    modified_at: str
    digest: str = ""
    family: Optional[str] = None
    parameter_size: Optional[str] = None
    quantization_level: Optional[str] = None

    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / (1024 * 1024), 1)

    @property
    def size_gb(self) -> float:
        return round(self.size_bytes / (1024 * 1024 * 1024), 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "size_bytes": self.size_bytes,
            "size_mb": self.size_mb,
            "size_gb": self.size_gb,
            "modified_at": self.modified_at,
            "digest": self.digest,
            "family": self.family,
            "parameter_size": self.parameter_size,
            "quantization_level": self.quantization_level,
        }


def _encode_image_payload(image: Any) -> str:
    """Konvertiert verschiedene Image-Inputs zu base64-string fuer Ollama.

    Akzeptiert: ``numpy.ndarray`` (RGB H,W,3), ``bytes``, ``str`` (bereits b64).
    Liefert: nackter base64-String (kein data-URI Praefix — Ollama erwartet raw).
    """
    if isinstance(image, str):
        return image
    if isinstance(image, (bytes, bytearray)):
        return base64.b64encode(bytes(image)).decode("ascii")
    if isinstance(image, np.ndarray):
        try:
            from PIL import Image as PILImage  # lazy
        except ImportError as exc:  # pragma: no cover - PIL ist Pflicht
            raise OllamaError(
                f"Pillow fehlt fuer numpy-Bildkodierung: {exc}"
            ) from exc
        arr = image
        if arr.ndim != 3 or arr.shape[2] not in (3, 4):
            raise OllamaError(
                f"Erwarte (H,W,3|4) RGB(A) np.ndarray, bekommen shape={arr.shape}"
            )
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        mode = "RGBA" if arr.shape[2] == 4 else "RGB"
        pil = PILImage.fromarray(arr, mode=mode)
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    raise OllamaError(
        f"Unbekannter Image-Typ: {type(image).__name__} "
        "(unterstuetzt: bytes, np.ndarray, base64-str)"
    )


class OllamaClient:
    """Asynchroner HTTP-Client fuer den lokalen Ollama-Daemon.

    Beispiel::

        async with OllamaClient() as client:
            models = await client.list_models()
            reply = await client.chat(
                model="gemma4:latest",
                messages=[{"role": "user", "content": "Hi"}],
            )

    Threadsafe: Jede Instanz besitzt einen eigenen ``httpx.AsyncClient``.
    Lebenszyklus via ``async with`` oder expliziter ``aclose()``.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.connect_timeout_seconds = connect_timeout_seconds
        self.retry_attempts = max(1, int(retry_attempts))
        self.retry_backoff_seconds = float(retry_backoff_seconds)
        self._transport = transport
        self._client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def __aenter__(self) -> "OllamaClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, *_exc_info: Any) -> None:
        await self.aclose()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            timeout = httpx.Timeout(
                self.timeout_seconds,
                connect=self.connect_timeout_seconds,
            )
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=timeout,
                transport=self._transport,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            finally:
                self._client = None

    # ------------------------------------------------------------------
    # Generic helpers (mit Retry-Logic)
    # ------------------------------------------------------------------
    async def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict[str, Any]] = None,
    ) -> httpx.Response:
        client = await self._ensure_client()
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = await client.request(method, path, json=json_body)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                last_exc = exc
                logger.warning(
                    "Ollama-Connect fehlgeschlagen (Versuch %s/%s): %s",
                    attempt,
                    self.retry_attempts,
                    exc,
                )
                if attempt < self.retry_attempts:
                    await asyncio.sleep(
                        self.retry_backoff_seconds * (2 ** (attempt - 1))
                    )
                continue
            except httpx.HTTPError as exc:
                raise OllamaError(f"HTTP-Fehler bei {method} {path}: {exc}") from exc
            if response.status_code >= 500 and attempt < self.retry_attempts:
                logger.warning(
                    "Ollama 5xx (%s) — Retry %s/%s",
                    response.status_code,
                    attempt,
                    self.retry_attempts,
                )
                await asyncio.sleep(
                    self.retry_backoff_seconds * (2 ** (attempt - 1))
                )
                continue
            return response
        raise OllamaConnectionError(
            f"Ollama nicht erreichbar nach {self.retry_attempts} Versuchen "
            f"({self.base_url}): {last_exc}"
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response, context: str) -> None:
        if response.status_code >= 400:
            body = ""
            try:
                body = response.text[:500]
            except Exception:
                pass
            raise OllamaResponseError(
                f"{context}: HTTP {response.status_code} — {body}"
            )

    # ------------------------------------------------------------------
    # /api/tags — installierte Modelle
    # ------------------------------------------------------------------
    async def list_models(self) -> list[OllamaModelInfo]:
        """Liefert alle installierten Modelle (``GET /api/tags``)."""
        response = await self._request_with_retry("GET", "/api/tags")
        self._raise_for_status(response, "list_models")
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise OllamaResponseError(
                f"list_models: ungueltige JSON-Antwort: {exc}"
            ) from exc
        raw_models = payload.get("models") or []
        result: list[OllamaModelInfo] = []
        for raw in raw_models:
            details = raw.get("details") or {}
            result.append(
                OllamaModelInfo(
                    name=str(raw.get("name") or raw.get("model") or "unknown"),
                    size_bytes=int(raw.get("size") or 0),
                    modified_at=str(raw.get("modified_at") or ""),
                    digest=str(raw.get("digest") or ""),
                    family=details.get("family"),
                    parameter_size=details.get("parameter_size"),
                    quantization_level=details.get("quantization_level"),
                )
            )
        return result

    # ------------------------------------------------------------------
    # /api/chat — Chat-Completion (+ Vision)
    # ------------------------------------------------------------------
    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        images: Optional[Iterable[Any]] = None,
        stream: bool = False,
        options: Optional[dict[str, Any]] = None,
        keep_alive: Optional[str] = None,
    ) -> dict[str, Any]:
        """``POST /api/chat`` (non-streaming).

        ``images`` werden — falls gesetzt — an die LETZTE Message angehaengt
        (Ollama-Konvention). Vision-Modelle wie ``gemma4`` / ``llava`` lesen
        sie automatisch.
        """
        msgs = [dict(m) for m in messages]
        if images:
            encoded = [_encode_image_payload(img) for img in images]
            if not msgs:
                raise OllamaError(
                    "chat: 'images' angegeben, aber 'messages' ist leer"
                )
            msgs[-1] = dict(msgs[-1])
            existing = msgs[-1].get("images") or []
            msgs[-1]["images"] = list(existing) + encoded

        body: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "stream": bool(stream),
        }
        if options:
            body["options"] = options
        if keep_alive is not None:
            body["keep_alive"] = keep_alive

        response = await self._request_with_retry("POST", "/api/chat", json_body=body)
        self._raise_for_status(response, "chat")
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise OllamaResponseError(
                f"chat: ungueltige JSON-Antwort: {exc}"
            ) from exc

    async def generate(
        self,
        model: str,
        prompt: str,
        *,
        images: Optional[Iterable[Any]] = None,
        options: Optional[dict[str, Any]] = None,
        keep_alive: Optional[str] = None,
    ) -> dict[str, Any]:
        """``POST /api/generate`` (single-prompt, non-streaming)."""
        body: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if images:
            body["images"] = [_encode_image_payload(img) for img in images]
        if options:
            body["options"] = options
        if keep_alive is not None:
            body["keep_alive"] = keep_alive

        response = await self._request_with_retry(
            "POST", "/api/generate", json_body=body
        )
        self._raise_for_status(response, "generate")
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise OllamaResponseError(
                f"generate: ungueltige JSON-Antwort: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # /api/pull — Streaming-Progress
    # ------------------------------------------------------------------
    async def pull_model(self, name: str) -> AsyncIterator[dict[str, Any]]:
        """``POST /api/pull`` — yieldet Progress-Events bis fertig.

        Jedes Event ist ein dict mit Feldern wie ``status``, ``completed``,
        ``total``, ``digest``. Letztes Event enthaelt ``status="success"``.
        """
        client = await self._ensure_client()
        body = {"name": name, "stream": True}
        try:
            async with client.stream(
                "POST", "/api/pull", json=body
            ) as response:
                self._raise_for_status(response, "pull_model")
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug("pull_model: konnte Zeile nicht parsen: %r", line)
                        continue
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise OllamaConnectionError(
                f"pull_model({name}): Ollama nicht erreichbar: {exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaError(f"pull_model({name}): HTTP-Fehler: {exc}") from exc

    # ------------------------------------------------------------------
    # /api/delete — Modell loeschen
    # ------------------------------------------------------------------
    async def delete_model(self, name: str) -> bool:
        """``DELETE /api/delete`` — liefert True bei Erfolg."""
        client = await self._ensure_client()
        try:
            response = await client.request(
                "DELETE", "/api/delete", json={"name": name}
            )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise OllamaConnectionError(
                f"delete_model({name}): Ollama nicht erreichbar: {exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaError(f"delete_model({name}): HTTP-Fehler: {exc}") from exc

        if response.status_code == 404:
            return False
        self._raise_for_status(response, f"delete_model({name})")
        return True

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    async def is_alive(self) -> bool:
        """Health-Probe. Liefert True wenn ``/api/tags`` antwortet."""
        try:
            await self.list_models()
            return True
        except OllamaError:
            return False
