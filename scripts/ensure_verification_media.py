from __future__ import annotations

import argparse
import math
import struct
import subprocess
import wave
from pathlib import Path


def generate_click_track_wav(output_path: Path, *, bpm: float = 120.0, duration_sec: float = 8.0, sample_rate: int = 44100) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    beat_interval = 60.0 / bpm
    click_duration_sec = 0.06
    amplitude = 0.55
    frequency = 880.0
    fade_samples = int(sample_rate * 0.008)
    total_samples = int(sample_rate * duration_sec)

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        frames = bytearray()
        for sample_index in range(total_samples):
            t = sample_index / sample_rate
            beat_pos = t % beat_interval
            sample_value = 0.0
            if beat_pos < click_duration_sec:
                env = 1.0 - (beat_pos / click_duration_sec)
                if sample_index < fade_samples:
                    env *= sample_index / max(1, fade_samples)
                sample_value = amplitude * env * math.sin(2.0 * math.pi * frequency * beat_pos)
            pcm_value = max(-32767, min(32767, int(sample_value * 32767)))
            frames.extend(struct.pack("<h", pcm_value))

        wav_file.writeframes(frames)


def run_ffmpeg(args: list[str]) -> None:
    completed = subprocess.run(args, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "ffmpeg failed").strip())


def generate_color_bars_video(output_path: Path, *, duration_sec: float = 8.0, size: str = "640x360", rate: int = 24) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={size}:rate={rate}:duration={duration_sec}",
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            str(output_path),
        ]
    )


def ensure_media(root: Path) -> dict[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    audio_path = root / "test_120bpm.wav"
    video_a_path = root / "test_bars.mp4"
    video_b_path = root / "test_bars2.mp4"

    if not audio_path.exists() or audio_path.stat().st_size == 0:
        generate_click_track_wav(audio_path)
    if not video_a_path.exists() or video_a_path.stat().st_size == 0:
        generate_color_bars_video(video_a_path)
    if not video_b_path.exists() or video_b_path.stat().st_size == 0:
        generate_color_bars_video(video_b_path, duration_sec=6.0, size="854x480", rate=30)

    return {
        "audio": str(audio_path),
        "video_a": str(video_a_path),
        "video_b": str(video_b_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ensure lightweight verification media fixtures exist.")
    parser.add_argument("root", type=Path, help="Directory where verification media should exist")
    args = parser.parse_args()

    result = ensure_media(args.root)
    for key, value in result.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
