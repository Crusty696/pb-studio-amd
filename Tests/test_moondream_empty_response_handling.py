from PIL import Image


def test_generate_caption_surfaces_empty_pytorch_response(monkeypatch):
    from pb_studio.video.moondream import MoondreamAnalyzer

    analyzer = MoondreamAnalyzer(lazy_load=True)
    analyzer._initialized = True
    analyzer._pytorch_fallback = type(
        "Fallback",
        (),
        {"answer_question": lambda self, image, prompt: "   "},
    )()

    image = Image.new("RGB", (8, 8), color="white")
    result = analyzer.generate_caption(image, "Describe this image.")

    assert result == "[Error: Model returned empty response]"


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
