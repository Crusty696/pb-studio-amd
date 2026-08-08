"""Static contracts for reachable project lifecycle actions."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_overview_exposes_save_and_close_for_open_projects():
    view_model = (
        ROOT / "PBStudio.UI" / "ViewModels" / "ProjectOverviewViewModel.cs"
    ).read_text(encoding="utf-8")
    view = (
        ROOT / "PBStudio.UI" / "Views" / "ProjectOverviewView.xaml"
    ).read_text(encoding="utf-8")

    assert "[RelayCommand(CanExecute = nameof(CanManageProject))]" in view_model
    assert "private async Task SaveProjectAsync()" in view_model
    assert "private async Task CloseProjectAsync()" in view_model
    assert "var success = await _projectService.CloseProjectAsync();" in view_model
    assert '"Fehler: Projekt konnte nicht geschlossen werden."' in view_model
    assert 'Command="{Binding SaveProjectCommand}"' in view
    assert 'Command="{Binding CloseProjectCommand}"' in view


def test_project_commands_are_not_duplicated_in_main_view_model():
    main_view_model = (
        ROOT / "PBStudio.UI" / "ViewModels" / "MainViewModel.cs"
    ).read_text(encoding="utf-8")

    assert "private async Task CreateProject()" not in main_view_model
    assert "private async Task OpenProject()" not in main_view_model
    assert "private async Task SaveProject()" not in main_view_model
    assert "private async Task CloseProject()" not in main_view_model


def test_anchor_audio_reload_remains_internal_without_generated_command():
    anchor_view_model = (
        ROOT / "PBStudio.UI" / "ViewModels" / "AnchorViewModel.cs"
    ).read_text(encoding="utf-8")

    method = "private async Task LoadAudioSourcesAsync()"
    assert f"[RelayCommand]\n    {method}" not in anchor_view_model
    assert "await LoadAudioSourcesAsync();" in anchor_view_model
