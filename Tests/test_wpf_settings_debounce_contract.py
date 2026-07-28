"""Static contract for the Settings VRAM slider debounce."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_vram_debounce_preserves_ui_context_and_disposes_replaced_cts():
    source = (
        ROOT / "PBStudio.UI" / "ViewModels" / "SettingsViewModel.cs"
    ).read_text(encoding="utf-8")
    start = source.index("partial void OnVramLimitMbChanged")
    end = source.index("private void UpdateKiModeLabels", start)
    debounce = source[start:end]

    assert "Task.Run" not in debounce
    assert "_ = UpdateVramLimitAfterDelayAsync(value, current.Token);" in debounce
    assert "previous?.Cancel();" in debounce
    assert "previous?.Dispose();" in debounce
    assert "private async Task UpdateVramLimitAfterDelayAsync" in debounce
    assert "_disposed || ct.IsCancellationRequested" in debounce


def test_ffmpeg_probe_is_path_bound_and_only_current_probe_clears_state():
    source = (
        ROOT / "PBStudio.UI" / "ViewModels" / "SettingsViewModel.cs"
    ).read_text(encoding="utf-8")
    path_changed = source[
        source.index("partial void OnFfmpegPathChanged"):
        source.index("[RelayCommand]", source.index("partial void OnFfmpegPathChanged"))
    ]
    probe = source[
        source.index("private async Task ProbeFfmpegAsync()"):
        source.index("[RelayCommand]", source.index("private async Task ProbeFfmpegAsync()") + 1)
    ]

    assert "_probeCts?.Cancel();" in path_changed
    assert "var previous = _probeCts;" in probe
    assert "var current = new CancellationTokenSource();" in probe
    assert "previous?.Cancel();" in probe
    assert "if (ReferenceEquals(_probeCts, current))" in probe
    assert "_probeCts = null;" in probe
    assert "current.Dispose();" in probe
