"""Static contract for the Python 3.11-only WPF backend launcher."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_python_bridge_accepts_only_verified_python_311():
    source = (
        ROOT / "PBStudio.UI" / "Services" / "PythonBridgeService.cs"
    ).read_text(encoding="utf-8")

    assert "Python312" not in source
    assert 'return "python";' not in source
    assert "IsPython311" in source
    assert 'StartsWith("Python 3.11."' in source
    assert "Python 3.11 wurde nicht gefunden" in source
