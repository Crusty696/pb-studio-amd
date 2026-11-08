import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.main import app


@pytest.fixture(autouse=True)
def active_project(tmp_path):
    from backend.app_state import get_app_state
    state = get_app_state()
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    state.current_project = {"db_project_id": 1, "path": str(proj_dir), "name": "proj"}
    yield
    state.current_project = None


def test_clipwave_returns_peaks(monkeypatch):
    client = TestClient(app)
    fake_clip = {"id": 1, "path": "/x.mp4", "duration_seconds": 10.0}
    from backend.app_state import AppState
    monkeypatch.setattr(AppState, "get_video_clip",
                        lambda self, cid: fake_clip if cid == 1 else None)

    with patch("backend.routers.video_router._extract_clip_peaks",
               return_value=[0.1, 0.5, 0.9, 0.5, 0.1]):
        resp = client.get("/video/clipwave/1?n=5")

    assert resp.status_code == 200
    body = resp.json()
    assert body["clip_id"] == 1
    assert body["peaks"] == [0.1, 0.5, 0.9, 0.5, 0.1]
    assert body["count"] == 5


def test_clipwave_404_unknown(monkeypatch):
    client = TestClient(app)
    from backend.app_state import AppState
    monkeypatch.setattr(AppState, "get_video_clip", lambda self, cid: None)
    resp = client.get("/video/clipwave/99?n=64")
    assert resp.status_code == 404


def test_clipwave_n_clamped(monkeypatch):
    client = TestClient(app)
    fake_clip = {"id": 1, "path": "/x.mp4", "duration_seconds": 10.0}
    from backend.app_state import AppState
    monkeypatch.setattr(AppState, "get_video_clip", lambda self, cid: fake_clip)

    captured = {}
    def fake(path, n):
        captured["n"] = n
        return [0.0] * n
    with patch("backend.routers.video_router._extract_clip_peaks", side_effect=fake):
        client.get("/video/clipwave/1?n=99999")
    assert captured["n"] == 2048
