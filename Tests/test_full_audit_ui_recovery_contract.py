"""UI contracts for recovery when render SSE progress has a gap."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_replay_gap_triggers_render_status_reconciliation():
    source = (ROOT / "PBStudio.UI/ViewModels/ProductionViewModel.cs").read_text(
        encoding="utf-8"
    )

    assert 'if (e.EventType == "replay_gap")' in source
    assert "_ = ReconcileRenderStatusAsync();" in source
    assert "_api.GetRenderStatusAsync(taskId)" in source
    assert "status.TaskId, _currentTaskId" in source
    assert "ApplyProgressUpdate(" in source


def test_validation_phases_reach_render_view_model_and_visible_ui():
    source = (ROOT / "PBStudio.UI/ViewModels/ProductionViewModel.cs").read_text(
        encoding="utf-8"
    )
    events = (ROOT / "PBStudio.UI/Services/SSEClient.cs").read_text(
        encoding="utf-8"
    )
    view = (ROOT / "PBStudio.UI/Views/ProductionView.xaml").read_text(
        encoding="utf-8"
    )

    assert 'TryGetString(root, "validation_phase")' in events
    assert "UpdateValidationText(" in source
    assert "GetRenderStatusAsync(taskId)" in source
    assert 'Text="{Binding ValidationText}"' in view
