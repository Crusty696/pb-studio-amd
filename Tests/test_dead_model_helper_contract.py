"""Static contract preventing unmanaged, unreferenced model shortcuts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_unmanaged_model_convenience_helpers_are_absent():
    video_specialist = (
        ROOT / "src" / "pb_studio" / "ai" / "video_specialist.py"
    ).read_text(encoding="utf-8")
    moondream = (
        ROOT / "src" / "pb_studio" / "video" / "moondream.py"
    ).read_text(encoding="utf-8")

    assert "def analyze_video_similarity(" not in video_specialist
    assert "def tag_video_quick(" not in video_specialist
    assert "\ndef analyze_image(" not in moondream
