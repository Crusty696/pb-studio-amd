"""Static contract for truthful ProjectOverview timeline state."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_overview_uses_derived_timeline_status_and_action_state():
    view_model = (
        ROOT / "PBStudio.UI" / "ViewModels" / "ProjectOverviewViewModel.cs"
    ).read_text(encoding="utf-8")
    view = (
        ROOT / "PBStudio.UI" / "Views" / "ProjectOverviewView.xaml"
    ).read_text(encoding="utf-8")

    assert '"Kein Projekt geöffnet"' in view_model
    assert '"Noch keine Video-Timeline"' in view_model
    assert '"Video Timeline generiert"' in view_model
    assert "public bool CanGenerateTimeline" in view_model
    assert 'Text="{Binding TimelineStatusText}"' in view
    assert (
        "Visibility=\"{Binding CanGenerateTimeline, "
        "Converter={StaticResource BooleanToVisibilityConverter}}\""
    ) in view
    assert 'Text="Video Timeline generiert"' not in view
