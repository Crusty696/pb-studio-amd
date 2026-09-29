from __future__ import annotations

import subprocess
from fractions import Fraction

from pb_studio.rendering.render_service import RenderService
from pb_studio.video.encoder_utils import _get_ffmpeg_path


def test_production_aac_filter_keeps_transient_signal_below_true_peak_ceiling(
    tmp_path,
) -> None:
    service = RenderService(output_dir=str(tmp_path))
    command, _ = service._build_render_cmd(
        list_path=tmp_path / "unused-concat-list.txt",
        audio_path="unused-master-audio.wav",
        output_path=tmp_path / "unused-video.mp4",
        bitrate="12M",
        preset="quality",
        audio_offset=0.0,
        total_duration=10.0,
        audio_dur=10.0,
        encoder="hevc_amf",
        include_audio=True,
        target_rate=Fraction(30, 1),
    )
    audio_filter = command[command.index("-filter:a") + 1]
    artifact = tmp_path / "transient-master.m4a"
    ffmpeg = _get_ffmpeg_path()

    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "aevalsrc=0.999*sgn(sin(2*PI*997*t)):s=48000:d=10",
            "-af",
            audio_filter,
            "-c:a",
            "aac",
            "-b:a",
            "320k",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(artifact),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )

    measured_true_peak = service._measure_true_peak_dbtp(
        artifact,
        expected_duration=10.0,
    )

    assert measured_true_peak <= RenderService._AAC_TRUE_PEAK_LIMIT_DBTP
