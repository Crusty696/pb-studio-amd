"""Fail-closed validator for OBJ-77 independent real-media ground truth."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ALLOWED_SECTION_LABELS = {"intro", "verse", "chorus", "bridge", "outro", "drop"}
ALLOWED_SCENE_TYPES = {"cut", "fade", "dissolve"}
ALLOWED_TAG_LABELS = {
    "energy",
    "mood",
    "motion",
    "genre",
    "instrumental",
    "vocal",
    "dark",
    "uplifting",
    "calm",
    "intense",
}
REQUIRED_KPIS = ("section_alignment", "cut_accuracy", "sync_drift_under_10ms")
DEFAULT_AUDIO_ROOT = Path(r"C:\Users\david\Videos\test_data\audio")
DEFAULT_VIDEO_ROOT = Path(r"C:\Users\david\Videos\test_data\video")
DURATION_TOLERANCE_SECONDS = 0.001


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _version_tuple(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    pieces = value.split(".")
    if len(pieces) != 3 or any(not piece.isdigit() for piece in pieces):
        return None
    return tuple(int(piece) for piece in pieces)  # type: ignore[return-value]


def validate_time(value: object, duration_seconds: float, field: str) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return f"{field} must be finite"
    if value < 0.0 or value > duration_seconds:
        return f"{field} outside media duration"
    return None


def _validate_segments(
    items: object,
    duration_seconds: float,
    field: str,
    allowed_labels: set[str] | None = None,
) -> list[str]:
    if not isinstance(items, list):
        return [f"{field} must be a list"]
    errors: list[str] = []
    starts: list[float] = []
    previous_end: float | None = None
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{field}[{index}] must be an object")
            continue
        start = item.get("start_time")
        end = item.get("end_time")
        for key, value in (("start_time", start), ("end_time", end)):
            error = validate_time(value, duration_seconds, f"{field}[{index}].{key}")
            if error:
                errors.append(error)
        if isinstance(start, (int, float)) and not isinstance(start, bool) and math.isfinite(start):
            starts.append(float(start))
        if (
            isinstance(start, (int, float))
            and not isinstance(start, bool)
            and isinstance(end, (int, float))
            and not isinstance(end, bool)
            and math.isfinite(start)
            and math.isfinite(end)
            and end <= start
        ):
            errors.append(f"{field}[{index}] must have end_time after start_time")
        if allowed_labels is not None and item.get("label") not in allowed_labels:
            errors.append(f"{field}[{index}].label is not allowed")
        if (
            previous_end is not None
            and isinstance(start, (int, float))
            and not isinstance(start, bool)
            and math.isfinite(start)
            and start < previous_end
        ):
            errors.append(f"{field} must not overlap")
        if isinstance(end, (int, float)) and not isinstance(end, bool) and math.isfinite(end):
            previous_end = float(end)
    if starts != sorted(starts):
        errors.insert(0, f"{field} must be sorted by start_time")
    return errors


def validate_annotation(payload: dict, duration_seconds: float) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["annotation must be an object"]
    if payload.get("schema_version") != 1:
        errors.append("annotation schema_version must be 1")
    if payload.get("annotation_status") != "approved":
        errors.append("annotation_status must be approved")
    if not _is_nonempty_string(payload.get("annotator_id")):
        errors.append("annotator_id is required")
    if not _is_nonempty_string(payload.get("reviewer_id")):
        errors.append("reviewer_id is required")
    if payload.get("annotator_id") == payload.get("reviewer_id"):
        errors.append("annotator_id and reviewer_id must differ")
    if _version_tuple(payload.get("annotation_version")) is None:
        errors.append("annotation_version must be semantic version")

    downbeats = payload.get("downbeats", [])
    if not isinstance(downbeats, list):
        errors.append("downbeats must be a list")
    else:
        bars: list[object] = []
        times: list[float] = []
        for index, item in enumerate(downbeats):
            if not isinstance(item, dict):
                errors.append(f"downbeats[{index}] must be an object")
                continue
            error = validate_time(item.get("time"), duration_seconds, f"downbeats[{index}].time")
            if error:
                errors.append(error)
            elif isinstance(item["time"], (int, float)) and not isinstance(item["time"], bool):
                times.append(float(item["time"]))
            bars.append(item.get("bar_number"))
        if bars and bars != list(range(1, len(bars) + 1)):
            errors.append("bar_number must increase contiguously")
        if times != sorted(times):
            errors.append("downbeats must be sorted by time")

    errors.extend(_validate_segments(payload.get("subtracks", []), duration_seconds, "subtracks"))
    errors.extend(
        _validate_segments(
            payload.get("song_sections", []),
            duration_seconds,
            "song_sections",
            ALLOWED_SECTION_LABELS,
        )
    )
    errors.extend(_validate_segments(payload.get("pacing_cases", []), duration_seconds, "pacing_cases"))

    scene_boundaries = payload.get("scene_boundaries", [])
    if not isinstance(scene_boundaries, list):
        errors.append("scene_boundaries must be a list")
    else:
        scene_times: list[float] = []
        for index, item in enumerate(scene_boundaries):
            if not isinstance(item, dict):
                errors.append(f"scene_boundaries[{index}] must be an object")
                continue
            error = validate_time(item.get("time"), duration_seconds, f"scene_boundaries[{index}].time")
            if error:
                errors.append(error)
            elif isinstance(item["time"], (int, float)) and not isinstance(item["time"], bool):
                scene_times.append(float(item["time"]))
            if item.get("transition_type") not in ALLOWED_SCENE_TYPES:
                errors.append(f"scene_boundaries[{index}].transition_type is not allowed")
        if scene_times != sorted(scene_times):
            errors.append("scene_boundaries must be sorted by time")

    tags = payload.get("tags", {})
    if not isinstance(tags, dict):
        errors.append("tags must be an object")
    else:
        for group in ("required", "allowed", "forbidden"):
            values = tags.get(group, [])
            if not isinstance(values, list):
                errors.append(f"tags.{group} must be a list")
                continue
            for index, value in enumerate(values):
                if value not in ALLOWED_TAG_LABELS:
                    errors.append(f"tags.{group}[{index}] is not allowed")
    return errors


def validate_media_path(path: Path, approved_root: Path, media_id: str) -> list[str]:
    try:
        path.resolve().relative_to(approved_root.resolve())
    except ValueError:
        return [f"{media_id} path is outside the approved root"]
    return []


def validate_media_snapshot(
    entry: dict,
    *,
    observed_sha256: str,
    observed_duration_seconds: float,
    observed_stream: dict[str, str],
) -> list[str]:
    media_id = str(entry.get("media_id", "media"))
    errors: list[str] = []
    if entry.get("sha256") != observed_sha256:
        errors.append(f"{media_id} hash drift")
    expected_duration = entry.get("duration_seconds")
    if (
        isinstance(expected_duration, bool)
        or not isinstance(expected_duration, (int, float))
        or not math.isfinite(expected_duration)
        or not math.isfinite(observed_duration_seconds)
        or abs(float(expected_duration) - observed_duration_seconds) > DURATION_TOLERANCE_SECONDS
    ):
        errors.append(f"{media_id} duration drift")
    if entry.get("stream") != observed_stream:
        errors.append(f"{media_id} stream drift")
    return errors


def validate_corpus_metadata(payload: dict) -> list[str]:
    if not isinstance(payload, dict):
        return ["corpus must be an object"]
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("corpus schema_version must be 1")
    if payload.get("objective") != "OBJ-77":
        errors.append("corpus objective must be OBJ-77")

    media = payload.get("media", [])
    if not isinstance(media, list):
        errors.append("media must be a list")
        media = []
    for entry in media:
        if not isinstance(entry, dict):
            errors.append("media entry must be an object")
            continue
        media_id = str(entry.get("media_id", "media"))
        if entry.get("media_type") not in {"audio", "video"}:
            errors.append(f"{media_id} media_type is invalid")
        rights = entry.get("rights_evidence")
        if (
            not isinstance(rights, dict)
            or rights.get("approved") is not True
            or not _is_nonempty_string(rights.get("approval_id"))
            or not _is_nonempty_string(rights.get("approver_id"))
        ):
            errors.append(f"{media_id} rights evidence is incomplete")

    definitions = payload.get("kpi_definitions", {})
    if not isinstance(definitions, dict):
        definitions = {}
    for name in REQUIRED_KPIS:
        definition = definitions.get(name)
        if (
            not isinstance(definition, dict)
            or not _is_nonempty_string(definition.get("formula"))
            or not _is_nonempty_string(definition.get("owner_id"))
            or not _is_nonempty_string(definition.get("reviewer_id"))
        ):
            errors.append(f"kpi_definitions.{name} roles are incomplete")

    registrations = payload.get("annotations", [])
    if not isinstance(registrations, list):
        errors.append("annotations must be a list")
        registrations = []
    for record in registrations:
        if not isinstance(record, dict):
            errors.append("annotation registration must be an object")
            continue
        current = _version_tuple(record.get("annotation_version"))
        registered = _version_tuple(record.get("registered_annotation_version"))
        if (
            record.get("sha256") != record.get("registered_sha256")
            and current is not None
            and registered is not None
            and current <= registered
        ):
            errors.append(
                f"{record.get('media_id', 'media')} annotation mutation without a version increase"
            )
    return errors


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
    completed = subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError("ffprobe failed")
    try:
        payload = json.loads(completed.stdout)
        duration = float(payload["format"]["duration"])
        stream = next(item for item in payload["streams"] if item.get("codec_type") == media_type)
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("ffprobe returned an incomplete media description") from error
    if not math.isfinite(duration) or duration <= 0:
        raise RuntimeError("ffprobe returned an invalid media duration")
    return duration, {"codec_type": stream["codec_type"], "codec_name": stream["codec_name"]}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(str(error)) from error
    if not isinstance(payload, dict):
        raise ValueError("JSON document must be an object")
    return payload


def validate_corpus(corpus_path: Path, audio_root: Path, video_root: Path) -> list[str]:
    if not corpus_path.is_file():
        return [f"corpus file is missing: {corpus_path}"]
    try:
        corpus = _load_json(corpus_path)
    except ValueError as error:
        return [f"corpus JSON is invalid: {error}"]

    errors = validate_corpus_metadata(corpus)
    media_by_id: dict[str, dict] = {}
    media = corpus.get("media", [])
    if isinstance(media, list):
        audio_count = sum(
            1 for entry in media if isinstance(entry, dict) and entry.get("media_type") == "audio"
        )
        video_count = sum(
            1 for entry in media if isinstance(entry, dict) and entry.get("media_type") == "video"
        )
        if audio_count < 5:
            errors.append("corpus must contain at least five audio mixes")
        if video_count < 10:
            errors.append("corpus must contain at least ten videos")
        for entry in media:
            if not isinstance(entry, dict):
                continue
            media_id = str(entry.get("media_id", "media"))
            media_by_id[media_id] = entry
            media_type = entry.get("media_type")
            root = audio_root if media_type == "audio" else video_root
            relative_path = entry.get("relative_path")
            if not isinstance(relative_path, str):
                errors.append(f"{media_id} relative_path is invalid")
                continue
            media_path = root / relative_path
            errors.extend(validate_media_path(media_path, root, media_id))
            if not media_path.is_file():
                errors.append(f"{media_id} media file is missing")
                continue
            try:
                observed_duration, observed_stream = _probe_media(media_path, str(media_type))
                errors.extend(
                    validate_media_snapshot(
                        entry,
                        observed_sha256=_sha256_file(media_path),
                        observed_duration_seconds=observed_duration,
                        observed_stream=observed_stream,
                    )
                )
            except RuntimeError as error:
                errors.append(f"{media_id} {error}")

    registrations = corpus.get("annotations", [])
    if isinstance(registrations, list):
        annotation_root = corpus_path.parent.resolve()
        for record in registrations:
            if not isinstance(record, dict):
                continue
            media_id = str(record.get("media_id", "media"))
            relative_path = record.get("relative_path")
            if not isinstance(relative_path, str):
                errors.append(f"{media_id} annotation relative_path is invalid")
                continue
            annotation_path = annotation_root / relative_path
            try:
                annotation_path.resolve().relative_to(annotation_root)
            except ValueError:
                errors.append(f"{media_id} annotation path is outside the corpus directory")
                continue
            if not annotation_path.is_file():
                errors.append(f"{media_id} annotation file is missing")
                continue
            observed_sha256 = _sha256_file(annotation_path)
            if record.get("sha256") != observed_sha256:
                errors.append(f"{media_id} annotation hash drift")
            try:
                annotation = _load_json(annotation_path)
            except ValueError as error:
                errors.append(f"{media_id} annotation JSON is invalid: {error}")
                continue
            source_media = media_by_id.get(media_id)
            if source_media is None:
                errors.append(f"{media_id} annotation references unknown media")
                continue
            if annotation.get("media_sha256") != source_media.get("sha256"):
                errors.append(f"{media_id} annotation media hash mismatch")
            if annotation.get("annotation_version") != record.get("annotation_version"):
                errors.append(f"{media_id} annotation version mismatch")
            annotation_version = _version_tuple(annotation.get("annotation_version"))
            registered_version = _version_tuple(record.get("registered_annotation_version"))
            if (
                observed_sha256 != record.get("registered_sha256")
                and annotation_version is not None
                and registered_version is not None
                and annotation_version <= registered_version
            ):
                errors.append(f"{media_id} annotation mutation without a version increase")
            duration = source_media.get("duration_seconds")
            if isinstance(duration, (int, float)) and not isinstance(duration, bool) and math.isfinite(duration):
                errors.extend(validate_annotation(annotation, float(duration)))
            else:
                errors.append(f"{media_id} annotation cannot be checked without a finite duration")
    return errors


def build_registration_receipt(corpus_path: Path) -> dict[str, object]:
    corpus = _load_json(corpus_path)
    return {
        "corpus_sha256": _sha256_file(corpus_path),
        "annotation_sha256": [
            {"media_id": item.get("media_id"), "sha256": item.get("sha256")}
            for item in corpus.get("annotations", [])
            if isinstance(item, dict)
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--audio-root", type=Path, default=DEFAULT_AUDIO_ROOT)
    parser.add_argument("--video-root", type=Path, default=DEFAULT_VIDEO_ROOT)
    parser.add_argument("--strict", action="store_true", help="Reserved for the mandatory real-media gate.")
    args = parser.parse_args(argv)

    errors = validate_corpus(args.corpus, args.audio_root, args.video_root)
    if errors:
        print("OBJ-77 ground truth blocked:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(json.dumps(build_registration_receipt(args.corpus), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
