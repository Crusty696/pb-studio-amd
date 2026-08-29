"""Persistenzfehler duerfen nicht stillschweigend verschluckt werden.

Audit 2026-08-29: drei `except Exception: pass` an Stellen, an denen ein
Fehlschlag Daten kostet. Ein atexit-Handler darf nicht werfen — aber
"nicht werfen" ist nicht dasselbe wie "nicht melden".
"""

import logging
import threading

import pytest

# faiss ist nur in der Windows-.venv verfuegbar (faiss-cpu cp311-win_amd64)
faiss = pytest.importorskip(
    "faiss", reason="faiss nicht installiert (nur Windows-.venv)"
)


class TestBrainUnbindFailure:
    def test_failed_unbind_forces_state_conn_to_none(self, monkeypatch, caplog):
        """Fail-closed: lieber gar nicht schreiben als ins falsche Projekt."""
        from backend import _brain_singleton
        from pb_studio.brain.brain_service import BrainService

        class ExplodingService:
            def __init__(self):
                self.state_conn = "verbindung-des-geschlossenen-projekts"
                self._current_state_slot = "slot-des-geschlossenen-projekts"

            def unbind_project_state(self):
                raise RuntimeError("unbind kaputt")

        service = ExplodingService()
        monkeypatch.setattr(BrainService, "get", staticmethod(lambda: service))

        with caplog.at_level(logging.ERROR):
            _brain_singleton.clear_project_state()

        assert _brain_singleton._PROJECT_STATE_PATH is None
        assert any(
            "unbind" in r.message.lower() or "state" in r.message.lower()
            for r in caplog.records
        ), "fehlgeschlagenes unbind_project_state wurde ohne Logzeile verschluckt"
        assert service.state_conn is None, (
            "Brain haengt weiter an der state.db des geschlossenen Projekts"
        )
        assert service._current_state_slot is None, (
            "der Lease-Pfad liefert weiter die Verbindung des alten Projekts"
        )


def _detached_store(tmp_path):
    """Instanz ohne Singleton-/Writer-Zustand.

    `object.__new__` statt `VectorStore.__new__`: das ueberschriebene __new__
    setzt cls._instance und wuerde den prozessweiten Singleton (und damit den
    atexit-Handler) auf diese Wegwerf-Instanz umbiegen."""
    from pb_studio.data.vector_store import VectorStore

    store = object.__new__(VectorStore)
    store.index_path = tmp_path / "idx.faiss"
    store.meta_path = tmp_path / "idx_meta.json"
    store.tombstone_path = tmp_path / "idx_tombstones.json"
    store._lock = threading.Lock()
    store._closed = False
    return store


class TestVectorStoreSaveFailure:
    def test_failed_final_save_is_logged_and_marks_dirty(self, tmp_path, caplog):
        """Ein gescheiterter Abschluss-Save muss auffindbar sein."""
        store = _detached_store(tmp_path)

        def explode(*args, **kwargs):
            raise OSError("Platte voll")

        store._save_unlocked = explode

        with caplog.at_level(logging.ERROR):
            store.close()

        assert any(
            r.levelno >= logging.ERROR for r in caplog.records
        ), "gescheiterter FAISS-Save wurde ohne Logzeile verschluckt"
        assert (tmp_path / "idx.faiss.dirty").exists(), (
            "kein Dirty-Marker — der Verlust ist beim naechsten Start nicht feststellbar"
        )

    def test_failed_atexit_save_is_logged_and_marks_dirty(self, tmp_path, caplog):
        """Der atexit-Handler darf nicht werfen, aber auch nicht schweigen."""
        from pb_studio.data.vector_store import VectorStore

        store = _detached_store(tmp_path)

        def explode(*args, **kwargs):
            raise OSError("Platte voll")

        store._save_on_exit = explode

        previous_instance = VectorStore._instance
        VectorStore._instance = store
        try:
            with caplog.at_level(logging.ERROR):
                VectorStore._save_active_on_exit()
        finally:
            VectorStore._instance = previous_instance

        assert any(
            r.levelno >= logging.ERROR for r in caplog.records
        ), "gescheiterter atexit-Save wurde ohne Logzeile verschluckt"
        assert (tmp_path / "idx.faiss.dirty").exists(), (
            "kein Dirty-Marker — der Verlust ist beim naechsten Start nicht feststellbar"
        )
