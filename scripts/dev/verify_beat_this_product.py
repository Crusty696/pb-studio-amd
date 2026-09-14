"""Real-media Beat This product-path proof with in-memory SQLite persistence.

Uses the actual FastAPI audio router, AppState, shared GPU owner and Pacing
trigger builder. Does not import backend.main or execute its lifespan. Media
is read-only. MediaRepository alone is replaced by an in-memory SQLite adapter;
DatabaseCore construction is prohibited as a safety tripwire. The unrelated
CLAP/Brain embedding write is disabled. This is not a musical-accuracy verdict.

Run with PB Studio's Python 3.11 and PYTHONPATH=src from the repository root:
  python scripts/dev/verify_beat_this_product.py SOURCE --out NEW_RECEIPT.json
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
CONTRACT_FIELDS = ("bpm", "beats", "downbeats", "downbeat_provenance")


def _digest(value) -> str:
    data = json.dumps(value, sort_keys=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class FixtureStore:
    """One actual SQL row, plus small checkpoint-contract snapshots."""

    def __init__(self, source: Path, duration: float):
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.connection.execute(
            "CREATE TABLE media (id INTEGER PRIMARY KEY, file_path TEXT, "
            "duration_sec REAL, metadata_json TEXT, ai_data_json TEXT)"
        )
        self.connection.execute(
            "CREATE TABLE checkpoints (id INTEGER PRIMARY KEY, payload TEXT)"
        )
        metadata = {"clip_type": "audio", "clip_id": 1, "name": source.name}
        self.connection.execute(
            "INSERT INTO media VALUES (1, ?, ?, ?, '{}')",
            (str(source), duration, json.dumps(metadata)),
        )
        self.connection.commit()

    def row(self):
        with self.lock:
            return dict(self.connection.execute("SELECT * FROM media").fetchone())

    def write(self, payload):
        encoded = json.dumps(payload, allow_nan=False)
        checkpoint = {
            "bpm": payload.get("bpm"), "beats": payload.get("beats_json", []),
            "downbeats": payload.get("downbeats", []),
            "downbeat_provenance": payload.get("downbeat_provenance", {}),
            "stage_status": payload.get("stage_status", {}),
        }
        with self.lock, self.connection:
            self.connection.execute("UPDATE media SET ai_data_json=? WHERE id=1", (encoded,))
            self.connection.execute(
                "INSERT INTO checkpoints(payload) VALUES (?)", (json.dumps(checkpoint),)
            )

    def checkpoints(self, after_id):
        with self.lock:
            return [json.loads(row[0]) for row in self.connection.execute(
                "SELECT payload FROM checkpoints WHERE id>? ORDER BY id", (after_id,)
            )]

    def checkpoint_id(self):
        with self.lock:
            return self.connection.execute("SELECT COALESCE(MAX(id),0) FROM checkpoints").fetchone()[0]

    def repository_type(self):
        store = self

        class FixtureRepository:
            # No .db attribute: AppState must not run production vector recovery.
            def find_by_project_and_path(self, project_id, file_path):
                assert project_id == 1
                row = store.row()
                assert Path(file_path).resolve() == Path(row["file_path"]).resolve()
                return row

            def get_by_project(self, project_id):
                assert project_id == 1
                return [store.row()]

            def update_status(self, media_id, status, *, ai_data):
                assert media_id == 1 and status == "analyzed"
                store.write(ai_data)

            def delete_media(self, media_id):
                raise AssertionError("Verification cannot delete media")

        return FixtureRepository


def verify(source: Path, out: Path, *, start: float = 0.0, seconds: float | None = None) -> dict:
    import soundfile as sf
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pb_studio.data.database_core import DatabaseCore

    if DatabaseCore._instance is not None:
        raise RuntimeError("Run verification in a fresh process without DatabaseCore")
    initial_stat = source.stat()
    info = sf.info(str(source))
    original_duration = info.frames / info.samplerate
    if original_duration <= 0:
        raise ValueError("Source duration must be positive")
    fixture_root = REPO_ROOT / "scratch" / f"beat-this-product-{uuid4().hex}"
    fixture_root.mkdir(parents=True, exist_ok=False)
    media_source = source
    duration = original_duration
    if seconds is not None:
        if (not math.isfinite(start) or not math.isfinite(seconds)
                or start < 0 or seconds <= 0 or start >= original_duration):
            raise ValueError("Invalid excerpt bounds")
        first_frame = round(start * info.samplerate)
        frames = min(round(seconds * info.samplerate), info.frames - first_frame)
        signal, rate = sf.read(
            str(source), start=first_frame, frames=frames,
            dtype="float32", always_2d=True,
        )
        media_source = fixture_root / "excerpt-fixture.wav"
        with media_source.open("xb") as handle:
            sf.write(handle, signal, rate, format="WAV", subtype="FLOAT")
        duration = len(signal) / rate
        del signal
    elif start != 0:
        raise ValueError("--start requires bounded --seconds")
    store = FixtureStore(media_source, duration)
    receipt = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_name": source.name, "duration_seconds": duration,
        "source_duration_seconds": original_duration,
        "source_offset_seconds": start,
        "excerpt_requested_seconds": seconds,
        "media_mode": "bounded scratch WAV fixture" if seconds is not None else "whole original file read-only",
        "persistence": "sqlite3 :memory: fixture repository; actual AppState save/reload",
        "scope": "actual ASGI audio router, no backend.main lifespan or WPF",
        "disabled": ["unrelated CLAP/Brain embedding persistence"],
        "musical_accuracy": "not assessed; no human beat-one annotation",
        "runs": [],
    }

    async def no_brain_write(*args, **kwargs):
        return None

    try:
        with patch.object(
            DatabaseCore, "__new__",
            side_effect=AssertionError("Production DatabaseCore construction prohibited"),
        ), patch(
            "pb_studio.data.repositories.media_repository.MediaRepository",
            store.repository_type(),
        ):
            from backend.app_state import AppState, get_app_state
            from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine
            from pb_studio.pacing.pacing_models import TriggerSettings
            from pb_studio.services.pacing_service import PacingService

            router = importlib.import_module("backend.routers.audio_router")
            state = AppState(current_project={
                "db_project_id": 1, "path": str(fixture_root),
            })
            assert state.load_from_db(), "Initial fixture load failed"
            app = FastAPI()
            app.include_router(router.router)
            app.dependency_overrides[get_app_state] = lambda: state
            bodies = []
            with patch.object(router, "_store_audio_embedding_in_brain_cache", no_brain_write):
                with TestClient(app) as client:
                    for run_number in (1, 2):
                        checkpoint_start = store.checkpoint_id()
                        started = time.perf_counter()
                        response = client.post("/audio/analyze", json={
                            "clip_id": 1, "force": True, "detect_beats": True,
                            "detect_structure": False, "spectral_analysis": False,
                            "detect_key": False,
                        })
                        if response.status_code != 200:
                            raise RuntimeError(f"Audio API returned HTTP {response.status_code}")
                        body = response.json()
                        bodies.append(body)
                        assert math.isclose(body["duration_seconds"], duration, rel_tol=0, abs_tol=1 / info.samplerate)
                        native = body["downbeat_provenance"]
                        assert native["status"] == "measured", native
                        assert native["method"] == "beat_this_onnx_native", native
                        assert body["downbeats"], "No measured downbeats"
                        persisted = json.loads(store.row()["ai_data_json"])
                        persisted["beats"] = persisted["beats_json"]
                        assert all(persisted[k] == body[k] for k in CONTRACT_FIELDS)
                        checkpoints = store.checkpoints(checkpoint_start)
                        completed = [c for c in checkpoints if c["stage_status"].get("beats") == "completed"]
                        assert completed, "No completed beats checkpoint"
                        assert all(c[k] == body[k] for c in completed for k in CONTRACT_FIELDS)
                        assert state.load_from_db(), "Fixture reload failed"
                        cached = state.get_audio_analysis(1)
                        assert all(cached[k] == body[k] for k in CONTRACT_FIELDS)
                        assert client.get("/audio/beats/1").json() == body["beats"]
                        engine = AdvancedPacingEngine(
                            trigger_settings=TriggerSettings(beat_trigger_mode="downbeat_only")
                        )
                        PacingService.__new__(PacingService)._inject_cached_into_engine(
                            engine, str(media_source), cached
                        )
                        triggers = engine._build_beat_triggers(
                            engine._pre_cached_beats, engine._pre_cached_downbeats
                        )
                        assert [t.time for t in triggers] == body["downbeats"]
                        assert all(t.trigger_type == "downbeat" for t in triggers)
                        times = [b["time"] for b in body["beats"]]
                        assert times == sorted(set(times))
                        assert set(body["downbeats"]).issubset(times)
                        assert all(0 <= t < duration for t in times)
                        receipt["runs"].append({
                            "run": run_number, "seconds": time.perf_counter() - started,
                            "analysis_status": body["analysis_status"],
                            "duration_seconds": body["duration_seconds"],
                            "whole_fixture_duration_preserved": True,
                            "beat_count": len(times), "downbeat_count": len(body["downbeats"]),
                            "bpm": body["bpm"], "legacy_bpm": native.get("legacy_bpm"),
                            "legacy_beat_count": native.get("legacy_beat_count"),
                            "model_revision": native.get("model_revision"),
                            "beat_sha256": _digest(times),
                            "downbeat_sha256": _digest(body["downbeats"]),
                            "checkpoint_count": len(checkpoints),
                            "completed_beat_checkpoint_count": len(completed),
                            "checkpoint_consistent": True, "reload_api_consistent": True,
                            "downbeat_only_trigger_count": len(triggers),
                            "pacing_exact_downbeats": True,
                        })
            receipt["deterministic"] = all(bodies[0][k] == bodies[1][k] for k in CONTRACT_FIELDS)
            assert receipt["deterministic"], "Repeated native results differ"
            assert DatabaseCore._instance is None
        final_stat = source.stat()
        receipt["source_stat_unchanged"] = (
            initial_stat.st_size == final_stat.st_size
            and initial_stat.st_mtime_ns == final_stat.st_mtime_ns
        )
        assert receipt["source_stat_unchanged"]
        receipt["production_database_constructed"] = False
        receipt["technical_contract_passed"] = True
        receipt["fixture_integrity"] = store.connection.execute("PRAGMA integrity_check").fetchone()[0]
        assert receipt["fixture_integrity"] == "ok"
    finally:
        store.connection.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, allow_nan=False)
        handle.write("\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--seconds", type=float)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    out = args.out.resolve()
    if not source.is_file():
        parser.error("source must be an existing file")
    if out.exists():
        parser.error("receipt already exists; choose a new --out")
    if args.start != 0.0 and args.seconds is None:
        parser.error("--start requires --seconds for a bounded excerpt")
    receipt = verify(source, out, start=args.start, seconds=args.seconds)
    print(json.dumps(receipt, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
