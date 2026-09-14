"""Read-only real-media probe: fixed-model inference vs unchanged librosa grid."""

import argparse
import json
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import soxr

from pb_studio.audio.beat_this_tracker import BeatThisTracker
from pb_studio.audio.downbeat_alignment import align_downbeats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--start", type=float, default=60)
    parser.add_argument("--seconds", type=float, default=120)
    args = parser.parse_args()
    info = sf.info(str(args.path))
    signal, rate = sf.read(str(args.path), start=round(args.start * info.samplerate),
                           frames=round(args.seconds * info.samplerate),
                           dtype="float64", always_2d=True)
    signal = signal.mean(axis=1)
    signal = soxr.resample(signal, rate, 22050)
    tracker = BeatThisTracker()
    try:
        first = tracker.track_signal(signal)
        second = tracker.track_signal(signal)
    finally:
        tracker.close()
    _, frames = librosa.beat.beat_track(y=signal, sr=22050)
    grid = librosa.frames_to_time(frames, sr=22050)
    mapped, provenance = align_downbeats(
        [{"time": float(t)} for t in grid], *first
    )
    print(json.dumps({
        "file": args.path.name, "start": args.start, "duration": args.seconds,
        "repeat_equal": all(np.array_equal(a, b) for a, b in zip(first, second)),
        "grid_count": len(grid), "neural_beats": len(first[0]),
        "neural_downbeats": len(first[1]), "mapped_count": len(mapped),
        "provenance": provenance,
    }, indent=2))


if __name__ == "__main__":
    main()
