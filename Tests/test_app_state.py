"""
Unit-Tests für backend/app_state.py

Testet:
- AppState Initialisierung
- Thread-sichere ID-Vergabe (next_audio_id / next_video_id)
- reset() Methode
- get_app_state() Singleton-Verhalten
- DB-Restore filtert verwaiste Medien heraus
"""
import json
import threading
import pytest
from backend.app_state import AppState, PersistenceError, get_app_state


class TestAppStateInit:
    """AppState Initialzustand prüfen."""

    def test_leer_nach_init(self):
        state = AppState()
        assert state.audio_clips == {}
        assert state.audio_analysis_cache == {}
        assert state.video_clips == {}
        assert state.video_analysis_cache == {}
        assert state.current_timeline == []
        assert state.current_audio_path is None
        assert state.render_tasks == {}
        assert state.cancel_flags == {}

    def test_id_counter_startet_bei_1(self):
        state = AppState()
        assert state._audio_next_id == 1
        assert state._video_next_id == 1


class TestNextAudioId:
    """Thread-sichere Audio-ID-Vergabe."""

    def test_erste_id_ist_1(self):
        state = AppState()
        assert state.next_audio_id() == 1

    def test_ids_sind_aufsteigend(self):
        state = AppState()
        ids = [state.next_audio_id() for _ in range(5)]
        assert ids == [1, 2, 3, 4, 5]

    def test_thread_sicherheit(self):
        """500 parallele Threads dürfen keine doppelten IDs liefern."""
        state = AppState()
        results = []
        lock = threading.Lock()

        def worker():
            clip_id = state.next_audio_id()
            with lock:
                results.append(clip_id)

        threads = [threading.Thread(target=worker) for _ in range(500)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 500
        assert len(set(results)) == 500, "Doppelte IDs gefunden!"
        assert set(results) == set(range(1, 501))


class TestNextVideoId:
    """Thread-sichere Video-ID-Vergabe."""

    def test_erste_id_ist_1(self):
        state = AppState()
        assert state.next_video_id() == 1

    def test_ids_unabhaengig_von_audio(self):
        """Audio- und Video-IDs sind voneinander unabhängig."""
        state = AppState()
        state.next_audio_id()  # Audio-Zähler auf 2
        assert state.next_video_id() == 1  # Video-Zähler bleibt bei 1

    def test_thread_sicherheit(self):
        state = AppState()
        results = []
        lock = threading.Lock()

        def worker():
            clip_id = state.next_video_id()
            with lock:
                results.append(clip_id)

        threads = [threading.Thread(target=worker) for _ in range(200)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(set(results)) == 200, "Doppelte Video-IDs!"


class TestReset:
    """reset() löscht vollständig den State."""

    def test_reset_loescht_alle_daten(self):
        state = AppState()
        # State befüllen
        state.audio_clips[1] = {"id": 1, "name": "test.mp3"}
        state.video_clips[1] = {"id": 1, "name": "clip.mp4"}
        state.current_timeline = [{"time": 0.0, "duration": 2.0}]
        state.current_audio_path = "/pfad/zur/datei.mp3"
        state.render_tasks["abc"] = {"status": "running"}
        state.cancel_flags["abc"] = False
        state.next_audio_id()  # Zähler auf 2
        state.next_video_id()  # Zähler auf 2

        state.reset()

        assert state.audio_clips == {}
        assert state.video_clips == {}
        assert state.current_timeline == []
        assert state.current_audio_path is None
        assert state.render_tasks == {}
        # MEDIUM-015: reset() marks all remaining cancel flags as True (not clear) so
        # in-flight render threads observe the cancellation signal after project close.
        assert state.cancel_flags == {"abc": True}

    def test_reset_setzt_id_counter_zurueck(self):
        state = AppState()
        state.next_audio_id()
        state.next_audio_id()
        state.next_video_id()
        state.reset()

        assert state.next_audio_id() == 1
        assert state.next_video_id() == 1

    def test_reset_ist_thread_safe(self):
        """reset() während paralleler ID-Vergabe darf nicht crashen."""
        state = AppState()

        def worker():
            for _ in range(50):
                state.next_audio_id()

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()

        # Während Threads laufen: reset aufrufen
        state.reset()

        for t in threads:
            t.join()
        # Kein Exception = Test bestanden


class TestLoadFromDb:
    """DB-Restore darf nicht erreichbare Medien nicht in-memory laden."""

    def test_fehlende_medien_werden_uebersprungen_aber_persistiert(
        self,
        tmp_path,
        monkeypatch,
    ):
        existing_audio = tmp_path / "real.wav"
        existing_audio.write_bytes(b"RIFF")
        missing_audio = tmp_path / "missing.wav"

        rows = [
            {
                "id": 10,
                "file_path": str(missing_audio),
                "duration_sec": 12.0,
                "metadata_json": json.dumps({
                    "clip_type": "audio",
                    "clip_id": 12,
                    "name": "missing",
                    "sample_rate": 44100,
                    "channels": 2,
                    "format": "wav",
                }),
            },
            {
                "id": 11,
                "file_path": str(existing_audio),
                "duration_sec": 34.0,
                "metadata_json": json.dumps({
                    "clip_type": "audio",
                    "clip_id": 8,
                    "name": "real",
                    "sample_rate": 48000,
                    "channels": 1,
                    "format": "wav",
                }),
            },
        ]
        deleted_ids = []

        class FakeRepo:
            def get_by_project(self, project_id):
                assert project_id == 1
                return rows

            def delete_media(self, media_id):
                deleted_ids.append(media_id)

        monkeypatch.setattr("pb_studio.data.repositories.media_repository.MediaRepository", FakeRepo)

        state = AppState()
        state.load_from_db()

        assert 12 not in state.audio_clips
        assert state.audio_clips[8]["path"] == str(existing_audio)
        assert deleted_ids == []
        assert state._audio_next_id == 13

    def test_load_from_db_verwendet_aktive_db_project_id(self, tmp_path, monkeypatch):
        existing_audio = tmp_path / "active.wav"
        existing_audio.write_bytes(b"RIFF")

        captured_project_ids = []
        rows = [
            {
                "id": 21,
                "file_path": str(existing_audio),
                "duration_sec": 5.0,
                "metadata_json": json.dumps({
                    "clip_type": "audio",
                    "clip_id": 3,
                    "name": "active",
                }),
            },
        ]

        class FakeRepo:
            def get_by_project(self, project_id):
                captured_project_ids.append(project_id)
                return rows

            def delete_media(self, media_id):
                raise AssertionError("delete_media should not be called in this test")

        monkeypatch.setattr("pb_studio.data.repositories.media_repository.MediaRepository", FakeRepo)

        state = AppState()
        state.current_project = {"db_project_id": 42, "path": str(tmp_path)}
        state.load_from_db()

        assert captured_project_ids == [42]
        assert list(state.audio_clips) == [3]

    def test_load_from_db_akzeptiert_string_clip_ids_aus_legacy_metadata(self, tmp_path, monkeypatch):
        existing_video = tmp_path / "legacy.mp4"
        existing_video.write_bytes(b"\x00\x00\x00\x18ftyp")

        rows = [
            {
                "id": 31,
                "file_path": str(existing_video),
                "duration_sec": 7.5,
                "metadata_json": json.dumps({
                    "clip_type": "video",
                    "clip_id": "12",
                    "name": "legacy",
                    "width": 1280,
                    "height": 720,
                    "fps": 25.0,
                    "codec": "h264",
                }),
            },
        ]

        class FakeRepo:
            def get_by_project(self, project_id):
                assert project_id == 1
                return rows

            def delete_media(self, media_id):
                raise AssertionError("delete_media should not be called in this test")

        monkeypatch.setattr("pb_studio.data.repositories.media_repository.MediaRepository", FakeRepo)

        state = AppState()
        state.load_from_db()

        assert list(state.video_clips) == [12]
        assert state.video_clips[12]["path"] == str(existing_video)
        assert state._video_next_id == 13


class TestDeletePersistence:
    def test_audio_db_failure_preserves_memory_and_cache(self, monkeypatch):
        state = AppState()
        state.audio_clips[7] = {"id": 7, "path": r"C:\media\track.wav"}
        state.audio_analysis_cache[7] = {"bpm": 128.0}

        class FakeRepo:
            def find_by_project_and_path(self, project_id, file_path):
                return {"id": 70}

            def delete_media(self, media_id):
                raise RuntimeError("sqlite write failed")

        monkeypatch.setattr(
            "pb_studio.data.repositories.media_repository.MediaRepository",
            FakeRepo,
        )

        with pytest.raises(PersistenceError, match="Audio-Clip 7") as exc:
            state.delete_audio_clip(7)
        assert exc.value.source == "audio_delete"

        assert state.audio_clips[7]["path"] == r"C:\media\track.wav"
        assert state.audio_analysis_cache[7] == {"bpm": 128.0}

    def test_video_outbox_failure_preserves_memory_cache_and_db(self, monkeypatch):
        state = AppState()
        state.video_clips[9] = {"id": 9, "path": r"C:\media\clip.mp4"}
        state.video_analysis_cache[9] = {"scene_count": 3}
        deleted_media_ids = []

        class FakeRepo:
            def find_by_project_and_path(self, project_id, file_path):
                return {"id": 90}

            def delete_media(self, media_id):
                deleted_media_ids.append(media_id)

        class FakeOutbox:
            def delete_media(self, media_id):
                assert media_id == 90
                raise RuntimeError("tombstone write failed")

        monkeypatch.setattr(
            "pb_studio.data.repositories.media_repository.MediaRepository",
            FakeRepo,
        )
        monkeypatch.setattr(
            "pb_studio.data.vector_operation_outbox.VectorOperationOutbox",
            FakeOutbox,
        )

        with pytest.raises(PersistenceError, match="Video-Clip 9") as exc:
            state.delete_video_clip(9)
        assert exc.value.source == "video_delete"

        assert state.video_clips[9]["path"] == r"C:\media\clip.mp4"
        assert state.video_analysis_cache[9] == {"scene_count": 3}
        assert deleted_media_ids == []


class TestGetAppState:
    """get_app_state() Singleton-Verhalten."""

    def test_gibt_immer_dasselbe_objekt_zurueck(self):
        s1 = get_app_state()
        s2 = get_app_state()
        assert s1 is s2

    def test_singleton_ist_appstate_instanz(self):
        state = get_app_state()
        assert isinstance(state, AppState)

    def test_state_aenderungen_sind_persistent(self):
        """Änderungen am Singleton sind in allen Referenzen sichtbar."""
        s1 = get_app_state()
        s2 = get_app_state()

        test_key = 9999
        s1.audio_clips[test_key] = {"id": test_key, "name": "singleton_test"}

        assert test_key in s2.audio_clips

        # Aufräumen
        del s1.audio_clips[test_key]
