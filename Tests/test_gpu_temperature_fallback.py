"""Temperature monitoring remains adapter-bound without aggregate fallbacks."""


def test_cross_adapter_temperature_fallback_is_removed():
    from pb_studio.core.system_monitor import SystemMonitor

    assert not hasattr(SystemMonitor, "_query_temperature_alternative")


def test_get_stats_includes_temp_field():
    """Smoke: get_stats laeuft, gpu_temp existiert (0 oder real)."""
    from pb_studio.core.system_monitor import SystemMonitor
    sm = SystemMonitor()
    stats = sm.get_stats()
    assert "gpu_temp" in stats
    assert isinstance(stats["gpu_temp"], (int, float))
    assert 0.0 <= float(stats["gpu_temp"]) <= 200.0
