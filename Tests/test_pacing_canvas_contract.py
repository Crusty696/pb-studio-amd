"""Contracts for the live Obsidian Canvas pacing path."""

from pathlib import Path
from types import SimpleNamespace

from backend.schemas.pacing_schemas import PacingConfigSchema
from pb_studio.services.pacing_service import PacingService


ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_canvas_path_exists_in_live_request_and_forwarding_contract():
    config = PacingConfigSchema(
        audio_clip_id=1,
        video_clip_ids=[2],
        canvas_path=r"C:\Projects\story.canvas",
    )

    assert config.canvas_path == r"C:\Projects\story.canvas"
    router = _source("backend/routers/pacing_router.py")
    assert '"canvas_path": config.canvas_path' in router


def test_pacing_clip_id_is_prefixed_exactly_once(monkeypatch):
    service = PacingService()
    monkeypatch.setattr(service, "_get_random_clip_start", lambda *_: 0.0)
    monkeypatch.setattr(service, "_get_clip_duration", lambda *_: 30.0)
    cuts = [
        (
            SimpleNamespace(
                time=0.0,
                trigger_type="beat",
                strength=1.0,
                segment_type=None,
            ),
            r"C:\media\clip.mp4",
            "clip_7",
        ),
        (
            SimpleNamespace(
                time=2.0,
                trigger_type="beat",
                strength=1.0,
                segment_type=None,
            ),
            r"C:\media\clip.mp4",
            "7",
        ),
    ]

    result = service._process_pacing_cuts_to_cutlist(cuts, 2.0)

    assert result[0].clip_id == "clip_7"


def test_wpf_canvas_path_is_bound_and_sent():
    view_model = _source("PBStudio.UI/ViewModels/DirectorViewModel.cs")
    view = _source("PBStudio.UI/Views/DirectorView.xaml")
    api = _source("PBStudio.UI/Services/ApiClient.cs")

    assert "[ObservableProperty] private string? _canvasPath;" in view_model
    assert "CanvasPath: CanvasPath" in view_model
    assert "Text=\"{Binding CanvasPath" in view
    assert "string? CanvasPath = null" in api
