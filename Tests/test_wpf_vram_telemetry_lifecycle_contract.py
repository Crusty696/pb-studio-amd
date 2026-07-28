"""Static contract for VRAM telemetry request ownership."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_each_telemetry_load_owns_cts_and_only_current_load_clears_state():
    source = (
        ROOT / "PBStudio.UI" / "ViewModels" / "VramTelemetryViewModel.cs"
    ).read_text(encoding="utf-8")
    load = source[
        source.index("public async Task LoadAsync()"):
        source.index("private void ApplyBudget")
    ]

    assert "var previous = _loadCts;" in load
    assert "var current = new CancellationTokenSource();" in load
    assert "previous?.Cancel();" in load
    assert "if (ReferenceEquals(_loadCts, current))" in load
    assert "_loadCts = null;" in load
    assert "current.Dispose();" in load
    assert "if (!_disposed)" in load
