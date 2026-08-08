"""Focused T315-T320 regression contracts for release repair 00013.

These tests are authored in T328 and intentionally executed first in T332.
They stay at deterministic command, schema, and pure Python contract seams;
full-length media validation remains an End-QC responsibility.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


FULL_LENGTH_SECONDS = 6335.027


def test_export_maps_source_audio_without_synthesizing_silence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """T315: preserve source stream/end silence and apply only measured gain."""
    import pb_studio.rendering.render_service as render_module
    from pb_studio.rendering.render_service import RenderService

    monkeypatch.setattr(render_module, "_get_ffmpeg_path", lambda: "ffmpeg")
    service = RenderService(
        output_dir=str(tmp_path),
        encoder_override="h264_amf",
        job_id="t315-audio-contract",
    )
    source_audio = tmp_path / "release-qc-source.wav"
    command, effective_duration = service._build_render_cmd(
        list_path=tmp_path / "concat.txt",
        audio_path=str(source_audio),
        output_path=tmp_path / "staging.mp4",
        bitrate="15M",
        preset="balanced",
        audio_offset=0.0,
        total_duration=FULL_LENGTH_SECONDS,
        encoder="h264_amf",
        audio_dur=FULL_LENGTH_SECONDS,
        include_audio=True,
    )

    assert effective_duration == pytest.approx(FULL_LENGTH_SECONDS)
    assert command.count(str(source_audio)) == 1
    assert command[command.index("-map") + 1] == "0:v"
    assert command[command.index("-map", command.index("-map") + 1) + 1] == "1:a"
    assert command[command.index("-filter:a") + 1] == "volume=-2.0dB"
    assert command[command.index("-t") + 1] == f"{FULL_LENGTH_SECONDS:.3f}"
    forbidden_silence_sources = ("anullsrc", "aevalsrc", "apad", "adelay")
    assert not any(
        token in argument
        for argument in command
        for token in forbidden_silence_sources
    )


def test_full_length_chunk_evidence_covers_every_window_and_fault(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T316: all 254 windows survive, including concrete stage/load faults."""
    from pb_studio.audio.streaming_analyzer import StreamingAudioAnalyzer

    analyzer = StreamingAudioAnalyzer(window_sec=30.0, overlap_sec=5.0)

    def load_chunk(_path: Path, start: float, _duration: float) -> np.ndarray:
        if start == 50.0:
            raise OSError("forced chunk read fault")
        return np.ones(4096, dtype=np.float32)

    def process_beats(_chunk, start, _bpm_est, _beat_acc):
        return "forced beat fault" if start == 75.0 else None

    monkeypatch.setattr(analyzer, "_load_chunk", load_chunk)
    monkeypatch.setattr(analyzer, "_process_beats", process_beats)
    monkeypatch.setattr(analyzer, "_process_triggers", lambda *_args: None)
    monkeypatch.setattr(
        analyzer,
        "_extract_representative_features",
        lambda *_args, **_kwargs: {
            "chroma_weight": 1,
            "chroma_mean": [0.0] * 12,
            "times": [],
            "centroids": [],
            "bands": {},
        },
    )
    monkeypatch.setattr(analyzer, "_process_energy", lambda *_args, **_kwargs: None)

    result = analyzer._analyze_streaming_prepared(
        Path("release-qc-source.wav"),
        FULL_LENGTH_SECONDS,
        on_progress=None,
        energy_only=False,
        native_sr=44100,
    )

    assert result.window_count == 254
    assert len(result.chunk_evidence) == 254
    assert [row["chunk_index"] for row in result.chunk_evidence] == list(range(254))
    assert result.chunk_evidence[-1]["duration_seconds"] == pytest.approx(10.027)

    load_fault = result.chunk_evidence[2]
    assert load_fault["status"] == "failed"
    assert load_fault["stages"]["load"] == {
        "status": "failed",
        "error": "forced chunk read fault",
    }
    assert load_fault["stages"]["beats"]["status"] == "blocked"

    beat_fault = result.chunk_evidence[3]
    assert beat_fault["status"] == "partial"
    assert beat_fault["stages"]["beats"]["status"] == "failed"
    assert beat_fault["stages"]["beats"]["error"] == "forced beat fault"
    assert "chunk 2: forced chunk read fault" in result.stage_errors["load"]
    assert "chunk 3: forced beat fault" in result.stage_errors["beats"]


def test_partial_audio_contract_round_trips_chunk_and_downbeat_evidence() -> None:
    """T316/T317 public DTO: partial truth and provenance cannot be dropped."""
    from backend.schemas.audio_schemas import AudioAnalysisResult, AudioClipInfo

    chunk = {
        "chunk_index": 17,
        "start_seconds": 425.0,
        "duration_seconds": 30.0,
        "status": "partial",
        "stages": {
            "load": {"status": "completed"},
            "beats": {"status": "failed", "error": "forced beat fault"},
        },
    }
    response = AudioAnalysisResult(
        clip_id=1910,
        duration_seconds=FULL_LENGTH_SECONDS,
        analysis_status="partial",
        stage_status={"beats": "partial"},
        stage_errors={"beats": "chunk 17: forced beat fault"},
        chunk_evidence={
            "schema_version": 1,
            "primary": {"window_count": 254, "chunks": [chunk]},
        },
        downbeats=[],
        downbeat_provenance={
            "status": "unavailable",
            "method": "streaming_librosa_beat_track",
            "synthetic": False,
            "measured_count": 0,
        },
    ).model_dump()
    clip = AudioClipInfo(
        id=1910,
        name="release-qc-source",
        path=r"C:\release-qc-source.wav",
        duration_seconds=FULL_LENGTH_SECONDS,
        is_analyzed=False,
        analysis_status="partial",
        stage_status=response["stage_status"],
        stage_errors=response["stage_errors"],
    ).model_dump()

    assert response["analysis_status"] == "partial"
    assert response["chunk_evidence"]["primary"]["window_count"] == 254
    assert response["chunk_evidence"]["primary"]["chunks"][0] == chunk
    assert response["downbeat_provenance"]["synthetic"] is False
    assert clip["analysis_status"] == "partial"
    assert clip["is_analyzed"] is False
    assert clip["stage_errors"] == response["stage_errors"]


def test_downbeats_are_backend_measured_or_unavailable_never_every_fourth() -> None:
    """T317: missing bar positions must not become synthetic downbeats."""
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine

    engine = AdvancedPacingEngine.__new__(AdvancedPacingEngine)
    beats = [float(index) for index in range(16)]
    engine.audio_analysis = {}

    assert engine._identify_downbeats(beats) == []
    assert engine._last_downbeat_provenance == {
        "status": "unavailable",
        "method": "beat_positions_missing",
        "synthetic": False,
        "measured_count": 0,
    }

    engine.audio_analysis = {
        "beat_data": [
            [0.0, 1],
            [1.0, 2],
            [2.0, 3],
            [3.0, 4],
            [4.0, 1],
        ],
    }
    assert engine._identify_downbeats(beats) == [0.0, 4.0]
    assert engine._last_downbeat_provenance["method"] == "beatnet_bar_position"
    assert engine._last_downbeat_provenance["synthetic"] is False


def test_cached_downbeats_require_measured_backend_provenance() -> None:
    """T317 caller contract: cached labels are authoritative only when measured."""
    from pb_studio.services.pacing_service import PacingService

    service = PacingService()
    unavailable_engine = SimpleNamespace(clip_selector=SimpleNamespace())
    service._inject_cached_into_engine(
        unavailable_engine,
        "release-qc-source.wav",
        {
            "beats": [
                {"time": 0.0, "beat_type": "downbeat"},
                {"time": 1.0, "beat_type": "beat"},
            ],
            "downbeats": [0.0],
            "downbeat_provenance": {
                "status": "unavailable",
                "method": "streaming_librosa_beat_track",
                "synthetic": False,
                "measured_count": 0,
            },
        },
    )
    assert not hasattr(unavailable_engine, "_pre_cached_downbeats")
    assert (
        unavailable_engine._pre_cached_downbeat_provenance["status"]
        == "unavailable"
    )

    measured_engine = SimpleNamespace(clip_selector=SimpleNamespace())
    service._inject_cached_into_engine(
        measured_engine,
        "release-qc-source.wav",
        {
            "beats": [
                {"time": 0.0, "beat_type": "downbeat"},
                {"time": 1.0, "beat_type": "beat"},
            ],
            "downbeats": [4.0],
            "downbeat_provenance": {
                "status": "measured",
                "method": "beatnet_bar_position",
                "synthetic": False,
                "measured_count": 2,
            },
        },
    )
    assert measured_engine._pre_cached_downbeats == [0.0, 4.0]


def test_timeline_finalizer_clamps_source_and_exact_full_length_boundaries() -> None:
    """T318: remove start gap, clamp source offset, and close at target."""
    from pb_studio.pacing.pacing_models import CutListEntry
    from pb_studio.services.pacing_service import PacingService

    original_start = 1.9272562358276644
    cuts = [
        CutListEntry(
            clip_id="clip_1",
            start_time=original_start,
            end_time=4.0,
            metadata={"clip_start": 1.0},
        ),
        CutListEntry(
            clip_id="clip_2",
            start_time=6330.0,
            end_time=6340.0,
            metadata={"clip_start": 5.0},
        ),
        CutListEntry(
            clip_id="clip_overflow",
            start_time=FULL_LENGTH_SECONDS,
            end_time=FULL_LENGTH_SECONDS + 1.0,
        ),
    ]

    finalized = PacingService()._finalize_cut_list(cuts, FULL_LENGTH_SECONDS)

    assert [cut.clip_id for cut in finalized] == ["clip_1", "clip_2"]
    assert finalized[0].start_time == 0.0
    assert finalized[0].metadata["clip_start"] == 0.0
    assert finalized[0].metadata["boundary_original_start"] == pytest.approx(
        original_start
    )
    assert finalized[0].metadata["boundary_normalized_start"] == 0.0
    assert finalized[-1].end_time == pytest.approx(FULL_LENGTH_SECONDS)
    assert finalized[-1].metadata["boundary_original_end"] == 6340.0
    assert finalized[-1].metadata["boundary_normalized_end"] == pytest.approx(
        FULL_LENGTH_SECONDS
    )


def test_endpoint_snap_reclassifies_and_records_request_apply_delta_reason() -> None:
    """T319: endpoint mutation must replace stale type and retain full provenance."""
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
    from pb_studio.pacing.pacing_models import PacingCut

    requested_time = 99.8
    applied_time = 100.0
    engine = AdvancedPacingEngine.__new__(AdvancedPacingEngine)
    engine._pre_cached_subtracks = [{"start_time": 0.0, "end_time": applied_time}]
    cut = PacingCut(
        time=requested_time,
        trigger_type="downbeat",
        strength=0.8,
    )

    snapped = engine._snap_cuts_to_subtrack_boundaries([cut], window=0.5)

    assert snapped == [cut]
    assert cut.time == applied_time
    assert cut.trigger_type == "subtrack"
    assert cut.strength == 1.0
    assert cut.provenance["source_time_seconds"] == requested_time
    assert cut.provenance["target_time_seconds"] == applied_time
    assert cut.provenance["snap_distance_seconds"] == pytest.approx(
        applied_time - requested_time
    )
    assert cut.provenance["operation"] == "endpoint_snap"
    assert cut.provenance["source_trigger_type"] == "downbeat"
    assert cut.provenance["target_quality"] == "detected_subtrack_boundary"


@pytest.mark.parametrize(
    ("available_count", "expected_blacklist"),
    [(1, 0), (2, 1), (3, 0), (4, 1), (6, 3), (8, 4), (9, 6), (100, 20)],
)
def test_adaptive_diversity_preserves_selectable_capacity(
    available_count: int,
    expected_blacklist: int,
) -> None:
    """T320: blacklist adapts to library size and never consumes required floor."""
    from pb_studio.pacing.clip_selector import ClipSelector

    selector = ClipSelector(blacklist_percentage=0.8)
    blacklist_size = selector._adaptive_blacklist_size(available_count)

    assert blacklist_size == expected_blacklist
    expected_floor = 1 if available_count < 3 else 3
    assert available_count - blacklist_size >= expected_floor


def test_adaptive_diversity_relaxes_saturation_and_keeps_unique_lru() -> None:
    """T320: stale/repeated history cannot exhaust candidates or consume slots."""
    from pb_studio.pacing.clip_selector import ClipSelector

    clips = [
        {
            "id": str(index),
            "file_path": f"clip-{index}.mp4",
            "motion_score": index / 10.0,
        }
        for index in range(1, 7)
    ]
    selector = ClipSelector(
        strategy="round_robin",
        blacklist_percentage=0.8,
    )
    selector._recently_used = deque(["stale", "1", "1"])

    first_selected = selector.select_clip(clips).clip_id
    assert "stale" not in selector._recently_used
    assert len(selector._recently_used) == len(set(selector._recently_used))

    selected_ids = [first_selected] + [
        selector.select_clip(clips).clip_id
        for _ in range(23)
    ]

    assert set(selected_ids) <= {str(index) for index in range(1, 7)}
    assert selector._blacklist_size == 3
    assert len(selector._recently_used) == len(set(selector._recently_used))
    assert len(selector._recently_used) <= selector._blacklist_size
