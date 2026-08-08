"""Regression test: _snap_cuts_to_subtrack_boundaries must not raise
NameError 'PacingCut' is not defined.

Root cause (commit 9909d4a): the method constructed PacingCut(...) without
a local import (other engine methods carried their own local import). When
subtrack-anchor boundaries had no nearby cut, the insert-branch hit a
NameError, which surrounding PacingService caught and re-raised as
"Cut-List-Generierung endgueltig fehlgeschlagen".

This test exercises the insert-branch directly without going through
the full Pacing-Service.
"""

import pytest


def _make_engine():
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
    return AdvancedPacingEngine()


def test_snap_inserts_pacing_cut_when_no_nearby_cut():
    """Anchor with no nearby cut must insert a PacingCut(trigger_type='subtrack')."""
    from pb_studio.pacing.pacing_models import PacingCut

    engine = _make_engine()
    # Subtrack-Boundaries bei 100s und 200s (Anchors)
    engine._pre_cached_subtracks = [
        {"start_time": 0.0, "end_time": 100.0, "confidence": 0.9},
        {"start_time": 100.0, "end_time": 200.0, "confidence": 0.85},
        {"start_time": 200.0, "end_time": 300.0, "confidence": 0.8},
    ]
    # Existing cuts WEIT WEG von Anchors (window default 0.5s) → forciert insert-Branch
    existing_cuts = [
        PacingCut(time=10.0, trigger_type="beat", strength=1.0),
        PacingCut(time=50.0, trigger_type="beat", strength=1.0),
    ]

    snapped = engine._snap_cuts_to_subtrack_boundaries(existing_cuts)

    # _subtrack_boundary_anchors liefert ALLE boundaries (Start/End interior).
    # Mit 3 Segmenten ergeben sich Anchors bei 100, 200, 300 (end-of-last segment).
    # Keiner liegt im Window 0.5s zu existing (10, 50) → 3 inserts.
    inserted = [c for c in snapped if c.trigger_type == "subtrack"]
    assert len(inserted) == 3, f"erwartet 3 inserted subtrack-cuts, got {len(inserted)}: {[c.time for c in inserted]}"
    assert all(c.strength == 1.0 for c in inserted)
    assert sorted([c.time for c in inserted]) == [100.0, 200.0, 300.0]


def test_snap_no_anchors_returns_original_cuts():
    """Ohne _pre_cached_subtracks bleibt cuts-List unverändert."""
    from pb_studio.pacing.pacing_models import PacingCut

    engine = _make_engine()
    # Kein _pre_cached_subtracks gesetzt
    original = [
        PacingCut(time=1.0, trigger_type="beat", strength=1.0),
        PacingCut(time=2.0, trigger_type="beat", strength=1.0),
    ]
    out = engine._snap_cuts_to_subtrack_boundaries(original)
    assert out is original, "ohne anchors muss original-list zurueck (kein neu-konstruieren)"


def test_snap_empty_cuts_returns_empty():
    """Leere cuts-Liste muss leere Liste zurückgeben (kein Crash)."""
    engine = _make_engine()
    engine._pre_cached_subtracks = [
        {"start_time": 0.0, "end_time": 100.0, "confidence": 0.9},
    ]
    out = engine._snap_cuts_to_subtrack_boundaries([])
    assert out == []


def test_snap_anchor_close_to_existing_cut_snaps_instead_of_inserting():
    """Wenn Anchor innerhalb Window eines existierenden Cuts liegt → snap statt insert."""
    from pb_studio.pacing.pacing_models import PacingCut

    engine = _make_engine()
    engine._pre_cached_subtracks = [
        {"start_time": 0.0, "end_time": 100.0, "confidence": 0.9},
        {"start_time": 100.0, "end_time": 200.0, "confidence": 0.85},
    ]
    existing = [
        PacingCut(time=99.8, trigger_type="beat", strength=1.0),  # nahe 100.0
    ]
    snapped = engine._snap_cuts_to_subtrack_boundaries(existing, window=0.5)
    # Snap: time auf 100.0 gesetzt, kein neuer subtrack-Cut für 100.0
    snapped_cut = next(c for c in snapped if abs(c.time - 100.0) < 1e-6)
    assert snapped_cut.trigger_type == "subtrack"
    assert snapped_cut.provenance["operation"] == "endpoint_snap"
    assert snapped_cut.provenance["source_trigger_type"] == "beat"
    # Aber 200.0 hat keinen Cut in Nähe → wird inserted
    assert any(abs(c.time - 200.0) < 1e-6 and c.trigger_type == "subtrack" for c in snapped)
