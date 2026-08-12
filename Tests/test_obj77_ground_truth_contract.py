from __future__ import annotations

import json
import hashlib
from pathlib import Path

import scripts.validate_obj77_ground_truth as validator
from scripts.validate_obj77_ground_truth import (
    build_registration_payload,
    main,
    seal_registration_payload,
    validate_annotation,
    validate_registration_payload,
)


def _entry(media_id: str, media_type: str) -> dict:
    return {
        "media_id": media_id,
        "media_type": media_type,
        "absolute_path": rf"C:\approved\{media_type}\{media_id}.bin",
        "size_bytes": 1,
        "media_sha256": ("a" if media_type == "audio" else "b") * 64,
        "duration_seconds": 1.0,
        "stream": {"codec_type": media_type, "codec_name": "test"},
        "annotation_version": None,
        "verification_status": "pending",
    }


def _registration() -> dict:
    payload = {
        "schema_version": 1,
        "objective": "OBJ-77",
        "mode": "registration",
        "audio_root": r"C:\approved\audio",
        "video_root": r"C:\approved\video",
        "entries": [_entry("audio-001", "audio"), _entry("video-001", "video")],
    }
    return seal_registration_payload(payload)


def test_registration_mode_accepts_pending_real_media_entries() -> None:
    payload = _registration()
    errors = validate_registration_payload(payload, strict=False, verify_files=False)
    assert errors == []


def test_strict_kpi_mode_rejects_pending_entries() -> None:
    errors = validate_registration_payload(_registration(), strict=True, verify_files=False)
    assert "audio-001 verification_status must be verified for strict KPI validation" in errors
    assert "video-001 verification_status must be verified for strict KPI validation" in errors


def _annotation(media_id: str = "audio-001", media_sha256: str = "a" * 64) -> dict:
    return {
        "schema_version": 1,
        "media_id": media_id,
        "media_sha256": media_sha256,
        "annotation_version": "1.0.0",
        "verification_status": "verified",
        "downbeats": [{"time": 0.0, "bar_number": 1}],
        "subtracks": [], "song_sections": [], "scene_boundaries": [],
        "tags": {"required": [], "allowed": [], "forbidden": []}, "pacing_cases": [],
    }


def _strict_verified_payload(annotation_path: Path | None = None, annotation: dict | None = None) -> dict:
    entry = _entry("audio-001", "audio")
    entry.update({"annotation_version": "1.0.0", "verification_status": "verified"})
    if annotation_path is not None:
        content = json.dumps(annotation or _annotation(), sort_keys=True).encode("utf-8")
        annotation_path.write_bytes(content)
        entry.update({"annotation_path": str(annotation_path.resolve()), "annotation_sha256": hashlib.sha256(content).hexdigest()})
    payload = _registration()
    payload["entries"] = [entry]
    return seal_registration_payload(payload)


def test_strict_verified_entry_requires_annotation_document() -> None:
    errors = validate_registration_payload(_strict_verified_payload(), strict=True, verify_files=False)
    assert "audio-001 annotation_path is required for strict KPI validation" in errors
    assert "audio-001 annotation_sha256 is required for strict KPI validation" in errors


def test_strict_rejects_mismatched_annotation_document(tmp_path: Path) -> None:
    payload = _strict_verified_payload(tmp_path / "annotation.json", _annotation(media_id="wrong-media"))
    errors = validate_registration_payload(payload, strict=True, verify_files=False)
    assert "audio-001 annotation media_id does not bind to registration" in errors


def test_strict_accepts_hash_bound_verified_annotation_document(tmp_path: Path) -> None:
    assert validate_registration_payload(_strict_verified_payload(tmp_path / "annotation.json"), strict=True, verify_files=False) == []


def test_strict_cli_rejects_root_overrides(tmp_path: Path, capsys) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(_registration()), encoding="utf-8")
    assert main(["--receipt", str(receipt), "--strict", "--audio-root", str(tmp_path)]) == 1
    assert "receipt verification requires approved audio root" in capsys.readouterr().err


def test_registration_cli_rejects_root_overrides(tmp_path: Path, capsys) -> None:
    receipt = tmp_path / "receipt.json"
    assert main(["--receipt", str(receipt), "--register", "--audio-root", str(tmp_path)]) == 1
    assert not receipt.exists()
    assert "registration requires approved audio root" in capsys.readouterr().err


def test_rights_and_reviewer_fields_are_not_required_or_interpreted() -> None:
    payload = _registration()
    payload["entries"][0]["rights_evidence"] = {"not": "used"}
    payload["entries"][1]["reviewer_id"] = "not-used"
    payload = seal_registration_payload(payload)
    errors = validate_registration_payload(payload, strict=False, verify_files=False)
    assert errors == []


def test_rejects_path_hash_duration_stream_and_duplicates() -> None:
    payload = _registration()
    payload["entries"].append(payload["entries"][0].copy())
    payload["entries"][1]["absolute_path"] = r"C:\outside\video.bin"
    payload["entries"][1]["media_sha256"] = "invalid"
    payload["entries"][1]["duration_seconds"] = float("nan")
    payload["entries"][1]["stream"] = {"codec_type": "audio", "codec_name": ""}
    errors = validate_registration_payload(payload, strict=False, verify_files=False)
    assert "duplicate media_id: audio-001" in errors
    assert "duplicate media_sha256" in errors
    assert "video-001 path is outside the approved root" in errors
    assert "video-001 media_sha256 must be SHA-256" in errors
    assert "video-001 duration_seconds must be finite and positive" in errors
    assert "video-001 stream is invalid" in errors


def test_annotation_contract_needs_no_human_identity_or_rights_fields() -> None:
    annotation = {
        "schema_version": 1,
        "media_id": "audio-001",
        "media_sha256": "a" * 64,
        "annotation_version": "1.0.0",
        "verification_status": "verified",
        "downbeats": [{"time": 0.0, "bar_number": 1}],
        "subtracks": [],
        "song_sections": [],
        "scene_boundaries": [],
        "tags": {"required": [], "allowed": [], "forbidden": []},
        "pacing_cases": [],
    }
    assert validate_annotation(annotation, duration_seconds=1.0, strict=True) == []


def test_annotation_rejects_invalid_semantics_in_strict_mode() -> None:
    annotation = {
        "schema_version": 1,
        "media_id": "audio-001",
        "media_sha256": "a" * 64,
        "annotation_version": "1.0.0",
        "verification_status": "pending",
        "downbeats": [{"time": float("nan"), "bar_number": 2}],
        "subtracks": [],
        "song_sections": [{"start_time": 1.0, "end_time": 0.0, "label": "unknown"}],
        "scene_boundaries": [{"time": 2.0, "transition_type": "wipe"}],
        "tags": {"required": ["unknown"], "allowed": [], "forbidden": []},
        "pacing_cases": [],
    }
    errors = validate_annotation(annotation, duration_seconds=1.0, strict=True)
    assert "annotation verification_status must be verified for strict KPI validation" in errors
    assert "downbeats[0].time must be finite" in errors
    assert "bar_number must increase contiguously" in errors
    assert "song_sections[0] must have end_time after start_time" in errors
    assert "song_sections[0].label is not allowed" in errors
    assert "scene_boundaries[0].time outside media duration" in errors
    assert "scene_boundaries[0].transition_type is not allowed" in errors
    assert "tags.required[0] is not allowed" in errors


def test_registration_builder_records_only_actual_media_metadata(tmp_path: Path, monkeypatch) -> None:
    audio_root = tmp_path / "audio"
    video_root = tmp_path / "video"
    audio_root.mkdir()
    video_root.mkdir()
    monkeypatch.setattr(validator, "DEFAULT_AUDIO_ROOT", audio_root)
    monkeypatch.setattr(validator, "DEFAULT_VIDEO_ROOT", video_root)
    (audio_root / "sample.wav").write_bytes(b"audio")
    (video_root / "sample.mp4").write_bytes(b"video")
    payload = build_registration_payload(audio_root, video_root, probe=lambda path, media_type: (1.0, {"codec_type": media_type, "codec_name": "test"}))
    assert len(payload["entries"]) == 2
    assert all(entry["annotation_version"] is None for entry in payload["entries"])
    assert all(entry["verification_status"] == "pending" for entry in payload["entries"])
    assert "annotations" not in json.dumps(payload)


def test_committed_receipt_rejects_false_roots_omitted_media_and_drift(tmp_path: Path, monkeypatch) -> None:
    audio_root = tmp_path / "audio"
    video_root = tmp_path / "video"
    audio_root.mkdir(); video_root.mkdir()
    first = audio_root / "first.wav"
    second = audio_root / "second.wav"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    monkeypatch.setattr(validator, "DEFAULT_AUDIO_ROOT", audio_root)
    monkeypatch.setattr(validator, "DEFAULT_VIDEO_ROOT", video_root)
    monkeypatch.setattr(validator, "_probe_media", lambda path, media_type: (1.0, {"codec_type": media_type, "codec_name": "test"}))
    payload = build_registration_payload(audio_root, video_root, probe=validator._probe_media)
    payload["entries"] = [payload["entries"][0]]
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(seal_registration_payload(payload)), encoding="utf-8")
    errors = validator.validate_registration(receipt, audio_root, video_root, strict=False)
    assert any(error.startswith("current media missing from receipt:") for error in errors)
    payload["audio_root"] = r"C:\\false\\audio"
    receipt.write_text(json.dumps(seal_registration_payload(payload)), encoding="utf-8")
    errors = validator.validate_registration(receipt, audio_root, video_root, strict=False)
    assert any(error.startswith("receipt audio_root must equal approved root:") for error in errors)
    payload["audio_root"] = str(audio_root.resolve())
    payload["entries"] = [build_registration_payload(audio_root, video_root, probe=validator._probe_media)["entries"][0]]
    receipt.write_text(json.dumps(seal_registration_payload(payload)), encoding="utf-8")
    first.write_bytes(b"other")
    errors = validator.validate_registration(receipt, audio_root, video_root, strict=False)
    assert "audio-001 hash drift" in errors
