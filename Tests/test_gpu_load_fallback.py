"""Test: GPU Load Fallback wenn LHM 0 liefert (Audit D2)."""
import pytest


def test_load_alternative_returns_float():
    from pb_studio.core.system_monitor import SystemMonitor
    sm = SystemMonitor()
    val = sm._query_load_alternative()
    assert isinstance(val, float)
    assert 0.0 <= val <= 100.0


def test_get_stats_includes_load_field():
    from pb_studio.core.system_monitor import SystemMonitor
    sm = SystemMonitor()
    stats = sm.get_stats()
    assert "gpu_load" in stats
    assert isinstance(stats["gpu_load"], (int, float))
    assert 0.0 <= stats["gpu_load"] <= 100.0
