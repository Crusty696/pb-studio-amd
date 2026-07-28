"""Static contract for timeout-safe PythonBridge lifecycle disposal."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bridge_dispose_keeps_gate_alive_for_inflight_start_or_stop():
    source = (
        ROOT / "PBStudio.UI" / "Services" / "PythonBridgeService.cs"
    ).read_text(encoding="utf-8")
    dispose = source[source.index("public void Dispose()") :]

    assert "_disposed = true;" in dispose
    assert "_isStopping = true;" in dispose
    assert "_httpClient.Dispose();" in dispose
    assert "_lifecycleGate.Dispose();" not in dispose


def test_app_exit_can_dispose_provider_after_bounded_cleanup_wait():
    source = (ROOT / "PBStudio.UI" / "App.xaml.cs").read_text(encoding="utf-8")
    on_exit = source[source.index("protected override void OnExit") :]

    assert "cleanup.Wait(TimeSpan.FromSeconds(12))" in on_exit
    assert "_serviceProvider?.Dispose()" in on_exit
