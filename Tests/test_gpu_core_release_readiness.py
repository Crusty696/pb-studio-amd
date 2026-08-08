from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import MagicMock

import pytest

from pb_studio.core.model_loader import ModelLoader, ModelSpec, ModelType
from pb_studio.core.vram_arbiter import VRAMArbiter
from pb_studio.core.vram_budget_manager import ModelPriority, VRAMBudgetManager


def test_gpu_deadline_returns_while_worker_keeps_lock() -> None:
    from backend.dependencies import with_gpu_task
    from pb_studio.core.vram_budget_manager import get_vram_manager

    # Exclude one-time manager/hardware discovery from worker deadline timing.
    get_vram_manager()

    worker_started = threading.Event()
    worker_release = threading.Event()
    second_started = threading.Event()

    def slow_worker() -> str:
        worker_started.set()
        worker_release.wait(timeout=2)
        return "late-result"

    def second_worker() -> str:
        second_started.set()
        return "second-result"

    async def scenario() -> None:
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            await with_gpu_task(
                slow_worker,
                manage_vram=False,
                timeout_seconds=0.05,
            )
        assert time.monotonic() - started < 0.3
        assert worker_started.is_set()

        second = asyncio.create_task(
            with_gpu_task(
                second_worker,
                manage_vram=False,
                timeout_seconds=1,
            )
        )
        await asyncio.sleep(0.05)
        assert not second_started.is_set()

        worker_release.set()
        assert await second == "second-result"

    asyncio.run(scenario())


def test_failed_eviction_callback_keeps_committed_accounting() -> None:
    VRAMBudgetManager.reset_for_testing()
    manager = VRAMBudgetManager(max_vram_mb=2500)

    def fail_unload() -> bool:
        return False

    manager.register_model(
        "resident",
        "Resident",
        1500,
        ModelPriority.LOW,
        unload_callback=fail_unload,
    )
    manager.register_model("incoming", "Incoming", 1000, ModelPriority.HIGH)
    assert manager.reserve("resident")
    assert manager.commit("resident")

    assert manager.reserve("incoming", force=True) is False
    assert manager.is_model_loaded("resident") is True
    assert manager.total_committed_mb == 1500


def test_successful_eviction_callback_is_accounted_after_callback() -> None:
    VRAMBudgetManager.reset_for_testing()
    manager = VRAMBudgetManager(max_vram_mb=2500)
    callback_observations: list[tuple[bool, int]] = []

    def unload() -> bool:
        callback_observations.append(
            (manager.is_model_loaded("resident"), manager.total_committed_mb)
        )
        return True

    manager.register_model(
        "resident",
        "Resident",
        1500,
        ModelPriority.LOW,
        unload_callback=unload,
    )
    manager.register_model("incoming", "Incoming", 1000, ModelPriority.HIGH)
    assert manager.reserve("resident")
    assert manager.commit("resident")

    assert manager.reserve("incoming", force=True) is True
    assert callback_observations == [(True, 1500)]
    assert manager.is_model_loaded("resident") is False
    assert manager.total_committed_mb == 0
    assert manager.total_reserved_mb == 1000


def test_arbiter_forces_fresh_sensor_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monitor = MagicMock()
    monitor.get_stats.return_value = {
        "gpu_memory_used": 1000.0,
        "gpu_memory_total": 8192.0,
    }
    manager = MagicMock()
    manager.available_vram_mb = 6000
    manager.can_fit.return_value = True

    monkeypatch.setattr(
        "pb_studio.core.vram_budget_manager.get_vram_manager",
        lambda monitor=None: manager,
    )
    arbiter = VRAMArbiter(monitor)

    assert arbiter.can_allocate(1000) is True
    monitor.get_stats.assert_called_once_with(force_refresh=True)


def test_model_loader_rejects_failed_commit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    model_path = tmp_path / "test.onnx"
    model_path.touch()
    loader = object.__new__(ModelLoader)
    loader.config = MagicMock()
    loader.vram_manager = MagicMock()
    loader.vram_manager.reserve.return_value = True
    loader.vram_manager.commit.return_value = False
    loader._sessions = {}
    loader._session_lock = threading.RLock()
    loader._specs = {
        "test": ModelSpec(
            model_id="test",
            name="Test",
            model_type=ModelType.ONNX,
            vram_mb=100,
            model_path=model_path.name,
        )
    }
    loader._models_dir = tmp_path
    session = object()
    monkeypatch.setattr(loader, "_load_onnx", lambda spec: session)

    assert loader.load_model("test") is None
    assert "test" not in loader._sessions
    loader.vram_manager.cancel_reservation.assert_called_once_with("test")


def test_model_loader_unload_all_collects_before_checked_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = object.__new__(ModelLoader)
    loader._sessions = {"first": object(), "second": {"encoder": object()}}
    loader._session_lock = threading.RLock()
    loader.vram_manager = MagicMock()
    order: list[str] = []
    loader.vram_manager.release.side_effect = lambda model_id: (
        order.append(f"release:{model_id}") or model_id != "second"
    )
    monkeypatch.setattr("gc.collect", lambda: order.append("gc") or 0)

    assert loader.unload_all() is False
    assert order == ["gc", "release:first", "release:second"]
    assert loader._sessions == {}


def test_model_loader_unload_requires_release_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = object.__new__(ModelLoader)
    loader._sessions = {"test": object()}
    loader._session_lock = threading.RLock()
    loader.vram_manager = MagicMock()
    loader.vram_manager.release.return_value = False
    monkeypatch.setattr("gc.collect", lambda: 0)

    assert loader._do_unload("test") is False
    loader.vram_manager.release.assert_called_once_with("test")


def test_multi_gpu_fallbacks_do_not_mix_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pb_studio.core.system_monitor import SystemMonitor

    assert not hasattr(SystemMonitor, "_counter_query_vram_used")
    assert not hasattr(SystemMonitor, "_query_temperature_alternative")
    assert not hasattr(SystemMonitor, "_query_load_alternative")

    monitor = object.__new__(SystemMonitor)
    monitor._cache_lock = threading.Lock()
    monitor._cached_stats = {}
    monitor._cache_time = 0.0
    monitor._bg_refresh_running = True
    monitor._gpu_count = 2
    monitor.monitoring_status = "ready"

    monkeypatch.setattr(monitor, "_query_driver_version", lambda name: "driver")
    monkeypatch.setattr(monitor, "_wmi_query_vram_total", lambda name: 16384.0)
    monkeypatch.setattr(
        monitor,
        "_counter_query_vram_used",
        lambda: pytest.fail("cross-adapter VRAM aggregation used"),
        raising=False,
    )
    monkeypatch.setattr(
        monitor,
        "_query_temperature_alternative",
        lambda: pytest.fail("cross-adapter temperature used"),
        raising=False,
    )
    monkeypatch.setattr(
        monitor,
        "_query_load_alternative",
        lambda: pytest.fail("cross-adapter load used"),
        raising=False,
    )

    monitor._bg_refresh_ps_stats(
        {
            "gpu_name": "AMD Radeon RX 7800 XT",
            "gpu_load": 0.0,
            "gpu_temp": 0.0,
            "gpu_memory_used": 0.0,
            "gpu_memory_total": 0.0,
            "cpu_load": 0.0,
            "driver_version": "Unknown",
        }
    )

    assert monitor._cached_stats["gpu_name"] == "AMD Radeon RX 7800 XT"
    assert monitor._cached_stats["driver_version"] == "driver"
    assert monitor._cached_stats["gpu_memory_total"] == 16384.0
    assert monitor._cached_stats["gpu_memory_used"] == 0.0
