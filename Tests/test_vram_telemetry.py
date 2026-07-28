"""
Tests fuer VRAM-Budget-Manager Telemetrie + /health/vram Endpoint.

Geprueft wird:
  * record_task_observation() aktualisiert Aggregate, Histogram und Min/Max/Avg
  * Histogram-Buckets werden korrekt zugeordnet (inkl. Overflow)
  * Erfolgs-/Fehler-Beobachtungen werden separat gezaehlt
  * Reset-API bereinigt die Telemetrie
  * with_gpu_task laeuft die Beobachtung sauber durch (Erfolg + Fehlerfall)
  * GET /health/vram liefert ein konsistentes Schema (budget + telemetry)
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from pb_studio.core.vram_budget_manager import (
    DURATION_BUCKETS_MS,
    VRAM_BUCKETS_MB,
    VRAMBudgetManager,
    ModelPriority,
)


# -----------------------------------------------------------------------------
# Helper: frischer Manager pro Test (Singleton-Reset)
# -----------------------------------------------------------------------------

@pytest.fixture
def fresh_manager():
    VRAMBudgetManager.reset_for_testing()
    mgr = VRAMBudgetManager(max_vram_mb=4096)
    mgr.reset_telemetry()
    yield mgr
    VRAMBudgetManager.reset_for_testing()


# -----------------------------------------------------------------------------
# Unit-Tests: TelemetryEntry / record_task_observation
# -----------------------------------------------------------------------------

class TestTelemetryRecording:
    def test_first_observation_initialisiert_aggregate(self, fresh_manager):
        fresh_manager.record_task_observation(
            "moondream_fp16", duration_ms=120.0, vram_peak_mb=1800.0,
        )
        snap = fresh_manager.get_telemetry("moondream_fp16")
        assert snap["count"] == 1
        assert snap["success_count"] == 1
        assert snap["failure_count"] == 0
        assert snap["duration_ms"]["min"] == 120.0
        assert snap["duration_ms"]["max"] == 120.0
        assert snap["duration_ms"]["avg"] == 120.0
        assert snap["vram_peak_mb"]["min"] == 1800.0
        assert snap["vram_peak_mb"]["max"] == 1800.0

    def test_mehrere_beobachtungen_aggregieren_korrekt(self, fresh_manager):
        for d in (50.0, 100.0, 250.0, 500.0):
            fresh_manager.record_task_observation(
                "raft_small", duration_ms=d, vram_peak_mb=400.0,
            )
        snap = fresh_manager.get_telemetry("raft_small")
        assert snap["count"] == 4
        assert snap["duration_ms"]["min"] == 50.0
        assert snap["duration_ms"]["max"] == 500.0
        assert snap["duration_ms"]["avg"] == pytest.approx(225.0, rel=1e-3)

    def test_failure_observation_setzt_last_error(self, fresh_manager):
        fresh_manager.record_task_observation(
            "siglip_so400m", duration_ms=10000.0, vram_peak_mb=2500.0,
            success=False, error={"type": "TimeoutError", "message": "boom"},
        )
        snap = fresh_manager.get_telemetry("siglip_so400m")
        assert snap["count"] == 1
        assert snap["success_count"] == 0
        assert snap["failure_count"] == 1
        assert snap["last_error"]["type"] == "TimeoutError"

    def test_negative_werte_werden_geclamped(self, fresh_manager):
        fresh_manager.record_task_observation(
            "m_neg", duration_ms=-5.0, vram_peak_mb=-10.0,
        )
        snap = fresh_manager.get_telemetry("m_neg")
        assert snap["duration_ms"]["min"] == 0.0
        assert snap["vram_peak_mb"]["min"] == 0.0

    def test_leerer_model_id_landet_unter_unknown(self, fresh_manager):
        fresh_manager.record_task_observation("", duration_ms=42.0, vram_peak_mb=10.0)
        all_snap = fresh_manager.get_telemetry()
        assert "_unknown" in all_snap["models"]
        assert all_snap["models"]["_unknown"]["count"] == 1


class TestHistogramBuckets:
    def test_durations_landen_in_passenden_buckets(self, fresh_manager):
        # Wert direkt am Bucket-Rand: <= upper landet im Bucket
        fresh_manager.record_task_observation("m1", duration_ms=49.9, vram_peak_mb=50.0)
        fresh_manager.record_task_observation("m1", duration_ms=50.0, vram_peak_mb=50.0)
        fresh_manager.record_task_observation("m1", duration_ms=499.0, vram_peak_mb=50.0)
        fresh_manager.record_task_observation("m1", duration_ms=999999.0, vram_peak_mb=50.0)
        snap = fresh_manager.get_telemetry("m1")
        hist = snap["duration_ms"]["histogram"]
        assert hist["<= 50ms"] == 2          # 49.9 + 50.0
        assert hist["<= 500ms"] == 1         # 499.0
        assert hist["+infms"] == 1           # 999999.0

    def test_vram_overflow_geht_in_inf_bucket(self, fresh_manager):
        fresh_manager.record_task_observation(
            "m_big", duration_ms=10.0, vram_peak_mb=24576.0,  # > 8000
        )
        snap = fresh_manager.get_telemetry("m_big")
        assert snap["vram_peak_mb"]["histogram"]["+infMB"] == 1

    def test_summary_enthaelt_bucket_definitionen(self, fresh_manager):
        fresh_manager.record_task_observation("m", duration_ms=10.0, vram_peak_mb=10.0)
        all_snap = fresh_manager.get_telemetry()
        assert all_snap["summary"]["duration_buckets_ms"] == list(DURATION_BUCKETS_MS)
        assert all_snap["summary"]["vram_buckets_mb"] == list(VRAM_BUCKETS_MB)
        assert all_snap["summary"]["models_tracked"] == 1
        assert all_snap["summary"]["observations"] == 1


class TestTelemetryReset:
    def test_reset_einzelnes_model(self, fresh_manager):
        fresh_manager.record_task_observation("a", duration_ms=10.0, vram_peak_mb=10.0)
        fresh_manager.record_task_observation("b", duration_ms=10.0, vram_peak_mb=10.0)
        fresh_manager.reset_telemetry("a")
        assert "a" not in fresh_manager.get_telemetry()["models"]
        assert "b" in fresh_manager.get_telemetry()["models"]

    def test_reset_alle(self, fresh_manager):
        fresh_manager.record_task_observation("a", duration_ms=10.0, vram_peak_mb=10.0)
        fresh_manager.record_task_observation("b", duration_ms=10.0, vram_peak_mb=10.0)
        fresh_manager.reset_telemetry()
        assert fresh_manager.get_telemetry()["summary"]["observations"] == 0


# -----------------------------------------------------------------------------
# Integration: with_gpu_task fuettert die Telemetrie
# -----------------------------------------------------------------------------

class TestWithGpuTaskTelemetry:
    def test_externally_managed_budget_is_not_double_counted(self, fresh_manager):
        from backend.dependencies import with_gpu_task

        fresh_manager.register_model(
            "siglip_vision", "SigLIP Vision", 2000, ModelPriority.MEDIUM,
        )
        observed_committed = []

        def composite_work() -> int:
            assert fresh_manager.reserve("raft_small")
            assert fresh_manager.commit("raft_small")
            assert fresh_manager.reserve("siglip_vision")
            assert fresh_manager.commit("siglip_vision")
            observed_committed.append(fresh_manager.total_committed_mb)
            fresh_manager.release("siglip_vision")
            fresh_manager.release("raft_small")
            return 42

        result = asyncio.run(
            with_gpu_task(
                composite_work,
                model_id="video_analysis_full",
                manage_vram=False,
                timeout_seconds=5,
            ),
        )

        assert result == 42
        assert observed_committed == [2400]
        outer_budget = fresh_manager.get_model("video_analysis_full")
        assert outer_budget is not None
        assert outer_budget.is_reserved is False
        assert outer_budget.is_loaded is False
        assert fresh_manager.total_reserved_mb == 0
        assert fresh_manager.total_committed_mb == 0
        assert fresh_manager.get_telemetry("video_analysis_full")["count"] == 1

    def test_erfolgsfall_traegt_observation_ein(self, fresh_manager):
        from backend.dependencies import with_gpu_task

        fresh_manager.register_model(
            "raft_small", "RAFT Small", 400, ModelPriority.MEDIUM,
        )

        def work() -> int:
            return 21 + 21

        result = asyncio.run(
            with_gpu_task(work, model_id="raft_small", timeout_seconds=5),
        )
        assert result == 42
        snap = fresh_manager.get_telemetry("raft_small")
        assert snap["count"] == 1
        assert snap["success_count"] == 1
        assert snap["failure_count"] == 0
        # Dauer wird in ms gemessen — muss >=0 sein
        assert snap["duration_ms"]["min"] is not None
        assert snap["duration_ms"]["min"] >= 0.0

    def test_fehlerfall_traegt_failure_ein(self, fresh_manager):
        from backend.dependencies import with_gpu_task

        fresh_manager.register_model(
            "moondream_fp16", "Moondream FP16", 1800, ModelPriority.HIGH,
        )

        def boom() -> None:
            raise RuntimeError("kaputt")

        with pytest.raises(RuntimeError):
            asyncio.run(
                with_gpu_task(boom, model_id="moondream_fp16", timeout_seconds=5),
            )
        snap = fresh_manager.get_telemetry("moondream_fp16")
        assert snap["failure_count"] == 1
        assert snap["last_error"] is not None
        assert snap["last_error"]["type"] == "RuntimeError"


# -----------------------------------------------------------------------------
# Integration: GET /health/vram
# -----------------------------------------------------------------------------

class TestHealthVramEndpoint:
    def test_endpoint_ohne_observations(self, fresh_manager):
        from backend.main import app

        client = TestClient(app)
        r = client.get("/health/vram")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "budget" in body
        assert "telemetry" in body
        assert "max_vram_mb" in body["budget"]
        assert body["telemetry"]["summary"]["observations"] == 0

    def test_endpoint_zeigt_observation_nach_record(self, fresh_manager):
        from backend.main import app

        fresh_manager.record_task_observation(
            "raft_small", duration_ms=120.0, vram_peak_mb=400.0,
        )
        client = TestClient(app)
        r = client.get("/health/vram")
        assert r.status_code == 200
        body = r.json()
        assert body["telemetry"]["summary"]["observations"] == 1
        assert "raft_small" in body["telemetry"]["models"]
        raft = body["telemetry"]["models"]["raft_small"]
        assert raft["duration_ms"]["max"] == 120.0
        assert raft["vram_peak_mb"]["max"] == 400.0

    def test_endpoint_mit_model_id_filter(self, fresh_manager):
        from backend.main import app

        fresh_manager.record_task_observation("a", duration_ms=10.0, vram_peak_mb=10.0)
        fresh_manager.record_task_observation("b", duration_ms=20.0, vram_peak_mb=20.0)

        client = TestClient(app)
        r = client.get("/health/vram", params={"model_id": "a"})
        assert r.status_code == 200
        body = r.json()
        # Bei model_id-Filter ist telemetry direkt der Eintrag (kein "models"-Wrapper)
        assert body["telemetry"]["model_id"] == "a"
        assert body["telemetry"]["count"] == 1
        assert body["telemetry"]["duration_ms"]["max"] == 10.0
