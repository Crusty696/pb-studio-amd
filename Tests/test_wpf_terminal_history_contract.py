"""Static contracts for Terminal history before ViewModel creation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_terminal_sources_share_a_bounded_replay_buffer():
    buffer_source = _source("PBStudio.UI/Services/TerminalLogBuffer.cs")
    logger_source = _source("PBStudio.UI/Services/TerminalLoggerProvider.cs")
    sse_source = _source("PBStudio.UI/Services/SSEClient.cs")
    app_source = _source("PBStudio.UI/App.xaml.cs")

    assert "MaxCharacters = 100_000" in buffer_source
    assert "MaxMessageCharacters = 20_000" in buffer_source
    assert "Logeintrag gekürzt" in buffer_source
    assert "TerminalLogEntry[] Subscribe" in buffer_source
    assert "while (_characterCount > MaxCharacters" in buffer_source
    assert "_buffer.Append(levelStr" in logger_source
    assert "_terminalLogBuffer.Append(logEvent.Level, logEvent.Message)" in sse_source
    assert "services.AddSingleton(terminalLogBuffer);" in app_source


def test_terminal_view_model_replays_and_clears_shared_history():
    source = _source("PBStudio.UI/ViewModels/TerminalViewModel.cs")

    assert "_buffer.Subscribe(OnEntryAdded)" in source
    assert "foreach (var entry in history)" in source
    assert "_buffer.Clear();" in source
    assert "_buffer.Unsubscribe(OnEntryAdded);" in source
    assert "ConcurrentQueue<TerminalLogEntry>" in source
    assert "Interlocked.Exchange(ref _flushScheduled, 1)" in source
    assert "Volatile.Read(ref _disposed)" in source
    assert "WeakReferenceMessenger" not in source
    assert "_sse.LogReceived" not in source


def test_terminal_buffer_redacts_secrets_and_absolute_paths_centrally():
    buffer_source = _source("PBStudio.UI/Services/TerminalLogBuffer.cs")
    logger_source = _source("PBStudio.UI/Services/TerminalLoggerProvider.cs")

    assert "TerminalLogRedactor.Redact(message)" in buffer_source
    assert "message ?? string.Empty" not in buffer_source
    assert "internal static class TerminalLogRedactor" in logger_source
    assert 'RedactedSecret = "[REDACTED]"' in logger_source
    assert 'RedactedPath = "[LOCAL_PATH]"' in logger_source
    assert "BearerPattern.Replace" in logger_source
    assert "SecretAssignmentPattern.Replace" in logger_source
    assert "TokenPattern.Replace" in logger_source
    assert "UrlCredentialsPattern.Replace" in logger_source
    assert "AbsolutePathPattern.Replace" in logger_source
    assert "RegexMatchTimeoutException" in logger_source
    assert 'return "[REDACTION_FAILED]"' in logger_source
