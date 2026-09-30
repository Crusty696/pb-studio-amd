"""A clip without an audio track is fully analysed, not partial (T013 finding 6)."""

from backend.routers.video_router import (
    _derive_video_analysis_status,
    _video_analysis_status,
)

_DONE = {
    "scenes": "completed",
    "motion": "completed",
    "embedding": "completed",
    "colors": "completed",
    "captions": "completed",
}


def test_missing_audio_track_is_completed():
    assert _derive_video_analysis_status({**_DONE, "audio_key": "unavailable"}) == "completed"


def test_audio_key_detector_fault_stays_partial():
    assert _derive_video_analysis_status({**_DONE, "audio_key": "failed"}) == "partial"


def test_other_unavailable_stage_stays_partial():
    assert _derive_video_analysis_status({**_DONE, "captions": "unavailable"}) == "partial"


def test_persisted_partial_row_is_rederived():
    row = {"analysis_status": "partial", "stage_status": {**_DONE, "audio_key": "unavailable"}}
    assert _video_analysis_status(row) == "completed"


def test_persisted_real_partial_row_stays_partial():
    row = {"analysis_status": "partial", "stage_status": {**_DONE, "captions": "failed"}}
    assert _video_analysis_status(row) == "partial"
