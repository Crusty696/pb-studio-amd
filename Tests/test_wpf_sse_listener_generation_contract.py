"""Static contract for generation-bound SSE listener tokens."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sse_start_captures_one_local_cts_for_all_listener_tasks():
    source = (
        ROOT / "PBStudio.UI" / "Services" / "SSEClient.cs"
    ).read_text(encoding="utf-8")
    start = source[
        source.index("public void StartListening()") :
        source.index("public void StopListening()")
    ]

    assert "if (_disposed)" in start
    assert "var listenCts = new CancellationTokenSource();" in start
    assert "_cts = listenCts;" in start
    assert start.count("listenCts.Token") == 3
    assert "_cts.Token" not in start
