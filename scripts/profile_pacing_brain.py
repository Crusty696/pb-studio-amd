"""Profiling: Pacing-Run with vs. without Brain (Plan Phase 6 DoD).

Builds in-memory pacing config + dummy clips, runs annotate_cuts_with_brain
on N synthetic cuts, logs timings.

Usage:
    python scripts/profile_pacing_brain.py [N_CUTS]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
import tempfile


def main() -> int:
    sys.path.insert(0, "src")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100

    from pb_studio.brain.brain_service import BrainService
    from pb_studio.brain.post_processor import annotate_cuts_with_brain

    with tempfile.TemporaryDirectory() as td:
        # Use temp APPDATA so we don't pollute real brain dir
        import os
        os.environ["APPDATA"] = str(Path(td) / "appdata")
        BrainService.reset_singleton()
        svc = BrainService.get()
        # bind a fresh state.db
        state_db = Path(td) / "state.db"
        svc.bind_project_state(state_db)

        # synthetic cuts
        cuts = []
        for i in range(n):
            cuts.append({
                "clip_id": f"clip_{i % 20}",
                "start_time": float(i),
                "end_time": float(i + 1),
                "metadata": {
                    "trigger_type": "kick" if i % 4 == 0 else "beat",
                    "trigger_strength": 0.7,
                    "segment_type": "drop" if i % 8 == 0 else "verse",
                },
            })

        # synthetic video features
        vab = {
            f"clip_{j}": {
                "avg_motion": 0.3 + (j % 5) * 0.1,
                "motion_category": ["low", "medium", "high"][j % 3],
                "avg_brightness": 0.5,
                "avg_color_temp": 0.0,
                "mood_tags": [],
            }
            for j in range(20)
        }

        audio_analysis = {
            "mood_tags": ["neutral"],
            "energy_curve": [0.5] * 100,
            "duration_seconds": float(n + 1),
            "subtrack_segments": [
                {"start_time": 0.0, "end_time": float(n + 1), "confidence": 0.5}
            ],
        }

        t0 = time.perf_counter()
        out = annotate_cuts_with_brain(
            cuts,
            weight_store=svc.weights,
            audio_analysis=audio_analysis,
            video_analysis_by_clip=vab,
            audio_clip_id=1,
            persist_to_state_conn=svc.state_conn,
        )
        dt_ms = (time.perf_counter() - t0) * 1000.0

        print(f"N cuts:       {n}")
        print(f"Brain time:   {dt_ms:.1f} ms")
        print(f"Per cut:      {dt_ms / max(n, 1):.2f} ms")
        print(f"Returned:     {len(out)} cuts")
        print(f"Target:       <500 ms total (Plan DoD)")
        if dt_ms < 500.0:
            print("OK")
            BrainService.reset_singleton()
            return 0
        print("WARN: above 500 ms target")
        BrainService.reset_singleton()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
