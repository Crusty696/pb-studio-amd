from pathlib import Path

from pb_studio.config_manager import ConfigManager


def test_resolve_path_accepts_path_objects() -> None:
    resolved = ConfigManager().resolve_path(Path("models") / "test.onnx")

    assert resolved.is_absolute()
    assert resolved.name == "test.onnx"
    assert resolved.parent.name == "models"
