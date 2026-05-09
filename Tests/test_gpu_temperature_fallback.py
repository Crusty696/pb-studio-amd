"""Test: GPU Temperature Fallback wenn LHM 0 liefert (Audit D1)."""
import math


def test_temperature_alternative_returns_float():
    """_query_temperature_alternative gibt 0..200 zurueck (kein NaN/Inf)."""
    from pb_studio.core.system_monitor import SystemMonitor
    sm = SystemMonitor()
    val = sm._query_temperature_alternative()
    assert isinstance(val, float)
    assert not math.isnan(val)
    assert not math.isinf(val)
    assert 0.0 <= val <= 200.0


def test_get_stats_includes_temp_field():
    """Smoke: get_stats laeuft, gpu_temp existiert (0 oder real)."""
    from pb_studio.core.system_monitor import SystemMonitor
    sm = SystemMonitor()
    stats = sm.get_stats()
    assert "gpu_temp" in stats
    assert isinstance(stats["gpu_temp"], (int, float))
    assert 0.0 <= float(stats["gpu_temp"]) <= 200.0


def test_temperature_alternative_handles_no_computer():
    """Wenn computer=None (kein LHM), Fallback darf nicht crashen."""
    from pb_studio.core.system_monitor import SystemMonitor
    sm = SystemMonitor()
    # computer kann None sein wenn LHM nicht initialisiert (CI/Linux)
    # Methode muss robust gegen beide Faelle sein
    val = sm._query_temperature_alternative()
    assert isinstance(val, float)
    assert val >= 0.0
