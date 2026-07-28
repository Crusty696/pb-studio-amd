"""Regression tests for the DirectML-only motion-analysis contract."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pb_studio.ai.smart_director import SmartDirector
from pb_studio.video import raft


def test_raft_providers_are_directml_only(monkeypatch: pytest.MonkeyPatch):
    analyzer = raft.MotionAnalyzer(lazy_load=True)
    monkeypatch.setattr(
        raft.ort,
        "get_available_providers",
        lambda: ["DmlExecutionProvider", "CPUExecutionProvider"],
    )

    assert analyzer._get_providers() == [
        ("DmlExecutionProvider", {"device_id": 0})
    ]


def test_raft_has_no_provider_when_directml_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    analyzer = raft.MotionAnalyzer(lazy_load=True)
    monkeypatch.setattr(
        raft.ort,
        "get_available_providers",
        lambda: ["CPUExecutionProvider"],
    )

    assert analyzer._get_providers() == []


def test_factory_ignores_cpu_fallback_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ALLOW_CPU_FALLBACK", "1")
    analyzer = MagicMock()
    analyzer.is_ready = False

    with patch.object(raft, "MotionAnalyzer", return_value=analyzer):
        result = raft.create_motion_analyzer()

    assert result is analyzer


def test_video_package_does_not_export_farneback():
    import pb_studio.video as video

    assert not hasattr(video, "FarnebackFlowAnalyzer")
    assert "FarnebackFlowAnalyzer" not in video.__all__


def test_smart_director_returns_neutral_without_directml_and_unloads():
    analyzer = MagicMock()
    analyzer.is_ready = False
    director = SmartDirector.__new__(SmartDirector)

    with patch.object(raft, "MotionAnalyzer", return_value=analyzer) as constructor:
        score = director._analyze_motion("missing.mp4")

    assert score == 0.5
    constructor.assert_called_once_with(lazy_load=False)
    analyzer.unload.assert_called_once_with()


def test_smart_director_uses_raft_and_releases_video_and_model():
    import cv2

    analyzer = MagicMock()
    analyzer.is_ready = True
    analyzer.get_motion_magnitude.return_value = 25.0

    first_frame = MagicMock()
    second_frame = MagicMock()
    capture = MagicMock()
    capture.isOpened.return_value = True
    capture.get.return_value = 2
    capture.read.side_effect = [
        (True, first_frame),
        (True, second_frame),
    ]
    director = SmartDirector.__new__(SmartDirector)

    with (
        patch.object(raft, "MotionAnalyzer", return_value=analyzer),
        patch.object(cv2, "VideoCapture", return_value=capture),
    ):
        score = director._analyze_motion("clip.mp4")

    assert score == 0.5
    analyzer.get_motion_magnitude.assert_called_once_with(first_frame, second_frame)
    capture.release.assert_called_once_with()
    analyzer.unload.assert_called_once_with()


def test_smart_director_reuses_caller_owned_raft_session():
    import cv2

    analyzer = MagicMock()
    analyzer.is_ready = True
    analyzer.get_motion_magnitude.return_value = 10.0
    capture = MagicMock()
    capture.isOpened.return_value = True
    capture.get.return_value = 2
    capture.read.side_effect = [(True, MagicMock()), (True, MagicMock())]
    director = SmartDirector.__new__(SmartDirector)

    with patch.object(cv2, "VideoCapture", return_value=capture):
        score = director._analyze_motion("clip.mp4", motion_analyzer=analyzer)

    assert score == pytest.approx(0.2)
    analyzer.unload.assert_not_called()


def test_analyze_clips_reuses_one_raft_session_for_the_batch():
    analyzer = MagicMock()
    analyzer.is_ready = True
    first_result = MagicMock()
    second_result = MagicMock()
    director = SmartDirector.__new__(SmartDirector)
    director._ensure_siglip_loaded = MagicMock()
    director._analyze_single_clip = MagicMock(
        side_effect=[first_result, second_result]
    )

    with patch.object(raft, "MotionAnalyzer", return_value=analyzer) as constructor:
        results = director.analyze_clips(["first.mp4", "second.mp4"])

    assert results == [first_result, second_result]
    constructor.assert_called_once_with(lazy_load=False)
    assert director._analyze_single_clip.call_count == 2
    for call in director._analyze_single_clip.call_args_list:
        assert call.kwargs["motion_analyzer"] is analyzer
        assert call.kwargs["analyze_motion"] is True
    analyzer.unload.assert_called_once_with()
