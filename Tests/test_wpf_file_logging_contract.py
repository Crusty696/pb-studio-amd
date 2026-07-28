"""Static contracts for non-blocking WPF file logging."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_file_logger_queues_writes_off_the_calling_thread():
    source = _source("PBStudio.UI/Services/FileLoggerProvider.cs")

    assert "Channel.CreateBounded<string>" in source
    assert "Task.Run(ProcessQueueAsync)" in source
    assert "_writer.TryWrite(line)" in source
    assert "await foreach" in source
    assert "_messages.Writer.TryComplete()" in source
    assert "File.AppendAllText" not in source


def test_main_window_has_no_global_click_audit_hook():
    source = _source("PBStudio.UI/MainWindow.xaml.cs")

    assert "PreviewMouseLeftButtonDown" not in source
    assert "OnPreviewMouseLeftButtonDown" not in source
    assert "[CLICK]" not in source
