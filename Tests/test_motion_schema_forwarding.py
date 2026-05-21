"""Test: MotionData Pydantic-Schema gibt peak_motion durch (L-VIDEO-2 / M-4).

Regression-Test fuer den silent-drop Bug: Pydantic v2 ignoriert unbekannte
Felder per Default. MotionData(**motion) hat peak_motion verschluckt weil
das Feld im Schema fehlte. Backend computation war richtig, aber API liefert
peak_motion=0.0 statt der echten Spitze.

Fix: peak_motion in backend/schemas/video_schemas.py:MotionData hinzugefuegt.
"""

import pytest


def test_motion_data_schema_has_peak_motion_field():
    """Schema selbst muss peak_motion als Feld haben (kein silent-drop)."""
    from backend.schemas.video_schemas import MotionData

    md = MotionData(clip_id=1)
    assert hasattr(md, "peak_motion"), "MotionData schema fehlt peak_motion field"
    assert md.peak_motion == 0.0  # Default ist 0.0


def test_motion_data_accepts_and_serializes_peak_motion():
    """MotionData(**dict) muss peak_motion behalten, nicht silent droppen."""
    from backend.schemas.video_schemas import MotionData

    motion_dict = {
        "clip_id": 42,
        "avg_motion": 12.5,
        "peak_motion": 99.7,  # vorher silent gedropped
        "motion_curve": [1.0, 2.0, 99.7, 5.0],
        "peak_frames": [{"frame_index": 100, "confidence": 0.95}],
        "motion_category": "high",
    }
    md = MotionData(**motion_dict)
    assert md.peak_motion == pytest.approx(99.7), (
        "peak_motion wurde silent gedropped — L-VIDEO-2 regression!"
    )
    # JSON-Roundtrip — REST liefert die Daten so an die UI
    js = md.model_dump()
    assert "peak_motion" in js
    assert js["peak_motion"] == pytest.approx(99.7)


def test_motion_endpoint_forwards_peak_motion():
    """Integration: /video/motion/{id} liefert peak_motion an die UI durch.

    Nutzt FastAPI dependency_overrides um den AppState fuer den Route-Handler
    zu setzen — sonst sieht der Handler eine andere AppState-Instanz als der Test.
    """
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.app_state import AppState, get_app_state

    state = AppState()
    state.reset()

    # Cache-Eintrag manuell setzen — simuliert abgeschlossene Analyse
    state.video_clips[1] = {
        "id": 1, "name": "test.mp4", "path": "/fake/test.mp4",
        "duration_seconds": 10.0, "width": 1920, "height": 1080,
        "fps": 30.0, "codec": "h264", "thumbnail_available": False, "tags": [],
    }
    # /video/motion/{id} liest analysis.get("motion", {}) — also muss
    # die MotionData in einem nested "motion" key liegen
    # (so wie _run_video_analysis es im result dict baut).
    state.set_video_analysis(1, {
        "clip_id": 1,
        "scene_count": 0,
        "avg_motion": 12.5,
        "motion": {
            "clip_id": 1,
            "avg_motion": 12.5,
            "peak_motion": 99.7,
            "motion_curve": [1.0, 2.0, 99.7, 5.0],
            "peak_frames": [{"frame_index": 100, "confidence": 0.95}],
            "motion_category": "high",
        },
    })

    # Dependency-Override: Route-Handler bekommt unsere prepared state-Instanz
    app.dependency_overrides[get_app_state] = lambda: state
    try:
        client = TestClient(app)
        resp = client.get("/video/motion/1")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "peak_motion" in body, "REST-Endpoint /video/motion/{id} liefert kein peak_motion!"
        assert body["peak_motion"] == pytest.approx(99.7)
    finally:
        app.dependency_overrides.clear()
