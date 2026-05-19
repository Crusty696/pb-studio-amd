"""Tool-Registry fuer den PB-Studio KI-Chat-Agenten.

Bildet REST-Endpoints des lokalen FastAPI-Backends als ``Tool``-Objekte ab,
die ein LLM ueber Function-Calling (Ollama ``tools``-Parameter) aufrufen kann.
Jedes Tool hat ein JSON-Schema fuer die Argumente und einen async Handler,
der den eigentlichen HTTP-Call ausfuehrt.

Der Chat-Agent ruft via HTTP-Loopback auf das eigene Backend an
(``http://localhost:8765``). Damit bleibt die Trennung Frontend/Backend
sauber — keine direkten Module-Imports im Chat-Pfad, kein Risiko von
Singleton-Side-Effects.

Aufbau::

    registry = build_default_registry()
    tools = registry.openai_schema()   # an Ollama uebergeben
    handler = registry.get("audio.list_clips")
    result = await handler({}, http_client=...)
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

import httpx

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Defaults
# ----------------------------------------------------------------------
DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8765"


def _get_backend_base_url() -> str:
    return os.environ.get("PBSTUDIO_BACKEND_URL", DEFAULT_BACKEND_BASE_URL)


# ----------------------------------------------------------------------
# Tool-Datenklasse
# ----------------------------------------------------------------------
ToolHandler = Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class Tool:
    """Definition eines aufrufbaren Tools fuer den Chat-Agenten.

    Attributes:
        name: Voll-qualifizierter Tool-Name, z.B. ``"audio.list_clips"``.
            Punkte erlaubt Ollama nicht in Tool-Namen, deshalb wird in
            ``openai_schema()`` ein Unterstrich-Alias (``audio_list_clips``)
            erzeugt und beim Dispatch zurueckgemappt.
        description: 1-2 Saetze fuer das LLM, was das Tool tut.
        parameters: JSON-Schema fuer die Tool-Argumente.
        handler: async Callable(args: dict, *, http_client: AsyncClient) -> dict
        destructive: True wenn der Aufruf Daten loescht oder externe Effekte
            hat (Render-Start, Stem-Separation, Modell-Pull, ...). Der Chat-
            Agent kann pre-Confirmation einbauen — aktuell nur als Audit-Flag.
        category: Logische Gruppe fuer UI/Debug (audio, video, ...).
    """
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    destructive: bool = False
    category: str = "general"

    @property
    def llm_name(self) -> str:
        """Ollama erlaubt keine Punkte in Tool-Names — wir ersetzen mit '_'."""
        return self.name.replace(".", "_")

    def to_openai_schema(self) -> dict[str, Any]:
        """Konvertiert in das OpenAI-Function-Calling-Schema (Ollama-kompatibel)."""
        return {
            "type": "function",
            "function": {
                "name": self.llm_name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------
class ToolRegistry:
    """Container fuer Tools mit Lookup-API (per name UND llm_name)."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._by_llm_name: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} bereits registriert")
        self._tools[tool.name] = tool
        self._by_llm_name[tool.llm_name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Sucht Tool per name ODER llm_name (Punkt-/Unterstrich-Form)."""
        if name in self._tools:
            return self._tools[name]
        return self._by_llm_name.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def openai_schema(self) -> list[dict[str, Any]]:
        """Schema-Liste fuer den ``tools``-Parameter von Ollama ``/api/chat``."""
        return [t.to_openai_schema() for t in self._tools.values()]

    def inventory(self) -> list[dict[str, Any]]:
        """Flache Tool-Liste fuer den ``GET /chat/tools``-Endpoint."""
        return [
            {
                "name": t.name,
                "llm_name": t.llm_name,
                "description": t.description,
                "category": t.category,
                "destructive": t.destructive,
                "parameters": t.parameters,
            }
            for t in self._tools.values()
        ]

    def __len__(self) -> int:
        return len(self._tools)


# ----------------------------------------------------------------------
# HTTP-Hilfsfunktionen fuer die Handler
# ----------------------------------------------------------------------
def _normalize_response(response: httpx.Response, *, context: str) -> dict[str, Any]:
    """Konvertiert eine httpx-Response zu einem dict fuer das LLM.

    Bei JSON-Bodies: direkt zurueckgeben.
    Bei Listen: in ``{"items": [...], "count": n}`` wrappen.
    Bei Fehlern (4xx/5xx): ``{"error": ..., "status_code": ...}``.
    Bei Binary-Bodies (Thumbnails etc.): ``{"binary_size": n}``.
    """
    if response.status_code >= 400:
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError):
            payload = response.text[:500]
        return {
            "error": payload if not isinstance(payload, dict) else payload.get("detail", payload),
            "status_code": response.status_code,
            "context": context,
        }

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            return {"error": f"Ungueltige JSON-Antwort: {exc}", "context": context}
        if isinstance(data, list):
            return {"items": data, "count": len(data)}
        return data
    if not response.content:
        return {"status": "ok", "context": context}
    return {"binary_size": len(response.content), "content_type": content_type}


async def _call(
    method: str,
    path: str,
    *,
    http_client: httpx.AsyncClient,
    json_body: Optional[dict[str, Any]] = None,
    params: Optional[dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> dict[str, Any]:
    """Generischer HTTP-Aufruf — fangt Connection/Timeout sauber."""
    try:
        request = http_client.build_request(
            method, path, json=json_body, params=params
        )
        response = await http_client.send(request, follow_redirects=True)
    except httpx.TimeoutException as exc:
        return {
            "error": f"Backend-Timeout: {exc}",
            "context": f"{method} {path}",
        }
    except httpx.HTTPError as exc:
        return {
            "error": f"Backend-Connection-Error: {exc}",
            "context": f"{method} {path}",
        }
    return _normalize_response(response, context=f"{method} {path}")


# ----------------------------------------------------------------------
# Schema-Helfer
# ----------------------------------------------------------------------
def _empty_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "required": []}


def _schema(properties: dict[str, dict[str, Any]], required: Optional[list[str]] = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


# ----------------------------------------------------------------------
# Argument-Coercion fuer LLM-Outputs
# ----------------------------------------------------------------------
def _coerce_int(v: Any, *, default: Optional[int] = None) -> Optional[int]:
    if v is None:
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def _coerce_float(v: Any, *, default: Optional[float] = None) -> Optional[float]:
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _coerce_bool(v: Any, *, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "1", "yes", "ja"}:
            return True
        if s in {"false", "0", "no", "nein"}:
            return False
    if isinstance(v, (int, float)):
        return bool(v)
    return default


def _coerce_str(v: Any, *, default: Optional[str] = None) -> Optional[str]:
    if v is None:
        return default
    return str(v)


def _coerce_int_list(v: Any) -> list[int]:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        out: list[int] = []
        for item in v:
            x = _coerce_int(item)
            if x is not None:
                out.append(x)
        return out
    if isinstance(v, (int, float)):
        return [int(v)]
    if isinstance(v, str):
        # Erlaubt "1,2,3" oder "[1,2]"
        cleaned = re.sub(r"[\[\]\s]", "", v)
        if not cleaned:
            return []
        out = []
        for piece in cleaned.split(","):
            x = _coerce_int(piece)
            if x is not None:
                out.append(x)
        return out
    return []


# ----------------------------------------------------------------------
# Handler-Definitionen pro Bereich
# ----------------------------------------------------------------------

# --- Project --------------------------------------------------------------
async def _h_project_create(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    name = _coerce_str(args.get("name")) or ""
    path = _coerce_str(args.get("path")) or ""
    if not name or not path:
        return {"error": "name und path sind erforderlich"}
    return await _call(
        "POST", "/project/create",
        http_client=http_client,
        json_body={"name": name, "path": path},
    )


async def _h_project_open(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    path = _coerce_str(args.get("path")) or ""
    if not path:
        return {"error": "path ist erforderlich"}
    return await _call(
        "POST", "/project/open",
        http_client=http_client,
        json_body={"path": path},
    )


async def _h_project_save(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    return await _call("POST", "/project/save", http_client=http_client)


async def _h_project_close(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    return await _call("POST", "/project/close", http_client=http_client)


async def _h_project_info(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    return await _call("GET", "/project/info", http_client=http_client)


# --- Audio ----------------------------------------------------------------
async def _h_audio_import(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    path = _coerce_str(args.get("path")) or ""
    if not path:
        return {"error": "path ist erforderlich (absoluter Pfad)"}
    return await _call(
        "POST", "/audio/import",
        http_client=http_client,
        json_body={"path": path},
    )


async def _h_audio_list_clips(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    page = _coerce_int(args.get("page"), default=1)
    limit = _coerce_int(args.get("limit"), default=50)
    return await _call(
        "GET", "/audio/clips",
        http_client=http_client,
        params={"page": page, "limit": limit},
    )


async def _h_audio_analyze(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    clip_id = _coerce_int(args.get("clip_id"))
    if clip_id is None:
        return {"error": "clip_id ist erforderlich"}
    body = {
        "clip_id": clip_id,
        "detect_beats": _coerce_bool(args.get("detect_beats"), default=True),
        "detect_structure": _coerce_bool(args.get("detect_structure"), default=True),
        "spectral_analysis": _coerce_bool(args.get("spectral_analysis"), default=True),
    }
    return await _call("POST", "/audio/analyze", http_client=http_client, json_body=body)


async def _h_audio_get_beats(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    clip_id = _coerce_int(args.get("clip_id"))
    if clip_id is None:
        return {"error": "clip_id ist erforderlich"}
    return await _call("GET", f"/audio/beats/{clip_id}", http_client=http_client)


async def _h_audio_get_structure(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    clip_id = _coerce_int(args.get("clip_id"))
    if clip_id is None:
        return {"error": "clip_id ist erforderlich"}
    return await _call("GET", f"/audio/structure/{clip_id}", http_client=http_client)


async def _h_audio_get_spectral(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    clip_id = _coerce_int(args.get("clip_id"))
    if clip_id is None:
        return {"error": "clip_id ist erforderlich"}
    return await _call("GET", f"/audio/spectral/{clip_id}", http_client=http_client)


async def _h_audio_separate_stems(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    clip_id = _coerce_int(args.get("clip_id"))
    if clip_id is None:
        return {"error": "clip_id ist erforderlich"}
    model = _coerce_str(args.get("model")) or "UVR-MDX-NET-Inst_HQ_3.onnx"
    return await _call(
        "POST", "/audio/stems/separate",
        http_client=http_client,
        json_body={"clip_id": clip_id, "model": model},
    )


# --- Video ----------------------------------------------------------------
async def _h_video_import(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    paths = args.get("paths")
    if isinstance(paths, str):
        paths = [paths]
    if not paths or not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        return {"error": "paths (Liste absoluter Pfade) ist erforderlich"}
    return await _call(
        "POST", "/video/import",
        http_client=http_client,
        json_body={"paths": paths},
    )


async def _h_video_list_clips(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    page = _coerce_int(args.get("page"), default=1)
    limit = _coerce_int(args.get("limit"), default=50)
    return await _call(
        "GET", "/video/clips",
        http_client=http_client,
        params={"page": page, "limit": limit},
    )


async def _h_video_analyze(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    clip_id = _coerce_int(args.get("clip_id"))
    if clip_id is None:
        return {"error": "clip_id ist erforderlich"}
    body = {
        "clip_id": clip_id,
        "detect_scenes": _coerce_bool(args.get("detect_scenes"), default=True),
        "generate_embeddings": _coerce_bool(args.get("generate_embeddings"), default=True),
        "analyze_motion": _coerce_bool(args.get("analyze_motion"), default=True),
        "generate_captions": _coerce_bool(args.get("generate_captions"), default=False),
    }
    return await _call("POST", "/video/analyze", http_client=http_client, json_body=body)


async def _h_video_get_scenes(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    clip_id = _coerce_int(args.get("clip_id"))
    if clip_id is None:
        return {"error": "clip_id ist erforderlich"}
    return await _call("GET", f"/video/scenes/{clip_id}", http_client=http_client)


async def _h_video_get_motion(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    clip_id = _coerce_int(args.get("clip_id"))
    if clip_id is None:
        return {"error": "clip_id ist erforderlich"}
    return await _call("GET", f"/video/motion/{clip_id}", http_client=http_client)


# --- Pacing ---------------------------------------------------------------
async def _h_pacing_generate(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    audio_clip_id = _coerce_int(args.get("audio_clip_id"))
    if audio_clip_id is None:
        return {"error": "audio_clip_id ist erforderlich"}
    body: dict[str, Any] = {
        "audio_clip_id": audio_clip_id,
        "video_clip_ids": _coerce_int_list(args.get("video_clip_ids")),
        "expected_bpm": _coerce_float(args.get("expected_bpm"), default=120.0),
        "use_motion_matching": _coerce_bool(args.get("use_motion_matching"), default=False),
        "use_semantic_matching": _coerce_bool(args.get("use_semantic_matching"), default=False),
        "use_structure_awareness": _coerce_bool(args.get("use_structure_awareness"), default=False),
        "use_key_matching": _coerce_bool(args.get("use_key_matching"), default=False),
        "use_stem_pacing": _coerce_bool(args.get("use_stem_pacing"), default=False),
        "use_brain": _coerce_bool(args.get("use_brain"), default=False),
    }
    duration_limit = _coerce_float(args.get("duration_limit"))
    if duration_limit is not None:
        body["duration_limit"] = duration_limit
    brain_min_confidence = _coerce_float(args.get("brain_min_confidence"))
    if brain_min_confidence is not None:
        body["brain_min_confidence"] = brain_min_confidence
    return await _call("POST", "/pacing/generate", http_client=http_client, json_body=body)


async def _h_pacing_timeline(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    return await _call("GET", "/pacing/timeline", http_client=http_client)


async def _h_pacing_preview(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    start_sec = _coerce_float(args.get("start_sec"), default=0.0)
    duration = _coerce_float(args.get("duration"), default=10.0)
    return await _call(
        "POST", "/pacing/preview",
        http_client=http_client,
        json_body={"start_sec": start_sec, "duration": duration},
    )


# --- Brain ----------------------------------------------------------------
async def _h_brain_suggest(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    audio_clip_id = _coerce_int(args.get("audio_clip_id"))
    if audio_clip_id is None:
        return {"error": "audio_clip_id ist erforderlich"}
    return await _call(
        "POST", "/brain/suggest",
        http_client=http_client,
        json_body={
            "audio_clip_id": audio_clip_id,
            "video_clip_ids": _coerce_int_list(args.get("video_clip_ids")),
            "top_n": _coerce_int(args.get("top_n"), default=20),
        },
    )


async def _h_brain_feedback(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    cut_id = _coerce_int(args.get("cut_id"))
    rating = _coerce_str(args.get("rating")) or ""
    if cut_id is None or rating not in {"perfect", "fits", "not_quite", "no_match"}:
        return {
            "error": "cut_id (int) und rating (perfect|fits|not_quite|no_match) sind erforderlich",
        }
    return await _call(
        "POST", "/brain/feedback",
        http_client=http_client,
        json_body={"cut_id": cut_id, "rating": rating},
    )


async def _h_brain_learning_session(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    return await _call("POST", "/brain/learning_session", http_client=http_client)


async def _h_brain_stats(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    return await _call("GET", "/brain/stats", http_client=http_client)


async def _h_brain_explain(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    cut_id = _coerce_int(args.get("cut_id"))
    if cut_id is None:
        return {"error": "cut_id ist erforderlich"}
    top_n = _coerce_int(args.get("top_n"), default=3)
    narrative = _coerce_bool(args.get("narrative"), default=True)
    return await _call(
        "GET", f"/brain/explain/{cut_id}",
        http_client=http_client,
        params={"top_n": top_n, "narrative": str(narrative).lower()},
    )


# --- Render ---------------------------------------------------------------
async def _h_render_start(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    output_path = _coerce_str(args.get("output_path")) or ""
    audio_path = _coerce_str(args.get("audio_path")) or ""
    if not output_path or not audio_path:
        return {"error": "output_path und audio_path sind erforderlich"}
    body: dict[str, Any] = {
        "output_path": output_path,
        "audio_path": audio_path,
        "quality": _coerce_str(args.get("quality")) or "high",
        "resolution_width": _coerce_int(args.get("resolution_width"), default=1920),
        "resolution_height": _coerce_int(args.get("resolution_height"), default=1080),
        "fps": _coerce_float(args.get("fps"), default=30.0),
        "bitrate_mbps": _coerce_float(args.get("bitrate_mbps"), default=12.0),
        "include_audio": _coerce_bool(args.get("include_audio"), default=True),
    }
    encoder = _coerce_str(args.get("encoder"))
    if encoder:
        body["encoder"] = encoder
    return await _call("POST", "/render/start", http_client=http_client, json_body=body)


async def _h_render_status(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    task_id = _coerce_str(args.get("task_id")) or ""
    if not task_id:
        return {"error": "task_id ist erforderlich"}
    return await _call("GET", f"/render/status/{task_id}", http_client=http_client)


async def _h_render_cancel(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    task_id = _coerce_str(args.get("task_id")) or ""
    if not task_id:
        return {"error": "task_id ist erforderlich"}
    return await _call("POST", f"/render/cancel/{task_id}", http_client=http_client)


# --- Models ---------------------------------------------------------------
async def _h_models_list(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    return await _call("GET", "/models/list", http_client=http_client)


async def _h_models_available(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    return await _call("GET", "/models/available", http_client=http_client)


async def _h_models_recommendations(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    task = _coerce_str(args.get("task")) or "video_captioning"
    mode = _coerce_str(args.get("mode")) or "balance"
    return await _call(
        "GET", "/models/recommendations",
        http_client=http_client,
        params={"task": task, "mode": mode},
    )


# --- System ---------------------------------------------------------------
async def _h_system_health(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    return await _call("GET", "/health", http_client=http_client)


async def _h_system_gpu_status(args: dict[str, Any], *, http_client: httpx.AsyncClient) -> dict[str, Any]:
    return await _call("GET", "/gpu/status", http_client=http_client)


# ----------------------------------------------------------------------
# Default-Registry-Builder
# ----------------------------------------------------------------------
def build_default_registry() -> ToolRegistry:
    """Baut die Default-Registry mit allen Tools der PB-Studio-Bereiche."""
    reg = ToolRegistry()

    # Project -----------------------------------------------------------
    reg.register(Tool(
        name="project.info",
        description="Liefert Infos zum aktuell geoeffneten Projekt (Name, Pfad, Anzahl Audio/Video-Clips, has_timeline).",
        parameters=_empty_schema(),
        handler=_h_project_info,
        category="project",
    ))
    reg.register(Tool(
        name="project.create",
        description="Legt ein neues PB-Studio-Projekt an. name=Projektname, path=Zielverzeichnis (absoluter Pfad).",
        parameters=_schema({
            "name": {"type": "string", "description": "Projektname"},
            "path": {"type": "string", "description": "Absoluter Pfad zum Zielverzeichnis"},
        }, required=["name", "path"]),
        handler=_h_project_create,
        category="project",
        destructive=True,
    ))
    reg.register(Tool(
        name="project.open",
        description="Oeffnet ein bestehendes Projekt. path=Pfad zur Projektdatei oder zum Projektordner.",
        parameters=_schema({
            "path": {"type": "string", "description": "Absoluter Pfad zum Projekt"},
        }, required=["path"]),
        handler=_h_project_open,
        category="project",
    ))
    reg.register(Tool(
        name="project.save",
        description="Speichert den aktuellen Projektzustand (Timeline, Brain-State).",
        parameters=_empty_schema(),
        handler=_h_project_save,
        category="project",
    ))
    reg.register(Tool(
        name="project.close",
        description="Schliesst das aktive Projekt (speichert vorher).",
        parameters=_empty_schema(),
        handler=_h_project_close,
        category="project",
    ))

    # Audio -------------------------------------------------------------
    reg.register(Tool(
        name="audio.list_clips",
        description="Liefert die Liste aller importierten Audio-Clips inkl. BPM/Key/Beat-Anzahl. Paginiert.",
        parameters=_schema({
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
        }),
        handler=_h_audio_list_clips,
        category="audio",
    ))
    reg.register(Tool(
        name="audio.import",
        description="Importiert eine Audio-Datei (MP3/WAV/FLAC/OGG/M4A/AAC). path muss absoluter Pfad sein.",
        parameters=_schema({
            "path": {"type": "string", "description": "Absoluter Pfad zur Audiodatei"},
        }, required=["path"]),
        handler=_h_audio_import,
        category="audio",
        destructive=True,
    ))
    reg.register(Tool(
        name="audio.analyze",
        description="Analysiert einen Audio-Clip (Beats, Struktur, Spektral). Liefert BPM, Key, Beat-Liste, Strukturen.",
        parameters=_schema({
            "clip_id": {"type": "integer", "description": "Audio-Clip-ID aus audio.list_clips"},
            "detect_beats": {"type": "boolean", "default": True},
            "detect_structure": {"type": "boolean", "default": True},
            "spectral_analysis": {"type": "boolean", "default": True},
        }, required=["clip_id"]),
        handler=_h_audio_analyze,
        category="audio",
    ))
    reg.register(Tool(
        name="audio.get_beats",
        description="Liefert die Beat-Liste (Zeitpunkte + Staerken) eines analysierten Audio-Clips.",
        parameters=_schema({
            "clip_id": {"type": "integer"},
        }, required=["clip_id"]),
        handler=_h_audio_get_beats,
        category="audio",
    ))
    reg.register(Tool(
        name="audio.get_structure",
        description="Liefert die Struktur-Segmente (Verse, Chorus, Drop, ...) eines analysierten Audio-Clips.",
        parameters=_schema({
            "clip_id": {"type": "integer"},
        }, required=["clip_id"]),
        handler=_h_audio_get_structure,
        category="audio",
    ))
    reg.register(Tool(
        name="audio.get_spectral",
        description="Liefert die Spektral-Analyse-Daten (Frequenz-Baender, Drop/Buildup-Events) eines Audio-Clips.",
        parameters=_schema({
            "clip_id": {"type": "integer"},
        }, required=["clip_id"]),
        handler=_h_audio_get_spectral,
        category="audio",
    ))
    reg.register(Tool(
        name="audio.separate_stems",
        description="Startet Stem-Separation (Demucs DirectML) — generiert Vocals/Instrumental/Drums/Bass-Spuren. Laufzeitintensiv.",
        parameters=_schema({
            "clip_id": {"type": "integer"},
            "model": {"type": "string", "default": "UVR-MDX-NET-Inst_HQ_3.onnx"},
        }, required=["clip_id"]),
        handler=_h_audio_separate_stems,
        category="audio",
        destructive=True,
    ))

    # Video -------------------------------------------------------------
    reg.register(Tool(
        name="video.list_clips",
        description="Liefert die Liste aller importierten Video-Clips inkl. Aufloesung/FPS/Motion/Embedding-Status.",
        parameters=_schema({
            "page": {"type": "integer", "minimum": 1, "default": 1},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
        }),
        handler=_h_video_list_clips,
        category="video",
    ))
    reg.register(Tool(
        name="video.import",
        description="Importiert eine oder mehrere Video-Dateien. paths=Liste absoluter Pfade.",
        parameters=_schema({
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Absolute Pfade zu Video-Dateien",
            },
        }, required=["paths"]),
        handler=_h_video_import,
        category="video",
        destructive=True,
    ))
    reg.register(Tool(
        name="video.analyze",
        description="Analysiert einen Video-Clip: Szenen-Erkennung, Motion-Analyse (RAFT), SigLIP-Embeddings, optional Captions.",
        parameters=_schema({
            "clip_id": {"type": "integer"},
            "detect_scenes": {"type": "boolean", "default": True},
            "generate_embeddings": {"type": "boolean", "default": True},
            "analyze_motion": {"type": "boolean", "default": True},
            "generate_captions": {"type": "boolean", "default": False},
        }, required=["clip_id"]),
        handler=_h_video_analyze,
        category="video",
    ))
    reg.register(Tool(
        name="video.get_scenes",
        description="Liefert die erkannten Szenen-Cuts eines analysierten Video-Clips.",
        parameters=_schema({
            "clip_id": {"type": "integer"},
        }, required=["clip_id"]),
        handler=_h_video_get_scenes,
        category="video",
    ))
    reg.register(Tool(
        name="video.get_motion",
        description="Liefert die Motion-Curve (avg/peak motion + Kurve) eines Video-Clips.",
        parameters=_schema({
            "clip_id": {"type": "integer"},
        }, required=["clip_id"]),
        handler=_h_video_get_motion,
        category="video",
    ))

    # Pacing ------------------------------------------------------------
    reg.register(Tool(
        name="pacing.generate",
        description="Generiert eine Cut-List (Timeline) aus einem Audio-Track + Video-Clips. Optional mit Motion/Semantic/Key/Brain.",
        parameters=_schema({
            "audio_clip_id": {"type": "integer"},
            "video_clip_ids": {
                "type": "array", "items": {"type": "integer"},
                "description": "Leer = alle verfuegbaren Video-Clips.",
            },
            "expected_bpm": {"type": "number", "default": 120.0},
            "use_motion_matching": {"type": "boolean", "default": False},
            "use_semantic_matching": {"type": "boolean", "default": False},
            "use_structure_awareness": {"type": "boolean", "default": False},
            "use_key_matching": {"type": "boolean", "default": False},
            "use_stem_pacing": {"type": "boolean", "default": False},
            "use_brain": {"type": "boolean", "default": False},
            "duration_limit": {"type": "number"},
            "brain_min_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        }, required=["audio_clip_id"]),
        handler=_h_pacing_generate,
        category="pacing",
    ))
    reg.register(Tool(
        name="pacing.timeline",
        description="Liefert die aktuelle Timeline (Cut-Entries, Gesamtdauer, Audio-Pfad).",
        parameters=_empty_schema(),
        handler=_h_pacing_timeline,
        category="pacing",
    ))
    reg.register(Tool(
        name="pacing.preview",
        description="Rendert eine Vorschau der Timeline ab start_sec fuer duration Sekunden. Liefert preview_path.",
        parameters=_schema({
            "start_sec": {"type": "number", "minimum": 0.0, "default": 0.0},
            "duration": {"type": "number", "exclusiveMinimum": 0.0, "default": 10.0},
        }),
        handler=_h_pacing_preview,
        category="pacing",
    ))

    # Brain -------------------------------------------------------------
    reg.register(Tool(
        name="brain.suggest",
        description="Brain (HIRN) generiert Top-N Cut-Suggestions fuer Audio+Video-Clips basierend auf den gelernten Achsen.",
        parameters=_schema({
            "audio_clip_id": {"type": "integer"},
            "video_clip_ids": {"type": "array", "items": {"type": "integer"}},
            "top_n": {"type": "integer", "minimum": 1, "maximum": 200, "default": 20},
        }, required=["audio_clip_id"]),
        handler=_h_brain_suggest,
        category="brain",
    ))
    reg.register(Tool(
        name="brain.feedback",
        description="Sendet User-Feedback fuer einen Cut an das HIRN. rating muss eines von 'perfect', 'fits', 'not_quite', 'no_match' sein.",
        parameters=_schema({
            "cut_id": {"type": "integer"},
            "rating": {"type": "string", "enum": ["perfect", "fits", "not_quite", "no_match"]},
        }, required=["cut_id", "rating"]),
        handler=_h_brain_feedback,
        category="brain",
    ))
    reg.register(Tool(
        name="brain.learning_session",
        description="Startet eine Brain-Learning-Session — liefert unsichere Cuts fuer aktives Lernen.",
        parameters=_empty_schema(),
        handler=_h_brain_learning_session,
        category="brain",
    ))
    reg.register(Tool(
        name="brain.stats",
        description="Brain-Statistik: total_clicks, cold_start_axes, gelernte Achsen, Top-positive/negative Buckets.",
        parameters=_empty_schema(),
        handler=_h_brain_stats,
        category="brain",
    ))
    reg.register(Tool(
        name="brain.explain",
        description="Liefert die Brain-Explanation fuer einen Cut: welche Achsen haben am meisten beigetragen, mit Narrative.",
        parameters=_schema({
            "cut_id": {"type": "integer"},
            "top_n": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
            "narrative": {"type": "boolean", "default": True},
        }, required=["cut_id"]),
        handler=_h_brain_explain,
        category="brain",
    ))

    # Render ------------------------------------------------------------
    reg.register(Tool(
        name="render.start",
        description="Startet das finale Render einer Timeline. Liefert task_id zur Fortschritts-Abfrage. ACHTUNG: schreibt Datei.",
        parameters=_schema({
            "output_path": {"type": "string"},
            "audio_path": {"type": "string"},
            "quality": {"type": "string", "enum": ["preview", "standard", "high", "ultra"], "default": "high"},
            "encoder": {"type": "string", "enum": ["hevc_amf", "h264_amf", "av1_amf", "libx265", "libx264"]},
            "resolution_width": {"type": "integer", "default": 1920},
            "resolution_height": {"type": "integer", "default": 1080},
            "fps": {"type": "number", "default": 30.0},
            "bitrate_mbps": {"type": "number", "default": 12.0},
            "include_audio": {"type": "boolean", "default": True},
        }, required=["output_path", "audio_path"]),
        handler=_h_render_start,
        category="render",
        destructive=True,
    ))
    reg.register(Tool(
        name="render.status",
        description="Abfrage Render-Fortschritt anhand task_id. Liefert percent, frames, eta_seconds.",
        parameters=_schema({
            "task_id": {"type": "string"},
        }, required=["task_id"]),
        handler=_h_render_status,
        category="render",
    ))
    reg.register(Tool(
        name="render.cancel",
        description="Bricht einen laufenden Render-Task ab.",
        parameters=_schema({
            "task_id": {"type": "string"},
        }, required=["task_id"]),
        handler=_h_render_cancel,
        category="render",
        destructive=True,
    ))

    # Models ------------------------------------------------------------
    reg.register(Tool(
        name="models.list",
        description="Listet alle installierten Ollama-Modelle inkl. Groesse und Quantisierungslevel.",
        parameters=_empty_schema(),
        handler=_h_models_list,
        category="models",
    ))
    reg.register(Tool(
        name="models.available",
        description="Kuratierte Liste der von PB Studio unterstuetzten Vision-Modelle + Installations-Status.",
        parameters=_empty_schema(),
        handler=_h_models_available,
        category="models",
    ))
    reg.register(Tool(
        name="models.recommendations",
        description="Empfehlung welches Modell die Auto-Selection fuer einen Task wuerde. Task=video_captioning|image_captioning|chat|brain_explanation|chat_general|chat_tool_use.",
        parameters=_schema({
            "task": {"type": "string", "default": "video_captioning"},
            "mode": {"type": "string", "enum": ["speed", "balance", "quality"], "default": "balance"},
        }),
        handler=_h_models_recommendations,
        category="models",
    ))

    # System ------------------------------------------------------------
    reg.register(Tool(
        name="system.health",
        description="Backend Health-Check: status, uptime_seconds, gpu_available.",
        parameters=_empty_schema(),
        handler=_h_system_health,
        category="system",
    ))
    reg.register(Tool(
        name="system.gpu_status",
        description="GPU-Status via LibreHardwareMonitor: name, vram_total/used_mb, temperature_c.",
        parameters=_empty_schema(),
        handler=_h_system_gpu_status,
        category="system",
    ))

    return reg


__all__ = [
    "Tool",
    "ToolRegistry",
    "ToolHandler",
    "build_default_registry",
    "DEFAULT_BACKEND_BASE_URL",
]
