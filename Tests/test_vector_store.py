"""
Unit Tests for VectorStore

Tests:
- FAISS index creation and loading
- Embedding addition
- Similarity search
- Persistence (save/load)
"""

import threading

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

            embedding = np.random.rand(768).astype(np.float32)
            meta = {"media_id": 1, "description": "Test"}

            result_id = store.add_embedding(embedding, meta)

            # After adding, ntotal would be 5, so ID should be 4
            assert result_id == 4

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

