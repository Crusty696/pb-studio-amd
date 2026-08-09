from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import backend.recovery_bootstrap as recovery_bootstrap

from backend.recovery_bootstrap import (
    RecoveryBootstrapError,
    ensure_recovery_ready,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _generation(
    root: Path,
    generation_id: str,
    target: Path,
    content: bytes,
    *,
    external_references: list[dict] | None = None,
) -> str:
    generation = root / "generations" / generation_id
    artifact = generation / "artifacts" / "state.bin"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(content)
    manifest = {
        "schema_version": 1,
        "generation_id": generation_id,
        "artifacts": [{
            "logical_id": "state",
            "class": "owned",
            "required": True,
            "absolute_target": str(target.resolve()),
            "generation_relpath": "artifacts/state.bin",
            "size": len(content),
            "sha256": _sha256(artifact),
        }],
        "external_references": external_references or [],
    }
    manifest_path = generation / "manifest.json"
    _write_json(manifest_path, manifest)
    return _sha256(manifest_path)


def test_missing_control_root_is_uninitialized(tmp_path: Path) -> None:
    result = ensure_recovery_ready(tmp_path / "missing")
    assert result.status == "uninitialized"


def test_backend_runs_bootstrap_before_config_and_logging() -> None:
    source = (Path(__file__).parents[1] / "backend" / "main.py").read_text(
        encoding="utf-8"
    )
    bootstrap = source.index("_recovery_bootstrap_result = ensure_recovery_ready()")
    config = source.index("from .config import config")
    log_directory = source.index('log_dir = Path("logs")')
    assert bootstrap < config < log_directory


def test_ready_current_validates_manifest_without_replacing_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "control"
    target = tmp_path / "live.bin"
    target.write_bytes(b"current")
    manifest_hash = _generation(root, "g1", target, b"current")
    _write_json(root / "CURRENT", {
        "schema_version": 1,
        "generation_id": "g1",
        "manifest_sha256": manifest_hash,
    })

    result = ensure_recovery_ready(root)

    assert result.status == "ready"
    assert result.generation_id == "g1"
    assert target.read_bytes() == b"current"


def test_current_generation_never_replays_without_restore_journal(tmp_path: Path) -> None:
    root = tmp_path / "control"
    target = tmp_path / "missing-live.bin"
    manifest_hash = _generation(root, "g1", target, b"restored")
    _write_json(root / "CURRENT", {
        "schema_version": 1,
        "generation_id": "g1",
        "manifest_sha256": manifest_hash,
    })

    result = ensure_recovery_ready(root)

    assert result.status == "ready"
    assert not target.exists()


def test_committed_restore_never_replays_over_newer_live_work(tmp_path: Path) -> None:
    root = tmp_path / "control"
    target = tmp_path / "live.bin"
    target.write_bytes(b"restored")
    manifest_hash = _generation(root, "g1", target, b"restored")
    _write_json(root / "CURRENT", {
        "schema_version": 1,
        "generation_id": "g1",
        "manifest_sha256": manifest_hash,
    })
    _write_json(root / "journal.json", {
        "schema_version": 1,
        "operation": "restore",
        "state": "COMMITTED",
        "previous_generation": "",
        "next_generation": "g1",
        "next_manifest_sha256": manifest_hash,
        "committed_generation": "g1",
        "applied": ["state"],
    })
    target.write_bytes(b"newer-live-work")

    result = ensure_recovery_ready(root)

    assert result.status == "ready"
    assert result.generation_id == "g1"
    assert target.read_bytes() == b"newer-live-work"


def test_manifest_cannot_restore_into_control_root(tmp_path: Path) -> None:
    root = tmp_path / "control"
    target = root / "CURRENT"
    manifest_hash = _generation(root, "g1", target, b"malicious")
    _write_json(root / "CURRENT", {
        "schema_version": 1,
        "generation_id": "g1",
        "manifest_sha256": manifest_hash,
    })

    with pytest.raises(RecoveryBootstrapError, match="control root"):
        ensure_recovery_ready(root)


def test_staged_snapshot_publishes_current_without_touching_live_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "control"
    target = tmp_path / "live.bin"
    target.write_bytes(b"newer-live")
    manifest_hash = _generation(root, "g1", target, b"snapshot")
    _write_json(root / "journal.json", {
        "schema_version": 1,
        "operation": "snapshot",
        "state": "STAGED",
        "previous_generation": "",
        "next_generation": "g1",
        "next_manifest_sha256": manifest_hash,
        "applied": [],
    })

    result = ensure_recovery_ready(root)

    assert result.status == "snapshot_committed"
    assert target.read_bytes() == b"newer-live"
    current = json.loads((root / "CURRENT").read_text(encoding="utf-8"))
    assert current["generation_id"] == "g1"


def test_preparing_snapshot_keeps_previous_current(tmp_path: Path) -> None:
    root = tmp_path / "control"
    target = tmp_path / "live.bin"
    target.write_bytes(b"live")
    previous_hash = _generation(root, "g0", target, b"previous")
    _write_json(root / "CURRENT", {
        "schema_version": 1,
        "generation_id": "g0",
        "manifest_sha256": previous_hash,
    })
    _write_json(root / "journal.json", {
        "schema_version": 1,
        "operation": "snapshot",
        "state": "PREPARING",
        "previous_generation": "g0",
        "previous_manifest_sha256": previous_hash,
        "next_generation": "g1",
        "applied": [],
    })

    result = ensure_recovery_ready(root)

    assert result.status == "snapshot_aborted"
    assert result.generation_id == "g0"
    assert target.read_bytes() == b"live"


@pytest.mark.parametrize("state", ["STAGED", "APPLYING", "VALIDATING"])
def test_interrupted_publish_rolls_forward_idempotently(
    tmp_path: Path,
    state: str,
) -> None:
    root = tmp_path / "control"
    target = tmp_path / "live.bin"
    target.write_bytes(b"old")
    old_hash = _generation(root, "g1", target, b"old")
    new_hash = _generation(root, "g2", target, b"new")
    _write_json(root / "CURRENT", {
        "schema_version": 1,
        "generation_id": "g1",
        "manifest_sha256": old_hash,
    })
    _write_json(root / "journal.json", {
        "schema_version": 1,
        "state": state,
        "previous_generation": "g1",
        "previous_manifest_sha256": old_hash,
        "next_generation": "g2",
        "next_manifest_sha256": new_hash,
        "applied": [],
    })

    first = ensure_recovery_ready(root)
    second = ensure_recovery_ready(root)

    assert first.status == "recovered"
    assert second.status == "ready"
    assert first.generation_id == second.generation_id == "g2"
    assert target.read_bytes() == b"new"


def test_corrupt_next_generation_rolls_back_previous(tmp_path: Path) -> None:
    root = tmp_path / "control"
    target = tmp_path / "live.bin"
    target.write_bytes(b"mixed")
    old_hash = _generation(root, "g1", target, b"old")
    new_hash = _generation(root, "g2", target, b"new")
    (root / "generations" / "g2" / "artifacts" / "state.bin").write_bytes(
        b"corrupt"
    )
    _write_json(root / "journal.json", {
        "schema_version": 1,
        "state": "APPLYING",
        "previous_generation": "g1",
        "previous_manifest_sha256": old_hash,
        "next_generation": "g2",
        "next_manifest_sha256": new_hash,
        "applied": [],
    })

    result = ensure_recovery_ready(root)

    assert result.generation_id == "g1"
    assert target.read_bytes() == b"old"


def test_missing_both_generations_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "control"
    _write_json(root / "journal.json", {
        "schema_version": 1,
        "state": "STAGED",
        "previous_generation": "missing-old",
        "next_generation": "missing-new",
        "applied": [],
    })

    with pytest.raises(RecoveryBootstrapError):
        ensure_recovery_ready(root)


def test_manifest_path_traversal_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "control"
    target = tmp_path / "live.bin"
    generation = root / "generations" / "g1"
    outside = root / "outside.bin"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(b"outside")
    manifest = {
        "schema_version": 1,
        "generation_id": "g1",
        "artifacts": [{
            "logical_id": "escape",
            "class": "owned",
            "required": True,
            "absolute_target": str(target.resolve()),
            "generation_relpath": "../../outside.bin",
            "size": 7,
            "sha256": _sha256(outside),
        }],
    }
    manifest_path = generation / "manifest.json"
    _write_json(manifest_path, manifest)
    _write_json(root / "CURRENT", {
        "schema_version": 1,
        "generation_id": "g1",
        "manifest_sha256": _sha256(manifest_path),
    })

    with pytest.raises(RecoveryBootstrapError):
        ensure_recovery_ready(root)


def test_optional_external_reference_is_degraded(tmp_path: Path) -> None:
    root = tmp_path / "control"
    target = tmp_path / "live.bin"
    target.write_bytes(b"current")
    manifest_hash = _generation(
        root,
        "g1",
        target,
        b"current",
        external_references=[{
            "logical_id": "source-video",
            "absolute_path": str((tmp_path / "missing.mp4").resolve()),
            "required": False,
            "sha256": "0" * 64,
        }],
    )
    _write_json(root / "CURRENT", {
        "schema_version": 1,
        "generation_id": "g1",
        "manifest_sha256": manifest_hash,
    })

    result = ensure_recovery_ready(root)

    assert result.degraded_references == ("source-video",)


def test_required_external_reference_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "control"
    target = tmp_path / "live.bin"
    target.write_bytes(b"current")
    manifest_hash = _generation(
        root,
        "g1",
        target,
        b"current",
        external_references=[{
            "logical_id": "required-audio",
            "absolute_path": str((tmp_path / "missing.wav").resolve()),
            "required": True,
            "sha256": "0" * 64,
        }],
    )
    _write_json(root / "CURRENT", {
        "schema_version": 1,
        "generation_id": "g1",
        "manifest_sha256": manifest_hash,
    })

    with pytest.raises(RecoveryBootstrapError):
        ensure_recovery_ready(root)


def test_busy_windows_target_fails_closed_and_keeps_restore_journal(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "control"
    target = tmp_path / "live.db"
    target.write_bytes(b"newer")
    old_hash = _generation(root, "g1", target, b"old")
    _write_json(root / "journal.json", {
        "schema_version": 1,
        "operation": "restore",
        "state": "STAGED",
        "previous_generation": "",
        "next_generation": "g1",
        "next_manifest_sha256": old_hash,
        "applied": [],
    })
    real_replace = recovery_bootstrap.os.replace

    def deny_target_replace(source, destination):
        if Path(destination) == target:
            raise PermissionError("simulated open Windows handle")
        return real_replace(source, destination)

    monkeypatch.setattr(recovery_bootstrap.os, "replace", deny_target_replace)

    with pytest.raises(RecoveryBootstrapError, match="busy or unavailable"):
        ensure_recovery_ready(root)

    assert target.read_bytes() == b"newer"
    journal = json.loads((root / "journal.json").read_text(encoding="utf-8"))
    assert journal["state"] == "APPLYING"


def test_restore_stages_target_on_target_volume_sibling(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "control-volume" / "artifact.bin"
    target = tmp_path / "target-volume" / "nested" / "live.bin"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"confirmed")
    observed: list[tuple[Path, Path]] = []
    real_replace = recovery_bootstrap.os.replace

    def observe_replace(staged, destination):
        observed.append((Path(staged), Path(destination)))
        return real_replace(staged, destination)

    monkeypatch.setattr(recovery_bootstrap.os, "replace", observe_replace)
    recovery_bootstrap._replace_target(source, target, _sha256(source))

    staged, destination = observed[-1]
    assert destination == target
    assert staged.parent == target.parent
    assert target.read_bytes() == b"confirmed"


def test_partially_applied_multi_artifact_restore_converges(tmp_path: Path) -> None:
    root = tmp_path / "control"
    generation = root / "generations" / "g1"
    artifacts = generation / "artifacts"
    artifacts.mkdir(parents=True)
    first_source = artifacts / "first.bin"
    second_source = artifacts / "second.bin"
    first_source.write_bytes(b"first-new")
    second_source.write_bytes(b"second-new")
    first_target = tmp_path / "first-live.bin"
    second_target = tmp_path / "second-live.bin"
    first_target.write_bytes(b"first-new")
    second_target.write_bytes(b"second-old")
    manifest = {
        "schema_version": 1,
        "generation_id": "g1",
        "artifacts": [
            {
                "logical_id": "first",
                "class": "owned",
                "required": True,
                "absolute_target": str(first_target.resolve()),
                "generation_relpath": "artifacts/first.bin",
                "size": first_source.stat().st_size,
                "sha256": _sha256(first_source),
            },
            {
                "logical_id": "second",
                "class": "owned",
                "required": True,
                "absolute_target": str(second_target.resolve()),
                "generation_relpath": "artifacts/second.bin",
                "size": second_source.stat().st_size,
                "sha256": _sha256(second_source),
            },
        ],
        "external_references": [],
    }
    manifest_path = generation / "manifest.json"
    _write_json(manifest_path, manifest)
    _write_json(root / "journal.json", {
        "schema_version": 1,
        "operation": "restore",
        "state": "APPLYING",
        "previous_generation": "",
        "next_generation": "g1",
        "next_manifest_sha256": _sha256(manifest_path),
        "applied": ["first"],
    })

    result = ensure_recovery_ready(root)

    assert result.status == "recovered"
    assert first_target.read_bytes() == b"first-new"
    assert second_target.read_bytes() == b"second-new"
    journal = json.loads((root / "journal.json").read_text(encoding="utf-8"))
    assert journal["state"] == "COMMITTED"
    assert journal["applied"] == ["first", "second"]
