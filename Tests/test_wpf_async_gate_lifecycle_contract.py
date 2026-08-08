"""Static contract for scope-safe WPF async load gates."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEW_MODELS = ROOT / "PBStudio.UI" / "ViewModels"


def _source(name: str) -> str:
    return (VIEW_MODELS / name).read_text(encoding="utf-8")


def _dispose(source: str) -> str:
    return source[source.index("public void Dispose()") :]


def test_inflight_load_gates_are_not_disposed_by_viewmodel_scope_shutdown():
    for name in (
        "AnchorViewModel.cs",
        "VideoLibraryViewModel.cs",
        "DirectorViewModel.cs",
    ):
        assert "_loadGate.Dispose();" not in _dispose(_source(name))


def test_anchor_dispose_invalidates_work_and_blocks_followup_reload():
    source = _source("AnchorViewModel.cs")
    dispose = _dispose(source)
    load = source[
        source.index("private async Task LoadAudioSourcesAsync()") :
        source.index("[RelayCommand]", source.index("private async Task LoadAudioSourcesAsync()"))
    ]

    assert "Interlocked.Increment(ref _loadSequence);" in dispose
    assert "_reloadQueued = false;" in dispose
    assert "_shutdownCts.Cancel();" in dispose
    assert "if (_disposed)" in load
    assert "if (_reloadQueued && !_disposed)" in load


def test_director_dispose_invalidates_work_and_blocks_followup_reload():
    source = _source("DirectorViewModel.cs")
    dispose = _dispose(source)
    load = source[
        source.index("private async Task LoadClipsAsync()") :
        source.index("private async Task RequestClipReloadAsync()")
    ]

    assert "Interlocked.Increment(ref _loadVersion);" in dispose
    assert "_reloadQueued = false;" in dispose
    assert "if (_isShuttingDown)" in load
    assert "version != Volatile.Read(ref _loadVersion) || _isShuttingDown" in load
    assert "if (_reloadQueued && !_isShuttingDown)" in load
