"""
Unit Tests for VectorStore

Tests:
- FAISS index creation and loading
- Embedding addition
- Similarity search
- Persistence (save/load)
"""

import json
import threading
from contextlib import contextmanager

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

# faiss ist nur in der Windows-.venv verfügbar (faiss-cpu cp311-win_amd64)
faiss = pytest.importorskip("faiss", reason="faiss nicht installiert (nur Windows-.venv)")


class TestVectorStoreEmbeddings:
    """Tests for embedding operations."""

    def test_add_embedding_returns_valid_id(self, reset_config_singleton):
        """Verify add_embedding returns valid FAISS ID."""
        with patch("pb_studio.data.vector_store.faiss") as mock_faiss:
            mock_index = MagicMock()
            mock_index.ntotal = 5
            mock_faiss.IndexFlatIP.return_value = mock_index

            from pb_studio.data.vector_store import VectorStore

            store = VectorStore.__new__(VectorStore)
            store.dimension = 768
            store.index = mock_index
            store.metadata = {}
            store._lock = threading.Lock()
            store._request_save = MagicMock()

            embedding = np.random.rand(768).astype(np.float32)
            meta = {"media_id": 1, "description": "Test"}

            result_id = store.add_embedding(embedding, meta)

            # After adding, ntotal would be 5, so ID should be 4
            assert result_id == 4
            store._request_save.assert_called_once_with()

    def test_add_embedding_rejects_wrong_dimension(self, reset_config_singleton):
        """Verify add_embedding rejects embeddings with wrong dimension."""
        from pb_studio.data.vector_store import VectorStore

        store = VectorStore.__new__(VectorStore)
        store.dimension = 768
        store.index = MagicMock()
        store.index.ntotal = 1  # Non-empty index → raises ValueError
        store.metadata = {}
        store._lock = threading.Lock()

        # Wrong dimension (512 instead of 768)
        embedding = np.random.rand(512).astype(np.float32)
        meta = {"media_id": 1}

        with pytest.raises(ValueError, match="dimension"):
            store.add_embedding(embedding, meta)

    def test_linked_add_rejects_missing_media_before_index_write(self):
        from pb_studio.data.vector_store import VectorStore

        store = VectorStore.__new__(VectorStore)
        store.dimension = 4
        store.index = faiss.IndexFlatIP(4)
        store.metadata = {}
        store._lock = threading.Lock()
        store._request_save = MagicMock()

        with pytest.raises(ValueError, match="media_id"):
            store.add_embedding_with_media_link(
                np.ones(4, dtype=np.float32),
                {"name": "unlinked"},
                media_id=None,
            )

        assert store.index.ntotal == 0
        assert store.metadata == {}
        store._request_save.assert_not_called()

    def test_failed_vector_map_insert_leaves_no_active_orphan(self, monkeypatch):
        from pb_studio.data.vector_store import VectorStore

        store = VectorStore.__new__(VectorStore)
        store.dimension = 4
        store.index = faiss.IndexFlatIP(4)
        store.metadata = {}
        store._tombstoned_ids = set()
        store._lock = threading.Lock()
        store._request_save = MagicMock()

        class FailingDatabase:
            @contextmanager
            def transaction(self, immediate=False):
                raise RuntimeError("forced vector_map insert failure")
                yield

        monkeypatch.setattr(
            "pb_studio.data.database_core.DatabaseCore",
            FailingDatabase,
        )

        with pytest.raises(RuntimeError, match="forced vector_map insert failure"):
            store.add_embedding_with_media_link(
                np.ones(4, dtype=np.float32),
                {"name": "must-not-be-active"},
                media_id=42,
            )

        assert store.search(np.ones(4, dtype=np.float32), k=1) == []
        assert store.index.ntotal == 0 or store._tombstoned_ids == {0}


class TestVectorStoreSearch:
    """Tests for similarity search."""

    def test_search_returns_empty_for_empty_index(self, reset_config_singleton):
        """Verify search returns empty list for empty index."""
        from pb_studio.data.vector_store import VectorStore

        store = VectorStore.__new__(VectorStore)
        store.dimension = 768
        store.index = MagicMock()
        store.index.ntotal = 0
        store.metadata = {}
        store._lock = threading.Lock()

        query = np.random.rand(768).astype(np.float32)
        results = store.search(query, k=5)

        assert results == []

    def test_search_returns_metadata_and_scores(self, reset_config_singleton):
        """Verify search returns metadata with similarity scores."""
        with patch("pb_studio.data.vector_store.faiss") as mock_faiss:
            from pb_studio.data.vector_store import VectorStore

            store = VectorStore.__new__(VectorStore)
            store.dimension = 768
            store._lock = threading.Lock()
            mock_index = MagicMock()
            mock_index.ntotal = 3
            # Simulate search results: distances and indices
            mock_index.search.return_value = (
                np.array([[0.95, 0.85, 0.75]]),  # Distances (similarity scores)
                np.array([[0, 2, 1]])            # Indices
            )
            store.index = mock_index
            store.metadata = {
                0: {"id": "A", "desc": "First"},
                1: {"id": "B", "desc": "Second"},
                2: {"id": "C", "desc": "Third"}
            }

            query = np.random.rand(768).astype(np.float32)
            results = store.search(query, k=3)

            assert len(results) == 3
            # Results should be (metadata, score) tuples
            assert results[0][0]["id"] == "A"
            assert results[0][1] == 0.95

    def test_search_expands_past_tombstoned_top_hits(self):
        from pb_studio.data.vector_store import VectorStore

        store = object.__new__(VectorStore)
        store.dimension = 2
        store._lock = threading.Lock()
        store._closed = False
        store.index = faiss.IndexFlatIP(2)
        store.index.add(
            np.asarray(
                [[1.0, 0.0], [0.99, 0.01], [0.8, 0.2]],
                dtype=np.float32,
            )
        )
        store.metadata = {
            0: {"id": "deleted"},
            1: {"id": "valid-1"},
            2: {"id": "valid-2"},
        }
        store._tombstoned_ids = {0}

        results = store.search(np.asarray([1.0, 0.0], dtype=np.float32), k=2)

        assert [metadata["id"] for metadata, _score in results] == ["valid-1", "valid-2"]


class TestVectorStoreTombstones:
    """Tests for tombstones and re-indexing."""

    def test_clean_tombstones_rebuilds_index(self, reset_config_singleton, tmp_path):
        """Verify that clean_tombstones removes tombstoned items and compacts index."""
        from pb_studio.data.vector_store import VectorStore
        
        # Neuen echten VectorStore mit Dimension 4 im tmp_path erstellen
        store = VectorStore(index_name="test_tombstones_index", dimension=4)
        store.index_path = tmp_path / "test_tombstones_index.faiss"
        store.meta_path = tmp_path / "test_tombstones_index_meta.json"
        store.tombstone_path = tmp_path / "test_tombstones_index_tombstones.json"
        store._create_new_index()
        
        # 3 Embeddings hinzufügen
        v0 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        v1 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float32)
        
        id0 = store.add_embedding(v0, {"name": "zero"})
        id1 = store.add_embedding(v1, {"name": "one"})
        id2 = store.add_embedding(v2, {"name": "two"})
        
        assert store.index.ntotal == 3
        assert len(store.metadata) == 3
        
        # ID 1 (Eintrag 2) tombstonieren
        store.mark_tombstoned([id1])
        assert id1 in store._tombstoned_ids
        
        # Suche sollte ID 1 nicht mehr zurückliefern
        res = store.search(v1, k=3)
        # ID 1 ("one") sollte ausgefiltert sein
        names = [r[0]["name"] for r in res]
        assert "one" not in names
        assert len(names) == 2
        
        # clean_tombstones manuell aufrufen (Re-Indexing)
        store.clean_tombstones()
        
        # Index sollte nun nur noch 2 Einträge haben und Tombstones leer sein
        assert store.index.ntotal == 2
        assert len(store.metadata) == 2
        assert len(store._tombstoned_ids) == 0
        
        # Die verbleibenden Einträge müssen "zero" und "two" sein
        assert store.metadata[0]["name"] == "zero"
        assert store.metadata[1]["name"] == "two"

    def test_failed_vector_map_remap_keeps_active_index_and_tombstones(
        self,
        monkeypatch,
    ):
        from pb_studio.data.vector_store import VectorStore

        store = VectorStore.__new__(VectorStore)
        store.dimension = 4
        store._lock = threading.Lock()
        store.index = faiss.IndexFlatIP(4)
        vectors = np.eye(4, dtype=np.float32)[:3]
        store.index.add(vectors)
        store.metadata = {
            0: {"name": "zero"},
            1: {"name": "one"},
            2: {"name": "two"},
        }
        store._tombstoned_ids = {0}
        store._request_save = MagicMock()
        original_index = store.index
        original_metadata = store.metadata.copy()

        class FailingDatabase:
            @contextmanager
            def transaction(self, immediate=False):
                raise RuntimeError("forced vector_map remap failure")
                yield

        monkeypatch.setattr(
            "pb_studio.data.database_core.DatabaseCore",
            FailingDatabase,
        )

        store.clean_tombstones()

        assert store.index is original_index
        assert store.metadata == original_metadata
        assert store._tombstoned_ids == {0}
        store._request_save.assert_not_called()


class TestVectorStoreSnapshotTransaction:
    @staticmethod
    def _make_store(tmp_path):
        from pb_studio.data.vector_store import VectorStore

        store = VectorStore.__new__(VectorStore)
        store.index_path = tmp_path / "index.faiss"
        store.meta_path = tmp_path / "index_meta.json"
        store.tombstone_path = tmp_path / "index_tombstones.json"
        return store

    def test_failed_live_replace_restores_complete_previous_generation(
        self,
        tmp_path,
        monkeypatch,
    ):
        store = self._make_store(tmp_path)
        targets = [
            store.index_path,
            store.meta_path,
            store.tombstone_path,
        ]
        old_values = [b"old-index", b"old-meta", b"old-tombstones"]
        new_values = [b"new-index", b"new-meta", b"new-tombstones"]
        temp_paths = []
        for target, old_value, new_value in zip(
            targets,
            old_values,
            new_values,
        ):
            target.write_bytes(old_value)
            temp_path = Path(str(target) + ".tmp")
            temp_path.write_bytes(new_value)
            temp_paths.append(temp_path)

        real_replace = __import__("os").replace
        live_replaces = {"count": 0}

        def fail_second_live_replace(source, destination):
            source_path = Path(source)
            if source_path in temp_paths:
                live_replaces["count"] += 1
                if live_replaces["count"] == 2:
                    raise OSError("forced mid-generation crash")
            return real_replace(source, destination)

        monkeypatch.setattr(
            "pb_studio.data.vector_store.os.replace",
            fail_second_live_replace,
        )

        with pytest.raises(OSError, match="forced mid-generation crash"):
            store._commit_snapshot_files(temp_paths)

        assert [path.read_bytes() for path in targets] == old_values
        assert not store._snapshot_journal_path().exists()

    def test_startup_recovery_restores_backups_before_load(self, tmp_path):
        store = self._make_store(tmp_path)
        store.dimension = 2
        store.index = None
        store.metadata = {}
        store._tombstoned_ids = set()

        old_index = faiss.IndexFlatIP(2)
        old_index.add(np.eye(2, dtype=np.float32))
        faiss.write_index(old_index, str(store.index_path) + ".bak")
        Path(str(store.meta_path) + ".bak").write_text(
            json.dumps({"0": {"name": "zero"}, "1": {"name": "one"}}),
            encoding="utf-8",
        )
        Path(str(store.tombstone_path) + ".bak").write_text(
            json.dumps([1]),
            encoding="utf-8",
        )
        for target in store._snapshot_targets():
            target.write_bytes(b"partial-new")

        store._snapshot_journal_path().write_text(
            json.dumps({"version": 1}),
            encoding="utf-8",
        )

        store._load_index()

        assert store.index.ntotal == 2
        assert store.metadata == {
            0: {"name": "zero"},
            1: {"name": "one"},
        }
        assert store._tombstoned_ids == {1}
        assert not store._snapshot_journal_path().exists()

    def test_synchronous_save_commits_complete_generation(self, tmp_path):
        store = self._make_store(tmp_path)
        store.dimension = 2
        store._lock = threading.Lock()
        store._write_lock = threading.Lock()
        store.index = faiss.IndexFlatIP(2)
        store.index.add(np.eye(2, dtype=np.float32))
        store.metadata = {
            0: {"name": "zero"},
            1: {"name": "one"},
        }
        store._tombstoned_ids = {1}

        store.save()

        assert faiss.read_index(str(store.index_path)).ntotal == 2
        assert json.loads(store.meta_path.read_text(encoding="utf-8")) == {
            "0": {"name": "zero"},
            "1": {"name": "one"},
        }
        assert json.loads(
            store.tombstone_path.read_text(encoding="utf-8")
        ) == [1]
        assert not store._snapshot_journal_path().exists()
        assert not any(
            Path(str(target) + ".bak").exists()
            for target in store._snapshot_targets()
        )


class TestVectorStoreLifecycle:
    def test_writer_retries_failed_snapshot_without_clearing_dirty(self):
        from pb_studio.data.vector_store import VectorStore

        store = object.__new__(VectorStore)
        store._save_cv = threading.Condition()
        store._save_dirty = False
        store._save_generation = 0
        store._writer_stop = False
        store._save_debounce_sec = 0.0
        store._lock = threading.Lock()
        store.index = faiss.IndexFlatIP(2)
        store.metadata = {}
        store._tombstoned_ids = set()
        second_attempt = threading.Event()
        release_second_attempt = threading.Event()
        attempts = {"count": 0}

        def persist(_index, _metadata, _tombstones):
            attempts["count"] += 1
            if attempts["count"] == 2:
                second_attempt.set()
                release_second_attempt.wait(timeout=10.0)
                return True
            return False

        store._write_snapshot = persist
        writer = threading.Thread(target=store._writer_loop, daemon=True)
        writer.start()
        store._request_save()
        assert second_attempt.wait(timeout=10.0)
        with store._save_cv:
            store._writer_stop = True
            store._save_cv.notify_all()
        release_second_attempt.set()
        writer.join(timeout=2.0)

        assert not writer.is_alive()
        assert attempts["count"] == 2
        assert store._save_dirty is False

    def test_index_switch_closes_old_writer_and_close_allows_reopen(self):
        from pb_studio.data.vector_store import VectorStore

        first = VectorStore(index_name="lifecycle_a", dimension=4)
        first_writer = first._writer_thread
        assert first_writer.is_alive()

        second = VectorStore(index_name="lifecycle_b", dimension=4)

        assert first._closed is True
        assert not first_writer.is_alive()
        assert second is not first
        assert second._writer_thread.is_alive()

        second.close()
        assert not second._writer_thread.is_alive()

        reopened = VectorStore(index_name="lifecycle_b", dimension=4)
        try:
            assert reopened is not second
            assert reopened._writer_thread.is_alive()
        finally:
            reopened.close()
