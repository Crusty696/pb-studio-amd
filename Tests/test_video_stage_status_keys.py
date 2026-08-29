"""Nur echte Stage-Namen duerfen in stage_status landen.

Audit 2026-08-29 (C-2): der Except-Zweig in `_analyze_video_in_project` schreibt
`result["stage_status"][current_stage] = "failed"`. `current_stage` traegt aber
PHASEN-Namen ("motion_embedding", "colors_captions", "persistence"), keine
Stage-Namen. Legale Stages sind ausschliesslich die Schluessel von
VIDEO_ANALYSIS_STAGE_FIELDS.

Die Folge ist dauerhaft, nicht voruebergehend:
- `_video_analysis_resume_base` kopiert stage_status unveraendert zurueck,
- `_video_stage_should_run` schlaegt nur unter echten Stage-Namen nach und
  raeumt den Phantomschluessel deshalb nie weg - auch `force=True` nicht,
- `_derive_video_analysis_status` iteriert ueber ALLE Werte, ein ueberlebendes
  "failed" macht den Clip fuer immer zu "partial"/"failed",
- und `is_analyzed = (status == "completed")` wird damit nie wieder True.
"""

import pytest

from backend.routers.video_router import (
    VIDEO_ANALYSIS_STAGE_FIELDS,
    _derive_video_analysis_status,
    _drop_unknown_stage_keys,
    _stage_status_keys_for_phase,
)

PHASES = ["scenes", "motion_embedding", "colors_captions", "audio_key", "persistence"]


@pytest.mark.parametrize("phase", PHASES)
def test_phase_maps_only_to_real_stage_names(phase):
    """Jede Phase darf ausschliesslich echte Stage-Namen erzeugen."""
    keys = _stage_status_keys_for_phase(phase)
    unknown = set(keys) - set(VIDEO_ANALYSIS_STAGE_FIELDS)
    assert not unknown, (
        f"Phase {phase!r} wuerde {sorted(unknown)} in stage_status schreiben - "
        "das sind keine Stage-Namen und niemand raeumt sie je weg"
    )


def test_motion_embedding_phase_marks_both_stages_it_covers():
    """Die Phase faehrt zwei Stages; scheitert sie, sind beide betroffen."""
    assert set(_stage_status_keys_for_phase("motion_embedding")) == {
        "motion",
        "embedding",
    }


def test_colors_captions_phase_marks_both_stages_it_covers():
    assert set(_stage_status_keys_for_phase("colors_captions")) == {
        "colors",
        "captions",
    }


def test_persistence_phase_is_not_a_stage_at_all():
    """Persistenz ist keine Analyse-Stage - sie darf stage_status nicht anfassen."""
    assert _stage_status_keys_for_phase("persistence") == ()


def test_resume_base_drops_a_key_that_is_not_a_stage():
    """Altlast-Heilung an der richtigen Stelle.

    Bereits persistierte Phantomschluessel duerfen nicht ewig nachwirken. Sie
    gehoeren beim Wiederaufsetzen entfernt - NICHT in der Statusableitung
    ignoriert: `_derive_video_analysis_status` wird ausschliesslich laufintern
    gerufen (video_router.py:1156, :1223, :1300) und muss streng bleiben, sonst
    verschluckt sie echte Fehlschlaege.

    Nach dem Entfernen hat die betroffene Stage gar keinen Status mehr,
    `_video_stage_should_run` laesst sie also wieder laufen und das Ergebnis
    wird ehrlich neu bestimmt.
    """
    cleaned = _drop_unknown_stage_keys(
        {
            "scenes": "completed",
            "motion_embedding": "failed",   # Phantom aus dem alten Except-Zweig
            "persistence": "failed",
        }
    )
    assert cleaned == {"scenes": "completed"}


def test_derive_stays_strict_about_real_failures():
    """Gegenprobe: die Ableitung selbst darf nichts verschlucken."""
    assert _derive_video_analysis_status(
        {"scenes": "completed", "motion": "failed"}
    ) == "partial"
    assert _derive_video_analysis_status(
        {"scenes": "completed", "motion": "completed"}
    ) == "completed"
