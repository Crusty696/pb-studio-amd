"""Static contract for truthful ProjectOverview constructor wiring."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_overview_does_not_inject_unused_video_state():
    source = (
        ROOT / "PBStudio.UI" / "ViewModels" / "ProjectOverviewViewModel.cs"
    ).read_text(encoding="utf-8")
    constructor = source[
        source.index("public ProjectOverviewViewModel(") :
        source.index("[RelayCommand]", source.index("public ProjectOverviewViewModel("))
    ]

    assert "VideoLibraryStateService" not in constructor
    assert "_videoState" not in source
