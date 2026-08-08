"""Import-state regressions for the optional BeatNet dependency."""

import importlib
import importlib.util
import sys

import pytest


def test_missing_pyaudio_stub_does_not_leak_into_sys_modules():
    sys.modules.pop("pyaudio", None)
    if importlib.util.find_spec("pyaudio") is not None:
        pytest.skip("Real PyAudio is installed")

    import pb_studio.audio.beat_detector as beat_detector

    importlib.reload(beat_detector)

    assert "pyaudio" not in sys.modules
