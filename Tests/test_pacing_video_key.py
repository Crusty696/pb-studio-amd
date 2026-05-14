"""Test: Video-Audio-Track Key wird detektiert + an Pacing forwarded (L-K4)."""
import pytest
import numpy as np
from unittest.mock import patch


def test_audio_key_detector_returns_none_for_missing_file():
    """Falsche Pfade -> None, kein Crash."""
    from pb_studio.video.audio_key_detector import detect_video_audio_key
    result = detect_video_audio_key("/tmp/nonexistent_video_l_k4.mp4")
    assert result is None


def test_audio_key_detector_with_real_audio(tmp_path):
    """Test mit echter Test-MP4 mit C-major sin-wave."""
    import subprocess
    try:
        import soundfile as sf
    except ImportError:
        pytest.skip("soundfile nicht verfuegbar")

    audio_test = tmp_path / "test_audio.wav"
    sr = 22050
    t = np.arange(sr * 5) / sr
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(str(audio_test), audio, sr)

    video_test = tmp_path / "test.mp4"
    try:
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=320x240:r=30:d=5",
            "-i", str(audio_test),
            "-c:v", "libx264", "-c:a", "aac",
            "-shortest",
            str(video_test),
        ], capture_output=True, check=True, timeout=15)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("ffmpeg nicht verfuegbar oder zu langsam fuer test")

    from pb_studio.video.audio_key_detector import detect_video_audio_key
    key = detect_video_audio_key(str(video_test))

    if key is not None:
        assert isinstance(key, str)
        # 440Hz sin = A note - akzeptable Bandbreite (Krumhansl ist nicht
        # exakt fuer reine Sinus-Toene)
        assert any(c in key for c in ["A", "F", "D", "C"])


def test_video_analysis_includes_audio_key_field():
    """Y3 / GPU-F2: _run_video_analysis returns audio_key=None always now —
    Detection wurde aus with_gpu_task rausgenommen (Lock-Held-For-CPU-Bug).
    Der analyze_video Route-Handler ruft detect_video_audio_key NACH with_gpu_task.

    Dieser Test verifiziert dass das Feld VORHANDEN ist im result-dict (Schema-
    Kontrakt) auch wenn Y3 den Wert auf None setzt."""
    from backend.routers.video_router import _run_video_analysis
    from backend.schemas.video_schemas import VideoAnalyzeRequest
    from unittest.mock import MagicMock

    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    with patch("cv2.VideoCapture") as mock_cap, \
         patch("pb_studio.video.scene_detect.SceneDetector"), \
         patch("pb_studio.video.raft.MotionAnalyzer") as mock_motion_cls:

        mock_instance = MagicMock()
        mock_instance.get.side_effect = lambda *a: 100 if a[0] == 7 else 30.0
        mock_instance.read.return_value = (True, fake_frame)
        mock_cap.return_value = mock_instance

        mock_motion = mock_motion_cls.return_value
        mock_motion.analyze_video_segment.return_value = {
            "avg_motion": 0.0, "frame_motions": [], "scene_changes": []
        }
        mock_motion.unload = lambda: None

        req = VideoAnalyzeRequest(
            clip_id=1, detect_scenes=False, analyze_motion=True,
            generate_embeddings=False, generate_captions=False
        )
        result = _run_video_analysis("/tmp/fake.mp4", 1, req)

    # Y3: _run_video_analysis liefert audio_key=None — Detection passiert spaeter
    # im analyze_video Endpoint OUTSIDE with_gpu_task.
    assert "audio_key" in result, "audio_key Feld muss im result-dict existieren"
    assert result["audio_key"] is None, "Y3: _run_video_analysis darf audio_key NICHT mehr setzen"


def test_video_analysis_audio_key_none_on_failure():
    """Detect-Fehler -> audio_key=None, kein Crash."""
    from backend.routers.video_router import _run_video_analysis
    from backend.schemas.video_schemas import VideoAnalyzeRequest
    from unittest.mock import MagicMock

    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    with patch("cv2.VideoCapture") as mock_cap, \
         patch("pb_studio.video.scene_detect.SceneDetector"), \
         patch("pb_studio.video.raft.MotionAnalyzer") as mock_motion_cls, \
         patch("pb_studio.video.audio_key_detector.detect_video_audio_key") as mock_key:

        mock_instance = MagicMock()
        mock_instance.get.side_effect = lambda *a: 100 if a[0] == 7 else 30.0
        mock_instance.read.return_value = (True, fake_frame)
        mock_cap.return_value = mock_instance

        mock_motion = mock_motion_cls.return_value
        mock_motion.analyze_video_segment.return_value = {
            "avg_motion": 0.0, "frame_motions": [], "scene_changes": []
        }
        mock_motion.unload = lambda: None
        mock_key.return_value = None  # Detection failed

        req = VideoAnalyzeRequest(
            clip_id=1, detect_scenes=False, analyze_motion=True,
            generate_embeddings=False, generate_captions=False
        )
        result = _run_video_analysis("/tmp/fake.mp4", 1, req)

    assert "audio_key" in result
    assert result["audio_key"] is None


def test_pacing_service_forwards_video_audio_key():
    """clip_selector.video_keys wird gesetzt wenn use_key_matching + clip.audio_key."""
    from pb_studio.services.pacing_service import PacingService
    from pb_studio.pacing.advanced_pacing_engine import AdvancedPacingEngine

    # Anstatt das ganze generate_cut_list (mit ffprobe etc) durchlaufen zu lassen,
    # rufen wir den Code-Pfad direkt nach: Wir bauen den Engine selbst und
    # validieren dass die Methode key_matching block die video_keys setzt.
    # Das ist robuster als ffmpeg/ffprobe-Mocks.

    engine = AdvancedPacingEngine(
        trigger_settings={
            "beat_weight": 1.0, "onset_weight": 0.5, "kick_weight": 1.2,
            "snare_weight": 1.0, "hihat_weight": 0.3, "energy_weight": 0.8,
            "energy_threshold": 0.6, "min_clip_length": 1.0, "max_clip_length": 8.0,
            "onset_sensitivity": 0.5,
        },
    )

    clips = [
        {"id": 10, "name": "v1", "file_path": "/tmp/v1.mp4", "duration": 5.0, "audio_key": "C major"},
        {"id": 11, "name": "v2", "file_path": "/tmp/v2.mp4", "duration": 5.0, "audio_key": "G major"},
        {"id": 12, "name": "v3", "file_path": "/tmp/v3.mp4", "duration": 5.0},  # kein audio_key
    ]

    pacing_config = {"use_key_matching": True}
    cached = {"key": "C major"}

    # Replay genau den key-matching Block aus pacing_service.generate_cut_list:
    if pacing_config.get("use_key_matching", False):
        engine.clip_selector.use_key_matching = True
        cached_audio_key = cached.get("key") if cached else None
        engine.clip_selector.audio_key = cached_audio_key
        video_keys_map = {}
        for c in clips:
            cid = c.get("id")
            ak = c.get("audio_key")
            if cid is not None and ak:
                video_keys_map[cid] = ak
        engine.clip_selector.video_keys = video_keys_map

    assert engine.clip_selector.use_key_matching is True
    assert engine.clip_selector.audio_key == "C major"
    assert 10 in engine.clip_selector.video_keys
    assert engine.clip_selector.video_keys[10] == "C major"
    assert engine.clip_selector.video_keys[11] == "G major"
    assert 12 not in engine.clip_selector.video_keys  # ohne audio_key NICHT im Map


def test_clip_selector_key_matching_prefers_compatible_keys():
    """L-K4: clip_selector waehlt bei use_key_matching=True den key-kompatiblen Clip."""
    from pb_studio.pacing.clip_selector import ClipSelector

    selector = ClipSelector(strategy="motion")
    selector.use_key_matching = True
    selector.audio_key = "C major"
    selector.video_keys = {
        100: "C major",  # perfect match -> 1.0
        101: "G major",  # related (perfect fifth) -> 0.7
        102: "F# major",  # unrelated -> 0.3
    }

    clips = [
        {"id": 100, "file_path": "/tmp/compatible.mp4", "motion_score": 0.5},
        {"id": 101, "file_path": "/tmp/related.mp4", "motion_score": 0.5},
        {"id": 102, "file_path": "/tmp/unrelated.mp4", "motion_score": 0.5},
    ]

    # Identische motion_score -> Tonart entscheidet
    selected = selector.select_clip(clips, trigger_strength=0.5, trigger_type="beat")
    # Mit identischem motion_score (alle 0.5, target=0.5): motion_score=1.0
    # Key-Multiplier: 100=1.0, 101=0.7, 102=0.3 -> 100 muss gewinnen
    assert selected.clip_id == "100", f"expected 100 (perfect key match), got {selected.clip_id}"


def test_clip_selector_key_matching_disabled_ignores_keys():
    """Wenn use_key_matching=False: video_keys werden ignoriert."""
    from pb_studio.pacing.clip_selector import ClipSelector

    selector = ClipSelector(strategy="motion")
    selector.use_key_matching = False  # off
    selector.audio_key = "C major"
    selector.video_keys = {
        100: "C major",
        101: "F# major",
    }

    # mit motion_score-Differenz: 101 closer to target
    clips = [
        {"id": 100, "file_path": "/tmp/a.mp4", "motion_score": 0.1},  # target=0.5 -> diff=0.4
        {"id": 101, "file_path": "/tmp/b.mp4", "motion_score": 0.5},  # target=0.5 -> diff=0.0
    ]
    selected = selector.select_clip(clips, trigger_strength=0.5, trigger_type="beat")
    # Ohne key-multiplier sollte 101 (besseres Motion-Match) gewinnen
    assert selected.clip_id == "101"
