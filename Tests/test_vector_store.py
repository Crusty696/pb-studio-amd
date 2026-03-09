"""
Unit Tests for VectorStore

Tests:
- FAISS index creation and loading
- Embedding addition
- Similarity search
- Persistence (save/load)
"""

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
        store.metadata = {}

        # Wrong dimension (512 instead of 768)
        embedding = np.random.rand(512).astype(np.float32)
        meta = {"media_id": 1}

        result_id = store.add_embedding(embedding, meta)

        assert result_id == -1


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

        query = np.random.rand(768).astype(np.float32)
        results = store.search(query, k=5)

        assert results == []

    def test_search_returns_metadata_and_scores(self, reset_config_singleton):
        """Verify search returns metadata with similarity scores."""
        with patch("pb_studio.data.vector_store.faiss") as mock_faiss:
            from pb_studio.data.vector_store import VectorStore

            store = VectorStore.__new__(VectorStore)
            store.dimension = 768
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
