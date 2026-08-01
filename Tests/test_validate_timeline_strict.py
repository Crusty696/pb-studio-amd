"""Test L-TI-5: validate_timeline strict mode.

Audit Timeline-Integrity L-TI-5: Overlapping cuts und Audio-Overflow waren
zuvor nur Warnings. User konnte fehlerhafte Timelines rendern. Jetzt fuehren
beide Faelle zu errors[] und damit zu HTTP 400 in den drei Validation-
Pfaden (Auto-Generate, Manuell-Update, Pre-Render).

Die public API von validate_timeline bleibt als Tuple (warnings, errors)
erhalten, damit project_router (das die Liste nur logged) weiterhin
funktioniert.
"""

import pytest


# --- Unit Tests: validate_timeline direkt ---------------------------------

def test_validate_blocks_overlapping_cuts():
    """Overlap > 10ms muss in errors, nicht in warnings landen."""
    from backend.schemas.common import validate_timeline
    entries = [
        {
            "start_time": 0.0,
            "end_time": 5.0,
            "clip_id": "clip_1",
            "metadata": {"file_path": "/tmp/a.mp4"},
        },
        {
            "start_time": 3.0,  # overlap mit prev (cur_end=5.0 > 3.0)
            "end_time": 8.0,
            "clip_id": "clip_2",
            "metadata": {"file_path": "/tmp/b.mp4"},
        },
    ]
    warnings, errors = validate_timeline(entries, audio_duration=60.0)
    assert any("berlapp" in e or "verlapp" in e or "verlap" in e for e in errors), (
        f"L-TI-5: Overlap muss als Error gemeldet werden, errors={errors}"
    )


def test_validate_blocks_audio_overflow():
    """Timeline-Ende > audio_duration+0.5 muss in errors landen."""
    from backend.schemas.common import validate_timeline
    entries = [
        {
            "start_time": 0.0,
            "end_time": 100.0,
            "clip_id": "clip_1",
            "metadata": {"file_path": "/tmp/a.mp4"},
        },
    ]
    warnings, errors = validate_timeline(entries, audio_duration=60.0)
    assert any("Audio" in e or "audio" in e for e in errors), (
        f"L-TI-5: Audio-Overflow muss als Error gemeldet werden, errors={errors}"
    )


def test_validate_passes_good_timeline():
    """Korrekte non-overlapping Timeline darf KEINE errors haben."""
    from backend.schemas.common import validate_timeline
    entries = [
        {
            "start_time": 0.0,
            "end_time": 5.0,
            "clip_id": "clip_1",
            "metadata": {"file_path": "/tmp/a.mp4"},
        },
        {
            "start_time": 5.0,
            "end_time": 10.0,
            "clip_id": "clip_2",
            "metadata": {"file_path": "/tmp/b.mp4"},
        },
    ]
    warnings, errors = validate_timeline(entries, audio_duration=60.0)
    assert errors == [], f"Saubere Timeline darf keine Errors haben, errors={errors}"


def test_validate_overlap_below_tolerance_no_error():
    """Sub-Millisekunden-Overlap (Float-Drift) bleibt unter der Toleranz."""
    from backend.schemas.common import validate_timeline
    entries = [
        {
            "start_time": 0.0,
            "end_time": 5.0,
            "clip_id": "clip_1",
            "metadata": {"file_path": "/tmp/a.mp4"},
        },
        # 5.0000000001 < 5.0 by 1e-10 — Float-Noise, kein echter Overlap.
        {
            "start_time": 4.9999999999,
            "end_time": 10.0,
            "clip_id": "clip_2",
            "metadata": {"file_path": "/tmp/b.mp4"},
        },
    ]
    warnings, errors = validate_timeline(entries, audio_duration=60.0)
    # 0.1ms Drift soll keinen Error (auch keine Warning) triggern.
    assert errors == [], f"Sub-Tolerance darf nicht Error werden: {errors}"


def test_validate_audio_overflow_below_tolerance_no_error():
    """Bei 0.5s Tolerance unter dem Cutoff bleibt es sauber."""
    from backend.schemas.common import validate_timeline
    entries = [
        {
            "start_time": 0.0,
            "end_time": 60.3,  # 0.3s ueber 60.0 — unter 0.5s Tolerance
            "clip_id": "clip_1",
            "metadata": {"file_path": "/tmp/a.mp4"},
        },
    ]
    warnings, errors = validate_timeline(entries, audio_duration=60.0)
    assert errors == [], f"Innerhalb der Tolerance kein Error: {errors}"


def test_validate_end_lte_start_still_error():
    """Bestehende Pruefung end<=start bleibt erhalten (Regression)."""
    from backend.schemas.common import validate_timeline
    entries = [
        {
            "start_time": 5.0,
            "end_time": 5.0,
            "clip_id": "clip_1",
            "metadata": {"file_path": "/tmp/a.mp4"},
        },
    ]
    warnings, errors = validate_timeline(entries)
    assert any("end_time" in e for e in errors), (
        f"Regression: end<=start muss Error bleiben, errors={errors}"
    )


# --- Integration Tests: HTTP 400 in den drei Pfaden -----------------------

def test_post_timeline_returns_400_on_overlap(monkeypatch, tmp_path):
    """POST /pacing/timeline mit overlap-entries → HTTP 400."""
    from fastapi.testclient import TestClient

    monkeypatch.setattr(
        "pb_studio.rendering.render_service.RenderService._get_audio_duration",
        lambda self, p: 60.0,
        raising=False,
    )

    from backend.main import app
    from backend.app_state import get_app_state

    state = get_app_state()
    state.reset()
    state.current_project = {
        "name": "TimelineTest",
        "path": str(tmp_path),
        "db_project_id": 1,
    }
    state.current_audio_path = "/tmp/audio.wav"
    for vid in (30, 31):
        state.set_video_clip(
            vid,
            {
                "id": vid,
                "name": f"v{vid}",
                "path": f"/tmp/v{vid}.mp4",
                "duration_seconds": 60.0,
            },
        )

    client = TestClient(app)
    payload = {
        "entries": [
            {
                "clip_id": "clip_30",
                "clip_name": "v30",
                "file_path": "/tmp/v30.mp4",
                "start_time": 0.0,
                "end_time": 5.0,
                "clip_start": 0.0,
                "trigger_type": "beat",
                "trigger_strength": 0.5,
            },
            {
                "clip_id": "clip_31",
                "clip_name": "v31",
                "file_path": "/tmp/v31.mp4",
                "start_time": 3.0,  # overlap mit prev cut (0..5)
                "end_time": 8.0,
                "clip_start": 0.0,
                "trigger_type": "beat",
                "trigger_strength": 0.5,
            },
        ]
    }
    resp = client.post("/pacing/timeline", json=payload)
    assert resp.status_code == 400, (
        f"L-TI-5: Overlap muss HTTP 400 erzeugen, got {resp.status_code}: {resp.text}"
    )
    state.reset()


def test_post_timeline_returns_400_on_audio_overflow(monkeypatch, tmp_path):
    """POST /pacing/timeline mit timeline > audio_duration → HTTP 400."""
    from fastapi.testclient import TestClient

    monkeypatch.setattr(
        "pb_studio.rendering.render_service.RenderService._get_audio_duration",
        lambda self, p: 10.0,  # nur 10s Audio
        raising=False,
    )

    from backend.main import app
    from backend.app_state import get_app_state

    state = get_app_state()
    state.reset()
    state.current_project = {
        "name": "TimelineTest",
        "path": str(tmp_path),
        "db_project_id": 1,
    }
    state.current_audio_path = "/tmp/audio.wav"
    state.set_video_clip(
        40,
        {
            "id": 40,
            "name": "v40",
            "path": "/tmp/v40.mp4",
            "duration_seconds": 100.0,
        },
    )

    client = TestClient(app)
    payload = {
        "entries": [
            {
                "clip_id": "clip_40",
                "clip_name": "v40",
                "file_path": "/tmp/v40.mp4",
                "start_time": 0.0,
                "end_time": 50.0,  # Timeline 50s, Audio nur 10s
                "clip_start": 0.0,
                "trigger_type": "beat",
                "trigger_strength": 0.5,
            },
        ]
    }
    resp = client.post("/pacing/timeline", json=payload)
    assert resp.status_code == 400, (
        f"L-TI-5: Audio-Overflow muss HTTP 400 erzeugen, "
        f"got {resp.status_code}: {resp.text}"
    )
    state.reset()
