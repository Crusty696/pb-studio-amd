from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
PROJECT_UUID = "98cbb214-5438-4701-a96b-5c1220901ce4"


def test_manifest_declares_all_embedding_contracts():
    payload = json.loads(
        (ROOT / "config" / "directml-model-assets.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["embedding_contracts"] == {
        "raw_audio": {
            "dimension": 512,
            "dtype": "float32",
            "normalization": "l2",
            "producer": "clap-audio-directml",
        },
        "raw_video": {
            "dimension": 1152,
            "dtype": "float32",
            "normalization": "l2",
            "producer": "siglip-so400m-vision-static",
        },
        "brain_projected": {
            "dimension": 256,
            "dtype": "float32",
            "normalization": "l2",
            "producer": "cross-modal-projector-v2",
        },
    }


def test_contract_loader_is_manifest_bound_and_fail_closed(tmp_path: Path):
    from pb_studio.storage.embedding_contract import load_embedding_contracts

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": [{"id": "asset"}],
                "embedding_contracts": {
                    "raw_audio": {
                        "dimension": 2,
                        "dtype": "float32",
                        "normalization": "l2",
                        "producer": "asset",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    contracts = load_embedding_contracts(manifest)
    assert contracts["raw_audio"].dimension == 2

    manifest.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="embedding contract"):
        load_embedding_contracts(manifest)


@pytest.mark.parametrize(
    ("vector", "message"),
    [
        ([1.0, 0.0], "numpy.ndarray"),
        (np.ones(2, dtype=np.float64), "float32"),
        (np.ones((1, 2), dtype=np.float32), "one-dimensional"),
        (np.ones(0, dtype=np.float32), "dimension"),
        (np.ones(3, dtype=np.float32), "dimension"),
        (np.array([np.nan, 1.0], dtype=np.float32), "finite"),
        (np.array([np.inf, 1.0], dtype=np.float32), "finite"),
        (np.zeros(2, dtype=np.float32), "zero norm"),
    ],
)
def test_vector_validation_rejects_invalid_input(vector, message):
    from pb_studio.storage.embedding_contract import validate_embedding

    with pytest.raises((TypeError, ValueError), match=message):
        validate_embedding(vector, expected_dimension=2, contract_name="test")


def test_vector_validation_returns_normalized_copy():
    from pb_studio.storage.embedding_contract import validate_embedding

    original = np.array([3.0, 4.0], dtype=np.float32)
    normalized = validate_embedding(
        original,
        expected_dimension=2,
        contract_name="test",
    )

    np.testing.assert_array_equal(original, np.array([3.0, 4.0], dtype=np.float32))
    assert normalized.dtype == np.float32
    assert np.linalg.norm(normalized) == pytest.approx(1.0)


def test_new_video_vec_schema_matches_manifest_dimension(tmp_path: Path):
    from pb_studio.storage.embedding_repository import EmbeddingRepository, VIDEO_DIM

    repo = EmbeddingRepository(
        tmp_path / "embeddings.db", project_uuid=PROJECT_UUID
    )
    try:
        vector = np.ones(VIDEO_DIM, dtype=np.float32)
        unit_id = repo.add_video_unit(
            parent_id=None,
            level="clip",
            media_id=1,
            media_hash="a" * 64,
            start_time=0.0,
            end_time=1.0,
            embedding=vector,
        )
        assert repo.search_video(vector, limit=1)[0].unit_id == unit_id
    finally:
        repo.close()
