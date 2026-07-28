"""Static contract for ChatViewModel stream ownership."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_chat_stream_is_scope_bound_and_generation_guarded():
    source = (
        ROOT / "PBStudio.UI" / "ViewModels" / "ChatViewModel.cs"
    ).read_text(encoding="utf-8")

    assert "ChatViewModel : ObservableObject, IDisposable" in source
    assert "private int _streamGeneration;" in source
    assert "var generation = Interlocked.Increment(ref _streamGeneration);" in source
    assert "generation != Volatile.Read(ref _streamGeneration)" in source
    assert "current.Dispose();" in source
    assert "Interlocked.Increment(ref _streamGeneration);" in source[
        source.index("public async Task ClearAsync()"):
    ]
    dispose = source[source.index("public void Dispose()"):]
    assert "_streamCts?.Cancel();" in dispose
    assert "_streamCts = null;" in dispose
