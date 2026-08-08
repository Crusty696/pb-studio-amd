"""Regression-Test fuer P-C1 (Audit 2026-05-19):
render_router rief validate_timeline ohne audio_duration auf → Audio-Overflow-Check
übersprungen → User konnte Timeline > Audio rendern.

Fix: render_router.py:534 ruft jetzt validate_timeline(timeline, audio_duration=...).
"""
from __future__ import annotations

from backend.schemas.common import validate_timeline
from backend.routers.render_router import _finalize_timeline_for_render


def test_validate_timeline_with_audio_duration_blocks_overflow():
    """Timeline laenger als audio_duration MUSS Error werfen."""
    timeline = [
        {"clip_id": 1, "start_time": 0.0, "end_time": 30.0},
        {"clip_id": 2, "start_time": 30.0, "end_time": 65.0},
    ]
    warnings, errors = validate_timeline(timeline, audio_duration=60.0)
    assert any("audio" in e.lower() or "overflow" in e.lower() or "länger" in e.lower() or "exceed" in e.lower()
               for e in errors), \
        f"Audio-Overflow muss als Error markiert sein. Got errors={errors}, warnings={warnings}"


def test_validate_timeline_without_audio_duration_no_overflow_check():
    """Ohne audio_duration KEIN overflow-check (Fail-Soft) — vor Fix war das default."""
    timeline = [
        {"clip_id": 1, "start_time": 0.0, "end_time": 30.0},
        {"clip_id": 2, "start_time": 30.0, "end_time": 65.0},
    ]
    warnings, errors = validate_timeline(timeline)
    overflow_errors = [e for e in errors if "audio" in e.lower() or "overflow" in e.lower()]
    assert not overflow_errors, \
        f"Ohne audio_duration darf kein overflow-error kommen. Got: {overflow_errors}"


def test_validate_timeline_within_audio_duration_passes():
    """Timeline innerhalb audio_duration: kein error."""
    timeline = [
        {"clip_id": 1, "start_time": 0.0, "end_time": 30.0},
        {"clip_id": 2, "start_time": 30.0, "end_time": 60.0},
    ]
    warnings, errors = validate_timeline(timeline, audio_duration=60.0)
    overflow_errors = [e for e in errors if "audio" in e.lower() or "overflow" in e.lower()]
    assert not overflow_errors, f"Timeline == audio_duration darf kein overflow. errors={errors}"


def test_render_snapshot_uses_canonical_full_length_finalization():
    original = [
        {
            "clip_id": "a",
            "start_time": 1.927,
            "end_time": 3.0,
            "metadata": {"clip_start": 2.5, "file_path": "a.mp4"},
        },
        {
            "clip_id": "b",
            "start_time": 3.0,
            "end_time": 9.5,
            "metadata": {"clip_start": 1.0, "file_path": "b.mp4"},
        },
    ]

    finalized = _finalize_timeline_for_render(original, 10.0)

    assert original[0]["start_time"] == 1.927
    assert original[-1]["end_time"] == 9.5
    assert finalized[0]["start_time"] == 0.0
    assert finalized[0]["metadata"]["clip_start"] == 0.573
    assert finalized[0]["metadata"]["boundary_original_start"] == 1.927
    assert finalized[-1]["end_time"] == 10.0
    assert finalized[-1]["metadata"]["boundary_original_end"] == 9.5
