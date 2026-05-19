"""GET /video/thumbstrip/{clip_id} liefert n base64-Frames + duration."""
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from backend.main import app


def test_thumbstrip_returns_n_base64_frames(monkeypatch):
    client = TestClient(app)

    # Mock AppState video clip
    fake_clip = {"id": 1, "path": "/x.mp4", "duration_seconds": 30.0}
    from backend.app_state import AppState
    monkeypatch.setattr(AppState, "get_video_clip",
                        lambda self, cid: fake_clip if cid == 1 else None)

    # Mock FrameGrabber to return 6 small PIL images
    from PIL import Image
    fake_frames = [Image.new("RGB", (160, 90), color=(i * 30, 0, 0)) for i in range(6)]
    with patch("backend.routers.video_router._extract_thumbstrip", return_value=fake_frames):
        resp = client.get("/video/thumbstrip/1?n=6")

    assert resp.status_code == 200
    body = resp.json()
    assert "frames" in body
    assert len(body["frames"]) == 6
    assert all(f.startswith("data:image/jpeg;base64,") for f in body["frames"])
    assert body["count"] == 6


def test_thumbstrip_404_unknown_clip(monkeypatch):
    client = TestClient(app)
    from backend.app_state import AppState
    monkeypatch.setattr(AppState, "get_video_clip", lambda self, cid: None)
    resp = client.get("/video/thumbstrip/999?n=6")
    assert resp.status_code == 404


def test_thumbstrip_n_clamped_to_safe_range(monkeypatch):
    """n is clamped to [1,32] to prevent abuse."""
    client = TestClient(app)
    fake_clip = {"id": 1, "path": "/x.mp4", "duration_seconds": 30.0}
    from backend.app_state import AppState
    monkeypatch.setattr(AppState, "get_video_clip", lambda self, cid: fake_clip)

    captured = {}
    def fake_extract(path, n, size):
        captured["n"] = n
        from PIL import Image
        return [Image.new("RGB", (160, 90)) for _ in range(n)]
    with patch("backend.routers.video_router._extract_thumbstrip", side_effect=fake_extract):
        resp = client.get("/video/thumbstrip/1?n=999")
    assert resp.status_code == 200
    assert captured["n"] == 32  # clamped
