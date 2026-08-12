from __future__ import annotations

import json
from pathlib import Path

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


def test_strict_cli_rejects_root_overrides(tmp_path: Path, capsys) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps(_registration()), encoding="utf-8")
    assert main(["--receipt", str(receipt), "--strict", "--audio-root", str(tmp_path)]) == 1
    assert "--strict requires approved audio root" in capsys.readouterr().err


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


def test_registration_builder_records_only_actual_media_metadata(tmp_path: Path) -> None:
    audio_root = tmp_path / "audio"
    video_root = tmp_path / "video"
    audio_root.mkdir()
    video_root.mkdir()
    (audio_root / "sample.wav").write_bytes(b"audio")
    (video_root / "sample.mp4").write_bytes(b"video")
    payload = build_registration_payload(audio_root, video_root, probe=lambda path, media_type: (1.0, {"codec_type": media_type, "codec_name": "test"}))
    assert len(payload["entries"]) == 2
    assert all(entry["annotation_version"] is None for entry in payload["entries"])
    assert all(entry["verification_status"] == "pending" for entry in payload["entries"])
    assert "annotations" not in json.dumps(payload)
