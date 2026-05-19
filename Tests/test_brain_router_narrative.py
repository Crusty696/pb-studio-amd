"""Tests fuer die ``narrative``-Erweiterung von GET /brain/explain/{cut_id}.

Verifiziert:
* ``narrative`` wird im Response geliefert, wenn LLM-Narrator OK ist
* ``narrative=False`` als Query-Param unterdrueckt den LLM-Call
* Backward-Compat: ohne narrative-Param wird default-true verwendet
* Bei LLM-Fehler bleibt ``narrative=None`` und alle anderen Felder unveraendert
* Strukturierte Felder (top_axes, bottom_axes, cold_start_axes, final_score)
  bleiben in jedem Fall vorhanden (Iron Rule 10)

Wir monkeypatchen ``pb_studio.brain.llm_narrator.generate_explanation`` damit
kein echter Ollama-Daemon laufen muss.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend._brain_singleton import set_project_state
from backend.routers.brain_router import router as brain_router
from pb_studio.brain.brain_service import BrainService
from pb_studio.brain.bridge_dimensions import BRIDGE_AXES


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(brain_router)
    return app


@pytest.fixture()
def brain_client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    BrainService.reset_singleton()

    state_db = tmp_path / "state.db"
    set_project_state(state_db)

    conn = sqlite3.connect(str(state_db), isolation_level=None)
    conn.execute(
        "INSERT INTO timelines (id, name, audio_clip_id, created_at, is_current) "
        "VALUES (1, 't', 1, '2026-05-16T00:00:00Z', 1)"
    )
    ctx_keys = [
        "", "section=drop", "section=drop|mood=dark",
        "section=drop|mood=dark|motion=high",
        "section=drop|mood=dark|motion=high|energy=high",
        "section=drop|mood=dark|motion=high|energy=high|pace=fast|subpos=middle",
    ]
    md = json.dumps({
        "context_keys": ctx_keys,
        "trigger_type": "kick",
        "segment_type": "drop",
    })
    scores = {a: round(0.1 + 0.05 * i, 2) for i, a in enumerate(BRIDGE_AXES)}
    conn.execute(
        "INSERT INTO timeline_cuts (id, timeline_id, position_idx, clip_id, "
        "start_time, end_time, segment_type, brain_scores_json, metadata_json) "
        "VALUES (200, 1, 0, 'clipA', 0.0, 1.0, 'drop', ?, ?)",
        (json.dumps(scores), md),
    )
    conn.close()

    yield TestClient(_make_app())
    BrainService.reset_singleton()


# ======================================================================
# Backward-Compat / Default ohne narrative-Param
# ======================================================================
def test_explain_without_narrative_param_returns_narrative_field_present(brain_client, monkeypatch):
    """Default: narrative=True -> Feld vorhanden (Wert kann None sein wenn Mock None liefert)."""
    async def _mock(**kwargs):
        return "Der Cut sitzt sauber auf dem Beat. Die Stimmung passt zur Hookline."

    monkeypatch.setattr(
        "pb_studio.brain.llm_narrator.generate_explanation", _mock
    )

    r = brain_client.get("/brain/explain/200")
    assert r.status_code == 200
    body = r.json()
    assert "narrative" in body
    assert body["narrative"] == "Der Cut sitzt sauber auf dem Beat. Die Stimmung passt zur Hookline."


# ======================================================================
# narrative=False unterdrueckt LLM-Call
# ======================================================================
def test_explain_narrative_false_skips_llm_call(brain_client, monkeypatch):
    called = {"n": 0}

    async def _mock(**kwargs):
        called["n"] += 1
        return "Sollte nicht gerufen werden."

    monkeypatch.setattr(
        "pb_studio.brain.llm_narrator.generate_explanation", _mock
    )

    r = brain_client.get("/brain/explain/200?narrative=false")
    assert r.status_code == 200
    body = r.json()
    assert body["narrative"] is None
    assert called["n"] == 0


# ======================================================================
# narrative=True (explizit) + LLM-Mock liefert Text
# ======================================================================
def test_explain_narrative_true_returns_llm_text(brain_client, monkeypatch):
    received_kwargs: dict = {}

    async def _mock(**kwargs):
        received_kwargs.update(kwargs)
        return "Schnitt liegt auf dem Beat und passt zur Bewegung."

    monkeypatch.setattr(
        "pb_studio.brain.llm_narrator.generate_explanation", _mock
    )

    r = brain_client.get("/brain/explain/200?narrative=true&top_n=3")
    assert r.status_code == 200
    body = r.json()
    assert body["narrative"] == "Schnitt liegt auf dem Beat und passt zur Bewegung."
    # die wichtigen Daten muessen am narrator angekommen sein
    assert received_kwargs.get("cut_id") == 200
    assert received_kwargs.get("segment_type") == "drop"
    assert isinstance(received_kwargs.get("top_axes"), list)
    assert isinstance(received_kwargs.get("bottom_axes"), list)
    assert isinstance(received_kwargs.get("cold_start_axes"), list)
    assert 0.0 <= float(received_kwargs.get("final_score")) <= 1.0


# ======================================================================
# LLM-Fehler -> narrative=None, andere Felder unveraendert
# ======================================================================
def test_explain_llm_error_returns_null_narrative_but_structured_data(brain_client, monkeypatch):
    async def _mock(**kwargs):
        raise RuntimeError("Ollama exploded")

    monkeypatch.setattr(
        "pb_studio.brain.llm_narrator.generate_explanation", _mock
    )

    r = brain_client.get("/brain/explain/200")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["narrative"] is None
    # Strukturierte Daten bleiben da
    assert body["cut_id"] == 200
    assert isinstance(body["top_axes"], list) and len(body["top_axes"]) > 0
    assert isinstance(body["bottom_axes"], list)
    assert "cold_start_axes" in body
    assert 0.0 <= body["final_score"] <= 1.0


# ======================================================================
# LLM liefert None (Ollama unreachable / kein Modell) -> narrative=None
# ======================================================================
def test_explain_llm_returns_none_passthrough(brain_client, monkeypatch):
    async def _mock(**kwargs):
        return None

    monkeypatch.setattr(
        "pb_studio.brain.llm_narrator.generate_explanation", _mock
    )

    r = brain_client.get("/brain/explain/200")
    assert r.status_code == 200
    body = r.json()
    assert body["narrative"] is None
    # Strukturierte Daten bleiben da
    assert body["cut_id"] == 200


# ======================================================================
# mode-Param landet beim LLM
# ======================================================================
def test_explain_mode_param_forwarded(brain_client, monkeypatch):
    received: dict = {}

    async def _mock(**kwargs):
        received.update(kwargs)
        return "Antwort."

    monkeypatch.setattr(
        "pb_studio.brain.llm_narrator.generate_explanation", _mock
    )

    r = brain_client.get("/brain/explain/200?mode=quality")
    assert r.status_code == 200
    assert received.get("mode") == "quality"


# ======================================================================
# Vollstaendige Backward-Compat-Pruefung: alle alten Felder existieren
# ======================================================================
def test_explain_all_legacy_fields_still_present(brain_client, monkeypatch):
    """Alte Clients verlassen sich auf top_axes/bottom_axes/cold_start_axes/etc."""
    async def _mock(**kwargs):
        return None

    monkeypatch.setattr(
        "pb_studio.brain.llm_narrator.generate_explanation", _mock
    )

    r = brain_client.get("/brain/explain/200")
    body = r.json()
    for key in (
        "cut_id", "clip_id", "start_time", "end_time", "segment_type",
        "final_score", "context_keys", "top_axes", "bottom_axes",
        "cold_start_axes", "narrative",
    ):
        assert key in body, f"Feld {key!r} fehlt im Response"
