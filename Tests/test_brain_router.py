"""Tests für brain_router REST-API (Plan Phase 4)."""

from __future__ import annotations

import json
import sqlite3
import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import owner_capability
from backend.main import app
from backend._brain_singleton import set_project_state
from pb_studio.brain.brain_service import BrainService
from pb_studio.brain.bridge_dimensions import BRIDGE_AXES

OWNER_CAPABILITY = "A" * 44
OWNER_HEADER = "X-PBStudio-Owner-Capability"


@pytest.fixture()
def brain_client(tmp_path: Path, monkeypatch):
    # Force brain to use a per-test directory
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(
        owner_capability,
        "_OWNER_CAPABILITY",
        OWNER_CAPABILITY,
    )
    BrainService.reset_singleton()

    state_db = tmp_path / "state.db"
    set_project_state(state_db)

    # Seed timeline + cut so /feedback can find it
    conn = sqlite3.connect(str(state_db), isolation_level=None)
    conn.execute(
        "INSERT INTO timelines (id, name, audio_clip_id, created_at, is_current) "
        "VALUES (1, 't', 1, '2026-05-06T00:00:00Z', 1)"
    )
    ctx_keys = ["", "section=drop"]
    md = json.dumps({
        "context_keys": ctx_keys,
        "bridge_values": {
            "beat_weight": 1.0,
            "semantic_match_weight": 0.9,
        },
        "brain_axis_status": {
            "semantic_match_weight": {
                "status": "unavailable",
                "reason": "audio_embedding_missing",
            },
        },
    })
    conn.execute(
        "INSERT INTO timeline_cuts (id, timeline_id, position_idx, clip_id, "
        "start_time, end_time, brain_scores_json, metadata_json) "
        "VALUES (42, 1, 0, 'c0', 0.0, 1.0, ?, ?)",
        (json.dumps({a: 0.5 for a in BRIDGE_AXES}), md),
    )
    conn.execute(
        "INSERT INTO timeline_cuts (id, timeline_id, position_idx, clip_id, "
        "start_time, end_time, brain_scores_json, metadata_json) "
        "VALUES (43, 1, 1, 'c1', 1.0, 2.0, ?, ?)",
        (json.dumps({a: 0.4 for a in BRIDGE_AXES}), md),
    )
    conn.close()

    with TestClient(app) as client:
        client.headers.update({OWNER_HEADER: OWNER_CAPABILITY})
        yield client

    BrainService.reset_singleton()


def test_suggest_returns_cuts(brain_client):
    resp = brain_client.post("/brain/suggest",
                             json={"audio_clip_id": 1, "video_clip_ids": [], "top_n": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["suggestions"]) == 2
    assert {s["cut_id"] for s in data["suggestions"]} == {42, 43}


def test_feedback_increments_buckets(brain_client):
    resp = brain_client.post("/brain/feedback",
                             json={"cut_id": 42, "rating": "perfect"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # Relevant beat axis x two available context levels; semantic unavailable.
    assert body["updated_buckets"] == 2
    assert body["total_clicks"] >= 1


def test_feedback_unknown_cut_404(brain_client):
    resp = brain_client.post("/brain/feedback",
                             json={"cut_id": 9999, "rating": "perfect"})
    assert resp.status_code == 404


def test_learning_session_returns_15_or_fewer(brain_client):
    resp = brain_client.post("/brain/learning_session")
    assert resp.status_code == 200
    cuts = resp.json()["cuts"]
    assert len(cuts) <= 15


def test_stats_returns_structured(brain_client):
    brain_client.post("/brain/feedback",
                      json={"cut_id": 42, "rating": "perfect"})
    resp = brain_client.get("/brain/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_clicks"] >= 1
    assert body["cold_start_axes"] + body["learned_axes"] == len(BRIDGE_AXES)


def test_stats_holds_weights_connection_lock(monkeypatch):
    brain_router = __import__(
        "backend.routers.brain_router",
        fromlist=["stats"],
    )

    class TrackingLock:
        def __init__(self):
            self.depth = 0
            self.entries = 0

        def __enter__(self):
            self.depth += 1
            self.entries += 1
            return self

        def __exit__(self, exc_type, exc, tb):
            self.depth -= 1
            return False

    class LockedConnection:
        def __init__(self, lock):
            self.lock = lock

        def execute(self, query):
            assert self.lock.depth > 0, "weights_conn query without _weights_lock"
            return self

        def fetchall(self):
            return []

    lock = TrackingLock()
    event_loop_thread = threading.get_ident()

    service = SimpleNamespace(
        brain=SimpleNamespace(
            _weights_lock=lock,
            weights_conn=LockedConnection(lock),
        ),
        weights=SimpleNamespace(total_clicks=lambda: 0),
    )
    monkeypatch.setattr(brain_router, "get_brain_service", lambda: service)

    original_execute = service.brain.weights_conn.execute

    def execute_off_event_loop(query):
        assert threading.get_ident() != event_loop_thread
        return original_execute(query)

    service.brain.weights_conn.execute = execute_off_event_loop
    result = asyncio.run(brain_router.stats())

    assert result.total_clicks == 0
    assert lock.entries == 1


def test_reset_two_step(brain_client):
    brain_client.post("/brain/feedback",
                      json={"cut_id": 42, "rating": "perfect"})

    r1 = brain_client.post("/brain/reset")
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["status"] == "pending_confirmation"
    token = body1["confirmation_token"]
    assert token

    r2 = brain_client.post("/brain/reset", json={"confirmation_token": token})
    assert r2.status_code == 200
    assert r2.json()["status"] == "reset_complete"

    stats = brain_client.get("/brain/stats").json()
    assert stats["total_clicks"] == 0


def test_reset_invalid_token(brain_client):
    r = brain_client.post("/brain/reset",
                          json={"confirmation_token": "bogus"})
    assert r.status_code == 400


def test_reset_rejects_non_owner_and_preserves_owner_token(brain_client):
    request = brain_client.post("/brain/reset")
    token = request.json()["confirmation_token"]

    denied = brain_client.post(
        "/brain/reset",
        json={"confirmation_token": token},
        headers={OWNER_HEADER: "B" * 44},
    )
    assert denied.status_code == 403

    accepted = brain_client.post(
        "/brain/reset",
        json={"confirmation_token": token},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "reset_complete"
