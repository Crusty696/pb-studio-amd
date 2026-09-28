from __future__ import annotations

import asyncio
import importlib
import json
import os
import subprocess
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app_state import AppState, ProjectOperationContext
from backend.schemas.render_schemas import RenderRequest
from pb_studio.rendering import render_service
from pb_studio.rendering.render_service import RenderService

render_router = importlib.import_module("backend.routers.render_router")


def test_incident_frame_deficit_reproduces_through_router_and_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "discardable-source.mp4"
    source.write_bytes(b"test source")
    duration = 3299.456508
    decoded_end = 3299.456508
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        render_service,
        "RenderService",
        lambda **kwargs: _service_with_incident_identity(kwargs),
    )
    monkeypatch.setattr(
        RenderService,
        "_get_audio_duration",
        lambda self, path, *_args, **_kwargs: duration,
    )
    monkeypatch.setattr(
        RenderService,
        "_measure_trailing_silence_seconds",
        lambda *args, **kwargs: 0.0,
    )
    monkeypatch.setattr(RenderService, "_normalize_clips", lambda self, *args: [
        {"file_path": str(source), "in_point": 0.0, "out_point": duration}
    ])

    def fake_run_ffmpeg(self, *args, **kwargs):
        captured["run_ffmpeg_kwargs"] = kwargs
        service_args = args
        cmd, _ = self._build_render_cmd(
            Path("concat.txt"), str(tmp_path / "mix.wav"),
            Path(args[2]), "12M", "quality", 0.0,
            duration, "h264_amf", include_audio=True,
            target_rate=kwargs.get("target_rate"),
        )
        expected_frames = int(cmd[cmd.index("-frames:v") + 1]) if "-frames:v" in cmd else 98982
        captured["final_command"] = cmd
        captured["rendered_frames"] = expected_frames
        rendered_frames = expected_frames
        staging = Path(args[2])
        staging.write_bytes(b"completed FFmpeg artifact")
        progress_log = (
            f"frame={rendered_frames}\n"
            "out_time_us=3299456508\n"
            "progress=end\n"
        )
        self._persist_render_evidence(
            status="completed",
            exit_code=0,
            progress_end=True,
            machine_progress={
                "frame": str(rendered_frames),
                "out_time_us": "3299456508",
                "fps": "250.67",
            },
            progress_log=progress_log,
            stderr_log="",
            total_duration=duration,
            total_frames=expected_frames,
        )
        return {
            "fps": 250.67,
            "current_frame": rendered_frames,
            "total_frames": 98984,
            "progress_end": True,
            "out_time_us": 3299439456,
        }

    monkeypatch.setattr(RenderService, "_run_ffmpeg_render", fake_run_ffmpeg)

    def fake_capture(self, cmd, *, timeout, cancel_callback=None):
        captured.setdefault("probe_commands", []).append(cmd)
        if "-show_entries" in cmd:
            stdout = json.dumps({
                "streams": [{
                    "codec_type": "video", "codec_name": "h264",
                    "width": 1920, "height": 1080,
                }, {
                    "codec_type": "audio", "codec_name": "aac",
                    "sample_rate": "44100", "channels": 2,
                }],
                "format": {"duration": str(decoded_end)},
            })
        else:
            frame_count = int(captured.get("rendered_frames", 98982))
            stdout = (
                f"frame={frame_count}\nout_time_us=3299456508\nprogress=end\n"
            )
        return subprocess.CompletedProcess(cmd, 0, stdout, "")

    monkeypatch.setattr(RenderService, "_run_capture_process", fake_capture)
    monkeypatch.setattr(RenderService, "_measure_true_peak_dbtp", lambda *a, **k: -2.0)
    monkeypatch.setattr(
        render_router,
        "_finalize_timeline_for_render",
        lambda timeline, _duration: timeline,
    )

    state = AppState()
    state.set_render_task("incident", {"task_id": "incident", "queue_job_id": "q-incident"})
    state.set_cancel_flag("incident", False)
    (tmp_path / "mix.wav").write_bytes(b"test audio")
    request = RenderRequest(
        output_path=str(tmp_path / "incident-output.mp4"),
        audio_path=str(tmp_path / "mix.wav"),
        fps=30.0,
    )
    loop = asyncio.new_event_loop()

    async def run_task() -> None:
        monkeypatch.setattr(render_router, "_queue_update_or_raise", lambda *a, **k: None)
        monkeypatch.setattr(render_router, "_safe_queue_update", lambda *a, **k: None)
        monkeypatch.setattr(render_router, "publish_event", _noop_async)
        monkeypatch.setattr(render_router, "publish_log", _noop_async)
        await render_router._run_render_task(
            "incident", request, state,
            [{
                "clip_id": "clip_test",
                "start_time": 0.0,
                "end_time": duration,
                "metadata": {"file_path": str(source), "clip_start": 0.0},
            }],
            "q-incident",
        )

    try:
        loop.run_until_complete(run_task())
    finally:
        loop.close()

    task = state.get_render_task("incident")
    assert task["status"] == "completed"
    assert task["validation_status"] == "validated"
    assert Path(task["evidence_path"]).is_file()
    assert Path(task["validation_path"]).is_file()
    validation = json.loads(Path(task["validation_path"]).read_text(encoding="utf-8"))
    assert validation["status"] == "passed"
    assert validation["metrics"]["decoded_frames"] == 98984


def test_render_command_and_validator_share_rational_frame_rate(
    tmp_path: Path,
) -> None:
    service = RenderService(output_dir=str(tmp_path), encoder_override="h264_amf")
    cmd, _ = service._build_render_cmd(
        tmp_path / "concat.txt", str(tmp_path / "mix.wav"),
        tmp_path / "out.mp4", "12M", "quality", 0.0,
        3299.456508, "h264_amf", include_audio=True,
        target_rate=__import__("fractions").Fraction(30, 1),
    )
    assert cmd[cmd.index("-r") + 1] == "30/1"
    assert "settb=AVTB,setpts=PTS-STARTPTS,fps=fps=30/1" in cmd[cmd.index("-vf") + 1]
    assert cmd[cmd.index("-frames:v") + 1] == "98984"
    assert cmd[cmd.index("-t") + 1] == "3299.457"


def test_rational_non_integer_fps_frame_count_matches_artifact_validator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rate = Fraction(30_000, 1_001)
    duration = 60_000.0
    expected_frames = 1_798_202
    service = RenderService(output_dir=str(tmp_path), encoder_override="h264_amf")
    service._render_rate = rate
    command, _ = service._build_render_cmd(
        tmp_path / "concat.txt",
        str(tmp_path / "mix.wav"),
        tmp_path / "out.mp4",
        "12M",
        "quality",
        0.0,
        duration,
        "h264_amf",
        include_audio=False,
        target_rate=rate,
    )
    assert command[command.index("-r") + 1] == "30000/1001"
    assert command[command.index("-frames:v") + 1] == str(expected_frames)

    monkeypatch.setattr(
        service,
        "_run_capture_process",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "format": {"duration": str(duration)},
                "streams": [{
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                }],
            }),
            stderr="",
        ),
    )
    monkeypatch.setattr(
        service,
        "_decode_artifact_stream",
        lambda *_args, **_kwargs: {
            "frame": str(expected_frames),
            "out_time_us": str(int(duration * 1_000_000)),
            "progress": "end",
        },
    )

    validation = service._validate_render_artifact(
        tmp_path / "out.mp4",
        expected_duration=duration,
        target_fps=30_000 / 1_001,
        target_width=1920,
        target_height=1080,
        include_audio=False,
    )
    assert validation["decoded_frames"] == expected_frames
    assert validation["expected_frames"] == expected_frames


@pytest.mark.skipif(
    os.environ.get("PBSTUDIO_LIVE_AMF_RENDER_TEST") != "1",
    reason="requires explicit opt-in to real-media AMD AMF integration test",
)
def test_live_music_selected_cutlist_renders_all_fractional_rate_frames(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise real cached music/video analysis through pacing and AMF export.

    This catches segment-boundary frames discarded by concat selection. The
    prior live run produced 897 frames where a 30 s 30000/1001 export requires
    899, so RenderService rejected the otherwise encoded output.
    """
    import random
    import sqlite3

    from pb_studio.data import vector_store
    from pb_studio.rendering.preview_renderer import PreviewGenerator, TimelineEntry
    from pb_studio.services.pacing_service import PacingService
    from pb_studio.video.encoder_utils import _get_ffprobe_path

    # Semantic matching is disabled in this test, so FAISS is irrelevant. Avoid
    # loading its persistent index or triggering VectorStore's exit snapshot save.
    monkeypatch.setattr(vector_store, "VectorStore", lambda **_kwargs: None)

    repository = Path(__file__).resolve().parents[1]
    database = repository / "data" / "pb_studio.db"
    if not database.is_file():
        pytest.skip("local approved QA catalog is unavailable")

    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        records = connection.execute(
            "SELECT id, file_path, duration_sec, ai_data_json FROM media"
        ).fetchall()
    finally:
        connection.close()

    by_name = {Path(row["file_path"]).name.casefold(): row for row in records}
    audio = by_name.get("test_30s.wav")
    video_rows = [by_name.get(name) for name in ("test_20s.mp4", "test_12s.mp4")]
    if (
        audio is None
        or any(row is None for row in video_rows)
        or not Path(audio["file_path"]).is_file()
        or any(not Path(row["file_path"]).is_file() for row in video_rows)
    ):
        pytest.skip("approved real-media fixtures are unavailable")

    audio_analysis = json.loads(audio["ai_data_json"] or "{}")
    audio_analysis["beats"] = audio_analysis.get("beats_json", [])
    audio_analysis["duration_seconds"] = float(audio["duration_sec"])
    clips = []
    for row in video_rows:
        analysis = json.loads(row["ai_data_json"] or "{}")
        motion = analysis.get("motion") or {}
        if (
            analysis.get("stage_status", {}).get("motion") != "completed"
            or not motion.get("motion_curve")
        ):
            pytest.skip("real-media motion-analysis cache is incomplete")
        clips.append({
            "id": row["id"],
            "file_path": row["file_path"],
            "duration": row["duration_sec"],
            "name": Path(row["file_path"]).stem,
            "motion_score": motion.get("avg_motion", 0.0),
            "motion_curve": motion["motion_curve"],
            "scene_changes": analysis.get("scenes", []),
            "ai_data": analysis,
        })

    random_state = random.getstate()
    random.seed(35035)
    pacing = PacingService()
    try:
        cuts = pacing.generate_cut_list(
            audio["file_path"],
            clips,
            {
                "use_semantic_matching": False,
                "use_motion_matching": True,
                "use_key_matching": False,
                "use_brain": False,
                "use_structure_awareness": True,
                "expected_bpm": audio_analysis.get("bpm") or 120,
                "min_cut_interval": 0.5,
                "max_cut_interval": 6.0,
                "min_clip_length": 2.0,
                "max_clip_length": 8.0,
            },
            float(audio["duration_sec"]),
            cached_analysis=audio_analysis,
        )
    finally:
        random.setstate(random_state)
    assert cuts
    assert abs(sum(cut.end_time - cut.start_time for cut in cuts) - 30.0) < 0.01
    selected_clip_ids = {
        str(cut.clip_id).removeprefix("clip_")
        for cut in cuts
    }
    assert selected_clip_ids == {str(clip["id"]) for clip in clips}
    assert any(
        cut.metadata.get("trigger_type") in {
            "beat", "kick", "snare", "hihat", "onset", "energy", "downbeat"
        }
        for cut in cuts
    )

    timeline = []
    for cut in cuts:
        source = float(cut.metadata.get("clip_start", 0.0))
        timeline.append({
            "file_path": cut.metadata["file_path"],
            "in_point": source,
            "out_point": source + cut.end_time - cut.start_time,
        })

    preview_timeline = [
        TimelineEntry(
            video_path=entry["file_path"],
            start_time=entry["in_point"],
            end_time=entry["out_point"],
            timeline_start=cut.start_time,
            timeline_end=cut.end_time,
        )
        for cut, entry in zip(cuts, timeline, strict=True)
    ]
    preview_generator = PreviewGenerator(output_dir=tmp_path / "preview")
    preview_path = preview_generator.generate_preview(
        preview_timeline,
        start_time_sec=0.0,
        duration=10.0,
        audio_path=audio["file_path"],
    )
    assert preview_path is not None and preview_path.is_file()
    assert preview_generator.last_duration_sec == pytest.approx(10.0, abs=0.05)
    assert preview_generator.audio_included
    preview_probe = subprocess.run(
        [
            _get_ffprobe_path(),
            "-v", "error",
            "-show_entries", "stream=codec_type,duration",
            "-of", "json",
            str(preview_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    preview_streams = json.loads(preview_probe.stdout)["streams"]
    assert {stream["codec_type"] for stream in preview_streams} == {"video", "audio"}
    audio_stream = next(stream for stream in preview_streams if stream["codec_type"] == "audio")
    assert float(audio_stream["duration"]) == pytest.approx(10.0, abs=0.05)

    renderer = RenderService(output_dir=str(tmp_path))
    rendered_path = renderer.render_timeline(
        timeline,
        audio["file_path"],
        "music_selected_fractional_rate.mp4",
        target_width=1280,
        target_height=720,
        target_fps=30_000 / 1_001,
        bitrate="5M",
    )
    assert Path(rendered_path).is_file()
    assert Path(rendered_path).stat().st_size > 0
    validation_path = (
        tmp_path
        / ".render_evidence"
        / renderer.job_token
        / renderer.run_id
        / "validation.json"
    )
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    assert validation["status"] == "passed"
    assert validation["metrics"]["expected_frames"] == 899
    assert validation["metrics"]["decoded_frames"] == 899


def test_artifact_validation_emits_named_phase_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = RenderService(output_dir=str(tmp_path), encoder_override="h264_amf")
    monkeypatch.setattr(
        service,
        "_run_capture_process",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "format": {"duration": "1.0"},
                "streams": [{
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                }],
            }),
            stderr="",
        ),
    )
    monkeypatch.setattr(
        service,
        "_decode_artifact_stream",
        lambda *_args, **_kwargs: {
            "frame": "30",
            "out_time_us": "1000000",
            "progress": "end",
        },
    )
    emitted: list[dict[str, object]] = []

    service._validate_render_artifact(
        tmp_path / "validated.mp4",
        expected_duration=1.0,
        target_fps=30.0,
        target_width=1920,
        target_height=1080,
        include_audio=False,
        progress_callback=lambda _message, _percent, details: emitted.append(details),
    )

    assert [event["validation_phase"] for event in emitted] == [
        "container_probe",
        "video_decode",
    ]
    assert all(event["validation_status"] == "running" for event in emitted)


@pytest.mark.parametrize("same_as", ["video", "audio", "video-hardlink"])
def test_start_render_rejects_input_output_identity_before_enqueue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    same_as: str,
) -> None:
    media = tmp_path / "source.mp4"
    audio = tmp_path / "mix.wav"
    media.write_bytes(b"video")
    audio.write_bytes(b"audio")
    if same_as == "video":
        output = media
    elif same_as == "audio":
        output = audio
    else:
        output = tmp_path / "source-hardlink.mp4"
        os.link(media, output)
    request = RenderRequest(
        output_path=str(output), audio_path=str(audio),
    )
    state = AppState()
    state.current_project = {"name": "test", "path": str(tmp_path), "db_project_id": 1}
    state.set_audio_clip(1, {"id": 1, "path": str(audio)})
    state.set_video_clip(1, {"id": 1, "path": str(media)})
    state.set_timeline([{
        "clip_id": "clip_1", "start_time": 0.0, "end_time": 1.0,
        "metadata": {"file_path": str(media), "clip_start": 0.0},
    }])
    enqueues: list[object] = []
    monkeypatch.setattr(render_router, "_get_render_queue", lambda: SimpleNamespace(
        cleanup_terminal=lambda **kwargs: None,
        enqueue=lambda *args, **kwargs: _queued_job(enqueues, kwargs),
        update_status=lambda *args, **kwargs: SimpleNamespace(job_id=args[0]),
    ))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(render_router._start_render_for_project(
            request, state,
            ProjectOperationContext(1, tmp_path.resolve(), state._project_epoch),
        ))
    assert exc.value.status_code == 400
    assert "same file" in exc.value.detail.lower() or "dieselbe datei" in exc.value.detail.lower()
    assert not enqueues


def _service_with_incident_identity(kwargs: dict[str, object]) -> RenderService:
    options = dict(kwargs)
    options["encoder_override"] = "h264_amf"
    options.setdefault("job_id", "incident-98982")
    return RenderService(**options)


def _queued_job(enqueues: list[object], kwargs: dict[str, object]) -> SimpleNamespace:
    enqueues.append(kwargs)
    return SimpleNamespace(job_id=kwargs["job_id"], status="queued")


async def _noop_async(*args, **kwargs) -> None:
    return None
