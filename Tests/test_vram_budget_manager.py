import pytest
import time
from types import SimpleNamespace
from pb_studio.core.vram_budget_manager import VRAMBudgetManager, ModelPriority


def test_forced_vram_environment_takes_priority_over_normal_cap(monkeypatch):
    manager = object.__new__(VRAMBudgetManager)
    manager._physical_vram_mb = 16384
    manager.adapter = SimpleNamespace(device_id=0, luid="test-luid")
    manager.config = SimpleNamespace(get=lambda *_args, **_kwargs: {})
    monkeypatch.setenv("PBSTUDIO_VRAM_LIMIT_MB", "15872")
    monkeypatch.setenv("PB_STUDIO_FORCED_VRAM", "14336")

    assert manager._detect_vram_limit() == 14336

def test_vram_allocation_and_eviction():
    VRAMBudgetManager.reset_for_testing()
    mgr = VRAMBudgetManager(max_vram_mb=4096)
    
    # We should have exactly max - 500 (safety buffer)
    assert mgr.available_vram_mb == 4096 - 500
    
    # Register models
    mgr.register_model(
        "m1", "Model 1", 1000, ModelPriority.LOW,
        unload_callback=lambda: True,
    )
    mgr.register_model(
        "m2", "Model 2", 1500, ModelPriority.MEDIUM,
        unload_callback=lambda: True,
    )
    mgr.register_model("m3", "Model 3", 2000, ModelPriority.HIGH)
    
    # Reserve and commit m1
    assert mgr.reserve("m1")
    assert mgr.commit("m1")
    assert mgr.is_model_loaded("m1")
    
    # Reserve and commit m2
    assert mgr.reserve("m2")
    assert mgr.commit("m2")
    assert mgr.is_model_loaded("m2")
    
    # VRAM should now be (4096 - 500) - 2500 = 1096
    assert mgr.available_vram_mb == 1096
    
    # Try to allocate m3 (needs 2000), should fail without force
    assert not mgr.reserve("m3", force=False)
    
    # Try to allocate m3 with force, should evict m1 (LOW)
    assert mgr.reserve("m3", force=True)
    assert not mgr.is_model_loaded("m1")
    assert mgr.is_model_loaded("m2")
    
    assert mgr.commit("m3")
    assert mgr.is_model_loaded("m3")

def test_eviction_lru():
    VRAMBudgetManager.reset_for_testing()
    mgr = VRAMBudgetManager(max_vram_mb=4096)
    
    mgr.register_model(
        "m1", "Model 1", 1000, ModelPriority.LOW,
        unload_callback=lambda: True,
    )
    mgr.register_model(
        "m2", "Model 2", 1000, ModelPriority.LOW,
        unload_callback=lambda: True,
    )
    mgr.register_model("m3", "Model 3", 2000, ModelPriority.LOW)
    
    assert mgr.reserve("m1")
    assert mgr.commit("m1")
    time.sleep(0.01) # Ensure time difference
    
    assert mgr.reserve("m2")
    assert mgr.commit("m2")
    
    # Both are LOW, but m1 is older. 
    # Available is (4096 - 500) - 2000 = 1596
    # We need 2000 for m3.
    assert mgr.reserve("m3", force=True)
    
    # m1 should be evicted because it's least recently used
    assert not mgr.is_model_loaded("m1")
    assert mgr.is_model_loaded("m2")
    assert mgr.commit("m3")
    assert mgr.is_model_loaded("m3")


# ======================================================================
# Sensor-Gegencheck (Audit 2026-08-07)
#
# self.monitor war gesetzt, wurde aber in keiner Allokationsentscheidung
# gelesen. Der einzige Gegencheck lag in VRAMArbiter.can_allocate(), das
# repo-weit keinen Aufrufer hat — deshalb stand in 56.746 Logzeilen kein
# einziges "VRAM tracking discrepancy", obwohl die Eigenbuchhaltung um
# ~7,5 GB danebenlag (LM Studio haelt dauerhaft ~6,8 GB auf derselben Karte).
# ======================================================================
class _FakeMonitor:
    """Monitor-Double. ``selected_adapter_luid`` muss zur DirectML-Karte passen,
    sonst verwirft ``_coherent_monitor`` ihn (bewusste Sicherung gegen iGPU-Werte)."""

    def __init__(self, luid, **stats):
        self.selected_adapter_luid = luid
        self._stats = stats
        self.aufrufe = 0

    def get_stats(self, *, force_refresh: bool = False) -> dict:
        self.aufrufe += 1
        return dict(self._stats)


def _adapter_luid():
    from pb_studio.core.directml_adapter import get_directml_adapter

    return get_directml_adapter().luid


def _manager_mit_monitor(monitor):
    from pb_studio.core.vram_budget_manager import VRAMBudgetManager

    VRAMBudgetManager.reset_for_testing()
    return VRAMBudgetManager(monitor=monitor, max_vram_mb=16000)


def test_sensor_free_vram_zieht_sicherheitspuffer_ab():
    monitor = _FakeMonitor(
        _adapter_luid(),
        monitoring_status="ready", gpu_memory_total=16177, gpu_memory_used=11470,
        adapter_luid=_adapter_luid(),
    )
    mgr = _manager_mit_monitor(monitor)
    try:
        # 16177 - 11470 - 500 Puffer
        assert mgr.sensor_free_vram_mb() == 16177 - 11470 - 500
    finally:
        type(mgr).reset_for_testing()


def test_sensor_free_vram_ist_none_ohne_verlaesslichen_sensor():
    from pb_studio.core.vram_budget_manager import VRAMBudgetManager

    for stats in (
        {"monitoring_status": "degraded", "gpu_memory_total": 16177, "gpu_memory_used": 100},
        {"monitoring_status": "ready", "gpu_memory_total": 0, "gpu_memory_used": 0},
    ):
        mgr = _manager_mit_monitor(_FakeMonitor(_adapter_luid(), **stats))
        try:
            assert mgr.sensor_free_vram_mb() is None, stats
        finally:
            VRAMBudgetManager.reset_for_testing()

    mgr = _manager_mit_monitor(None)
    try:
        assert mgr.sensor_free_vram_mb() is None
    finally:
        VRAMBudgetManager.reset_for_testing()


def test_reserve_meldet_diskrepanz_zwischen_buchhaltung_und_sensor(caplog):
    import logging as _logging
    from pb_studio.core.vram_budget_manager import VRAMBudgetManager

    # Sensor sieht real fast nichts frei, die Eigenbuchhaltung glaubt an viel.
    monitor = _FakeMonitor(
        _adapter_luid(),
        monitoring_status="ready", gpu_memory_total=16177, gpu_memory_used=15000,
        adapter_luid=_adapter_luid(),
    )
    mgr = _manager_mit_monitor(monitor)
    try:
        mgr.register_model("testmodell", "Testmodell", 2000)
        with caplog.at_level(_logging.WARNING, logger="pb_studio.core.vram_budget_manager"):
            assert mgr.reserve("testmodell") is True
        text = caplog.text
        assert "VRAM tracking discrepancy" in text, text
        assert "VRAM real knapp" in text, text
    finally:
        VRAMBudgetManager.reset_for_testing()


def test_diskrepanz_meldung_ist_gedrosselt(caplog):
    import logging as _logging
    from pb_studio.core.vram_budget_manager import VRAMBudgetManager

    monitor = _FakeMonitor(
        _adapter_luid(),
        monitoring_status="ready", gpu_memory_total=16177, gpu_memory_used=15000,
        adapter_luid=_adapter_luid(),
    )
    mgr = _manager_mit_monitor(monitor)
    try:
        for i in range(3):
            mgr.register_model(f"m{i}", f"M{i}", 100)
        with caplog.at_level(_logging.WARNING, logger="pb_studio.core.vram_budget_manager"):
            for i in range(3):
                mgr.reserve(f"m{i}")
        treffer = caplog.text.count("VRAM tracking discrepancy")
        assert treffer == 1, f"Meldung nicht gedrosselt: {treffer}x"
    finally:
        VRAMBudgetManager.reset_for_testing()
