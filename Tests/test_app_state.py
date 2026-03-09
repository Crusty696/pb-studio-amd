"""
Unit-Tests für backend/app_state.py

Testet:
- AppState Initialisierung
- Thread-sichere ID-Vergabe (next_audio_id / next_video_id)
- reset() Methode
- get_app_state() Singleton-Verhalten
"""
import threading
import pytest
from backend.app_state import AppState, get_app_state


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
        assert state.cancel_flags == {}

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
