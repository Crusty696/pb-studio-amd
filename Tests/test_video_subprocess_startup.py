"""Platform-neutral regression tests for hidden video subprocess startup."""

import importlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


video_router = importlib.import_module("backend.routers.video_router")


class _FakeStartupInfo:
    def __init__(self) -> None:
        self.dwFlags = 0


@pytest.fixture
def fake_windows_subprocess(monkeypatch):
    monkeypatch.setattr(video_router, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(subprocess, "STARTUPINFO", _FakeStartupInfo, raising=False)
    monkeypatch.setattr(subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)


def test_get_video_info_hides_ffprobe_window_on_windows(
    monkeypatch,
    fake_windows_subprocess,
):
    captured = {}

    def fake_check_output(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return json.dumps({
            "streams": [{
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "30/1",
                "codec_name": "h264",
                "duration": "10.0",
            }],
            "format": {"duration": "10.0"},
        }).encode("utf-8")

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    result = video_router._get_video_info(r"C:\media\clip.mp4")

    startupinfo = captured["kwargs"]["startupinfo"]
    assert isinstance(startupinfo, _FakeStartupInfo)
    assert startupinfo.dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert captured["command"][-1] == r"C:\media\clip.mp4"
    assert result["duration"] == 10.0


def test_generate_thumbnail_hides_ffmpeg_window_on_windows(
    monkeypatch,
    fake_windows_subprocess,
):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        Path(command[-1]).write_bytes(b"jpeg-data")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = video_router._generate_thumbnail(r"C:\media\clip.mp4")

    startupinfo = captured["kwargs"]["startupinfo"]
    assert isinstance(startupinfo, _FakeStartupInfo)
    assert startupinfo.dwFlags & subprocess.STARTF_USESHOWWINDOW
    assert captured["command"][3] == r"C:\media\clip.mp4"
    assert result == b"jpeg-data"


@pytest.mark.parametrize("function_name", ["_get_video_info", "_generate_thumbnail"])
def test_video_subprocesses_leave_startupinfo_empty_off_windows(
    monkeypatch,
    function_name,
):
    monkeypatch.setattr(video_router, "os", SimpleNamespace(name="posix"))
    captured = {}

    if function_name == "_get_video_info":
        def fake_check_output(_command, **kwargs):
            captured.update(kwargs)
            return json.dumps({
                "streams": [{"r_frame_rate": "1/1"}],
                "format": {"duration": "1.0"},
            }).encode("utf-8")

        monkeypatch.setattr(subprocess, "check_output", fake_check_output)
        video_router._get_video_info("/media/clip.mp4")
    else:
        def fake_run(command, **kwargs):
            captured.update(kwargs)
            Path(command[-1]).write_bytes(b"jpeg-data")

        monkeypatch.setattr(subprocess, "run", fake_run)
        video_router._generate_thumbnail("/media/clip.mp4")

    assert captured["startupinfo"] is None
