"""Static contract for generation-safe aggregated SSE connection state."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sse_connection_state_is_aggregated_by_stream_and_generation():
    source = (
        ROOT / "PBStudio.UI" / "Services" / "SSEClient.cs"
    ).read_text(encoding="utf-8")
    listener = source[
        source.index("private async Task ListenAsync") :
        source.index("private void DispatchBufferedEvent")
    ]
    updater = source[
        source.index("private void UpdateStreamState") :
        source.index("private void DispatchBufferedEvent")
    ]

    assert "private readonly HashSet<StreamKind> _connectedStreams = [];" in source
    assert "private int _listenGeneration;" in source
    assert "int generation" in listener
    assert "generation != _listenGeneration" in updater
    assert "_connectedStreams.Count > 0" in updater
    assert "markUnreachable && !connectionValue" in updater
    assert "UpdateStreamState(streamKind, true, generation" in listener
    assert listener.count("UpdateStreamState(streamKind, false, generation") >= 2
    assert "markUnreachable: reconnectAttempts >= NotifyUiAfterAttempts" in listener
    assert "IsConnected = true;" not in listener
    assert "IsConnected = false;" not in listener
