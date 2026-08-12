"""Register OBJ-77 real media and fail closed for later strict KPI validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


DEFAULT_AUDIO_ROOT = Path(r"C:\Users\david\Videos\test_data\audio")
DEFAULT_VIDEO_ROOT = Path(r"C:\Users\david\Videos\test_data\video")
ALLOWED_VERIFICATION_STATUSES = {"pending", "verified", "rejected"}
ALLOWED_SECTION_LABELS = {"intro", "verse", "chorus", "bridge", "outro", "drop"}
ALLOWED_SCENE_TYPES = {"cut", "fade", "dissolve"}
ALLOWED_TAG_LABELS = {"energy", "mood", "motion", "genre", "instrumental", "vocal", "dark", "uplifting", "calm", "intense"}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
REGISTRATION_REQUIRED = {"schema_version", "objective", "mode", "audio_root", "video_root", "entries", "registration_sha256"}
REGISTRATION_ALLOWED = REGISTRATION_REQUIRED | {"registered_at_utc"}
ENTRY_REQUIRED = {"media_id", "media_type", "absolute_path", "size_bytes", "media_sha256", "duration_seconds", "stream", "annotation_version", "verification_status"}
ENTRY_OPTIONAL = {"annotation_path", "annotation_sha256"}
ANNOTATION_REQUIRED = {"schema_version", "media_id", "media_sha256", "annotation_version", "verification_status", "downbeats", "subtracks", "song_sections", "scene_boundaries", "tags", "pacing_cases"}
IGNORED_LEGACY_FIELDS = {"rights_evidence", "reviewer_id", "annotator_id", "independent_labeling", "kpi_definitions"}


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _is_semver(value: object) -> bool:
    return isinstance(value, str) and SEMVER_RE.fullmatch(value) is not None


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _object_errors(payload: object, name: str, required: set[str], allowed: set[str]) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{name} must be an object"]
    errors = [f"{name} missing required field: {key}" for key in sorted(required - payload.keys())]
    errors.extend(f"{name} has unexpected field: {key}" for key in sorted(payload.keys() - allowed))
    return errors


def _canonical_bytes(payload: dict) -> bytes:
    sealed = {key: value for key, value in payload.items() if key != "registration_sha256"}
    return json.dumps(sealed, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def seal_registration_payload(payload: dict) -> dict:
    sealed = dict(payload)
    sealed["registration_sha256"] = hashlib.sha256(_canonical_bytes(sealed)).hexdigest()
    return sealed


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe_media(path: Path, media_type: str) -> tuple[float, dict[str, str]]:
    executable = shutil.which("ffprobe")
    if executable is None:
        raise RuntimeError("ffprobe executable unavailable")
    completed = subprocess.run([executable, "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name", "-of", "json", str(path)], capture_output=True, text=True, encoding="utf-8", check=False)
    if completed.returncode != 0:
        raise RuntimeError("ffprobe failed")
    try:
        output = json.loads(completed.stdout)
        duration = float(output["format"]["duration"])
        stream = next(item for item in output["streams"] if item.get("codec_type") == media_type)
        result = {"codec_type": stream["codec_type"], "codec_name": stream["codec_name"]}
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("ffprobe returned an incomplete media description") from error
    if not math.isfinite(duration) or duration <= 0:
        raise RuntimeError("ffprobe returned an invalid media duration")
    return duration, result


def build_registration_payload(
    audio_root: Path,
    video_root: Path,
    *,
    probe: Callable[[Path, str], tuple[float, dict[str, str]]] = _probe_media,
) -> dict:
    if audio_root.resolve() != DEFAULT_AUDIO_ROOT.resolve():
        raise ValueError(f"registration requires approved audio root: {DEFAULT_AUDIO_ROOT}")
    if video_root.resolve() != DEFAULT_VIDEO_ROOT.resolve():
        raise ValueError(f"registration requires approved video root: {DEFAULT_VIDEO_ROOT}")
    entries: list[dict[str, object]] = []
    for media_type, root in (("audio", audio_root), ("video", video_root)):
        if not root.is_dir():
            raise ValueError(f"approved {media_type} root is missing: {root}")
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            duration, stream = probe(path, media_type)
            entries.append(
                {
                    "media_id": f"{media_type}-{len([entry for entry in entries if entry['media_type'] == media_type]) + 1:03d}",
                    "media_type": media_type,
                    "absolute_path": str(path.resolve()),
                    "size_bytes": path.stat().st_size,
                    "media_sha256": _sha256_file(path),
                    "duration_seconds": duration,
                    "stream": stream,
                    "annotation_version": None,
                    "verification_status": "pending",
                }
            )
    return seal_registration_payload(
        {
            "schema_version": 1,
            "objective": "OBJ-77",
            "mode": "registration",
            "registered_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "audio_root": str(audio_root.resolve()),
            "video_root": str(video_root.resolve()),
            "entries": entries,
        }
    )


def _entry_errors(entry: object, index: int, audio_root: Path, video_root: Path, strict: bool) -> list[str]:
    errors = _object_errors(entry, f"entries[{index}]", ENTRY_REQUIRED, ENTRY_REQUIRED | ENTRY_OPTIONAL | IGNORED_LEGACY_FIELDS)
    if not isinstance(entry, dict):
        return errors
    media_id = entry.get("media_id")
    display = media_id if isinstance(media_id, str) and media_id else f"entries[{index}]"
    if not isinstance(media_id, str) or not media_id:
        errors.append(f"entries[{index}].media_id is invalid")
    media_type = entry.get("media_type")
    if media_type not in {"audio", "video"}:
        errors.append(f"{display} media_type is invalid")
        return errors
    root = audio_root if media_type == "audio" else video_root
    path_value = entry.get("absolute_path")
    try:
        path = Path(path_value) if isinstance(path_value, str) else None
        if path is None or not path.is_absolute() or not path.resolve().is_relative_to(root.resolve()):
            errors.append(f"{display} path is outside the approved root")
    except (OSError, ValueError):
        errors.append(f"{display} path is outside the approved root")
    if not isinstance(entry.get("size_bytes"), int) or isinstance(entry.get("size_bytes"), bool) or entry["size_bytes"] < 0:
        errors.append(f"{display} size_bytes is invalid")
    if not _is_sha256(entry.get("media_sha256")):
        errors.append(f"{display} media_sha256 must be SHA-256")
    if not _is_number(entry.get("duration_seconds")) or entry["duration_seconds"] <= 0:
        errors.append(f"{display} duration_seconds must be finite and positive")
    stream = entry.get("stream")
    if not isinstance(stream, dict) or set(stream) != {"codec_type", "codec_name"} or stream.get("codec_type") != media_type or not isinstance(stream.get("codec_name"), str) or not stream["codec_name"]:
        errors.append(f"{display} stream is invalid")
    annotation_version = entry.get("annotation_version")
    if annotation_version is not None and not _is_semver(annotation_version):
        errors.append(f"{display} annotation_version must be semantic version or null")
    status = entry.get("verification_status")
    if status not in ALLOWED_VERIFICATION_STATUSES:
        errors.append(f"{display} verification_status is invalid")
    if strict and status != "verified":
        errors.append(f"{display} verification_status must be verified for strict KPI validation")
    if strict and not _is_semver(annotation_version):
        errors.append(f"{display} annotation_version must be semantic version for strict KPI validation")
    annotation_path = entry.get("annotation_path")
    annotation_sha256 = entry.get("annotation_sha256")
    if annotation_path is not None and (not isinstance(annotation_path, str) or not annotation_path or not Path(annotation_path).is_absolute()):
        errors.append(f"{display} annotation_path is invalid")
    if annotation_sha256 is not None and not _is_sha256(annotation_sha256):
        errors.append(f"{display} annotation_sha256 must be SHA-256")
    if strict and not isinstance(annotation_path, str):
        errors.append(f"{display} annotation_path is required for strict KPI validation")
    if strict and not _is_sha256(annotation_sha256):
        errors.append(f"{display} annotation_sha256 is required for strict KPI validation")
    return errors


def _validate_entry_annotation(entry: dict[str, Any], duration_seconds: float) -> list[str]:
    media_id = entry.get("media_id", "entry")
    path_value = entry.get("annotation_path")
    expected_sha256 = entry.get("annotation_sha256")
    if not isinstance(path_value, str) or not _is_sha256(expected_sha256):
        return []
    path = Path(path_value)
    if not path.is_file():
        return [f"{media_id} annotation file is missing"]
    try:
        annotation_bytes = path.read_bytes()
    except OSError as error:
        return [f"{media_id} annotation file is unreadable: {error}"]
    if hashlib.sha256(annotation_bytes).hexdigest() != expected_sha256:
        return [f"{media_id} annotation hash drift"]
    try:
        annotation = json.loads(annotation_bytes)
    except json.JSONDecodeError:
        return [f"{media_id} annotation JSON is invalid"]
    if not isinstance(annotation, dict):
        return [f"{media_id} annotation must be an object"]
    errors: list[str] = []
    for field in ("media_id", "media_sha256", "annotation_version", "verification_status"):
        if annotation.get(field) != entry.get(field):
            errors.append(f"{media_id} annotation {field} does not bind to registration")
    errors.extend(f"{media_id} {error}" for error in validate_annotation(annotation, duration_seconds, strict=True))
    return errors


def validate_registration_payload(payload: object, *, strict: bool, verify_files: bool, audio_root: Path | None = None, video_root: Path | None = None) -> list[str]:
    errors = _object_errors(payload, "registration", REGISTRATION_REQUIRED, REGISTRATION_ALLOWED)
    if not isinstance(payload, dict):
        return errors
    if payload.get("schema_version") != 1:
        errors.append("registration schema_version must be 1")
    if payload.get("objective") != "OBJ-77" or payload.get("mode") != "registration":
        errors.append("registration objective or mode is invalid")
    try:
        expected_registration_sha256 = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    except (TypeError, ValueError):
        expected_registration_sha256 = None
    if payload.get("registration_sha256") != expected_registration_sha256:
        errors.append("registration_sha256 mismatch")
    registered_audio = Path(payload["audio_root"]) if isinstance(payload.get("audio_root"), str) else None
    registered_video = Path(payload["video_root"]) if isinstance(payload.get("video_root"), str) else None
    if registered_audio is None or registered_video is None:
        errors.append("registration roots are invalid")
        return errors
    effective_audio = audio_root or registered_audio
    effective_video = video_root or registered_video
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return errors + ["entries must be a list"]
    media_ids: list[str] = []
    paths: list[str] = []
    hashes: list[str] = []
    for index, entry in enumerate(entries):
        errors.extend(_entry_errors(entry, index, effective_audio, effective_video, strict))
        if not isinstance(entry, dict):
            continue
        if isinstance(entry.get("media_id"), str):
            media_ids.append(entry["media_id"])
        if isinstance(entry.get("absolute_path"), str):
            paths.append(str(Path(entry["absolute_path"]).resolve()).casefold())
        if isinstance(entry.get("media_sha256"), str):
            hashes.append(entry["media_sha256"].casefold())
        if verify_files and isinstance(entry.get("absolute_path"), str):
            path = Path(entry["absolute_path"])
            media_id = entry.get("media_id", f"entries[{index}]")
            if not path.is_file():
                errors.append(f"{media_id} media file is missing")
                continue
            if path.stat().st_size != entry.get("size_bytes"):
                errors.append(f"{media_id} size drift")
            if _sha256_file(path) != entry.get("media_sha256"):
                errors.append(f"{media_id} hash drift")
            try:
                duration, stream = _probe_media(path, str(entry.get("media_type")))
                if not _is_number(entry.get("duration_seconds")) or abs(duration - entry["duration_seconds"]) > 0.001:
                    errors.append(f"{media_id} duration drift")
                if stream != entry.get("stream"):
                    errors.append(f"{media_id} stream drift")
            except RuntimeError as error:
                errors.append(f"{media_id} {error}")
        if strict and isinstance(entry, dict) and _is_number(entry.get("duration_seconds")):
            errors.extend(_validate_entry_annotation(entry, float(entry["duration_seconds"])))
    for label, values in (("media_id", media_ids), ("absolute_path", paths), ("media_sha256", hashes)):
        duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
        for value in duplicates:
            errors.append(f"duplicate {label}: {value}" if label != "media_sha256" else "duplicate media_sha256")
    return errors


def _current_inventory(audio_root: Path, video_root: Path) -> tuple[set[str], list[str]]:
    inventory: set[str] = set()
    errors: list[str] = []
    for media_type, root in (("audio", audio_root), ("video", video_root)):
        if not root.is_dir():
            errors.append(f"approved {media_type} root is missing: {root}")
            continue
        inventory.update(str(path.resolve()).casefold() for path in root.rglob("*") if path.is_file())
    return inventory, errors


def validate_registration(receipt_path: Path, audio_root: Path, video_root: Path, *, strict: bool) -> list[str]:
    if not receipt_path.is_file():
        return [f"registration file is missing: {receipt_path}"]
    try:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"registration JSON is invalid: {error}"]
    errors: list[str] = []
    if audio_root.resolve() != DEFAULT_AUDIO_ROOT.resolve():
        errors.append(f"receipt verification requires approved audio root: {DEFAULT_AUDIO_ROOT}")
    if video_root.resolve() != DEFAULT_VIDEO_ROOT.resolve():
        errors.append(f"receipt verification requires approved video root: {DEFAULT_VIDEO_ROOT}")
    if not isinstance(payload, dict) or payload.get("audio_root") != str(DEFAULT_AUDIO_ROOT.resolve()):
        errors.append(f"receipt audio_root must equal approved root: {DEFAULT_AUDIO_ROOT}")
    if not isinstance(payload, dict) or payload.get("video_root") != str(DEFAULT_VIDEO_ROOT.resolve()):
        errors.append(f"receipt video_root must equal approved root: {DEFAULT_VIDEO_ROOT}")
    inventory, inventory_errors = _current_inventory(DEFAULT_AUDIO_ROOT, DEFAULT_VIDEO_ROOT)
    errors.extend(inventory_errors)
    if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
        receipt_paths = {
            str(Path(entry["absolute_path"]).resolve()).casefold()
            for entry in payload["entries"]
            if isinstance(entry, dict) and isinstance(entry.get("absolute_path"), str)
        }
        for path in sorted(inventory - receipt_paths):
            errors.append(f"current media missing from receipt: {path}")
        for path in sorted(receipt_paths - inventory):
            errors.append(f"receipt media is not in current inventory: {path}")
    errors.extend(validate_registration_payload(payload, strict=strict, verify_files=True, audio_root=DEFAULT_AUDIO_ROOT, video_root=DEFAULT_VIDEO_ROOT))
    return errors


def validate_time(value: object, duration_seconds: float, field: str) -> str | None:
    if not _is_number(value):
        return f"{field} must be finite"
    if value < 0 or value > duration_seconds:
        return f"{field} outside media duration"
    return None


def validate_annotation(payload: object, duration_seconds: float, *, strict: bool) -> list[str]:
    errors = _object_errors(payload, "annotation", ANNOTATION_REQUIRED, ANNOTATION_REQUIRED | IGNORED_LEGACY_FIELDS)
    if not isinstance(payload, dict):
        return errors
    if payload.get("schema_version") != 1:
        errors.append("annotation schema_version must be 1")
    if not isinstance(payload.get("media_id"), str) or not payload["media_id"]:
        errors.append("annotation media_id is invalid")
    if not _is_sha256(payload.get("media_sha256")):
        errors.append("annotation media_sha256 must be SHA-256")
    if not _is_semver(payload.get("annotation_version")):
        errors.append("annotation_version must be semantic version")
    if payload.get("verification_status") not in ALLOWED_VERIFICATION_STATUSES:
        errors.append("annotation verification_status is invalid")
    if strict and payload.get("verification_status") != "verified":
        errors.append("annotation verification_status must be verified for strict KPI validation")
    downbeats = payload.get("downbeats")
    if not isinstance(downbeats, list):
        errors.append("downbeats must be a list")
    else:
        bars: list[object] = []
        for index, item in enumerate(downbeats):
            if not isinstance(item, dict) or set(item) != {"time", "bar_number"}:
                errors.append(f"downbeats[{index}] must be an object with time and bar_number")
                continue
            error = validate_time(item.get("time"), duration_seconds, f"downbeats[{index}].time")
            if error:
                errors.append(error)
            bars.append(item.get("bar_number"))
        if bars and bars != list(range(1, len(bars) + 1)):
            errors.append("bar_number must increase contiguously")
    for name in ("subtracks", "song_sections", "pacing_cases"):
        _validate_segments(payload.get(name), duration_seconds, name, ALLOWED_SECTION_LABELS if name == "song_sections" else None, errors)
    scenes = payload.get("scene_boundaries")
    if not isinstance(scenes, list):
        errors.append("scene_boundaries must be a list")
    else:
        for index, item in enumerate(scenes):
            if not isinstance(item, dict) or set(item) != {"time", "transition_type"}:
                errors.append(f"scene_boundaries[{index}] must be an object with time and transition_type")
                continue
            error = validate_time(item.get("time"), duration_seconds, f"scene_boundaries[{index}].time")
            if error:
                errors.append(error)
            if item.get("transition_type") not in ALLOWED_SCENE_TYPES:
                errors.append(f"scene_boundaries[{index}].transition_type is not allowed")
    tags = payload.get("tags")
    if not isinstance(tags, dict) or set(tags) != {"required", "allowed", "forbidden"}:
        errors.append("tags must contain required, allowed and forbidden lists")
    else:
        for group, values in tags.items():
            if not isinstance(values, list):
                errors.append(f"tags.{group} must be a list")
            else:
                for index, value in enumerate(values):
                    if value not in ALLOWED_TAG_LABELS:
                        errors.append(f"tags.{group}[{index}] is not allowed")
    return errors


def _validate_segments(items: object, duration: float, name: str, labels: set[str] | None, errors: list[str]) -> None:
    if not isinstance(items, list):
        errors.append(f"{name} must be a list")
        return
    previous_end: float | None = None
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not {"start_time", "end_time"}.issubset(item) or set(item) - {"start_time", "end_time", "label"}:
            errors.append(f"{name}[{index}] must be a segment object")
            continue
        start, end = item.get("start_time"), item.get("end_time")
        for key, value in (("start_time", start), ("end_time", end)):
            error = validate_time(value, duration, f"{name}[{index}].{key}")
            if error:
                errors.append(error)
        if _is_number(start) and _is_number(end) and end <= start:
            errors.append(f"{name}[{index}] must have end_time after start_time")
        if previous_end is not None and _is_number(start) and start < previous_end:
            errors.append(f"{name} must not overlap")
        if _is_number(end):
            previous_end = end
        if labels is not None and item.get("label") not in labels:
            errors.append(f"{name}[{index}].label is not allowed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--audio-root", type=Path, default=DEFAULT_AUDIO_ROOT)
    parser.add_argument("--video-root", type=Path, default=DEFAULT_VIDEO_ROOT)
    args = parser.parse_args(argv)
    if args.register:
        if args.strict:
            parser.error("--register and --strict cannot be combined")
        if args.audio_root.resolve() != DEFAULT_AUDIO_ROOT.resolve():
            print(f"OBJ-77 registration blocked: registration requires approved audio root: {DEFAULT_AUDIO_ROOT}", file=sys.stderr)
            return 1
        if args.video_root.resolve() != DEFAULT_VIDEO_ROOT.resolve():
            print(f"OBJ-77 registration blocked: registration requires approved video root: {DEFAULT_VIDEO_ROOT}", file=sys.stderr)
            return 1
        try:
            payload = build_registration_payload(DEFAULT_AUDIO_ROOT, DEFAULT_VIDEO_ROOT)
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except (OSError, RuntimeError, ValueError) as error:
            print(f"OBJ-77 registration blocked: {error}", file=sys.stderr)
            return 1
    errors: list[str] = []
    if args.audio_root.resolve() != DEFAULT_AUDIO_ROOT.resolve():
        errors.append(f"receipt verification requires approved audio root: {DEFAULT_AUDIO_ROOT}")
    if args.video_root.resolve() != DEFAULT_VIDEO_ROOT.resolve():
        errors.append(f"receipt verification requires approved video root: {DEFAULT_VIDEO_ROOT}")
    errors.extend(validate_registration(args.receipt, args.audio_root, args.video_root, strict=args.strict))
    if errors:
        print("OBJ-77 ground truth blocked:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("OBJ-77 registration valid" if not args.strict else "OBJ-77 strict KPI validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
