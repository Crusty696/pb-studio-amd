"""Manifest-bound embedding dimensions and fail-closed vector validation."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Mapping

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "config" / "directml-model-assets.json"
REQUIRED_CONTRACTS = frozenset({"raw_audio", "raw_video", "brain_projected"})


class EmbeddingContractError(RuntimeError):
    """The checked-in embedding contract is missing or inconsistent."""


class EmbeddingMigrationRequiredError(EmbeddingContractError):
    """A durable vector schema cannot serve the manifested dimension."""


@dataclass(frozen=True)
class EmbeddingContract:
    name: str
    dimension: int
    dtype: str
    normalization: str
    producer: str


def load_embedding_contracts(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> Mapping[str, EmbeddingContract]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise ValueError("unsupported manifest schema")
        raw_contracts = payload["embedding_contracts"]
        if not isinstance(raw_contracts, dict) or not raw_contracts:
            raise ValueError("embedding_contracts must be a non-empty object")
        asset_ids = {
            asset["id"]
            for asset in payload.get("assets", [])
            if isinstance(asset, dict) and isinstance(asset.get("id"), str)
        }
        result: dict[str, EmbeddingContract] = {}
        for name, raw in raw_contracts.items():
            if not isinstance(name, str) or not isinstance(raw, dict):
                raise ValueError("invalid embedding contract entry")
            if set(raw) != {"dimension", "dtype", "normalization", "producer"}:
                raise ValueError(f"invalid fields for {name}")
            dimension = raw["dimension"]
            if isinstance(dimension, bool) or not isinstance(dimension, int):
                raise ValueError(f"invalid dimension for {name}")
            if dimension <= 0:
                raise ValueError(f"invalid dimension for {name}")
            if raw["dtype"] != "float32" or raw["normalization"] != "l2":
                raise ValueError(f"unsupported vector representation for {name}")
            producer = raw["producer"]
            if not isinstance(producer, str) or not producer:
                raise ValueError(f"invalid producer for {name}")
            if name != "brain_projected" and producer not in asset_ids:
                raise ValueError(f"unknown producer for {name}")
            result[name] = EmbeddingContract(
                name=name,
                dimension=dimension,
                dtype="float32",
                normalization="l2",
                producer=producer,
            )
        return result
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise EmbeddingContractError(
            f"Invalid embedding contract manifest: {manifest_path}"
        ) from exc


@lru_cache(maxsize=1)
def embedding_contracts() -> Mapping[str, EmbeddingContract]:
    contracts = load_embedding_contracts()
    if set(contracts) != REQUIRED_CONTRACTS:
        raise EmbeddingContractError(
            "Manifest must define raw_audio, raw_video and brain_projected"
        )
    return contracts


def get_embedding_contract(name: str) -> EmbeddingContract:
    try:
        return embedding_contracts()[name]
    except KeyError as exc:
        raise EmbeddingContractError(f"Unknown embedding contract: {name}") from exc


def validate_embedding(
    vector: np.ndarray,
    *,
    expected_dimension: int,
    contract_name: str,
) -> np.ndarray:
    if not isinstance(vector, np.ndarray):
        raise TypeError(f"{contract_name} embedding must be a numpy.ndarray")
    if vector.dtype != np.float32:
        raise TypeError(f"{contract_name} embedding dtype must be float32")
    if vector.ndim != 1:
        raise ValueError(f"{contract_name} embedding must be one-dimensional")
    if vector.size != expected_dimension:
        raise ValueError(
            f"{contract_name} embedding dimension {vector.size} != "
            f"expected {expected_dimension}"
        )
    if not np.isfinite(vector).all():
        raise ValueError(f"{contract_name} embedding must contain only finite values")
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm <= 1e-8:
        raise ValueError(f"{contract_name} embedding has zero norm")
    normalized = vector.copy()
    normalized /= np.float32(norm)
    return normalized
