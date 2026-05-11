"""Test L-TI-6: _enforce_clip_lengths darf min_clip_length nicht verletzen.

Audit Timeline-Integrity L-TI-6 (HIGH):
Die Split-Logik in _enforce_clip_lengths (advanced_pacing_engine.py:~1946)
prueft beim Einfuegen eines Auto-Split-Cuts nur die Distanz zum *letzten*
Split, nicht zum *naechsten* echten Cut. In Kombination mit Random-Jitter
konnten dadurch Splits entstehen, die die min_clip_length unterschreiten.

Diese Tests verifizieren, dass *alle* resultierenden Cut-Intervalle
>= min_length sind, auch bei aggressivem Jitter und Edge-Cases.
"""
import random

import pytest


def _gaps(cuts, audio_duration):
    """Berechne Intervalle zwischen aufeinanderfolgenden Cuts (inkl. End-Gap)."""
    sorted_cuts = sorted(cuts, key=lambda c: c.time)
    gaps = []
    for i in range(len(sorted_cuts) - 1):
        gaps.append(sorted_cuts[i + 1].time - sorted_cuts[i].time)
    # End-Gap: letzter Cut bis audio_duration
    if sorted_cuts:
        gaps.append(audio_duration - sorted_cuts[-1].time)
    return gaps


def _make_cut(time: float, trigger_type: str = "beat", strength: float = 0.7):
    from pb_studio.pacing.pacing_models import PacingCut
    return PacingCut(time=time, trigger_type=trigger_type, strength=strength)


def test_enforce_clip_lengths_no_split_violates_min():
    """Langer Source-Clip wird gesplittet ohne min_length zu unterschreiten."""
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine

    engine = AdvancedPacingEngine()
    # Single cut at t=0, audio length 10s, min=1.0, max=3.0
    # -> muss in mehrere Splits aufgeteilt werden
    cuts = [_make_cut(0.0)]
    audio_duration = 10.0
    min_length = 1.0
    max_length = 3.0

    result = engine._enforce_clip_lengths(
        cuts, min_length=min_length, max_length=max_length,
        audio_duration=audio_duration, variation=0.0,
    )

    gaps = _gaps(result, audio_duration)
    for i, gap in enumerate(gaps):
        assert gap >= min_length - 1e-6, (
            f"Gap[{i}]={gap:.4f} verletzt min_length={min_length}; cuts={[c.time for c in result]}"
        )


def test_enforce_clip_lengths_short_clip_no_split():
    """Clip kuerzer als 2x min_clip_length wird nicht gesplittet."""
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine

    engine = AdvancedPacingEngine()
    # cut at t=0, audio 1.5s, max=3.0 -> 1.5 < max, kein split
    cuts = [_make_cut(0.0)]
    audio_duration = 1.5
    result = engine._enforce_clip_lengths(
        cuts, min_length=1.0, max_length=3.0,
        audio_duration=audio_duration, variation=0.0,
    )
    # Nur der eine Original-Cut soll bleiben
    assert len(result) == 1
    assert result[0].time == 0.0


def test_enforce_clip_lengths_random_jitter_safe():
    """Mit Random-Jitter und vielen Iterationen darf nie min_length unterschritten werden."""
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine

    engine = AdvancedPacingEngine()
    min_length = 1.0
    max_length = 2.0
    audio_duration = 60.0
    # Multiple cuts so dass zwischen ihnen jeweils Auto-Splits noetig werden
    cuts = [_make_cut(t) for t in [0.0, 8.0, 20.0, 35.0, 50.0]]

    # Lauf 50 Iterationen mit unterschiedlichen Random-States
    for seed in range(50):
        random.seed(seed)
        result = engine._enforce_clip_lengths(
            cuts, min_length=min_length, max_length=max_length,
            audio_duration=audio_duration,
            variation=1.0,  # max jitter
        )
        gaps = _gaps(result, audio_duration)
        for i, gap in enumerate(gaps):
            assert gap >= min_length - 1e-6, (
                f"seed={seed} gap[{i}]={gap:.4f} < min={min_length}; "
                f"times={[round(c.time, 3) for c in result]}"
            )


def test_enforce_clip_lengths_split_near_next_cut_skipped():
    """
    Edge-Case: Ein langer Gap zu einem direkt folgenden Cut.
    Splits, die zu nah am next-real-cut waeren, muessen geskippt werden.

    Setup: Cut bei t=0, naechster Cut bei t=4.0, min_length=1.0, max_length=2.5.
    Jitter ist 0.0 (deterministisch). Ohne Fix wuerde split bei t=2.0 platziert,
    next-cut bei t=4.0 -> gap=2.0, ok. ABER:
    Mit max_length=2.5 und gap 4.0 wuerde num_splits = int(4/2.5)=1,
    split_duration = 4/2 = 2.0, split bei t=0+2.0=2.0. Distanz zu prev=2.0,
    zu next=2.0. OK.
    Test eher: max=3.5 -> num_splits=int(4/3.5)=1, split_duration=4/2=2.0,
    split bei t=2.0 -> gaps 2.0, 2.0 -> ok.
    Echter Edge-Case: gap=2.1, min=1.0, max=1.5 -> num_splits=int(2.1/1.5)=1,
    split_duration=2.1/2=1.05, split bei t=1.05 -> prev-gap=1.05, next-gap=1.05.
    """
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine

    engine = AdvancedPacingEngine()
    # Cuts bei 0 und 2.05; min=1.0, max=1.5 -> num_splits=1, split_dur=1.025
    # split bei t=1.025 - mit Jitter -0.205 -> t=0.82 -> prev_gap=0.82 < min=1.0 -> SKIP
    cuts = [_make_cut(0.0), _make_cut(2.05)]
    audio_duration = 4.0

    # Fixed seed reproduces jitter consistently
    for seed in range(20):
        random.seed(seed)
        result = engine._enforce_clip_lengths(
            cuts, min_length=1.0, max_length=1.5,
            audio_duration=audio_duration,
            variation=1.0,
        )
        gaps = _gaps(result, audio_duration)
        for i, gap in enumerate(gaps):
            assert gap >= 1.0 - 1e-6, (
                f"seed={seed} gap[{i}]={gap:.4f}; times={[round(c.time, 3) for c in result]}"
            )


def test_enforce_clip_lengths_split_too_close_to_end():
    """
    Ein Split der zu nah an audio_duration platziert wird, muss geskippt werden.

    Setup: Cut bei t=0, audio_duration=2.05, min=1.0, max=1.5.
    Ohne audio_duration-Boundary-Check kann ein Split bei t=1.95 entstehen
    -> Gap zum Ende = 0.10 < min=1.0.
    """
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine

    engine = AdvancedPacingEngine()
    cuts = [_make_cut(0.0)]
    audio_duration = 2.05

    for seed in range(20):
        random.seed(seed)
        result = engine._enforce_clip_lengths(
            cuts, min_length=1.0, max_length=1.5,
            audio_duration=audio_duration,
            variation=1.0,
        )
        gaps = _gaps(result, audio_duration)
        for i, gap in enumerate(gaps):
            assert gap >= 1.0 - 1e-6, (
                f"seed={seed} gap[{i}]={gap:.4f}; times={[round(c.time, 3) for c in result]}, "
                f"audio_dur={audio_duration}"
            )
