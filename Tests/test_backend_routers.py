"""
Tier-1 Tests für FastAPI Backend Router.

Testet via TestClient (sync, kein echtes I/O):
- audio_router: Import-Validierung, 404/400-Fehlerbehandlung
- video_router: Import (skip-Semantik), Paginierung, 404-Endpoints
- pacing_router: State-Snapshot (keine Cross-Router Imports)
- render_router: Task-Lifecycle (start → status → cancel)
- AppState Isolation zwischen Tests (via Dependency-Override)

WICHTIG: Kein echtes Filesystem/GPU – alle heavy Funktionen werden gemockt.

Hinweis zu Patch-Pfaden:
  backend/routers/__init__.py exportiert `from .audio_router import router as audio_router`.
  Dadurch schlägt `patch("backend.routers.audio_router.publish_event")` fehl (Name-Kollision).
  Wir importieren die Module per importlib und patchen über sys.modules direkt.
"""
import importlib
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.app_state import AppState


# ─────────────────────────────────────────────────────────────────
# Hilfsfunktion: Modul per importlib holen (umgeht __init__ Shadowing)
# ─────────────────────────────────────────────────────────────────

def _get_module(name: str):
    """Gibt das echte Modul zurück, nicht den __init__.py-Alias."""
    if name not in sys.modules:
        importlib.import_module(name)
    return sys.modules[name]


# ─────────────────────────────────────────────────────────────────
# Fixture: frischer AppState pro Test (Dependency Override)
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_state():
    """Gibt einen frischen AppState zurück und überschreibt die DI."""
    from backend.app_state import get_app_state
    state = AppState()
    app.dependency_overrides[get_app_state] = lambda: state
    yield state
    app.dependency_overrides.clear()


@pytest.fixture
def client(fresh_state):
    """TestClient mit frischem State."""
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_gibt_ok_zurueck(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "uptime_seconds" in body
        assert "gpu_available" in body


# ─────────────────────────────────────────────────────────────────
# Audio Router
# ─────────────────────────────────────────────────────────────────

class TestAudioRouter:

    def test_reimport_gleiche_datei_reused_clip_id(self, client, tmp_path, fresh_state):
        audio_mod = _get_module("backend.routers.audio_router")
        orig_probe = audio_mod._probe_audio_info
        orig_pub = audio_mod.publish_event

        async def fake_pub(*a, **kw): pass

        audio_mod._probe_audio_info = lambda _: {"duration": 180.0, "sample_rate": 44100, "channels": 2}
        audio_mod.publish_event = fake_pub

        try:
            audio = tmp_path / "musik.mp3"
            audio.write_bytes(b"\xff\xfb" * 100)
            r1 = client.post("/audio/import", json={"path": str(audio)})
            r2 = client.post("/audio/import", json={"path": str(audio)})
        finally:
            audio_mod._probe_audio_info = orig_probe
            audio_mod.publish_event = orig_pub

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"] == 1
        assert list(fresh_state.audio_clips.keys()) == [1]

    def test_import_datei_nicht_gefunden_404(self, client):
        r = client.post("/audio/import", json={"path": r"C:\nicht\vorhanden\audio.mp3"})
        assert r.status_code == 404
        assert "nicht gefunden" in r.json()["detail"].lower()

    def test_import_relativer_pfad_400(self, client):
        r = client.post("/audio/import", json={"path": "../../../etc/passwd"})
        assert r.status_code == 400
        assert "absolut" in r.json()["detail"].lower()

    def test_import_ungueltiges_format_400(self, client, tmp_path):
        txt = tmp_path / "audio.txt"
        txt.write_text("kein audio")
        r = client.post("/audio/import", json={"path": str(txt)})
        assert r.status_code == 400

    def test_import_erfolgreich(self, client, tmp_path, fresh_state):
        audio_mod = _get_module("backend.routers.audio_router")
        orig_probe = audio_mod._probe_audio_info
        orig_pub = audio_mod.publish_event

        async def fake_pub(*a, **kw): pass

        audio_mod._probe_audio_info = lambda _: {"duration": 180.0, "sample_rate": 44100, "channels": 2}
        audio_mod.publish_event = fake_pub

        try:
            audio = tmp_path / "musik.mp3"
            audio.write_bytes(b"\xff\xfb" * 100)
            r = client.post("/audio/import", json={"path": str(audio)})
        finally:
            audio_mod._probe_audio_info = orig_probe
            audio_mod.publish_event = orig_pub

        assert r.status_code == 200
        body = r.json()
        assert body["id"] == 1
        assert body["name"] == "musik"
        assert body["duration_seconds"] == 180.0
        assert 1 in fresh_state.audio_clips

    def test_beats_nicht_gefunden_404(self, client):
        r = client.get("/audio/beats/999")
        assert r.status_code == 404

    def test_waveform_nicht_gefunden_404(self, client):
        r = client.get("/audio/waveform/999")
        assert r.status_code == 404

    def test_struktur_nicht_gefunden_404(self, client):
        r = client.get("/audio/structure/999")
        assert r.status_code == 404

    def test_spektral_nicht_gefunden_404(self, client):
        r = client.get("/audio/spectral/999")
        assert r.status_code == 404

    def test_spektral_cache_mit_clip_id_crasht_nicht(self, client, fresh_state):
        fresh_state.audio_analysis_cache[1] = {
            "spectral_data": {
                "clip_id": 1,
                "bands": {"bass": [0.1, 0.2]},
                "frequency_ranges": {"bass": [20.0, 250.0]},
            }
        }

        r = client.get("/audio/spectral/1")

        assert r.status_code == 200
        body = r.json()
        assert body["clip_id"] == 1
        assert body["bands"]["bass"] == [0.1, 0.2]

    def test_clips_haben_aufsteigende_ids(self, client, tmp_path, fresh_state):
        audio_mod = _get_module("backend.routers.audio_router")
        orig_probe = audio_mod._probe_audio_info
        orig_pub = audio_mod.publish_event

        async def fake_pub(*a, **kw): pass
        audio_mod._probe_audio_info = lambda _: {"duration": 120.0, "sample_rate": 44100, "channels": 2}
        audio_mod.publish_event = fake_pub

        try:
            for name in ["a.mp3", "b.wav", "c.flac"]:
                f = tmp_path / name
                f.write_bytes(b"\x00" * 100)
                r = client.post("/audio/import", json={"path": str(f)})
                assert r.status_code == 200
        finally:
            audio_mod._probe_audio_info = orig_probe
            audio_mod.publish_event = orig_pub

        ids = list(fresh_state.audio_clips.keys())
        assert ids == [1, 2, 3]

    def test_analyze_uses_stems_if_present(self, client, tmp_path, fresh_state):
        audio_mod = _get_module("backend.routers.audio_router")
        orig_probe = audio_mod._probe_audio_info
        orig_pub = audio_mod.publish_event
        orig_run_analysis = audio_mod._run_audio_analysis

        async def fake_pub(*a, **kw): pass
        audio_mod._probe_audio_info = lambda _: {"duration": 30.0, "sample_rate": 44100, "channels": 2}
        audio_mod.publish_event = fake_pub

        mock_run_analysis = MagicMock(return_value={
            "clip_id": 1,
            "duration_seconds": 30.0,
            "bpm": 120.0,
            "beat_count": 0,
            "beats": [],
            "key": "C Major",
            "energy_curve": [],
            "structure_segments": [],
            "spectral_data": None
        })
        audio_mod._run_audio_analysis = mock_run_analysis

        try:
            audio = tmp_path / "song.mp3"
            audio.write_bytes(b"\x00" * 100)
            
            r_import = client.post("/audio/import", json={"path": str(audio)})
            assert r_import.status_code == 200
            
            clip = fresh_state.get_audio_clip(1)
            stems_paths = {
                "drums": str(tmp_path / "drums.wav"),
                "instrumental": str(tmp_path / "instrumental.wav")
            }
            clip["stems_paths"] = stems_paths
            fresh_state.set_audio_clip(1, clip)

            r_analyze = client.post("/audio/analyze", json={"clip_id": 1, "detect_beats": True})
            assert r_analyze.status_code == 200
        finally:
            audio_mod._probe_audio_info = orig_probe
            audio_mod.publish_event = orig_pub
            audio_mod._run_audio_analysis = orig_run_analysis

        mock_run_analysis.assert_called_once()
        args, kwargs = mock_run_analysis.call_args
        assert args[3] == stems_paths



# ─────────────────────────────────────────────────────────────────
# Video Router
# ─────────────────────────────────────────────────────────────────

class TestVideoRouter:
    def test_reimport_gleiches_video_reused_clip_id(self, client, tmp_path, fresh_state):
        video_mod = _get_module("backend.routers.video_router")
        orig_info = video_mod._get_video_info
        orig_pub = video_mod.publish_event

        async def fake_pub(*a, **kw): pass

        video_mod._get_video_info = lambda _: {
            "duration": 10.0, "width": 1920, "height": 1080, "fps": 30.0, "codec": "h264"
        }
        video_mod.publish_event = fake_pub

        try:
            video = tmp_path / "clip.mp4"
            video.write_bytes(b"\x00" * 100)
            r1 = client.post("/video/import", json={"paths": [str(video)]})
            r2 = client.post("/video/import", json={"paths": [str(video)]})
        finally:
            video_mod._get_video_info = orig_info
            video_mod.publish_event = orig_pub

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()[0]["id"] == r2.json()[0]["id"] == 1
        assert list(fresh_state.video_clips.keys()) == [1]

    """
    Video-Router hat Skip-Semantik: ungültige Dateien werden ignoriert,
    kein Abbruch mit 404/400. Nur Thumbnail/Analyse-Endpoints geben 404.
    """

    def test_import_datei_nicht_vorhanden_gibt_leere_liste(self, client):
        """Video-Router: nicht existierende Datei → leere Liste (kein 404)."""
        r = client.post("/video/import", json={"paths": ["/nicht/vorhanden/clip.mp4"]})
        assert r.status_code == 200
        assert r.json() == []  # leere Liste, kein Fehler

    def test_import_ungueltiges_format_gibt_leere_liste(self, client, tmp_path):
        """Video-Router: ungültiges Format → leere Liste (kein 400)."""
        txt = tmp_path / "video.txt"
        txt.write_text("kein video")
        r = client.post("/video/import", json={"paths": [str(txt)]})
        assert r.status_code == 200
        assert r.json() == []

    def test_clips_liste_gibt_liste_zurueck(self, client):
        """GET /video/clips gibt eine Liste zurück (kein dict)."""
        r = client.get("/video/clips")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert r.json() == []

    def test_clips_paginierung(self, client, fresh_state):
        """Paginierung: 5 Clips, limit=3 → Seite 1: 3, Seite 2: 2."""
        for i in range(1, 6):
            fresh_state.video_clips[i] = {
                "id": i, "name": f"clip_{i}", "path": f"/pfad/clip_{i}.mp4",
                "duration_seconds": 10.0, "width": 1920, "height": 1080,
                "fps": 30.0, "codec": "h264", "thumbnail_available": False, "tags": [],
            }

        r = client.get("/video/clips?page=1&limit=3")
        assert r.status_code == 200
        assert len(r.json()) == 3

        r2 = client.get("/video/clips?page=2&limit=3")
        assert r2.status_code == 200
        assert len(r2.json()) == 2

    def test_thumbnail_nicht_gefunden_404(self, client):
        r = client.get("/video/thumbnails/999")
        assert r.status_code == 404

    def test_analyse_nicht_gefunden_404(self, client):
        r = client.post("/video/analyze", json={"clip_id": 999})
        assert r.status_code == 404

    def test_analyse_liefert_motion_mit_clip_id(self, client, fresh_state):
        video_mod = _get_module("backend.routers.video_router")
        orig_scene = video_mod._run_scene_detection
        orig_gpu = video_mod._run_video_gpu_analysis
        orig_color = video_mod._run_color_and_caption_analysis

        def fake_scene(video_path, detect_scenes):
            return {
                "scene_count": 1,
                "scenes": [{
                    "start_time": 0.0,
                    "end_time": 1.0,
                    "scene_type": "cut",
                    "confidence": 0.9,
                }]
            }

        def fake_gpu(video_path, clip_id, request, _loop=None):
            return {
                "avg_motion": 12.5,
                "motion": {
                    "clip_id": clip_id,
                    "avg_motion": 12.5,
                    "motion_curve": [10.0, 15.0],
                    "peak_frames": [{"frame_index": 3, "confidence": 0.8}],
                    "motion_category": "medium",
                },
                "embedding_dim": 512,
                "embedding_samples": 1,
                "has_embedding": True
            }

        async def fake_color(video_path, clip_id, generate_captions):
            return {
                "dominant_colors": ["#000000"],
                "tags": ["test"],
                "tag_source": "mock"
            }

        video_mod._run_scene_detection = fake_scene
        video_mod._run_video_gpu_analysis = fake_gpu
        video_mod._run_color_and_caption_analysis = fake_color

        fresh_state.video_clips[1] = {
            "id": 1, "name": "clip_1", "path": "C:/clip.mp4",
            "duration_seconds": 10.0, "width": 1920, "height": 1080,
            "fps": 30.0, "codec": "h264", "thumbnail_available": False, "tags": [],
        }

        # R15/C-02: Patch Path.exists so the new file-existence guard passes in tests.
        from pathlib import Path as _Path
        from unittest.mock import patch as _patch

        try:
            with _patch.object(_Path, "exists", return_value=True), \
                 _patch("pb_studio.video.audio_key_detector.detect_video_audio_key", return_value="C Major"):
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

        assert r.status_code == 200
        body = r.json()
        assert body["clip_id"] == 1
        assert body["motion"]["clip_id"] == 1
        assert body["motion"]["avg_motion"] == 12.5

    def test_motion_endpoint_akzeptiert_cache_mit_clip_id(self, client, fresh_state):
        fresh_state.video_analysis_cache[1] = {
            "clip_id": 1,
            "motion": {
                "clip_id": 1,
                "avg_motion": 7.5,
                "motion_curve": [7.5],
                "peak_frames": [],
                "motion_category": "low",
            },
        }

        r = client.get("/video/motion/1")

        assert r.status_code == 200
        body = r.json()
        assert body["clip_id"] == 1
        assert body["avg_motion"] == 7.5
        assert body["motion_category"] == "low"


# ─────────────────────────────────────────────────────────────────
# Pacing Router — kein Cross-Router Import
# ─────────────────────────────────────────────────────────────────

class TestPacingRouter:
    """
    Pacing-Router Response:
    - GET /pacing/timeline → TimelineResponse mit 'entries', 'total_duration', 'audio_path'
    """

    def test_timeline_leer_ohne_generierung(self, client):
        r = client.get("/pacing/timeline")
        assert r.status_code == 200
        body = r.json()
        # TimelineResponse: entries, total_duration, audio_path
        assert "entries" in body
        assert body["entries"] == []
        assert body["total_duration"] == 0.0

    def test_generate_nutzt_appstate_snapshots(self, client, fresh_state):
        """Pacing-Router liest Audio/Video aus AppState — keine Cross-Router-Imports."""
        pacing_mod = _get_module("backend.routers.pacing_router")
        orig_run = pacing_mod._run_pacing_generation
        orig_pub = pacing_mod.publish_event

        async def fake_pub(*a, **kw): pass

        def fake_run(config, audio_clips, video_clips, cached_analysis=None, video_analysis_cache=None, loop=None):
            # Audit L-M7: _run_pacing_generation hat jetzt optionalen loop Param fuer
            # per-iteration pacing_progress callback (SSE).
            # Überprüfung: Snapshots wurden korrekt übergeben
            assert 1 in audio_clips
            assert 1 in video_clips
            # clip_id muss str sein (CutListEntrySchema)
            return [
                {"clip_id": "1", "start_time": 0.0, "end_time": 3.0, "metadata": {}},
                {"clip_id": "1", "start_time": 3.0, "end_time": 6.0, "metadata": {}},
            ]

        pacing_mod._run_pacing_generation = fake_run
        pacing_mod.publish_event = fake_pub

        fresh_state.audio_clips[1] = {"id": 1, "path": "/audio.mp3", "duration_seconds": 120.0}
        fresh_state.video_clips[1] = {"id": 1, "path": "/clip.mp4", "duration_seconds": 10.0}

        try:
            r = client.post("/pacing/generate", json={
                "audio_clip_id": 1, "video_clip_ids": [1],
                "pacing": 3, "precision": 8, "energy_react": 5,
                "chaos": 2, "use_motion_matching": False, "expected_bpm": 120.0
            })
        finally:
            pacing_mod._run_pacing_generation = orig_run
            pacing_mod.publish_event = orig_pub

        assert r.status_code == 200
        body = r.json()
        assert body["cut_count"] == 2
        assert body["total_duration"] == 6.0
        assert len(fresh_state.current_timeline) == 2
        assert fresh_state.current_audio_path == "/audio.mp3"

    def test_generate_leere_clips_gibt_leere_timeline(self, client, fresh_state):
        """Pacing mit gültigen IDs aber leerem Ergebnis → leere Cut-Liste, kein Crash."""
        pacing_mod = _get_module("backend.routers.pacing_router")
        orig_run = pacing_mod._run_pacing_generation
        orig_pub = pacing_mod.publish_event

        async def fake_pub(*a, **kw): pass
        pacing_mod._run_pacing_generation = lambda *a, **kw: []
        pacing_mod.publish_event = fake_pub

        # Gültige Clip-IDs im State anlegen, damit Validierung durchläuft
        fresh_state.audio_clips[1] = {"id": 1, "path": "/audio.mp3", "duration_seconds": 60.0}
        fresh_state.video_clips[1] = {"id": 1, "path": "/clip.mp4", "duration_seconds": 5.0}

        try:
            r = client.post("/pacing/generate", json={
                "audio_clip_id": 1, "video_clip_ids": [1],
                "pacing": 3, "precision": 8, "energy_react": 5,
                "chaos": 2, "use_motion_matching": False, "expected_bpm": 120.0
            })
        finally:
            pacing_mod._run_pacing_generation = orig_run
            pacing_mod.publish_event = orig_pub

        assert r.status_code == 200
        assert r.json()["cut_count"] == 0


# ─────────────────────────────────────────────────────────────────
# Render Router
# ─────────────────────────────────────────────────────────────────

class TestRenderRouter:
    """
    Render-Router:
    - POST /render/start → task_id (Background Task, startet sofort)
    - GET  /render/status/{id} → RenderProgress
    - POST /render/cancel/{id} → {"cancelled": True, "task_id": id}
    """

    def _start_render(self, client, fresh_state):
        """Hilfs-Methode: Render starten mit Timeline im State."""
        fresh_state.current_timeline = [
            {"start_time": 0.0, "end_time": 5.0, "video_id": 1,
             "energy": 0.8, "transition": "cut", "beat_aligned": True}
        ]
        render_mod = _get_module("backend.routers.render_router")
        orig_loop = getattr(render_mod, '_loop_started', None)

        # Render-Task-Loop mocken damit kein echter asyncio.create_task läuft
        import asyncio as _asyncio
        orig_create = _asyncio.get_event_loop

        with patch.object(render_mod.asyncio, 'get_event_loop',
                          return_value=MagicMock(create_task=lambda x: None)):
            r = client.post("/render/start", json={
                "output_path": "/tmp/output.mp4",
                "audio_path": "/audio.mp3",
                "quality": "high",
                "resolution_width": 1920,
                "resolution_height": 1080,
                "fps": 30.0,
                "bitrate_mbps": 12.0,
                "include_audio": True
            })
        return r

    def test_status_nicht_gefunden_404(self, client):
        r = client.get("/render/status/nicht_vorhanden")
        assert r.status_code == 404

    def test_cancel_nicht_gefunden_404(self, client):
        r = client.post("/render/cancel/nicht_vorhanden")
        assert r.status_code == 404

    def test_cancel_setzt_flag(self, client, fresh_state):
        """POST /render/cancel/{id} setzt cancel_flag auf True."""
        task_id = "test_abc"
        fresh_state.render_tasks[task_id] = {
            "task_id": task_id, "status": "running",
            "percent": 50.0, "current_frame": 100, "total_frames": 200,
            "fps": 30.0, "elapsed_seconds": 5.0, "eta_seconds": 5.0,
            "output_path": None, "error": None
        }
        fresh_state.cancel_flags[task_id] = False

        r = client.post(f"/render/cancel/{task_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["cancelled"] is True
        assert body["task_id"] == task_id
        assert fresh_state.cancel_flags[task_id] is True

    def test_status_existierender_task(self, client, fresh_state):
        """GET /render/status/{id} gibt RenderProgress zurück."""
        task_id = "status_test"
        fresh_state.render_tasks[task_id] = {
            "task_id": task_id, "status": "running",
            "percent": 42.0, "current_frame": 300, "total_frames": 900,
            "fps": 29.5, "elapsed_seconds": 10.0, "eta_seconds": 14.0,
            "output_path": None, "error": None
        }

        r = client.get(f"/render/status/{task_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["task_id"] == task_id
        assert body["percent"] == 42.0
        assert body["status"] == "running"
