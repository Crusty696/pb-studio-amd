"""Read-only whole-file proof using the product GPU owner and pacing consumer."""

import argparse
import asyncio
import json
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from backend.routers.audio_router import _track_neural_downbeats
from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
from pb_studio.pacing.pacing_models import TriggerSettings


async def verify(path):
    duration = sf.info(str(path)).duration
    started = time.perf_counter()
    results = []
    for repeat in range(2):
        def progress(step, percent, message):
            print(f"run={repeat + 1} {message}", flush=True)
        results.append(await _track_neural_downbeats(
            str(path), duration, lambda: None, progress
        ))
    beats, downbeats, revision = results[0]
    engine = AdvancedPacingEngine(
        trigger_settings=TriggerSettings(beat_trigger_mode="downbeat_only")
    )
    triggers = engine._build_beat_triggers(beats, downbeats)
    return {
        "file": path.name, "duration_seconds": duration, "revision": revision,
        "repeat_equal": results[0] == results[1],
        "beat_count": len(beats), "downbeat_count": len(downbeats),
        "sorted_unique": beats == sorted(set(beats)) and downbeats == sorted(set(downbeats)),
        "downbeats_subset": set(downbeats).issubset(beats),
        "median_bar_in_beats": float(np.median(np.diff(downbeats)) / np.median(np.diff(beats))) if len(downbeats) > 1 else None,
        "raw_neural_pacing_trigger_count": len(triggers),
        "raw_neural_pacing_exact": [t.time for t in triggers] == downbeats,
        "scope": "Neural producer and actual pacing method; not legacy-grid mapping or human beat-one validation",
        "elapsed_seconds": time.perf_counter() - started,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    receipt = asyncio.run(verify(args.path))
    args.out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
