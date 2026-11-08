from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from pb_studio.rendering.render_service import RenderService


def _path_digest(path: Path) -> str:
    normalized = os.path.normcase(os.path.normpath(str(path)))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _timeline(first: Path, second: Path) -> list[dict]:
    return [
        {
            "clip_id": "timeline-cut-1",
            "file_path": str(first),
            "in_point": 1.25,
            "out_point": 3.25,
        },
        {
            "clip_id": "timeline-cut-2",
            "metadata": {"file_path": str(second)},
            "in": 4.0,
            "out": 5.5,
        },
    ]


def test_manifest_is_ordered_redacted_and_bound_into_render_receipt(
    tmp_path: Path,
) -> None:
    first = tmp_path / "confidential-first-clip.mp4"
    second = tmp_path / "confidential-second-clip.mp4"
    first.write_bytes(b"clip-one")
    second.write_bytes(b"clip-two")
    service = RenderService(output_dir=str(tmp_path / "exports"), job_id="job-1")
    service.run_id = "run-1"

    manifest_path = service._persist_segment_manifest(_timeline(first, second))
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)

    assert manifest["segments"] == [
        {
            "index": 0,
            "source_path_sha256": _path_digest(first),
            "source_in_seconds": 1.25,
            "source_out_seconds": 3.25,
            "timeline_start_seconds": 0.0,
            "timeline_end_seconds": 2.0,
        },
        {
            "index": 1,
            "source_path_sha256": _path_digest(second),
            "source_in_seconds": 4.0,
            "source_out_seconds": 5.5,
            "timeline_start_seconds": 2.0,
            "timeline_end_seconds": 3.5,
        },
    ]
    assert first.as_posix() not in manifest_bytes.decode("utf-8")
    assert second.name not in manifest_bytes.decode("utf-8")
    canonical_segments = json.dumps(
        manifest["segments"], sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    assert manifest["timeline_sha256"] == hashlib.sha256(canonical_segments).hexdigest()

    result_path = service._persist_render_evidence(
        status="completed",
        exit_code=0,
        progress_end=True,
        machine_progress={"frame": "105", "out_time_us": "3500000"},
        progress_log="frame=105\nprogress=end\n",
        stderr_log="",
        total_duration=3.5,
        total_frames=105,
    )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["segment_manifest_sha256"] == hashlib.sha256(manifest_bytes).hexdigest()
    assert result["timeline_sha256"] == manifest["timeline_sha256"]


def test_segment_manifest_is_exclusive_and_preserves_first_receipt(
    tmp_path: Path,
) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"clip")
    service = RenderService(output_dir=str(tmp_path / "exports"), job_id="job-2")
    service.run_id = "run-2"

    manifest_path = service._persist_segment_manifest([
        {"file_path": str(source), "in_point": 0.0, "out_point": 1.0}
    ])
    original = manifest_path.read_bytes()

    with pytest.raises(FileExistsError):
        service._persist_segment_manifest([
            {"file_path": str(source), "in_point": 2.0, "out_point": 3.0}
        ])

    assert manifest_path.read_bytes() == original
    assert list(manifest_path.parent.glob("*.tmp")) == []


def test_manifest_ranges_match_concat_input_microsecond_precision(
    tmp_path: Path,
) -> None:
    source = tmp_path / "precision-source.mp4"
    source.write_bytes(b"clip")
    service = RenderService(output_dir=str(tmp_path / "exports"), job_id="precision")
    service.run_id = "precision-run"
    timeline = [
        {
            "file_path": str(source),
            "in_point": 1.2345674,
            "out_point": 3.4567894,
        },
        {"file_path": str(source), "in_point": 0.1, "out_point": 0.2},
    ]
    concat_path = tmp_path / "concat.txt"

    service._generate_concat_file(timeline, concat_path)
    manifest_path = service._persist_segment_manifest(timeline)
    concat_text = concat_path.read_text(encoding="utf-8")
    segments = json.loads(manifest_path.read_text(encoding="utf-8"))["segments"]
    segment = segments[0]

    assert "inpoint 1.234567\n" in concat_text
    assert "outpoint 3.456789\n" in concat_text
    assert segment["source_in_seconds"] == 1.234567
    assert segment["source_out_seconds"] == 3.456789
    assert segment["timeline_end_seconds"] == 2.222222
    assert segments[1]["timeline_start_seconds"] == 2.222222
    assert segments[1]["timeline_end_seconds"] == 2.322222
    assert service._calculate_timeline_duration(timeline) == 2.322222


@pytest.mark.parametrize("encoder_fails", [False, True], ids=["completed", "failed"])
def test_render_persists_segment_manifest_before_final_ffmpeg(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    encoder_fails: bool,
) -> None:
    source = tmp_path / "private-source.mp4"
    source.write_bytes(b"source")
    output_dir = tmp_path / "exports"
    service = RenderService(
        output_dir=str(output_dir),
        encoder_override="hevc_amf",
        job_id="manifest-before-encode",
    )
    timeline = [{
        "file_path": str(source),
        "in_point": 0.5,
        "out_point": 2.5,
    }]
    monkeypatch.setattr(
        service,
        "_normalize_clips",
        lambda clips, *_args, **_kwargs: clips,
    )
    concat_receipt: dict[str, str] = {}

    def fake_final_ffmpeg(
        concat_path: Path,
        _audio_path: str | None,
        staging_path: Path,
        *_args: object,
        **_kwargs: object,
    ) -> dict[str, float | int]:
        concat_receipt["sha256"] = hashlib.sha256(concat_path.read_bytes()).hexdigest()
        run_evidence = output_dir / ".render_evidence" / service.job_token / service.run_id
        manifest_path = run_evidence / "segments.json"
        assert manifest_path.is_file(), "segment evidence must exist before final FFmpeg"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert len(manifest["segments"]) == 1
        if encoder_fails:
            failed_result = service._persist_render_evidence(
                status="failed",
                exit_code=1,
                progress_end=False,
                machine_progress={"frame": "12", "out_time_us": "400000"},
                progress_log="frame=12\nprogress=continue\n",
                stderr_log="synthetic final FFmpeg failure",
                total_duration=2.0,
                total_frames=60,
            )
            concat_receipt["failed_result"] = str(failed_result)
            raise RuntimeError("synthetic final FFmpeg failure")
        service._persist_render_evidence(
            status="completed",
            exit_code=0,
            progress_end=True,
            machine_progress={"frame": "60", "out_time_us": "2000000"},
            progress_log="frame=60\nprogress=end\n",
            stderr_log="",
            total_duration=2.0,
            total_frames=60,
        )
        staging_path.write_bytes(b"encoded-output")
        return {"current_frame": 60, "fps": 30.0}

    monkeypatch.setattr(service, "_run_ffmpeg_render", fake_final_ffmpeg)
    monkeypatch.setattr(
        service,
        "_validate_render_artifact",
        lambda *_args, **_kwargs: {"decoded_frames": 60},
    )

    render_call = lambda: service.render_timeline(
        timeline=timeline,
        audio_path="",
        output_filename="rendered.mp4",
        include_audio=False,
    )
    if encoder_fails:
        with pytest.raises(RuntimeError, match="synthetic final FFmpeg failure"):
            render_call()
        manifest_path = (
            output_dir
            / ".render_evidence"
            / service.job_token
            / service.run_id
            / "segments.json"
        )
        assert manifest_path.is_file()
        failure_record = json.loads(
            Path(concat_receipt["failed_result"]).read_text(encoding="utf-8")
        )
        assert failure_record["status"] == "failed"
        assert failure_record["concat_input_sha256"] == concat_receipt["sha256"]
        assert not (output_dir / "rendered.mp4").exists()
        return

    rendered = render_call()
    manifest_path = (
        output_dir
        / ".render_evidence"
        / service.job_token
        / service.run_id
        / "segments.json"
    )
    result_path = manifest_path.with_name("result.json")
    assert Path(rendered).read_bytes() == b"encoded-output"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["segment_manifest_sha256"]
    assert result["concat_input_sha256"] == concat_receipt["sha256"]
    result_text = result_path.read_text(encoding="utf-8")
    assert str(source) not in result_text
