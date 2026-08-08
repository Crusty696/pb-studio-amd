from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_learning_session_play_pause_is_a_real_toggle():
    view_model = (
        ROOT / "PBStudio.UI" / "ViewModels" / "LearningSessionViewModel.cs"
    ).read_text(encoding="utf-8")
    view = (
        ROOT / "PBStudio.UI" / "Views" / "LearningSessionDialog.xaml"
    ).read_text(encoding="utf-8")

    assert "[ObservableProperty] private bool _isPlaying;" in view_model
    assert "if (IsPlaying)" in view_model
    assert "PauseRequested?.Invoke();" in view_model
    assert "PlayRequested?.Invoke(CurrentStartTime, CurrentEndTime);" in view_model
    assert 'Content="{Binding PlayPauseLabel}"' in view
