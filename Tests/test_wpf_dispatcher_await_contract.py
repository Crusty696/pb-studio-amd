from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ui_bound_namespaces_preserve_dispatcher_context():
    sources = [
        *sorted((ROOT / "PBStudio.UI" / "ViewModels").glob("*.cs")),
        *sorted((ROOT / "PBStudio.UI" / "Views").glob("*.xaml.cs")),
        ROOT / "PBStudio.UI" / "MainWindow.xaml.cs",
    ]
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in sources
        if "ConfigureAwait(false)" in path.read_text(encoding="utf-8-sig")
    ]
    assert offenders == []


def test_services_keep_non_ui_configure_await_policy():
    for relative in (
        "PBStudio.UI/Services/ApiClient.cs",
        "PBStudio.UI/Services/SSEClient.cs",
        "PBStudio.UI/Services/PythonBridgeService.cs",
    ):
        assert "ConfigureAwait(false)" in (ROOT / relative).read_text(
            encoding="utf-8-sig"
        )


def test_native_dispatcher_continuation_regression_exists():
    source = (
        ROOT / "PBStudio.UI.Tests" / "DispatcherAwaitContractTests.cs"
    ).read_text(encoding="utf-8-sig")
    assert "VramRefresh_ContinuationPublishesOnRegisteredDispatcher" in source
    assert "dispatcher.CheckAccess()" in source
