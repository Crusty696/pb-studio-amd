"""LM Studio HTTP-Client fuer PB Studio (AMD Premium).

OpenAI-kompatibler REST-Client gegen den lokalen LM Studio Server
(Standard: ``http://localhost:1234/v1``). API-Surface mirroring fuer
``OllamaClient`` damit es als Drop-in-Replacement verwendet werden kann.

Wir benutzen ``httpx`` direkt um Abhaengigkeits-Konflikte mit dem
PyTorch-/DirectML-Stack zu vermeiden (analog zu ``ollama_client.py``).

Unterstuetzte Endpoints:
    * GET    /v1/models                — Liste geladener / verfuegbarer Modelle
    * POST   /v1/chat/completions      — Chat-Completion (auch Vision via images)
    * POST   /v1/chat/completions (stream)  — Streaming-Chat
    * POST   /v1/completions           — Single-Prompt (legacy)
    * POST   /v1/embeddings            — Embeddings (falls Embedding-Model geladen)

NICHT unterstuetzt:
    * pull_model / delete_model — LM Studio managed Modelle ueber seine App;
      diese Methoden raisen ``NotImplementedError`` (App benutzen).

Iron Rule 10 (100% Honesty): Bei Fehlern wird ``LMStudioError`` geworfen, niemals
silent ``None`` oder ``[]`` zurueckgegeben. Aufrufer entscheiden ueber Fallback.

Iron Rule 2 (AMD DirectML): Selektion der Runtime (Vulkan/ROCm/CPU) wird ueber
LM Studio Settings oder ``lms runtime select`` gemacht — NICHT hier im Client.
Empfehlung fuer RX 7800 XT (verifiziert 2026-05-17): Vulkan 2.14.0.
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

DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 0.5
MODEL_CAPABILITY_CHAT = "chat"
MODEL_CAPABILITY_VISION = "vision"
MODEL_CAPABILITY_EMBEDDING = "embedding"
VALID_MODEL_CAPABILITIES = frozenset({
    MODEL_CAPABILITY_CHAT,
    MODEL_CAPABILITY_VISION,
    MODEL_CAPABILITY_EMBEDDING,
})


class LMStudioError(RuntimeError):
    """Basis-Exception fuer alle LM-Studio-HTTP-Fehler."""


class LMStudioConnectionError(LMStudioError):
    """LM-Studio-Server nicht erreichbar (nach Retries)."""


class LMStudioResponseError(LMStudioError):
    """HTTP-Status != 2xx oder ungueltige Antwort."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        # Audit-Fix 2026-07-10 (Sweep-Finding CHAT-7): vorher ging der HTTP-Status
        # komplett verloren — chat_agent.py konnte 404 (Modell nicht geladen) von
        # 400 (z.B. Context-Length-Overflow) oder 500 nur per String-Match auf die
        # Fehlermeldung unterscheiden, was Context-Overflows faelschlich als
        # "Modell nicht geladen" behandelte und durch alle Modelle churnte.
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class LMStudioModelInfo:
    """Metadaten eines LM-Studio-Modells.

    Felder gemappt aus ``GET /v1/models`` (OpenAI-kompatibles Schema).
    Felder-API kompatibel zu ``OllamaModelInfo`` damit ``ModelRegistry``
    den Client transparent austauschen kann.
    """

    name: str
    size_bytes: int = 0
    modified_at: str = ""
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


def _encode_image_data_uri(image: Any) -> str:
    """Konvertiert verschiedene Image-Inputs zu OpenAI-konformer data-URI.

    OpenAI/LM-Studio erwartet bei Vision-Calls eine ``image_url`` Property
    die entweder ``http(s)://`` oder eine ``data:image/...;base64,...`` URI ist.

    Akzeptiert: ``numpy.ndarray`` (RGB H,W,3|4), ``bytes`` (PNG/JPEG), ``str``
    (bereits base64 ODER bereits eine data-URI).
    """
    if isinstance(image, str):
        if image.startswith("data:image/"):
            return image
        return f"data:image/png;base64,{image}"
    if isinstance(image, (bytes, bytearray)):
        b64 = base64.b64encode(bytes(image)).decode("ascii")
        return f"data:image/png;base64,{b64}"
    if isinstance(image, np.ndarray):
        try:
            from PIL import Image as PILImage
        except ImportError as exc:  # pragma: no cover
            raise LMStudioError(
                f"Pillow fehlt fuer numpy-Bildkodierung: {exc}"
            ) from exc
        arr = image
        if arr.ndim != 3 or arr.shape[2] not in (3, 4):
            raise LMStudioError(
                f"Erwarte (H,W,3|4) RGB(A) np.ndarray, bekommen shape={arr.shape}"
            )
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        mode = "RGBA" if arr.shape[2] == 4 else "RGB"
        pil = PILImage.fromarray(arr, mode=mode)
        # Downscale auf max. Kantenlaenge: volle Video-Frames (1920x1080+) als PNG
        # erzeugen riesige Payloads und lassen die Vision-Inferenz extrem langsam
        # werden (>180s ReadTimeout). Vision-Modelle arbeiten intern ohnehin mit
        # ~384-768px Tiles — ein Downscale aendert die Tag-Qualitaet kaum, macht
        # den Call aber Faktor 10+ schneller. JPEG statt PNG spart zusaetzlich.
        _MAX_EDGE = 768
        longest = max(pil.width, pil.height)
        if longest > _MAX_EDGE:
            scale = _MAX_EDGE / float(longest)
            new_size = (max(1, int(pil.width * scale)), max(1, int(pil.height * scale)))
            pil = pil.resize(new_size, PILImage.LANCZOS)
        buf = io.BytesIO()
        if mode == "RGBA":
            pil.save(buf, format="PNG")
            return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
        pil.save(buf, format="JPEG", quality=85)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
    raise LMStudioError(
        f"Unbekannter Image-Typ: {type(image).__name__} "
        "(unterstuetzt: bytes, np.ndarray, base64-str, data-URI-str)"
    )


def _messages_with_images(
    messages: list[dict[str, Any]],
    images: Optional[Iterable[Any]],
) -> list[dict[str, Any]]:
    """Konvertiert Ollama-Style messages (mit optionalen images-Array)
    in OpenAI-Style mit ``content`` als ``[{type:text,...}, {type:image_url,...}]``.

    Wenn keine images: messages durchreichen wie sie sind (nur shallow-copy).
    Wenn images: an LETZTE message anhaengen — ihre ``content`` wird zu
    einer Liste mit ``[{text}, {image_url}, ...]``.
    """
    msgs = [dict(m) for m in messages]
    if not images:
        return msgs
    if not msgs:
        raise LMStudioError(
            "chat: 'images' angegeben, aber 'messages' ist leer"
        )
    last = dict(msgs[-1])
    text_content = last.get("content") or ""
    if isinstance(text_content, list):
        parts = list(text_content)
    else:
        parts = [{"type": "text", "text": str(text_content)}]
    for img in images:
        parts.append({
            "type": "image_url",
            "image_url": {"url": _encode_image_data_uri(img)},
        })
    last["content"] = parts
    msgs[-1] = last
    return msgs


def _ollama_options_to_openai(
    options: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Mapped Ollama ``options`` (temperature, top_p, num_predict, …)
    auf OpenAI-Felder (temperature, top_p, max_tokens, …).
    """
    if not options:
        return {}
    out: dict[str, Any] = {}
    if "temperature" in options:
        out["temperature"] = options["temperature"]
    if "top_p" in options:
        out["top_p"] = options["top_p"]
    if "num_predict" in options and options["num_predict"] is not None:
        out["max_tokens"] = int(options["num_predict"])
    if "max_tokens" in options and options["max_tokens"] is not None:
        out["max_tokens"] = int(options["max_tokens"])
    if "stop" in options:
        out["stop"] = options["stop"]
    if "seed" in options:
        out["seed"] = options["seed"]
    if "presence_penalty" in options:
        out["presence_penalty"] = options["presence_penalty"]
    if "frequency_penalty" in options:
        out["frequency_penalty"] = options["frequency_penalty"]
    return out


def _openai_to_ollama_chat_response(resp: dict[str, Any]) -> dict[str, Any]:
    """Wrap eine OpenAI-Chat-Response so dass sie ``{message:{role,content}, ...}``
    aussieht wie Ollama. Tool-Calls bleiben unter ``message.tool_calls`` (gleiches
    Format wie Ollama, das selbst OpenAI-Style verwendet).
    """
    choices = resp.get("choices") or []
    if not choices:
        return {
            "model": resp.get("model", ""),
            "message": {"role": "assistant", "content": ""},
            "done": True,
            "usage": resp.get("usage"),
            "raw": resp,
        }
    msg = choices[0].get("message") or {}
    return {
        "model": resp.get("model", ""),
        "message": {
            "role": msg.get("role", "assistant"),
            "content": msg.get("content") or "",
            "tool_calls": msg.get("tool_calls") or [],
        },
        "done": True,
        "done_reason": choices[0].get("finish_reason"),
        "usage": resp.get("usage"),
        "raw": resp,
    }


class LMStudioClient:
    """Asynchroner HTTP-Client fuer den lokalen LM-Studio-Server.

    API-Surface mirror ``OllamaClient`` damit ein Tausch
    minimal-invasiv ist.

    Beispiel::

        async with LMStudioClient() as client:
            models = await client.list_models()
            reply = await client.chat(
                model="qwen3-vl-8b",
                messages=[{"role": "user", "content": "Hi"}],
            )
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
    async def __aenter__(self) -> "LMStudioClient":
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
    # Helpers
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
                    "LM-Studio-Connect fehlgeschlagen (Versuch %s/%s): %s",
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
                raise LMStudioError(
                    f"HTTP-Fehler bei {method} {path} "
                    f"({self.base_url}): {type(exc).__name__}: {exc}"
                ) from exc
            if response.status_code >= 500 and attempt < self.retry_attempts:
                logger.warning(
                    "LM Studio 5xx (%s) — Retry %s/%s",
                    response.status_code,
                    attempt,
                    self.retry_attempts,
                )
                await asyncio.sleep(
                    self.retry_backoff_seconds * (2 ** (attempt - 1))
                )
                continue
            return response
        raise LMStudioConnectionError(
            f"LM Studio nicht erreichbar nach {self.retry_attempts} Versuchen "
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
            raise LMStudioResponseError(
                f"{context}: HTTP {response.status_code} — {body}",
                status_code=response.status_code,
            )

    # ------------------------------------------------------------------
    # /v1/models
    # ------------------------------------------------------------------
    async def list_models(self) -> list[LMStudioModelInfo]:
        """Liefert alle in LM Studio verfuegbaren Modelle (``GET /v1/models``).

        Hinweis: LM Studio listet HIER nur Modelle die "ready to serve" sind
        (geladen ODER on-demand ladbar). Im Gegensatz zu Ollama gibt es kein
        klares "installed but unloaded" — die App entscheidet das selbst.
        """
        is_ollama = "11434" in self.base_url or "ollama" in self.base_url.lower()
        if is_ollama:
            base = self.base_url
            if base.endswith("/v1"):
                base = base[:-3]
            url = f"{base.rstrip('/')}/api/tags"
            try:
                client = await self._ensure_client()
                response = await client.get(url)
                self._raise_for_status(response, "list_models_ollama")
                payload = response.json()
                raw_models = payload.get("models") or []
                result: list[LMStudioModelInfo] = []
                for raw in raw_models:
                    name = str(raw.get("name") or "unknown")
                    details = raw.get("details") or {}
                    size_bytes = int(raw.get("size") or 0)
                    family = details.get("family") or (details.get("families") or [None])[0]
                    parameter_size = details.get("parameter_size")
                    quantization_level = details.get("quantization_level")
                    
                    result.append(LMStudioModelInfo(
                        name=name,
                        size_bytes=size_bytes,
                        modified_at=str(raw.get("modified_at") or ""),
                        digest=str(raw.get("digest") or ""),
                        family=family,
                        parameter_size=parameter_size,
                        quantization_level=quantization_level,
                    ))
                return result
            except Exception as exc:
                logger.warning("Fehler bei nativem Ollama-Modell-List (%s): %s. Fallback auf OpenAI API.", url, exc)

        response = await self._request_with_retry("GET", "/models")
        self._raise_for_status(response, "list_models")
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise LMStudioResponseError(
                f"list_models: ungueltige JSON-Antwort: {exc}"
            ) from exc
        raw_models = payload.get("data") or []
        result = []
        for raw in raw_models:
            name = str(raw.get("id") or raw.get("name") or "unknown")
            # OpenAI-Schema kennt size nicht direkt. LM Studio fuegt manchmal
            # owned_by, object, created — nicht hilfreich. Wir lassen size=0.
            result.append(LMStudioModelInfo(
                name=name,
                size_bytes=0,
                modified_at=str(raw.get("created") or ""),
                digest="",
                family=raw.get("type"),
            ))
        return result

    async def get_vision_model_names(self) -> set[str]:
        """Liefert die Namen aller vision-faehigen Modelle (``type == 'vlm'``).

        Nutzt LM Studios native REST-API ``/api/v0/models`` (liefert ein
        ``type``-Feld: ``vlm``/``llm``/``embeddings``). Best-effort: bei jedem
        Fehler (Endpoint fehlt, z.B. Ollama; Connection; JSON) -> leeres Set,
        damit der Caller auf Keyword-Heuristik zurueckfallen kann.

        Das OpenAI-kompatible ``/v1/models`` liefert KEIN ``type`` — daher ist
        dieser separate Call noetig, um z.B. ein Reasoning-Modell mit ``qwen``
        im Namen nicht faelschlich als Vision-Modell zu waehlen.
        """
        # base_url ist .../v1 — /api/v0/models liegt daneben (Host-Root).
        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[: -len("/v1")]
        url = f"{base}/api/v0/models"
        try:
            client = await self._ensure_client()
            response = await client.get(url)
            if response.status_code != 200:
                return set()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001 — best-effort, nie hart fehlschlagen
            logger.debug("get_vision_model_names: /api/v0/models nicht verfuegbar: %s", exc)
            return set()

        vision: set[str] = set()
        for raw in (payload.get("data") or []):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("type") or "").lower() == "vlm":
                name = str(raw.get("id") or raw.get("name") or "").strip()
                if name:
                    vision.add(name)
        return vision

    async def get_model_capabilities(self) -> dict[str, frozenset[str]]:
        """Liefert autoritative Chat-/Vision-/Embedding-Capabilities.

        LM Studio nutzt ``/api/v0/models`` mit ``type``. Ollama nutzt
        ``/api/tags`` mit explizitem ``capabilities``-Array. Fehlt die native
        API, liefert die Methode ein leeres Mapping.
        """
        base = self.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[: -len("/v1")]
        is_ollama = "11434" in self.base_url or "ollama" in self.base_url.lower()
        url = f"{base}/api/tags" if is_ollama else f"{base}/api/v0/models"
        try:
            client = await self._ensure_client()
            response = await client.get(url)
            if response.status_code != 200:
                return {}
            payload = response.json()
        except Exception as exc:  # noqa: BLE001 - best-effort capability probe
            logger.debug("get_model_capabilities: nativer Endpoint nicht verfuegbar: %s", exc)
            return {}

        raw_models = payload.get("models") if is_ollama else payload.get("data")
        capabilities_by_name: dict[str, frozenset[str]] = {}
        for raw in (raw_models or []):
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("id") or raw.get("name") or raw.get("model") or "").strip()
            if not name:
                continue
            capabilities: set[str] = set()
            if is_ollama:
                native = {
                    str(value).strip().lower()
                    for value in (raw.get("capabilities") or [])
                }
                if "completion" in native:
                    capabilities.add(MODEL_CAPABILITY_CHAT)
                if "vision" in native:
                    capabilities.add(MODEL_CAPABILITY_VISION)
                if "embedding" in native or "embeddings" in native:
                    capabilities.add(MODEL_CAPABILITY_EMBEDDING)
            else:
                model_type = str(raw.get("type") or "").strip().lower()
                if model_type == "vlm":
                    capabilities.update({
                        MODEL_CAPABILITY_CHAT,
                        MODEL_CAPABILITY_VISION,
                    })
                elif model_type == "llm":
                    capabilities.add(MODEL_CAPABILITY_CHAT)
                elif model_type in {"embedding", "embeddings"}:
                    capabilities.add(MODEL_CAPABILITY_EMBEDDING)
            if capabilities:
                capabilities_by_name[name] = frozenset(capabilities)
        return capabilities_by_name

    async def supports_capability(self, capability: str) -> bool:
        """True wenn mindestens ein aktuell gelistetes Modell Capability besitzt."""
        required = capability.strip().lower()
        if required not in VALID_MODEL_CAPABILITIES:
            raise ValueError(f"Unbekannte Modell-Capability: {capability!r}")

        models, capabilities_by_name = await asyncio.gather(
            self.list_models(),
            self.get_model_capabilities(),
        )
        installed_names = {model.name for model in models}
        if capabilities_by_name:
            return any(
                name in installed_names and required in model_capabilities
                for name, model_capabilities in capabilities_by_name.items()
            )

        lowered_names = [name.lower() for name in installed_names]
        if required == MODEL_CAPABILITY_VISION:
            vision_tokens = (
                "-vl", "vl-", "vl:", "vision", "vlm", "llava", "moondream",
                "multimodal", "minicpm-v", "internvl", "pixtral", "smolvlm",
                "gemma-3n", "gemma3n", "e4b", "e2b", "cpm-v",
                "qwen/qwen3.5-", "qwen/qwen3.6-",
            )
            return any(
                any(token in name for token in vision_tokens)
                for name in lowered_names
            )
        if required == MODEL_CAPABILITY_EMBEDDING:
            return any("embed" in name for name in lowered_names)
        return any("embed" not in name for name in lowered_names)

    # ------------------------------------------------------------------
    # /v1/chat/completions — Chat (+ Vision via images)
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
        tools: Optional[list[dict[str, Any]]] = None,
        format: Optional[str] = None,
    ) -> dict[str, Any]:
        """``POST /v1/chat/completions`` (non-streaming).

        Returns: Ollama-Style ``{"model","message":{"role","content","tool_calls"},
        "done","usage","raw":<openai_response>}``. ``raw`` enthaelt die
        unmodifizierte OpenAI-Antwort fuer Callers die das wollen.

        Vision: wenn ``images`` gesetzt sind, werden sie an die letzte Message
        als ``image_url`` Parts angehaengt (OpenAI Vision-Format).

        Tools: Function-Calling im OpenAI-Format
        ``[{"type":"function","function":{"name","description","parameters"}}]``.
        Tool-Calls kommen in ``message.tool_calls`` zurueck (gleiches Format
        wie Ollama, das selber OpenAI-Style verwendet).

        ``format``: ``"json"`` → setzt ``response_format={"type":"json_object"}``.
        Andere Werte werden als Schema-Strings durchgereicht.

        ``keep_alive``: in LM Studio nicht direkt unterstuetzt. Ignoriert
        (Idle-TTL wird ueber LM-Studio-Settings konfiguriert).
        """
        msgs = _messages_with_images(messages, images)
        body: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "stream": bool(stream),
        }
        body.update(_ollama_options_to_openai(options))
        if tools:
            body["tools"] = tools
        if format == "json":
            body["response_format"] = {"type": "json_object"}
        elif format and format != "json":
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "out", "schema": format if isinstance(format, dict) else {}}}
        # keep_alive: LM Studio ignoriert das, kein Mapping noetig.

        response = await self._request_with_retry(
            "POST", "/chat/completions", json_body=body
        )
        self._raise_for_status(response, "chat")
        try:
            openai_resp = response.json()
        except json.JSONDecodeError as exc:
            raise LMStudioResponseError(
                f"chat: ungueltige JSON-Antwort: {exc}"
            ) from exc
        return _openai_to_ollama_chat_response(openai_resp)

    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        images: Optional[Iterable[Any]] = None,
        options: Optional[dict[str, Any]] = None,
        keep_alive: Optional[str] = None,
        tools: Optional[list[dict[str, Any]]] = None,
        format: Optional[str] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Streaming-Chat. Yieldet Ollama-Style Events::

            {"model": str, "message": {"role": "assistant", "content": str,
             "tool_calls": [...]?}, "done": bool, "done_reason": str?}

        Pro OpenAI-SSE-Event wird ein Ollama-Event erzeugt. Tool-Calls werden
        ueber Delta-Aggregation gesammelt (OpenAI streamt sie inkrementell).
        ``done=True`` kommt einmal am Ende, mit ``done_reason`` aus ``finish_reason``.
        """
        client = await self._ensure_client()
        msgs = _messages_with_images(messages, images)
        body: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "stream": True,
        }
        body.update(_ollama_options_to_openai(options))
        if tools:
            body["tools"] = tools
        if format == "json":
            body["response_format"] = {"type": "json_object"}

        # Tool-Call-Aggregation across deltas
        tool_calls_buf: dict[int, dict[str, Any]] = {}

        try:
            async with client.stream(
                "POST", "/chat/completions", json=body
            ) as response:
                self._raise_for_status(response, "chat_stream")
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        # Final flush mit aggregierten tool_calls
                        final_calls = [
                            tc for _, tc in sorted(tool_calls_buf.items())
                        ]
                        yield {
                            "model": model,
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": final_calls,
                            },
                            "done": True,
                            "done_reason": "stop",
                        }
                        return
                    try:
                        ev = json.loads(payload)
                    except json.JSONDecodeError:
                        logger.debug("chat_stream: konnte SSE-Zeile nicht parsen: %r", line)
                        continue
                    choices = ev.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    finish = choices[0].get("finish_reason")
                    # Aggregate tool_calls deltas
                    for tc in (delta.get("tool_calls") or []):
                        idx = int(tc.get("index", 0))
                        if idx not in tool_calls_buf:
                            tool_calls_buf[idx] = {
                                "id": tc.get("id", ""),
                                "type": tc.get("type", "function"),
                                "function": {"name": "", "arguments": ""},
                            }
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            tool_calls_buf[idx]["function"]["name"] = fn["name"]
                        if fn.get("arguments"):
                            tool_calls_buf[idx]["function"]["arguments"] += fn["arguments"]
                        if tc.get("id"):
                            tool_calls_buf[idx]["id"] = tc["id"]
                    # Manche Modelle (Reasoning-Modelle wie gemma-3-thinking)
                    # streamen Inhalt unter ``reasoning_content`` bevor sie
                    # zu ``content`` umsteigen. Wir aggregieren beides damit
                    # Aufrufer eine kontinuierliche content-Spur sehen.
                    content = (
                        delta.get("content")
                        or delta.get("reasoning_content")
                        or ""
                    )
                    is_done = finish is not None
                    yield {
                        "model": ev.get("model", model),
                        "message": {
                            "role": delta.get("role", "assistant"),
                            "content": content,
                            "tool_calls": (
                                [tc for _, tc in sorted(tool_calls_buf.items())]
                                if is_done else []
                            ),
                        },
                        "done": is_done,
                        "done_reason": finish,
                    }
                    if is_done:
                        return
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise LMStudioConnectionError(
                f"chat_stream: LM Studio nicht erreichbar: {exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LMStudioError(f"chat_stream: HTTP-Fehler: {exc}") from exc

    async def generate(
        self,
        model: str,
        prompt: str,
        *,
        images: Optional[Iterable[Any]] = None,
        options: Optional[dict[str, Any]] = None,
        keep_alive: Optional[str] = None,
    ) -> dict[str, Any]:
        """Single-Prompt-Completion. Wir mappen das auf ``chat()`` mit
        einer einzelnen user-Message — das ist der OpenAI-empfohlene Weg
        und liefert dieselben Garantien (Vision, Tools, Streaming via chat).

        Returns: dict mit ``response`` (alias fuer message.content) plus
        die volle Ollama-Style-Struktur damit Caller die ``response``-Keyword
        wie bei Ollama benutzen koennen.
        """
        chat_resp = await self.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            images=images,
            options=options,
        )
        return {
            "model": chat_resp.get("model", model),
            "response": (chat_resp.get("message") or {}).get("content", ""),
            "done": chat_resp.get("done", True),
            "usage": chat_resp.get("usage"),
            "raw": chat_resp.get("raw"),
        }

    # ------------------------------------------------------------------
    # /v1/embeddings
    # ------------------------------------------------------------------
    async def embeddings(
        self,
        model: str,
        input: str | list[str],
    ) -> list[list[float]]:
        """``POST /v1/embeddings`` — gibt Embedding-Vector(en) zurueck."""
        body = {"model": model, "input": input}
        response = await self._request_with_retry(
            "POST", "/embeddings", json_body=body
        )
        self._raise_for_status(response, "embeddings")
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise LMStudioResponseError(
                f"embeddings: ungueltige JSON-Antwort: {exc}"
            ) from exc
        data = payload.get("data") or []
        return [item.get("embedding") or [] for item in data]

    # ------------------------------------------------------------------
    # NOT SUPPORTED — LM Studio managed Modelle ueber die App
    # ------------------------------------------------------------------
    async def pull_model(self, name: str):  # noqa: D401
        """Nicht unterstuetzt — LM Studio managed Downloads ueber seine UI.

        Aufrufer sollten den Benutzer per UI-Message auffordern, das Modell
        in LM Studio zu downloaden. Diese Methode raised explizit.
        """
        raise NotImplementedError(
            "pull_model wird von LM Studio nicht ueber API unterstuetzt — "
            "bitte ueber LM Studio App downloaden."
        )

    async def delete_model(self, name: str) -> bool:
        raise NotImplementedError(
            "delete_model wird von LM Studio nicht ueber API unterstuetzt — "
            "bitte ueber LM Studio App entfernen."
        )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    async def is_alive(self) -> bool:
        """Health-Probe. Liefert True wenn ``/v1/models`` antwortet."""
        try:
            await self.list_models()
            return True
        except LMStudioError:
            return False
