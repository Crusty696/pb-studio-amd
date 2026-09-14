"""Focused DirectML-only SigLIP text capability contracts."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from pb_studio.ai import siglip_wrapper
from pb_studio.ai.siglip_wrapper import SigLIPWrapper, _siglip_text_capability


class _Config:
    def __init__(self, root: Path) -> None:
        self.root = root

    def resolve_path(self, value: str) -> Path:
        return self.root / Path(value)


def _write_manifests(root: Path, expected_hash: str) -> None:
    config_dir = root / "config"
    config_dir.mkdir()
    (config_dir / "directml-model-assets.json").write_text(
        json.dumps(
            {
                "release_provenance": {
                    "status": "approved",
                    "bundle_manifest": "config/directml-asset-bundle.json",
                },
                "assets": [
                    {
                        "target": "models/siglip_text.onnx",
                        "target_sha256": expected_hash,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (config_dir / "directml-asset-bundle.json").write_text(
        json.dumps(
            {
                "approval_status": "approved",
                "files": [
                    {
                        "target": "models/siglip_text.onnx",
                        "sha256": expected_hash,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_unregistered_local_text_asset_remains_unavailable(tmp_path: Path):
    models = tmp_path / "models"
    models.mkdir()
    (models / "siglip_text.onnx").write_bytes(b"untrusted")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "directml-model-assets.json").write_text(
        json.dumps(
            {
                "release_provenance": {
                    "status": "approved",
                    "bundle_manifest": "config/directml-asset-bundle.json",
                },
                "assets": [],
            }
        ),
        encoding="utf-8",
    )

    available, generation = _siglip_text_capability(models, _Config(tmp_path))

    assert available is False
    assert generation


def test_manifest_and_bundle_hash_enable_text_asset(tmp_path: Path):
    models = tmp_path / "models"
    models.mkdir()
    payload = b"manifest-bound-directml-model"
    expected_hash = hashlib.sha256(payload).hexdigest()
    (models / "siglip_text.onnx").write_bytes(payload)
    _write_manifests(tmp_path, expected_hash)

    available, generation = _siglip_text_capability(models, _Config(tmp_path))

    assert available is True
    assert generation.endswith(expected_hash)


def test_unavailable_warning_is_once_per_capability_generation(caplog):
    with siglip_wrapper._TEXT_CAPABILITY_WARN_LOCK:
        siglip_wrapper._WARNED_TEXT_CAPABILITY_GENERATIONS.clear()
    wrapper = SigLIPWrapper.__new__(SigLIPWrapper)

    with caplog.at_level(logging.WARNING, logger=siglip_wrapper.__name__):
        wrapper._init_text_fallback("generation-a")
        wrapper._init_text_fallback("generation-a")
        wrapper._init_text_fallback("generation-b")

    messages = [
        record.message
        for record in caplog.records
        if "SigLIP text ONNX asset" in record.message
    ]
    assert len(messages) == 2
