"""Static contracts for lossless WPF timeline lifecycle transitions."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "PBStudio.UI"


def _read(relative: str) -> str:
    return (UI / relative).read_text(encoding="utf-8")


def test_flush_coordinator_is_registered_and_owned_by_active_timeline() -> None:
    app = _read("App.xaml.cs")
    timeline = _read("ViewModels/TimelineViewModel.cs")
    contract = _read("Services/ITimelineFlushCoordinator.cs")
    implementation = _read("Services/TimelineFlushCoordinator.cs")

    assert "services.AddSingleton<ITimelineFlushCoordinator, TimelineFlushCoordinator>();" in app
    assert "TimelineFlushResult" in contract
    assert "Register(" in contract
    assert "FlushAsync(" in contract
    assert "SemaphoreSlim" in implementation
    assert "ITimelineFlushCoordinator? timelineFlushCoordinator" in timeline
    assert "_timelineFlushRegistration = timelineFlushCoordinator.Register(" in timeline
    assert "_timelineFlushRegistration?.Dispose();" in timeline


def test_project_lifecycle_flushes_before_save_or_transition() -> None:
    source = _read("Services/ProjectService.cs")

    for start, end, api_call in (
        ("public async Task<bool> CreateProjectAsync", "public async Task<bool> OpenProjectAsync", "_api.CreateProjectAsync"),
        ("public async Task<bool> OpenProjectAsync", "public async Task<bool> SaveProjectAsync", "_api.OpenProjectAsync"),
        ("public async Task<bool> SaveProjectAsync", "public async Task<bool> RefreshProjectInfoAsync", "_api.SaveProjectAsync"),
        ("public async Task<bool> CloseProjectAsync", "private void RestoreStableProject", "_api.CloseProjectAsync"),
    ):
        method = source[source.index(start) : source.index(end)]
        flush = method.index("FlushTimelineAsync")
        api = method.index(api_call)
        assert flush < api
        if "BeginProjectTransition();" in method:
            assert flush < method.index("BeginProjectTransition();") < api
        assert "await FlushTimelineAsync" in method
        assert ").Success" in method


def test_window_close_is_async_reentrant_and_app_exit_never_saves_again() -> None:
    window = _read("MainWindow.xaml.cs")
    app = _read("App.xaml.cs")
    gate = _read("Services/MainWindowCloseGate.cs")
    closing = window[window.index("private async void OnClosing") :]
    on_exit = app[app.index("protected override void OnExit") :]

    assert "e.Cancel = true;" in closing
    assert "await _closeGate.TryAuthorizeAsync()" in closing
    assert "result.InProgress" in closing
    assert "if (!result.Authorized)" in closing
    assert "Close();" in closing
    assert "Interlocked.CompareExchange(ref _running, 1, 0)" in gate
    authorize = gate[gate.index("public async Task<MainWindowCloseResult> TryAuthorizeAsync") :]
    assert authorize.index("await projectService.SaveProjectAsync()") < authorize.index(
        "Interlocked.Exchange(ref _authorized, 1)"
    )
    assert "SaveProjectAsync()" not in on_exit
    assert on_exit.index("BeginShutdown()") < on_exit.index("ShutdownAsync()")


def test_flush_failure_is_a_first_class_result_not_a_silent_status_string() -> None:
    timeline = _read("ViewModels/TimelineViewModel.cs")
    coordinator = _read("Services/TimelineFlushCoordinator.cs")

    assert "Task<TimelineFlushResult> FlushPendingTimelineAsync" in timeline
    assert "TimelineFlushResult.Failed" in timeline
    assert "TimelineFlushResult.Succeeded" in timeline
    assert "return TimelineFlushResult.Failed" in coordinator
    project = _read("Services/ProjectService.cs")
    close_gate = _read("Services/MainWindowCloseGate.cs")
    assert "LastTimelineFlushResult" in project
    assert "flushFailure.Cancelled" in close_gate
    assert "flushFailure.ErrorMessage" in close_gate
