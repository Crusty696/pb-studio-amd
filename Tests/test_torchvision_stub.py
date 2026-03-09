import sys


def test_torchvision_stub_registers_when_missing(monkeypatch):
    from pb_studio.audio import separator as separator_module

    sys.modules.pop("torchvision", None)
    sys.modules.pop("torchvision.ops", None)

    monkeypatch.setattr(separator_module.importlib.util, "find_spec", lambda name: None if name == "torchvision" else object())

    created = separator_module._ensure_torchvision_stub()

    assert created is True
    assert "torchvision" in sys.modules
    assert hasattr(sys.modules["torchvision"].ops, "nms")

