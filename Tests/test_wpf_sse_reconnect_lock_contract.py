"""Static contract for thread-safe SSE reconnect log throttling."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sse_reconnect_dictionary_lookup_and_update_share_state_lock():
    source = (
        ROOT / "PBStudio.UI" / "Services" / "SSEClient.cs"
    ).read_text(encoding="utf-8")
    method = source[
        source.index("private void LogReconnectFailure") :
        source.index("private void ProcessEvent")
    ]
    locked = method[
        method.index("lock (_stateLock)") :
        method.index("if (!shouldLog)")
    ]

    assert "_lastReconnectLogUtc.TryGetValue" in locked
    assert "_lastReconnectLogUtc[endpoint] = now;" in locked
    assert "_logger." not in locked
