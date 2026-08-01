"""Test L-TI-3: POST /pacing/timeline cappt clip_start+duration gegen Source.

Audit Timeline-Integrity L-TI-3: Der manuelle Update-Endpoint hatte keinen
ffprobe-Cap. User konnte via Drag eine Dauer setzen die ueber source_duration
hinausgeht -> Render produzierte truncated frames / crash. Cap-Logik aus dem
Auto-Pfad (R12b/SEV-004 in pacing_service._process_pacing_cuts_to_cutlist)
wird im update_timeline-Endpoint repliziert.
"""

import pytest


def _make_state_with_video(video_id: int, duration_seconds: float):
    """Erzeugt einen frischen AppState mit einem einzelnen Video-Clip."""
    from backend.app_state import AppState
    state = AppState()
    state.set_video_clip(
        video_id,
        {
            "id": video_id,
            "name": f"v{video_id}",
            "path": f"/tmp/v{video_id}.mp4",
            "duration_seconds": duration_seconds,
        },
    )
    return state


def test_cap_entries_caps_duration_against_source():
    """duration > source_duration wird auf available gecappt."""
    from backend.routers.pacing_router import _cap_entries_against_source

    state = _make_state_with_video(video_id=10, duration_seconds=30.0)

    entries = [
        {
            "clip_id": "clip_10",
            "start_time": 0.0,
            "end_time": 60.0,  # 60s requested
            "metadata": {
                "clip_start": 0.0,
                "file_path": "/tmp/v10.mp4",
                "clip_name": "v10",
            },
        }
    ]
    capped = _cap_entries_against_source(entries, state)
    # duration = end_time - start_time muss <= source_duration sein
    duration = capped[0]["end_time"] - capped[0]["start_time"]
    assert duration <= 30.0, f"L-TI-3 cap missed: duration {duration} > 30s"


def test_cap_entries_caps_clip_start_overflow():
    """clip_start > source_duration wird zurueckgeschoben."""
    from backend.routers.pacing_router import _cap_entries_against_source

    state = _make_state_with_video(video_id=11, duration_seconds=20.0)

    entries = [
        {
            "clip_id": "clip_11",
            "start_time": 0.0,
            "end_time": 5.0,
            "metadata": {
                "clip_start": 999.0,  # weit ueber source
                "file_path": "/tmp/v11.mp4",
                "clip_name": "v11",
            },
        }
    ]
    capped = _cap_entries_against_source(entries, state)
    # clip_start im metadata muss <= source-duration sein
    new_clip_start = capped[0]["metadata"]["clip_start"]
    assert new_clip_start <= 20.0, (
        f"L-TI-3 clip_start cap missed: {new_clip_start} > source 20.0"
    )
    # Available range nach Cap = source - clip_start, muss >= 0 sein
    assert new_clip_start >= 0.0


def test_cap_entries_caps_clip_start_plus_duration():
    """clip_start + duration > source_duration wird gecappt."""
    from backend.routers.pacing_router import _cap_entries_against_source

    state = _make_state_with_video(video_id=12, duration_seconds=40.0)

    # clip_start = 30s, requested duration = 20s -> bound at 30+20=50 > 40
    entries = [
        {
            "clip_id": "clip_12",
            "start_time": 0.0,
            "end_time": 20.0,  # duration 20s
            "metadata": {
                "clip_start": 30.0,
                "file_path": "/tmp/v12.mp4",
                "clip_name": "v12",
            },
        }
    ]
    capped = _cap_entries_against_source(entries, state)
    new_duration = capped[0]["end_time"] - capped[0]["start_time"]
    new_clip_start = capped[0]["metadata"]["clip_start"]
    # In-Point + Cut-Length darf source_duration nicht ueberschreiten
    assert new_clip_start + new_duration <= 40.0 + 0.001, (
        f"L-TI-3 overflow: clip_start ({new_clip_start}) + duration "
        f"({new_duration}) > source 40.0"
    )


def test_cap_entries_leaves_valid_entries_untouched():
    """Korrekte entries werden NICHT modifiziert."""
    from backend.routers.pacing_router import _cap_entries_against_source

    state = _make_state_with_video(video_id=13, duration_seconds=60.0)

    entries = [
        {
            "clip_id": "clip_13",
            "start_time": 0.0,
            "end_time": 10.0,  # duration 10s
            "metadata": {
                "clip_start": 5.0,  # ends at 15s, source 60s
                "file_path": "/tmp/v13.mp4",
                "clip_name": "v13",
            },
        }
    ]
    capped = _cap_entries_against_source(entries, state)
    # nichts darf sich aendern
    assert capped[0]["end_time"] == 10.0
    assert capped[0]["start_time"] == 0.0
    assert capped[0]["metadata"]["clip_start"] == 5.0


def test_cap_entries_handles_unknown_clip_id():
    """clip_id ohne passenden Video-Clip im State -> entry bleibt unveraendert."""
    from backend.routers.pacing_router import _cap_entries_against_source
    from backend.app_state import AppState

    state = AppState()
    # KEIN Video-Clip registriert
    entries = [
        {
            "clip_id": "clip_99",
            "start_time": 0.0,
            "end_time": 100.0,
            "metadata": {"clip_start": 0.0, "file_path": "/tmp/unknown.mp4"},
        }
    ]
    capped = _cap_entries_against_source(entries, state)
    # Unmodified (kein Crash, aber auch kein Cap moeglich)
    assert capped[0]["end_time"] == 100.0


def test_cap_entries_handles_zero_source_duration():
    """source_duration <= 0 -> kein Cap (nicht crashen)."""
    from backend.routers.pacing_router import _cap_entries_against_source

    state = _make_state_with_video(video_id=14, duration_seconds=0.0)

    entries = [
        {
            "clip_id": "clip_14",
            "start_time": 0.0,
            "end_time": 100.0,
            "metadata": {"clip_start": 0.0, "file_path": "/tmp/v14.mp4"},
        }
    ]
    capped = _cap_entries_against_source(entries, state)
    # Nicht gecappt (kein Source-Wissen verfuegbar)
    assert capped[0]["end_time"] == 100.0


def test_cap_entries_via_fastapi_update_timeline(monkeypatch, tmp_path):
    """End-to-end: POST /pacing/timeline cappt overflow entries."""
    from fastapi.testclient import TestClient

    # Audio-Duration probe stubben (ohne ffprobe)
    monkeypatch.setattr(
        "pb_studio.rendering.render_service.RenderService._get_audio_duration",
        lambda self, p, cancel_callback=None: 30.0,
        raising=False,
    )

    from backend.main import app
    from backend.app_state import get_app_state

    state = get_app_state()
    state.reset()
    state.current_project = {
        "name": "PacingTest",
        "path": str(tmp_path),
        "db_project_id": 1,
    }
    audio_path = tmp_path / "audio.wav"
    video_path = tmp_path / "v20.mp4"
    audio_path.write_bytes(b"audio")
    video_path.write_bytes(b"video")
    state.current_audio_path = str(audio_path)
    state.set_audio_clip(
        1,
        {
            "id": 1,
            "name": "audio",
            "path": str(audio_path),
            "duration_seconds": 30.0,
        },
    )
    state.set_video_clip(
        20,
        {
            "id": 20,
            "name": "v20",
            "path": str(video_path),
            "duration_seconds": 15.0,
        },
    )

    client = TestClient(app)
    payload = {
        "entries": [
            {
                "clip_id": "clip_20",
                "clip_name": "v20",
                "file_path": str(video_path),
                "start_time": 0.0,
                "end_time": 25.0,  # 25s > source 15s
                "clip_start": 0.0,
                "trigger_type": "beat",
                "trigger_strength": 0.5,
            }
        ]
    }
    resp = client.post("/pacing/timeline", json=payload)
    # cap-Logik darf NICHT 400en — sie cappt still und persistiert.
    assert resp.status_code == 200, f"Body: {resp.text}"

    # Persistierte timeline pruefen: duration <= 15s
    timeline = state.get_timeline_snapshot()
    assert len(timeline) == 1
    dur = timeline[0]["end_time"] - timeline[0]["start_time"]
    assert dur <= 15.0 + 0.001, f"L-TI-3 cap not applied via API: dur={dur}"

    # Cleanup
    state.reset()
