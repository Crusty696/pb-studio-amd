"""Static WPF contracts for project-scoped cache invalidation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_direct_project_switch_publishes_full_lifecycle():
    source = _source("PBStudio.UI/Services/ProjectService.cs")

    assert "SwitchToProject" in source
    method = source[source.index("private void SwitchToProject"):]
    closing = method.index("new ProjectClosingMessage()")
    closed = method.index("new ProjectClosedMessage()")
    opened = method.index("new ProjectOpenedMessage()")
    assert closing < closed < opened


def test_audio_project_reset_invalidates_shared_cache():
    source = _source("PBStudio.UI/ViewModels/AudioLibraryViewModel.cs")
    reset = source[source.index("private void ResetProjectState()"):]

    assert "_audioLibraryState.Clear();" in reset


def test_export_project_switch_clears_and_reloads_timeline_state():
    source = _source("PBStudio.UI/ViewModels/ProductionViewModel.cs")
    opened = source[
        source.index(
            "Register<ProjectOpenedMessage>"
        ):source.index("Register<ProjectClosedMessage>")
    ]
    closed = source[
        source.index(
            "Register<ProjectClosedMessage>"
        ):source.index("if (HasProject)")
    ]

    assert 'StatusText = "Bereit für Rendering";' in opened
    assert "_ = SyncAudioPathFromTimelineAsync();" in opened
    assert "_timelineState.Clear();" in closed


def test_library_state_services_reject_late_refresh_results():
    for relative_path in (
        "PBStudio.UI/Services/AudioLibraryStateService.cs",
        "PBStudio.UI/Services/VideoLibraryStateService.cs",
    ):
        source = _source(relative_path)
        assert "_generation" in source
        assert "generation != _generation" in source


def test_video_project_reset_clears_thumbnail_identity_caches():
    source = _source("PBStudio.UI/ViewModels/VideoLibraryViewModel.cs")
    clear = source[source.index("private void ClearClips()"):]

    assert "_thumbnailCache.Clear();" in clear
    assert "_thumbnailFailureCache.Clear();" in clear


def test_project_lifecycle_messages_are_dispatched_to_ui_thread():
    source = _source("PBStudio.UI/Services/ProjectService.cs")
    close_method = source[source.index("public async Task<bool> CloseProjectAsync()"):]
    switch_method = source[source.index("private void SwitchToProject"):]

    assert close_method.count("RunOnUiThread(") >= 2
    assert "RunOnUiThread(() =>" in switch_method
    assert "dispatcher.Invoke(action);" in source


def test_failed_project_close_preserves_local_state_and_caches():
    source = _source("PBStudio.UI/Services/ProjectService.cs")
    close_method = source[
        source.index("public async Task<bool> CloseProjectAsync()"):
        source.index("private void SwitchToProject")
    ]

    api_result = close_method.index("await _api.CloseProjectAsync()")
    failure_guard = close_method.index("result?.Success != true")
    closing_message = close_method.index("new ProjectClosingMessage()")
    state_reset = close_method.index("CurrentProject = null")

    assert api_result < failure_guard < closing_message < state_reset
    assert "return false;" in close_method
    assert "return true;" in close_method


def test_project_info_refresh_uses_single_dispatched_switch_lifecycle():
    service = _source("PBStudio.UI/Services/ProjectService.cs")
    main_view_model = _source("PBStudio.UI/ViewModels/MainViewModel.cs")
    refresh = service[
        service.index("public async Task<bool> RefreshProjectInfoAsync()"):
        service.index("public async Task<bool> CloseProjectAsync()")
    ]
    initialize = main_view_model[
        main_view_model.index("private async Task InitializeAsync()"):
        main_view_model.index("private void OnBackendStatusChanged")
    ]

    assert "if (project == null)" in refresh
    assert "SwitchToProject(project);" in refresh
    assert "CurrentProject = project;" not in refresh
    assert "new ProjectOpenedMessage()" not in refresh
    assert "new ProjectOpenedMessage()" not in initialize


def test_project_save_publishes_state_on_ui_thread():
    source = _source("PBStudio.UI/Services/ProjectService.cs")
    save = source[
        source.index("public async Task<bool> SaveProjectAsync()"):
        source.index("public async Task<bool> RefreshProjectInfoAsync()")
    ]

    assert "var refreshedProject = await _api.GetProjectInfoAsync()" in save
    ui_update = save[save.index("RunOnUiThread(() =>"):]
    assert "CurrentProject = refreshedProject ?? CurrentProject;" in ui_update
    assert "ProjectChanged?.Invoke(this, CurrentProject);" in ui_update
