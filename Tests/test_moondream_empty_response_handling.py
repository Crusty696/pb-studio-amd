from PIL import Image


def test_generate_caption_no_model_returns_placeholder(monkeypatch):
    """IRON RULE: kein PyTorch-Fallback — nicht-initialisierter Analyzer liefert Platzhaltertext."""
    from pb_studio.video.moondream import MoondreamAnalyzer

    analyzer = MoondreamAnalyzer(lazy_load=True)
    # Simuliere: Modell nicht gefunden (_init_model gibt False zurück)
    monkeypatch.setattr(analyzer, "_init_model", lambda: False)

    image = Image.new("RGB", (8, 8), color="white")
    result = analyzer.generate_caption(image, "Describe this image.")

    assert result == "[Moondream-Modell nicht gefunden]"


def test_video_vision_worker_reports_pytorch_for_analyzer_fallback(monkeypatch):
    from pb_studio.workers.video.video_vision_worker import VideoVisionWorker

    class AnalyzerStub:
        def __init__(self, lazy_load=False):
            self.is_ready = True
            self.active_provider = "PyTorch (CPU)"
            self._hybrid_mode = False

    monkeypatch.setattr(
        "pb_studio.video.moondream.MoondreamAnalyzer",
        AnalyzerStub,
        raising=False,
    )

    worker = VideoVisionWorker("dummy.mp4", scenes=[])
    model_type = worker._init_vision_model()

    assert model_type == "PyTorch"
