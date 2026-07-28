"""Static contract for project-bound Brain UI async loads."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_brain_stats_and_learning_loads_are_generation_bound():
    source = (
        ROOT / "PBStudio.UI" / "ViewModels" / "BrainViewModel.cs"
    ).read_text(encoding="utf-8")
    reset = source[
        source.index("private void ResetForProjectClose()") :
        source.index("[RelayCommand]", source.index("private void ResetForProjectClose()"))
    ]
    stats = source[
        source.index("public async Task RefreshStatsAsync()") :
        source.index("[RelayCommand]", source.index("public async Task RefreshStatsAsync()"))
    ]
    learning = source[
        source.index("public async Task LoadLearningSessionAsync()") :
        source.index("[RelayCommand]", source.index("public async Task LoadLearningSessionAsync()"))
    ]
    dispose = source[source.index("public void Dispose()") :]

    for field in ("_statsLoadVersion", "_learningLoadVersion", "_loadingVersion"):
        assert f"Interlocked.Increment(ref {field});" in reset
        assert f"Interlocked.Increment(ref {field});" in dispose

    assert "statsVersion != Volatile.Read(ref _statsLoadVersion)" in stats
    assert "loadVersion == Volatile.Read(ref _loadingVersion)" in stats
    assert "learningVersion != Volatile.Read(ref _learningLoadVersion)" in learning
    assert "loadVersion == Volatile.Read(ref _loadingVersion)" in learning
