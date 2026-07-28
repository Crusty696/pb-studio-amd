"""Static contract for lossless ProjectOverview refresh generations."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_overview_coalesces_refreshes_and_rejects_stale_results():
    source = (
        ROOT / "PBStudio.UI" / "ViewModels" / "ProjectOverviewViewModel.cs"
    ).read_text(encoding="utf-8")
    refresh = source[
        source.index("public async Task RefreshAsync()") :
        source.index("[RelayCommand]", source.index("public async Task RefreshAsync()"))
    ]
    dispose = source[source.index("public void Dispose()") :]

    assert "private int _refreshVersion;" in source
    assert "private int _refreshActive;" in source
    assert "private int _refreshQueued;" in source
    assert "Interlocked.CompareExchange(ref _refreshActive, 1, 0)" in refresh
    assert "Interlocked.Exchange(ref _refreshQueued, 1);" in refresh
    assert refresh.count("version != Volatile.Read(ref _refreshVersion)") >= 2
    assert refresh.index("var audioClips = await") < refresh.index("ProjectName = info.Name;")
    assert "Interlocked.Exchange(ref _refreshQueued, 0) == 1" in refresh
    assert "await RefreshAsync();" in refresh
    assert "Interlocked.Increment(ref _refreshVersion);" in dispose
    assert "Interlocked.Exchange(ref _refreshQueued, 0);" in dispose
