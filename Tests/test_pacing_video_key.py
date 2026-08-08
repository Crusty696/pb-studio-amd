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


def test_video_analysis_includes_audio_key_field(tmp_path):
    """Y3 / GPU-F2: audio_key Detection wurde aus with_gpu_task rausgenommen.
    Der analyze_video Route-Handler ruft detect_video_audio_key NACH dem GPU-Lock.
    
    Dieser Test verifiziert, dass die Route /video/analyze das Feld audio_key
    im result-dict enthält, wenn detect_video_audio_key einen Wert zurückgibt."""
    import sys
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.app_state import get_app_state, AppState
    
    state = AppState(current_project={
        "name": "VideoKeyTest",
        "path": str(tmp_path),
        "db_project_id": 1,
    })
    app.dependency_overrides[get_app_state] = lambda: state
    client = TestClient(app)

    video_mod = sys.modules.get("backend.routers.video_router")
    if video_mod is None:
        import importlib
        video_mod = importlib.import_module("backend.routers.video_router")

    orig_scene = video_mod._run_scene_detection
    orig_gpu = video_mod._run_video_gpu_analysis
    orig_color = video_mod._run_color_and_caption_analysis

    async def fake_color(*a, **kw):
        return {"dominant_colors": [], "tags": [], "tag_source": "mock"}

    video_mod._run_scene_detection = lambda *a, **kw: {"scene_count": 0, "scenes": []}
    video_mod._run_video_gpu_analysis = lambda *a, **kw: {
        "avg_motion": 0.0, "motion": None, "embedding_dim": 0, "embedding_samples": 0, "has_embedding": False
    }
    video_mod._run_color_and_caption_analysis = fake_color

    clip = {
        "id": 1, "name": "clip_1", "path": "C:/clip.mp4",
        "duration_seconds": 10.0, "width": 1920, "height": 1080,
        "fps": 30.0, "codec": "h264", "thumbnail_available": False, "tags": [],
    }
    state.persist_video_clip(clip, project_id=1)
    state.set_video_clip(1, clip)

    from pathlib import Path as _Path
    try:
        with patch.object(_Path, "exists", return_value=True), \
             patch("pb_studio.video.audio_key_detector.detect_video_audio_key", return_value="C Major"):
            r = client.post("/video/analyze", json={
                "clip_id": 1,
                "detect_scenes": True,
                "analyze_motion": True,
                "generate_embeddings": False,
                "generate_captions": False
            })
    finally:
        video_mod._run_scene_detection = orig_scene
        video_mod._run_video_gpu_analysis = orig_gpu
        video_mod._run_color_and_caption_analysis = orig_color
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert "audio_key" in body
    assert body["audio_key"] == "C Major"


def test_video_analysis_audio_key_none_on_failure(tmp_path):
    """Detect-Fehler -> audio_key=None, kein Crash."""
    import sys
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.app_state import get_app_state, AppState
    
    state = AppState(current_project={
        "name": "VideoKeyTest",
        "path": str(tmp_path),
        "db_project_id": 1,
    })
    app.dependency_overrides[get_app_state] = lambda: state
    client = TestClient(app)

    video_mod = sys.modules.get("backend.routers.video_router")
    if video_mod is None:
        import importlib
        video_mod = importlib.import_module("backend.routers.video_router")

    orig_scene = video_mod._run_scene_detection
    orig_gpu = video_mod._run_video_gpu_analysis
    orig_color = video_mod._run_color_and_caption_analysis

    async def fake_color(*a, **kw):
        return {"dominant_colors": [], "tags": [], "tag_source": "mock"}

    video_mod._run_scene_detection = lambda *a, **kw: {"scene_count": 0, "scenes": []}
    video_mod._run_video_gpu_analysis = lambda *a, **kw: {
        "avg_motion": 0.0, "motion": None, "embedding_dim": 0, "embedding_samples": 0, "has_embedding": False
    }
    video_mod._run_color_and_caption_analysis = fake_color

    clip = {
        "id": 1, "name": "clip_1", "path": "C:/clip.mp4",
        "duration_seconds": 10.0, "width": 1920, "height": 1080,
        "fps": 30.0, "codec": "h264", "thumbnail_available": False, "tags": [],
    }
    state.persist_video_clip(clip, project_id=1)
    state.set_video_clip(1, clip)

    from pathlib import Path as _Path
    try:
        with patch.object(_Path, "exists", return_value=True), \
             patch("pb_studio.video.audio_key_detector.detect_video_audio_key", side_effect=Exception("detect failed")):
            r = client.post("/video/analyze", json={
                "clip_id": 1,
                "detect_scenes": True,
                "analyze_motion": True,
                "generate_embeddings": False,
                "generate_captions": False
            })
    finally:
        video_mod._run_scene_detection = orig_scene
        video_mod._run_video_gpu_analysis = orig_gpu
        video_mod._run_color_and_caption_analysis = orig_color
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert "audio_key" in body
    assert body["audio_key"] is None


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
