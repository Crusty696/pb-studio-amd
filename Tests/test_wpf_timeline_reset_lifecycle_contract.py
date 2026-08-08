"""Static contract for reset-safe Timeline async work."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_timeline_reset_invalidates_async_generations_and_keeps_gate_alive():
    source = (
        ROOT / "PBStudio.UI" / "ViewModels" / "TimelineViewModel.cs"
    ).read_text(encoding="utf-8")
    reset = source[
        source.index("private void ResetTimelineState()"):
        source.index("public void Dispose()")
    ]
    dispose = source[source.index("public void Dispose()"):]
    refresh = source[
        source.index("private async Task RefreshTimelineAsync()"):
        source.index("[RelayCommand]", source.index("private async Task RefreshTimelineAsync()"))
    ]
    waveform = source[
        source.index("private async Task LoadWaveformAsync"):
        source.index("private async Task RequestTimelineRefreshAsync")
    ]

    for field in ("_loadVersion", "_waveformSequence", "_motionLoadSequence"):
        assert f"Interlocked.Increment(ref {field});" in reset
        assert f"Interlocked.Increment(ref {field});" in dispose

    assert "version != Volatile.Read(ref _loadVersion)" in refresh
    assert "seq != Volatile.Read(ref _waveformSequence)" in waveform
    assert "if (seq == Volatile.Read(ref _waveformSequence))" in waveform
    assert "_loadGate.Dispose();" not in dispose
