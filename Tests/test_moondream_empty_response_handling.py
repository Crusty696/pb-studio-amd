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
