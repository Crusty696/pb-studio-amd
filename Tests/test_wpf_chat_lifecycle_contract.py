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


def test_chat_transport_errors_and_cancellation_remain_visible():
    api = (ROOT / "PBStudio.UI" / "Services" / "ApiClient.cs").read_text(
        encoding="utf-8"
    )
    view_model = (
        ROOT / "PBStudio.UI" / "ViewModels" / "ChatViewModel.cs"
    ).read_text(encoding="utf-8")

    open_stream = api[
        api.index("private async Task<System.IO.Stream?> OpenChatStreamAsync"):
        api.index("private static ChatStreamEvent? ParseChatEvent")
    ]
    assert "return null;" in open_stream
    assert "_logger.LogWarning" in open_stream
    assert "throw;" in open_stream
    assert 'errorMessage = $"Chat-Stream-Fehler: {ex.Message}";' in view_model
    assert 'errorMessage = "Abgebrochen";' in view_model
    assert 'StatusText = "Chat abgebrochen.";' in view_model
