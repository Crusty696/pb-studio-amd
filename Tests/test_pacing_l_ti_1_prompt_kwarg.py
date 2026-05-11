"""Test L-TI-1: select_clip akzeptiert prompt kwarg ohne Crash.

Regression-Test fuer den kritischen Bug, dass pacing_service.py
clip_selector.select_clip(prompt=...) aufruft, die Signatur den Kwarg aber
nicht kennt. Folge live: 4x TypeError in backend.log -> Round-Robin-Fallback
mit 14 Cuts statt 2184 (Struktur+Semantic verloren).
"""
import pytest


def test_select_clip_accepts_prompt_kwarg():
    """L-TI-1 regression: kein TypeError mehr bei prompt= kwarg."""
    from pb_studio.pacing.clip_selector import ClipSelector
    selector = ClipSelector()
    candidates = [
        {"id": 1, "name": "v1", "file_path": "/x/v1.mp4",
         "duration": 5.0, "motion_score": 5.0},
        {"id": 2, "name": "v2", "file_path": "/x/v2.mp4",
         "duration": 5.0, "motion_score": 10.0},
    ]
    # MUST NOT raise TypeError
    result = selector.select_clip(
        available_clips=candidates,
        trigger_strength=0.5,
        trigger_type="beat",
        prompt="energetic",
    )
    assert result is not None
    assert result.clip_id in ("1", "2")


def test_select_clip_without_prompt_still_works():
    """Backward-compat: alte Aufrufe ohne prompt funktionieren weiter."""
    from pb_studio.pacing.clip_selector import ClipSelector
    selector = ClipSelector()
    candidates = [{"id": 1, "file_path": "/x/v1.mp4",
                   "duration": 5.0, "motion_score": 5.0}]
    result = selector.select_clip(
        available_clips=candidates,
        trigger_strength=0.5,
        trigger_type="beat",
    )
    assert result is not None
    assert result.clip_id == "1"


def test_select_clip_prompt_with_none_is_safe():
    """prompt=None ist semantisch identisch zu 'kein prompt'."""
    from pb_studio.pacing.clip_selector import ClipSelector
    selector = ClipSelector()
    candidates = [{"id": 7, "file_path": "/x/v7.mp4",
                   "duration": 5.0, "motion_score": 5.0}]
    # prompt=None darf nicht crashen, nicht in semantic Pfad
    result = selector.select_clip(
        available_clips=candidates,
        trigger_strength=0.4,
        trigger_type="beat",
        prompt=None,
    )
    assert result is not None
    assert result.clip_id == "7"


def test_pacing_service_semantic_path_no_crash(tmp_path, caplog):
    """End-to-end: semantic_matching=True crashes nicht mehr mit prompt-TypeError.

    Wir verifizieren primaer: KEIN TypeError mit 'prompt' im Aufruf von
    select_clip. Wenn die Engine wegen fehlender ffprobe-Daten zum Fake-Video
    einen anderen Fehlertyp wirft, ist das fuer L-TI-1 irrelevant.
    """
    import logging
    import numpy as np
    import soundfile as sf
    audio = tmp_path / "t.wav"
    sf.write(str(audio), np.zeros(22050 * 3, dtype=np.float32), 22050)
    fake_v = tmp_path / "v.mp4"
    fake_v.touch()

    from pb_studio.services.pacing_service import PacingService
    svc = PacingService()
    caplog.set_level(logging.ERROR, logger="pb_studio.services.pacing_service")
    try:
        svc.generate_cut_list(
            audio_path=str(audio),
            clips=[
                {"id": 1, "name": "v1", "file_path": str(fake_v),
                 "duration": 5.0, "tags": ["energy"]},
                {"id": 2, "name": "v2", "file_path": str(fake_v),
                 "duration": 5.0, "tags": ["calm"]},
            ],
            pacing_config={
                "expected_bpm": 120,
                "use_semantic_matching": True,
                "trigger_settings": {
                    "min_clip_length": 1.0, "max_clip_length": 8.0,
                },
            },
            total_duration=3.0,
            cached_analysis={
                "beats": [{"time": 1.0, "strength": 1.0},
                          {"time": 2.0, "strength": 1.0}],
                "bpm": 120.0,
                "duration_seconds": 3.0,
            },
        )
    except TypeError as e:
        if "prompt" in str(e):
            pytest.fail(f"L-TI-1 regression (raised TypeError): {e}")
        # Anderer TypeError -> nicht unsere Baustelle, aber verifizieren
        # dass nichts in den Logs auf prompt-Crash hinweist:
        assert "unexpected keyword argument 'prompt'" not in caplog.text, (
            "L-TI-1 regression in log even if exception was swallowed"
        )
    except Exception:
        # ffprobe-FailedException / RuntimeError aus fake-mp4 ist erwartbar.
        # Hauptsache: kein prompt-TypeError in den Logs (Caller-Pfad lief
        # ohne die L-TI-1-Wurzelursache).
        assert "unexpected keyword argument 'prompt'" not in caplog.text, (
            "L-TI-1 regression: prompt-TypeError noch im pacing_service.log"
        )
    else:
        # Erfolgreich generiert
        pass
    # Final guard auch im Erfolgsfall:
    assert "unexpected keyword argument 'prompt'" not in caplog.text
