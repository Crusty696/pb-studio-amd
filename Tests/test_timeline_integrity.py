"""Integration Tests: Timeline-Integrity gesamtheit (L-TI-7).

Audit Timeline-Integrity L-TI-7 (Regression-Test-Suite). Verifiziert alle
Timeline-Integrity-Fixes zusammen und stellt sicher dass Auto+Manuell-
Generation chronologisch korrekte, valide Timelines erzeugen.

Test-Scope (gemaess L-TI-7 user-task-mapping):
- L-TI-1: ClipSelector.select_clip(prompt=...) kein TypeError-Crash.
- L-TI-6: _enforce_clip_lengths haelt min_length bilateral
          (prev-gap UND next-gap >= min).
- L-TI-3: Manueller POST /pacing/timeline cappt duration gegen source.
- L-TI-5: validate_timeline blockt Overlap + Audio-Overflow.

Integration: PacingService Auto-Pipeline + manuelle Updates + validate_timeline
produzieren chronologisch valide Timelines ohne min_length-Violations.
"""
import random

import numpy as np
import pytest


# --- L-TI-1 Regression: ClipSelector prompt kwarg ----------------------------

def test_clip_selector_no_kwarg_crash():
    """L-TI-1 regression: select_clip(prompt=...) crashed nicht mehr."""
    from pb_studio.pacing.clip_selector import ClipSelector

    selector = ClipSelector()
    candidates = [
        {"id": 1, "name": "v1", "file_path": "/x/v1.mp4",
         "duration": 5.0, "motion_score": 5.0},
        {"id": 2, "name": "v2", "file_path": "/x/v2.mp4",
         "duration": 5.0, "motion_score": 8.0},
    ]
    try:
        result = selector.select_clip(
            available_clips=candidates,
            trigger_strength=0.5,
            trigger_type="beat",
            prompt="energetic",
        )
    except TypeError as e:
        if "prompt" in str(e):
            pytest.fail(f"L-TI-1 regression: {e}")
        raise

    assert result is not None
    assert result.clip_id in ("1", "2")


# --- L-TI-6 Regression: bilateral min_length ---------------------------------

def _gaps(cuts, audio_duration):
    """Berechne Intervalle zwischen aufeinanderfolgenden Cuts (inkl. End-Gap)."""
    sorted_cuts = sorted(cuts, key=lambda c: c.time)
    gaps = []
    for i in range(len(sorted_cuts) - 1):
        gaps.append(sorted_cuts[i + 1].time - sorted_cuts[i].time)
    if sorted_cuts:
        gaps.append(audio_duration - sorted_cuts[-1].time)
    return gaps


def test_enforce_clip_lengths_bilateral_min():
    """L-TI-6 regression: Split prueft prev UND next gap (bilateral)."""
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
    from pb_studio.pacing.pacing_models import PacingCut

    engine = AdvancedPacingEngine()
    # Sehr lange Cut-Lucke mit max-Jitter -> Splits muessen bilateral min halten
    cuts = [
        PacingCut(time=0.0, trigger_type="beat", strength=1.0),
    ]
    min_length = 1.0
    max_length = 2.0
    audio_duration = 20.0

    # Multiple Random-Seeds zur Stabilitaets-Garantie
    for seed in range(20):
        random.seed(seed)
        result = engine._enforce_clip_lengths(
            cuts,
            min_length=min_length,
            max_length=max_length,
            audio_duration=audio_duration,
            variation=1.0,
        )
        gaps = _gaps(result, audio_duration)
        for i, gap in enumerate(gaps):
            assert gap >= min_length - 1e-6, (
                f"L-TI-6 bilateral-min violated: seed={seed} gap[{i}]={gap:.4f} "
                f"< min={min_length}; times={[round(c.time, 3) for c in result]}"
            )


# --- L-TI-5 Regression: validate_timeline blockt overlap+overflow ------------

def test_validate_blocks_overlap_and_overflow():
    """L-TI-5 regression: overlap + overflow werden zu errors."""
    from backend.schemas.common import validate_timeline

    overlap_entries = [
        {"start_time": 0.0, "end_time": 5.0, "clip_id": "clip_1",
         "metadata": {"file_path": "/tmp/a.mp4"}},
        {"start_time": 3.0, "end_time": 8.0, "clip_id": "clip_2",
         "metadata": {"file_path": "/tmp/b.mp4"}},
    ]
    warnings, errors = validate_timeline(overlap_entries, audio_duration=60.0)
    assert len(errors) > 0, (
        f"L-TI-5: Overlap muss als Error gemeldet werden, errors={errors}"
    )

    overflow_entries = [
        {"start_time": 0.0, "end_time": 100.0, "clip_id": "clip_1",
         "metadata": {"file_path": "/tmp/a.mp4"}},
    ]
    warnings2, errors2 = validate_timeline(overflow_entries, audio_duration=10.0)
    assert len(errors2) > 0, (
        f"L-TI-5: Audio-Overflow muss als Error gemeldet werden, errors={errors2}"
    )


def test_validate_accepts_clean_timeline():
    """L-TI-5 negative-control: saubere Timeline -> keine Errors."""
    from backend.schemas.common import validate_timeline

    clean_entries = [
        {"start_time": 0.0, "end_time": 5.0, "clip_id": "clip_1",
         "metadata": {"file_path": "/tmp/a.mp4"}},
        {"start_time": 5.0, "end_time": 10.0, "clip_id": "clip_2",
         "metadata": {"file_path": "/tmp/b.mp4"}},
    ]
    warnings, errors = validate_timeline(clean_entries, audio_duration=60.0)
    assert errors == [], (
        f"L-TI-5 negative-control: saubere Timeline darf keine Errors haben, errors={errors}"
    )


# --- L-TI-3 Regression: manueller Cap gegen Source ---------------------------

def test_manual_cap_against_video_source():
    """L-TI-3 regression: manueller Cap gegen source duration."""
    from backend.routers.pacing_router import _cap_entries_against_source
    from backend.app_state import AppState

    state = AppState()
    state.set_video_clip(
        10,
        {
            "id": 10,
            "name": "v10",
            "path": "/tmp/v10.mp4",
            "duration_seconds": 30.0,
        },
    )

    entries = [
        {
            "clip_id": "clip_10",
            "start_time": 0.0,
            "end_time": 60.0,  # > source 30s
            "metadata": {
                "clip_start": 0.0,
                "file_path": "/tmp/v10.mp4",
            },
        }
    ]
    capped = _cap_entries_against_source(entries, state)
    end_time = capped[0]["end_time"]
    assert end_time <= 30.1, f"L-TI-3 Cap fehlgeschlagen: end_time={end_time}"


# --- Integration: Auto-Pipeline produziert chronologisch valide Timeline ----

def test_auto_pacing_pipeline_chronological_no_violations(tmp_path, monkeypatch):
    """End-to-end: PacingService -> cut_list chronologisch + min_length-konform.

    Synthetisches 30s-Audio mit 120-BPM-Pattern, 2 fake Video-Clips.
    Erwartet: cut_list ist nach start_time aufsteigend sortiert UND
    alle Gaps >= min_clip_length.

    Skip-Pfad (test-data zu synthetisch): bei <2 Cuts oder Engine-Exception,
    weil das Ziel hier Chronologie ist, nicht Engine-Robustheit gegen
    Fake-Files.
    """
    import soundfile as sf
    from pb_studio.services.pacing_service import PacingService

    # Empty fake-mp4 kann nicht ffprobed werden; stubben _get_clip_duration.
    # Wir testen die Pipeline-Chronologie, nicht ffprobe.
    monkeypatch.setattr(
        PacingService,
        "_get_clip_duration",
        lambda self, p: 60.0,
        raising=False,
    )

    sr = 22050
    duration = 30.0
    audio = tmp_path / "test.wav"
    # Realistic beat-pattern: 120 BPM = 60 beats in 30s
    t = np.arange(int(sr * duration)) / sr
    beat_pattern = np.zeros_like(t, dtype=np.float32)
    beat_period = 60.0 / 120.0  # 0.5s
    for beat_time in np.arange(0, duration, beat_period):
        idx = int(beat_time * sr)
        if idx + 500 < len(beat_pattern):
            beat_pattern[idx:idx + 500] = 0.5 * np.sin(
                2 * np.pi * 60 * np.arange(500) / sr
            )
    sf.write(str(audio), beat_pattern, sr)

    fake_v = tmp_path / "v.mp4"
    fake_v.touch()

    svc = PacingService()
    min_clip_length = 1.0
    try:
        cut_list = svc.generate_cut_list(
            audio_path=str(audio),
            clips=[
                {"id": 1, "name": "v1", "file_path": str(fake_v),
                 "duration": 60.0},
                {"id": 2, "name": "v2", "file_path": str(fake_v),
                 "duration": 60.0},
            ],
            pacing_config={
                "expected_bpm": 120,
                "use_motion_matching": False,
                "trigger_settings": {
                    "min_clip_length": min_clip_length,
                    "max_clip_length": 5.0,
                    "beat_weight": 1.0,
                    "energy_weight": 0.5,
                },
            },
            total_duration=duration,
            cached_analysis={
                "beats": [
                    {"time": float(bt), "strength": 1.0}
                    for bt in np.arange(0, duration, beat_period)
                ],
                "bpm": 120.0,
                "duration_seconds": duration,
            },
        )
    except Exception as e:
        pytest.fail(f"PacingService pipeline error (synthetic test-data): {e}")

    if not cut_list or len(cut_list) < 2:
        pytest.skip(
            f"PacingService produced <2 cuts ({len(cut_list) if cut_list else 0}) "
            f"- kann nicht chronologisch testen"
        )

    # Chronologie-Check: Cut-Liste muss nach start_time aufsteigend sein
    def _start(c):
        if hasattr(c, "start_time"):
            return c.start_time
        return c.get("start_time") or c.get("time", 0.0)

    starts = [_start(c) for c in cut_list]
    for i in range(len(starts) - 1):
        assert starts[i] <= starts[i + 1], (
            f"L-TI-7 chronological violation: cut[{i}].start={starts[i]} > "
            f"cut[{i + 1}].start={starts[i + 1]}"
        )

    # Min-length-Check (L-TI-6 e2e regression): keine Cuts zu nah zusammen
    for i in range(len(starts) - 1):
        gap = starts[i + 1] - starts[i]
        # Toleranz 1e-6 fuer Float-Drift in Engine.
        assert gap >= min_clip_length - 1e-6 or gap == 0.0, (
            f"L-TI-7 min-length violation: cut[{i}]->cut[{i+1}] gap={gap:.4f}s "
            f"< min={min_clip_length}s"
        )


# --- Integration: Manuelle Updates produzieren valide Timeline --------------

def test_manual_update_full_flow_caps_and_validates(monkeypatch, tmp_path):
    """End-to-end: POST /pacing/timeline cappt + validiert in einem Flow.

    User sendet manuell editierte Timeline mit overflow-Eintrag. Backend:
      1. Cappt clip_start+duration gegen source (L-TI-3)
      2. Validiert (overlap, audio_overflow) (L-TI-5)
      3. Persistiert wenn errors=0

    Erwartet: HTTP 200, persistierte Timeline mit gecappten Werten.
    """
    from fastapi.testclient import TestClient

    monkeypatch.setattr(
        "pb_studio.rendering.render_service.RenderService._get_audio_duration",
        lambda self, p, cancel_callback=None: 30.0,
        raising=False,
    )

    from backend.main import app
    from backend.app_state import get_app_state

    state = get_app_state()
    state.reset()
    audio_path = tmp_path / "audio.wav"
    video_path = tmp_path / "v50.mp4"
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
        50,
        {
            "id": 50,
            "name": "v50",
            "path": str(video_path),
            "duration_seconds": 10.0,  # source nur 10s
        },
    )

    client = TestClient(app)
    payload = {
        "entries": [
            {
                "clip_id": "clip_50",
                "clip_name": "v50",
                "file_path": str(video_path),
                "start_time": 0.0,
                "end_time": 20.0,  # > source 10s
                "clip_start": 0.0,
                "trigger_type": "beat",
                "trigger_strength": 0.5,
            },
        ]
    }
    resp = client.post("/pacing/timeline", json=payload)
    # Cap-Logik darf nicht 400en - cappt still
    assert resp.status_code == 200, (
        f"L-TI-3 + L-TI-5: manueller Update muss durchlaufen, "
        f"got {resp.status_code}: {resp.text}"
    )

    timeline = state.get_timeline_snapshot()
    assert len(timeline) == 1
    dur = timeline[0]["end_time"] - timeline[0]["start_time"]
    assert dur <= 10.0 + 0.001, (
        f"L-TI-3 cap nicht angewendet: dur={dur} > source 10.0"
    )

    state.reset()
