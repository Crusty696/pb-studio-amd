"""GPU load monitoring remains adapter-bound without aggregate fallbacks."""


def test_cross_adapter_load_fallback_is_removed():
    from pb_studio.core.system_monitor import SystemMonitor

    assert not hasattr(SystemMonitor, "_query_load_alternative")


def test_get_stats_includes_load_field():
    from pb_studio.core.system_monitor import SystemMonitor
    sm = SystemMonitor()
    stats = sm.get_stats()
    assert "gpu_load" in stats
    assert isinstance(stats["gpu_load"], (int, float))
    assert 0.0 <= stats["gpu_load"] <= 100.0
