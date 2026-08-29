"""Persistenzfehler duerfen nicht stillschweigend verschluckt werden.

Audit 2026-08-29: drei `except Exception: pass` an Stellen, an denen ein
Fehlschlag Daten kostet. Ein atexit-Handler darf nicht werfen — aber
"nicht werfen" ist nicht dasselbe wie "nicht melden".
"""

import logging
import sqlite3
import threading
import uuid

import pytest

# faiss ist nur in der Windows-.venv verfuegbar (faiss-cpu cp311-win_amd64)
faiss = pytest.importorskip(
    "faiss", reason="faiss nicht installiert (nur Windows-.venv)"
)

_SINGLETON_LOGGER = "backend._brain_singleton"


def _unbind_errors(caplog):
    return [
        record
        for record in caplog.records
        if record.name == _SINGLETON_LOGGER and record.levelno >= logging.ERROR
    ]


class TestBrainUnbindFailure:
    def test_failed_unbind_forces_state_conn_to_none(self, monkeypatch, caplog):
        """Fail-closed: lieber gar nicht schreiben als ins falsche Projekt."""
        from backend import _brain_singleton
        from pb_studio.brain.brain_service import BrainService

        class ExplodingService:
            def __init__(self):
                self.state_conn = "verbindung-des-geschlossenen-projekts"
                self.forced = False

            def unbind_project_state(self):
                raise RuntimeError("unbind kaputt")

            def force_unbind_project_state(self, **kwargs):
                self.forced = True
                self.state_conn = None
                return True

        service = ExplodingService()
        monkeypatch.setattr(BrainService, "get", staticmethod(lambda: service))

        with caplog.at_level(logging.ERROR):
            _brain_singleton.clear_project_state()

        assert _brain_singleton._PROJECT_STATE_PATH is None
        errors = _unbind_errors(caplog)
        assert errors, (
            "fehlgeschlagenes unbind_project_state wurde ohne Logzeile verschluckt"
        )
        assert errors[0].exc_info is not None, (
            "Logzeile ohne exc_info — die Ursache des Fehlschlags bleibt unbekannt"
        )
        assert service.forced, "der Fail-closed-Notausgang wurde nicht gerufen"

    def test_failed_unbind_closes_the_real_state_connection(
        self, tmp_path, monkeypatch, caplog
    ):
        """Fail-closed darf den Datenverlust nicht gegen ein Handle-Leck tauschen.

        Gegen eine echte BrainService-Instanz mit echter state.db: nach dem
        gescheiterten Unbind darf weder ein Lease noch die offene sqlite3-
        Verbindung zurueckbleiben."""
        from backend import _brain_singleton
        from pb_studio.brain.brain_service import (
            BrainProjectNotBoundError,
            BrainService,
        )

        state_db = tmp_path / "project-a" / "state.db"
        state_db.parent.mkdir(parents=True, exist_ok=True)
        service = BrainService(brain_dir=tmp_path / "brain-runtime")
        try:
            service.bind_project_state(
                state_db,
                project_epoch=1,
                project_id=101,
                project_uuid=str(uuid.uuid4()),
            )
            slot = service._current_state_slot
            connection = slot.connection
            assert connection.execute("SELECT 1").fetchone() == (1,)

            monkeypatch.setattr(
                BrainService,
                "get",
                classmethod(lambda cls, **_kwargs: service),
            )

            def explode(self):
                raise RuntimeError("unbind kaputt")

            monkeypatch.setattr(BrainService, "unbind_project_state", explode)

            with caplog.at_level(logging.ERROR):
                _brain_singleton.clear_project_state()

            assert _unbind_errors(caplog), "Fehlschlag wurde nicht gemeldet"
            assert service.state_conn is None
            with pytest.raises(BrainProjectNotBoundError):
                service.project_state_lease()
            with pytest.raises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")
            assert slot not in service._state_slots, (
                "der Slot bleibt liegen und wird nie mehr aufgeraeumt"
            )
        finally:
            service.close()


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


def _explode(*args, **kwargs):
    raise OSError("Platte voll")


class TestVectorStoreSaveFailure:
    def test_failed_final_save_is_logged_and_marks_dirty(self, tmp_path, caplog):
        """Ein gescheiterter Abschluss-Save muss auffindbar sein."""
        store = _detached_store(tmp_path)
        store._save_unlocked = _explode

        with caplog.at_level(logging.ERROR):
            store.close()

        assert any(
            r.levelno >= logging.ERROR for r in caplog.records
        ), "gescheiterter FAISS-Save wurde ohne Logzeile verschluckt"
        assert (tmp_path / "idx.faiss.dirty").exists(), (
            "kein Dirty-Marker neben der Indexdatei"
        )

    def test_failed_atexit_save_is_logged_and_marks_dirty(self, tmp_path, caplog):
        """Der atexit-Handler darf nicht werfen, aber auch nicht schweigen."""
        from pb_studio.data.vector_store import VectorStore

        store = _detached_store(tmp_path)
        store._save_on_exit = _explode

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
            "kein Dirty-Marker neben der Indexdatei"
        )

    def test_dirty_marker_is_reported_on_next_start(self, tmp_path, caplog):
        """Ohne Leser waere der Marker ein weiterer Producer ohne Consumer."""
        store = _detached_store(tmp_path)
        store._mark_dirty("final save failed")

        reader = _detached_store(tmp_path)
        with caplog.at_level(logging.WARNING):
            reader._report_dirty_marker()

        messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("final save failed" in m for m in messages), (
            "der Dirty-Marker wird beim Start nicht gemeldet — der Verlust "
            "bleibt unsichtbar"
        )
