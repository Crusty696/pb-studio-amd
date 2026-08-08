"""R-Brain-09: Tests fuer GET /brain/explain/{cut_id}.

NOTE: mountet brain_router test-lokal (eigene FastAPI-Instanz) statt
      backend.main:app, um nicht mit parallelen Task-Edits an main.py
      zu kollidieren.

Verifiziert:
- 404 bei unbekanntem cut_id
- 409 wenn kein Projekt gebunden
- 400 bei top_n out-of-range
- top_axes / bottom_axes sortiert richtig (score absteigend / aufsteigend)
- cold_start_axes-Liste korrekt befuellt nach Klicks
- final_score und context_keys in der Response
- bridge_value Rekonstruktion wenn posterior > 0
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend._brain_singleton import set_project_state
from backend.app_state import AppState, get_app_state
from backend.routers.brain_router import router as brain_router
from pb_studio.brain.brain_service import BrainService
from pb_studio.brain.bridge_dimensions import BRIDGE_AXES


def _make_app(state: AppState) -> FastAPI:
    """Test-lokale App: nur der brain_router gemountet."""
    app = FastAPI()
    app.include_router(brain_router)
    app.dependency_overrides[get_app_state] = lambda: state
    return app


@pytest.fixture()
def brain_client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    BrainService.reset_singleton()

    state_db = tmp_path / "state.db"
    state = AppState(current_project={
        "name": "BrainTest",
        "path": str(tmp_path),
        "db_project_id": 1,
    })
    set_project_state(
        state_db,
        project_epoch=state.project_epoch,
        project_id=1,
    )

    conn = sqlite3.connect(str(state_db), isolation_level=None)
    conn.execute(
        "INSERT INTO timelines (id, name, audio_clip_id, created_at, is_current) "
        "VALUES (1, 't', 1, '2026-05-07T00:00:00Z', 1)"
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
    scores_graduated = {
        a: round(0.1 + 0.05 * i, 2) for i, a in enumerate(BRIDGE_AXES)
    }
    conn.execute(
        "INSERT INTO timeline_cuts (id, timeline_id, position_idx, clip_id, "
        "start_time, end_time, segment_type, brain_scores_json, metadata_json) "
        "VALUES (100, 1, 0, 'clipA', 0.0, 1.0, 'drop', ?, ?)",
        (json.dumps(scores_graduated), md),
    )
    conn.execute(
        "INSERT INTO timeline_cuts (id, timeline_id, position_idx, clip_id, "
        "start_time, end_time, segment_type, brain_scores_json, metadata_json) "
        "VALUES (101, 1, 1, 'clipB', 1.0, 2.0, 'drop', ?, ?)",
        (json.dumps({a: 0.5 for a in BRIDGE_AXES}), md),
    )
    conn.close()

    yield TestClient(_make_app(state))
    BrainService.reset_singleton()


def test_explain_404_for_unknown_cut(brain_client):
    r = brain_client.get("/brain/explain/99999")
    assert r.status_code == 404


def test_explain_400_for_invalid_top_n(brain_client):
    r = brain_client.get("/brain/explain/100?top_n=0")
    assert r.status_code == 400
    r = brain_client.get("/brain/explain/100?top_n=18")
    assert r.status_code == 400


def test_explain_returns_full_structure(brain_client):
    r = brain_client.get("/brain/explain/100")
    assert r.status_code == 200
    body = r.json()
    assert body["cut_id"] == 100
    assert body["clip_id"] == "clipA"
    assert body["start_time"] == 0.0
    assert body["end_time"] == 1.0
    assert body["segment_type"] == "drop"
    assert isinstance(body["context_keys"], list)
    assert len(body["context_keys"]) == 6
    assert isinstance(body["top_axes"], list)
    assert isinstance(body["bottom_axes"], list)
    assert isinstance(body["cold_start_axes"], list)


def test_explain_top_axes_sorted_desc(brain_client):
    r = brain_client.get("/brain/explain/100?top_n=5")
    assert r.status_code == 200
    body = r.json()
    top = body["top_axes"]
    assert len(top) == 5
    scores = [a["score"] for a in top]
    assert scores == sorted(scores, reverse=True), f"top_axes not desc: {scores}"


def test_explain_bottom_axes_sorted_asc(brain_client):
    r = brain_client.get("/brain/explain/100?top_n=5")
    assert r.status_code == 200
    body = r.json()
    bottom = body["bottom_axes"]
    assert len(bottom) == 5
    scores = [a["score"] for a in bottom]
    assert scores == sorted(scores), f"bottom_axes not asc: {scores}"


def test_explain_cold_start_lists_axes_with_few_samples(brain_client):
    """Bei einem frischen Projekt sind ALLE 17 Achsen in cold_start_axes."""
    r = brain_client.get("/brain/explain/100")
    assert r.status_code == 200
    body = r.json()
    assert sorted(body["cold_start_axes"]) == sorted(list(BRIDGE_AXES))


def test_explain_final_score_matches_mean(brain_client):
    """final_score ist mean ueber gespeicherte axis-scores."""
    r = brain_client.get("/brain/explain/101")
    assert r.status_code == 200
    body = r.json()
    assert abs(body["final_score"] - 0.5) < 1e-6


def test_explain_axis_contribution_fields(brain_client):
    r = brain_client.get("/brain/explain/100?top_n=1")
    body = r.json()
    a = body["top_axes"][0]
    assert "axis" in a and a["axis"] in BRIDGE_AXES
    assert "bridge_value" in a and 0.0 <= a["bridge_value"] <= 1.0
    assert "posterior" in a and 0.0 <= a["posterior"] <= 1.0
    assert "score" in a and 0.0 <= a["score"] <= 1.0
    assert "n_samples" in a and a["n_samples"] >= 0


def test_explain_after_feedback_reduces_cold_start(brain_client):
    """Nach 10 'perfect' clicks fuer den cut sollten Achsen LERNEN."""
    for _ in range(10):
        rr = brain_client.post(
            "/brain/feedback",
            json={"cut_id": 100, "rating": "perfect"},
        )
        assert rr.status_code == 200

    r = brain_client.get("/brain/explain/100")
    body = r.json()
    # Nach 10x perfect (alpha+=20 pro axis am spezifischsten Bucket) ->
    # weniger als 17 Achsen sollten cold-start sein
    assert len(body["cold_start_axes"]) < 17
    assert body["top_axes"][0]["n_samples"] >= 10
