"""Fail-closed validator for OBJ-77 independent real-media ground truth."""

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
from pathlib import Path
from typing import Any


ALLOWED_SECTION_LABELS = {"intro", "verse", "chorus", "bridge", "outro", "drop"}
ALLOWED_SCENE_TYPES = {"cut", "fade", "dissolve"}
ALLOWED_TAG_LABELS = {
    "energy", "mood", "motion", "genre", "instrumental", "vocal", "dark", "uplifting", "calm", "intense"
}
ALLOWED_RIGHTS_SOURCE_TYPES = {"licensed", "owned", "permission_granted", "public_domain"}
REQUIRED_KPIS = ("section_alignment", "cut_accuracy", "sync_drift_under_10ms")
REQUIRED_VIDEO_MARKERS = {"continuous", "cut", "fade", "dissolve"}
DEFAULT_AUDIO_ROOT = Path(r"C:\Users\david\Videos\test_data\audio")
DEFAULT_VIDEO_ROOT = Path(r"C:\Users\david\Videos\test_data\video")
DURATION_TOLERANCE_SECONDS = 0.001
SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
IDENTITY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

ANNOTATION_REQUIRED = {
    "schema_version", "media_id", "media_sha256", "annotation_version", "annotation_status",
    "annotator_id", "reviewer_id", "independent_labeling", "downbeats", "subtracks",
    "song_sections", "scene_boundaries", "tags", "pacing_cases",
}
CORPUS_REQUIRED = {"schema_version", "objective", "corpus_version", "corpus_policy", "kpi_definitions", "media", "annotations"}
CORPUS_ALLOWED = CORPUS_REQUIRED | {"previous_corpus_sha256", "previous_corpus_version"}


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _canonical_identity(value: object) -> str | None:
    if not _is_nonempty_string(value):
        return None
    normalized = value.strip().casefold()
    return normalized if IDENTITY_RE.fullmatch(normalized) else None


def _version_tuple(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, str) or not SEMVER_RE.fullmatch(value):
        return None
    return tuple(int(piece) for piece in value.split("."))  # type: ignore[return-value]


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _validate_object_keys(payload: object, *, name: str, required: set[str], allowed: set[str]) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{name} must be an object"]
    errors = [f"{name} missing required field: {key}" for key in sorted(required - payload.keys())]
    errors.extend(f"{name} has unexpected field: {key}" for key in sorted(payload.keys() - allowed))
    return errors


def validate_time(value: object, duration_seconds: float, field: str) -> str | None:
    if not _is_finite_number(value):
        return f"{field} must be finite"
    if value < 0.0 or value > duration_seconds:
        return f"{field} outside media duration"
    return None


def _validate_segment_structure(item: object, field: str) -> list[str]:
    errors = _validate_object_keys(item, name=field, required={"start_time", "end_time"}, allowed={"start_time", "end_time", "label"})
    if not isinstance(item, dict):
        return errors
    if "start_time" in item and not _is_finite_number(item["start_time"]):
        errors.append(f"{field}.start_time must be a finite number")
    if "end_time" in item and not _is_finite_number(item["end_time"]):
        errors.append(f"{field}.end_time must be a finite number")
    if "label" in item and not isinstance(item["label"], str):
        errors.append(f"{field}.label must be a string")
    return errors


def _validate_annotation_structure(payload: object) -> list[str]:
    errors = _validate_object_keys(payload, name="annotation", required=ANNOTATION_REQUIRED, allowed=ANNOTATION_REQUIRED)
    if not isinstance(payload, dict):
        return errors
    if payload.get("schema_version") != 1:
        errors.append("annotation schema_version must be 1")
    for field in ("media_id", "annotator_id", "reviewer_id"):
        if _canonical_identity(payload.get(field)) is None:
            errors.append(f"annotation {field} must use canonical identity syntax")
    if not _is_sha256(payload.get("media_sha256")):
        errors.append("annotation media_sha256 must be SHA-256")
    if _version_tuple(payload.get("annotation_version")) is None:
        errors.append("annotation_version must be semantic version")
    if payload.get("annotation_status") != "approved":
        errors.append("annotation_status must be approved")

    attestation = payload.get("independent_labeling")
    attestation_required = {"attested", "annotator_attestor_id", "reviewer_attestor_id", "source_system"}
    errors.extend(_validate_object_keys(attestation, name="independent_labeling", required=attestation_required, allowed=attestation_required))
    if isinstance(attestation, dict):
        if attestation.get("attested") is not True:
            errors.append("independent_labeling.attested must be true")
        if attestation.get("source_system") != "independent_of_pb_studio":
            errors.append("independent_labeling.source_system must be independent_of_pb_studio")
        for field in ("annotator_attestor_id", "reviewer_attestor_id"):
            if _canonical_identity(attestation.get(field)) is None:
                errors.append(f"independent_labeling.{field} must use canonical identity syntax")

    for field in ("downbeats", "subtracks", "song_sections", "scene_boundaries", "pacing_cases"):
        if field in payload and not isinstance(payload[field], list):
            errors.append(f"{field} must be a list")
    downbeats = payload.get("downbeats")
    if isinstance(downbeats, list):
        for index, item in enumerate(downbeats):
            errors.extend(_validate_object_keys(item, name=f"downbeats[{index}]", required={"time", "bar_number"}, allowed={"time", "bar_number"}))
            if isinstance(item, dict):
                if "time" in item and not _is_finite_number(item["time"]):
                    errors.append(f"downbeats[{index}].time must be finite")
                if "bar_number" in item and (not isinstance(item["bar_number"], int) or isinstance(item["bar_number"], bool) or item["bar_number"] < 1):
                    errors.append(f"downbeats[{index}].bar_number must be a positive integer")
    for field in ("subtracks", "song_sections", "pacing_cases"):
        items = payload.get(field)
        if isinstance(items, list):
            for index, item in enumerate(items):
                errors.extend(_validate_segment_structure(item, f"{field}[{index}]"))
    scenes = payload.get("scene_boundaries")
    if isinstance(scenes, list):
        for index, item in enumerate(scenes):
            errors.extend(_validate_object_keys(item, name=f"scene_boundaries[{index}]", required={"time", "transition_type"}, allowed={"time", "transition_type"}))
            if isinstance(item, dict):
                if "time" in item and not _is_finite_number(item["time"]):
                    errors.append(f"scene_boundaries[{index}].time must be finite")
                if "transition_type" in item and not isinstance(item["transition_type"], str):
                    errors.append(f"scene_boundaries[{index}].transition_type must be a string")
    tags = payload.get("tags")
    errors.extend(_validate_object_keys(tags, name="tags", required={"required", "allowed", "forbidden"}, allowed={"required", "allowed", "forbidden"}))
    if isinstance(tags, dict):
        for group in ("required", "allowed", "forbidden"):
            if group in tags and not isinstance(tags[group], list):
                errors.append(f"tags.{group} must be a list")
            elif isinstance(tags.get(group), list) and not all(isinstance(value, str) for value in tags[group]):
                errors.append(f"tags.{group} must contain strings")
    return errors


def _validate_segments(items: object, duration_seconds: float, field: str, allowed_labels: set[str] | None = None) -> list[str]:
    if not isinstance(items, list):
        return []
    errors: list[str] = []
    starts: list[float] = []
    previous_end: float | None = None
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        start, end = item.get("start_time"), item.get("end_time")
        for key, value in (("start_time", start), ("end_time", end)):
            error = validate_time(value, duration_seconds, f"{field}[{index}].{key}")
            if error:
                errors.append(error)
        if _is_finite_number(start):
            starts.append(float(start))
        if _is_finite_number(start) and _is_finite_number(end) and end <= start:
            errors.append(f"{field}[{index}] must have end_time after start_time")
        if allowed_labels is not None and item.get("label") not in allowed_labels:
            errors.append(f"{field}[{index}].label is not allowed")
        if previous_end is not None and _is_finite_number(start) and start < previous_end:
            errors.append(f"{field} must not overlap")
        if _is_finite_number(end):
            previous_end = float(end)
    if starts != sorted(starts):
        errors.insert(0, f"{field} must be sorted by start_time")
    return errors


def validate_annotation(payload: dict, duration_seconds: float) -> list[str]:
    errors = _validate_annotation_structure(payload)
    if not isinstance(payload, dict):
        return errors
    annotator = _canonical_identity(payload.get("annotator_id"))
    reviewer = _canonical_identity(payload.get("reviewer_id"))
    if annotator is not None and reviewer is not None and annotator == reviewer:
        errors.append("annotator_id and reviewer_id must differ")
    attestation = payload.get("independent_labeling")
    if isinstance(attestation, dict):
        if annotator is not None and reviewer is not None and annotator != reviewer:
            if _canonical_identity(attestation.get("annotator_attestor_id")) != annotator:
                errors.append("independent_labeling annotator identity mismatch")
            if _canonical_identity(attestation.get("reviewer_attestor_id")) != reviewer:
                errors.append("independent_labeling reviewer identity mismatch")

    downbeats = payload.get("downbeats")
    if isinstance(downbeats, list):
        bars: list[object] = []
        times: list[float] = []
        for index, item in enumerate(downbeats):
            if not isinstance(item, dict):
                continue
            error = validate_time(item.get("time"), duration_seconds, f"downbeats[{index}].time")
            if error and error not in errors:
                errors.append(error)
            elif _is_finite_number(item.get("time")):
                times.append(float(item["time"]))
            bars.append(item.get("bar_number"))
        if bars and bars != list(range(1, len(bars) + 1)):
            errors.append("bar_number must increase contiguously")
        if times != sorted(times):
            errors.append("downbeats must be sorted by time")
    errors.extend(_validate_segments(payload.get("subtracks"), duration_seconds, "subtracks"))
    errors.extend(_validate_segments(payload.get("song_sections"), duration_seconds, "song_sections", ALLOWED_SECTION_LABELS))
    errors.extend(_validate_segments(payload.get("pacing_cases"), duration_seconds, "pacing_cases"))
    scenes = payload.get("scene_boundaries")
    if isinstance(scenes, list):
        scene_times: list[float] = []
        for index, item in enumerate(scenes):
            if not isinstance(item, dict):
                continue
            error = validate_time(item.get("time"), duration_seconds, f"scene_boundaries[{index}].time")
            if error and error not in errors:
                errors.append(error)
            elif _is_finite_number(item.get("time")):
                scene_times.append(float(item["time"]))
            if item.get("transition_type") not in ALLOWED_SCENE_TYPES:
                errors.append(f"scene_boundaries[{index}].transition_type is not allowed")
        if scene_times != sorted(scene_times):
            errors.append("scene_boundaries must be sorted by time")
    tags = payload.get("tags")
    if isinstance(tags, dict):
        for group in ("required", "allowed", "forbidden"):
            values = tags.get(group)
            if isinstance(values, list):
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


def validate_media_snapshot(entry: dict, *, observed_sha256: str, observed_duration_seconds: float, observed_stream: dict[str, str]) -> list[str]:
    media_id = str(entry.get("media_id", "media"))
    errors: list[str] = []
    if entry.get("sha256") != observed_sha256:
        errors.append(f"{media_id} hash drift")
    expected_duration = entry.get("duration_seconds")
    if not _is_finite_number(expected_duration) or not math.isfinite(observed_duration_seconds) or abs(float(expected_duration) - observed_duration_seconds) > DURATION_TOLERANCE_SECONDS:
        errors.append(f"{media_id} duration drift")
    if entry.get("stream") != observed_stream:
        errors.append(f"{media_id} stream drift")
    return errors


def _validate_rights(entry: dict, media_id: str) -> list[str]:
    rights = entry.get("rights_evidence")
    if not isinstance(rights, dict):
        return [f"{media_id} rights evidence is incomplete"]
    required = {"approval_id", "approver_id", "approved", "provenance", "source_type", "real_media"}
    errors = _validate_object_keys(rights, name=f"{media_id} rights_evidence", required=required, allowed=required)
    if rights.get("approved") is not True or rights.get("real_media") is not True or not _is_nonempty_string(rights.get("approval_id")) or _canonical_identity(rights.get("approver_id")) is None or not _is_nonempty_string(rights.get("provenance")) or rights.get("source_type") not in ALLOWED_RIGHTS_SOURCE_TYPES:
        errors.append(f"{media_id} rights evidence is incomplete")
    return errors


def _validate_policy(payload: dict) -> list[str]:
    policy = payload.get("corpus_policy")
    required = {"mode", "audio_duration_slots", "video_coverage"}
    errors = _validate_object_keys(policy, name="corpus_policy", required=required, allowed=required)
    if not isinstance(policy, dict):
        return errors
    if policy.get("mode") not in {"initial", "update"}:
        errors.append("corpus_policy.mode must be initial or update")
    slots = policy.get("audio_duration_slots")
    if not isinstance(slots, list) or len(slots) != 5:
        errors.append("corpus_policy must define exactly five audio duration slots")
    elif isinstance(slots, list):
        slot_ids: list[str] = []
        for index, slot in enumerate(slots):
            errors.extend(_validate_object_keys(slot, name=f"audio_duration_slots[{index}]", required={"slot_id", "min_duration_seconds", "max_duration_seconds"}, allowed={"slot_id", "min_duration_seconds", "max_duration_seconds"}))
            if not isinstance(slot, dict):
                continue
            if not _is_nonempty_string(slot.get("slot_id")):
                errors.append(f"audio_duration_slots[{index}].slot_id is invalid")
            else:
                slot_ids.append(slot["slot_id"])
            minimum, maximum = slot.get("min_duration_seconds"), slot.get("max_duration_seconds")
            if not _is_finite_number(minimum) or not _is_finite_number(maximum) or minimum <= 0 or maximum < minimum:
                errors.append(f"audio_duration_slots[{index}] duration bounds are invalid")
        if len(slot_ids) != len(set(slot_ids)):
            errors.append("audio_duration_slots slot_id values must be unique")
    coverage = policy.get("video_coverage")
    required_coverage = {"required_markers", "approval_id", "approver_id"}
    errors.extend(_validate_object_keys(coverage, name="corpus_policy.video_coverage", required=required_coverage, allowed=required_coverage))
    if isinstance(coverage, dict):
        markers = coverage.get("required_markers")
        if not isinstance(markers, list):
            errors.append("corpus_policy.video_coverage required_markers must be a list")
        elif not all(isinstance(marker, str) for marker in markers):
            errors.append("corpus_policy.video_coverage required_markers must contain strings")
        elif set(markers) != REQUIRED_VIDEO_MARKERS:
            errors.append("corpus_policy.video_coverage markers must be continuous, cut, fade and dissolve")
        if not _is_nonempty_string(coverage.get("approval_id")) or _canonical_identity(coverage.get("approver_id")) is None:
            errors.append("corpus_policy.video_coverage approval is incomplete")
    return errors


def _validate_corpus_structure(payload: object) -> list[str]:
    errors = _validate_object_keys(payload, name="corpus", required=CORPUS_REQUIRED, allowed=CORPUS_ALLOWED)
    if not isinstance(payload, dict):
        return errors
    if payload.get("schema_version") != 1:
        errors.append("corpus schema_version must be 1")
    if payload.get("objective") != "OBJ-77":
        errors.append("corpus objective must be OBJ-77")
    if _version_tuple(payload.get("corpus_version")) is None:
        errors.append("corpus_version must be semantic version")
    if not isinstance(payload.get("media"), list):
        errors.append("media must be a list")
    if not isinstance(payload.get("annotations"), list):
        errors.append("annotations must be a list")
    definitions = payload.get("kpi_definitions")
    errors.extend(_validate_object_keys(definitions, name="kpi_definitions", required=set(REQUIRED_KPIS), allowed=set(REQUIRED_KPIS)))
    if isinstance(definitions, dict):
        for name in REQUIRED_KPIS:
            definition = definitions.get(name)
            errors.extend(_validate_object_keys(definition, name=f"kpi_definitions.{name}", required={"formula", "owner_id", "reviewer_id"}, allowed={"formula", "owner_id", "reviewer_id"}))
            if isinstance(definition, dict) and (not _is_nonempty_string(definition.get("formula")) or _canonical_identity(definition.get("owner_id")) is None or _canonical_identity(definition.get("reviewer_id")) is None):
                errors.append(f"kpi_definitions.{name} roles are incomplete")
    errors.extend(_validate_policy(payload))
    return errors


def _annotation_record_errors(record: object, index: int) -> list[str]:
    required = {"media_id", "relative_path", "sha256", "annotation_version"}
    errors = _validate_object_keys(record, name=f"annotations[{index}]", required=required, allowed=required | {"previous_sha256", "previous_annotation_version"})
    if not isinstance(record, dict):
        return errors
    if not _is_nonempty_string(record.get("media_id")):
        errors.append(f"annotations[{index}].media_id is invalid")
    if not _is_nonempty_string(record.get("relative_path")):
        errors.append(f"annotations[{index}].relative_path is invalid")
    if not _is_sha256(record.get("sha256")):
        errors.append(f"annotations[{index}].sha256 must be SHA-256")
    if _version_tuple(record.get("annotation_version")) is None:
        errors.append(f"annotations[{index}].annotation_version must be semantic version")
    return errors


def validate_corpus_metadata(payload: dict, prior_registration: dict | None = None) -> list[str]:
    errors = _validate_corpus_structure(payload)
    if not isinstance(payload, dict):
        return errors
    media = payload.get("media") if isinstance(payload.get("media"), list) else []
    registrations = payload.get("annotations") if isinstance(payload.get("annotations"), list) else []
    media_ids: list[str] = []
    paths: list[str] = []
    hashes: list[str] = []
    for index, entry in enumerate(media):
        media_required = {"media_id", "media_type", "relative_path", "sha256", "duration_seconds", "stream", "rights_evidence"}
        errors.extend(_validate_object_keys(entry, name=f"media[{index}]", required=media_required, allowed=media_required | {"profile_slot", "coverage_markers"}))
        if not isinstance(entry, dict):
            continue
        media_id = str(entry.get("media_id", f"media[{index}]"))
        if not _is_nonempty_string(entry.get("media_id")):
            errors.append(f"media[{index}].media_id is invalid")
        else:
            media_ids.append(entry["media_id"])
        if entry.get("media_type") not in {"audio", "video"}:
            errors.append(f"{media_id} media_type is invalid")
        if not _is_nonempty_string(entry.get("relative_path")):
            errors.append(f"{media_id} relative_path is invalid")
        else:
            paths.append(entry["relative_path"].replace("/", "\\").casefold())
        if not _is_sha256(entry.get("sha256")):
            errors.append(f"{media_id} sha256 must be SHA-256")
        else:
            hashes.append(entry["sha256"].casefold())
        if not _is_finite_number(entry.get("duration_seconds")) or entry["duration_seconds"] <= 0:
            errors.append(f"{media_id} duration_seconds is invalid")
        stream = entry.get("stream")
        errors.extend(_validate_object_keys(stream, name=f"{media_id} stream", required={"codec_type", "codec_name"}, allowed={"codec_type", "codec_name"}))
        if isinstance(stream, dict) and (stream.get("codec_type") != entry.get("media_type") or not _is_nonempty_string(stream.get("codec_name"))):
            errors.append(f"{media_id} stream is invalid")
        errors.extend(_validate_rights(entry, media_id))
        if entry.get("media_type") == "audio" and not _is_nonempty_string(entry.get("profile_slot")):
            errors.append(f"{media_id} profile_slot is required")
        if entry.get("media_type") == "video":
            coverage = entry.get("coverage_markers")
            if (
                not isinstance(coverage, list)
                or not coverage
                or not all(isinstance(marker, str) for marker in coverage)
                or not set(coverage).issubset(REQUIRED_VIDEO_MARKERS)
            ):
                errors.append(f"{media_id} coverage_markers are invalid")
    for label, values in (("media_id", media_ids), ("media relative_path", paths), ("media sha256", hashes)):
        for value, count in Counter(values).items():
            if count > 1:
                errors.append(f"duplicate {label}: {value}" if label != "media sha256" else "duplicate media sha256")

    for index, record in enumerate(registrations):
        errors.extend(_annotation_record_errors(record, index))
    registration_ids = [record["media_id"] for record in registrations if isinstance(record, dict) and _is_nonempty_string(record.get("media_id"))]
    registration_paths = [record["relative_path"].replace("/", "\\").casefold() for record in registrations if isinstance(record, dict) and _is_nonempty_string(record.get("relative_path"))]
    registration_hashes = [record["sha256"].casefold() for record in registrations if isinstance(record, dict) and _is_sha256(record.get("sha256"))]
    for label, values in (("annotation media_id", registration_ids), ("annotation relative_path", registration_paths), ("annotation sha256", registration_hashes)):
        for value, count in Counter(values).items():
            if count > 1:
                errors.append(f"duplicate {label}: {value}" if label != "annotation sha256" else "duplicate annotation sha256")
    media_id_set = set(media_ids)
    registration_id_set = set(registration_ids)
    for media_id in sorted(media_id_set - registration_id_set):
        errors.append(f"missing annotation registration for {media_id}")
    for media_id in sorted(registration_id_set - media_id_set):
        errors.append(f"annotation registration references unknown media: {media_id}")

    policy = payload.get("corpus_policy")
    if isinstance(policy, dict):
        slots = policy.get("audio_duration_slots")
        if isinstance(slots, list) and len(slots) == 5 and all(isinstance(slot, dict) for slot in slots):
            by_slot = {slot.get("slot_id"): slot for slot in slots}
            assigned = [entry.get("profile_slot") for entry in media if isinstance(entry, dict) and entry.get("media_type") == "audio"]
            if Counter(assigned) != Counter(by_slot.keys()):
                errors.append("audio mixes must map one-to-one to the frozen duration slots")
            for entry in media:
                if not isinstance(entry, dict) or entry.get("media_type") != "audio":
                    continue
                slot = by_slot.get(entry.get("profile_slot"))
                duration = entry.get("duration_seconds")
                if isinstance(slot, dict) and _is_finite_number(duration) and _is_finite_number(slot.get("min_duration_seconds")) and _is_finite_number(slot.get("max_duration_seconds")) and not (slot["min_duration_seconds"] <= duration <= slot["max_duration_seconds"]):
                    errors.append(f"{entry.get('media_id', 'media')} duration is outside its frozen profile slot")
        coverage = policy.get("video_coverage")
        if isinstance(coverage, dict) and isinstance(coverage.get("required_markers"), list):
            observed_markers = {
                marker
                for entry in media
                if isinstance(entry, dict) and entry.get("media_type") == "video"
                for marker in (entry.get("coverage_markers") if isinstance(entry.get("coverage_markers"), list) else [])
                if isinstance(marker, str)
            }
            if not REQUIRED_VIDEO_MARKERS.issubset(observed_markers):
                errors.append("video coverage markers are incomplete")

        mode = policy.get("mode")
        if mode == "initial":
            if "previous_corpus_sha256" in payload or "previous_corpus_version" in payload:
                errors.append("initial mode must not include prior registration fields")
        elif mode == "update":
            errors.extend(_validate_update_metadata(payload, registrations, prior_registration))
    return errors


def _validate_prior_registration(prior_registration: object) -> tuple[list[str], dict[str, dict]]:
    required = {"schema_version", "registration_kind", "corpus_sha256", "corpus_version", "annotations"}
    errors = _validate_object_keys(
        prior_registration,
        name="prior registration",
        required=required,
        allowed=required,
    )
    if not isinstance(prior_registration, dict):
        return errors, {}
    if prior_registration.get("schema_version") != 1:
        errors.append("prior registration schema_version must be 1")
    if prior_registration.get("registration_kind") != "OBJ-77-ground-truth-prior":
        errors.append("prior registration kind is invalid")
    if not _is_sha256(prior_registration.get("corpus_sha256")):
        errors.append("prior registration corpus_sha256 must be SHA-256")
    if _version_tuple(prior_registration.get("corpus_version")) is None:
        errors.append("prior registration corpus_version must be semantic version")
    annotations = prior_registration.get("annotations")
    if not isinstance(annotations, list):
        errors.append("prior registration annotations must be a list")
        return errors, {}
    previous: dict[str, dict] = {}
    media_ids: list[str] = []
    for index, entry in enumerate(annotations):
        entry_required = {"media_id", "sha256", "annotation_version"}
        errors.extend(
            _validate_object_keys(
                entry,
                name=f"prior registration annotations[{index}]",
                required=entry_required,
                allowed=entry_required,
            )
        )
        if not isinstance(entry, dict):
            continue
        media_id = entry.get("media_id")
        if not _is_nonempty_string(media_id):
            errors.append(f"prior registration annotations[{index}].media_id is invalid")
            continue
        media_ids.append(media_id)
        if not _is_sha256(entry.get("sha256")):
            errors.append(f"prior registration annotations[{index}].sha256 must be SHA-256")
        if _version_tuple(entry.get("annotation_version")) is None:
            errors.append(f"prior registration annotations[{index}].annotation_version must be semantic version")
        previous[media_id] = entry
    if len(media_ids) != len(set(media_ids)):
        errors.append("prior registration annotation media_id values must be unique")
    return errors, previous


def _validate_update_metadata(payload: dict, registrations: list[object], prior_registration: dict | None) -> list[str]:
    if prior_registration is None:
        return ["update mode requires --prior-registration"]
    errors, previous = _validate_prior_registration(prior_registration)
    if errors:
        errors.append("prior registration is invalid")
        return errors
    if payload.get("previous_corpus_sha256") != prior_registration.get("corpus_sha256") or payload.get("previous_corpus_version") != prior_registration.get("corpus_version"):
        errors.append("update corpus does not match the supplied prior registration")
    current_version = _version_tuple(payload.get("corpus_version"))
    prior_version = _version_tuple(prior_registration.get("corpus_version"))
    if current_version is not None and prior_version is not None and current_version <= prior_version:
        errors.append("update corpus_version must increase")
    for record in registrations:
        if not isinstance(record, dict):
            continue
        media_id = record.get("media_id")
        prior = previous.get(media_id)
        if not isinstance(prior, dict):
            errors.append(f"update annotation lacks prior registration: {media_id}")
            continue
        if record.get("previous_sha256") != prior.get("sha256") or record.get("previous_annotation_version") != prior.get("annotation_version"):
            errors.append(f"update annotation does not match prior registration: {media_id}")
            continue
        current_version = _version_tuple(record.get("annotation_version"))
        previous_version = _version_tuple(prior.get("annotation_version"))
        if record.get("sha256") != prior.get("sha256") and current_version is not None and previous_version is not None and current_version <= previous_version:
            errors.append(f"{media_id} annotation mutation without a version increase")
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
    completed = subprocess.run([executable, "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name", "-of", "json", str(path)], check=False, capture_output=True, text=True, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError("ffprobe failed")
    try:
        payload = json.loads(completed.stdout)
        duration = float(payload["format"]["duration"])
        stream = next(item for item in payload["streams"] if item.get("codec_type") == media_type)
        result = {"codec_type": stream["codec_type"], "codec_name": stream["codec_name"]}
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("ffprobe returned an incomplete media description") from error
    if not math.isfinite(duration) or duration <= 0:
        raise RuntimeError("ffprobe returned an invalid media duration")
    return duration, result


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(str(error)) from error
    if not isinstance(payload, dict):
        raise ValueError("JSON document must be an object")
    return payload


def validate_corpus(corpus_path: Path, audio_root: Path, video_root: Path, prior_registration_path: Path | None = None) -> list[str]:
    if not corpus_path.is_file():
        return [f"corpus file is missing: {corpus_path}"]
    try:
        corpus = _load_json(corpus_path)
    except ValueError as error:
        return [f"corpus JSON is invalid: {error}"]
    prior_registration: dict | None = None
    if prior_registration_path is not None:
        if prior_registration_path.resolve() == corpus_path.resolve():
            return ["prior registration must be a separate file"]
        if not prior_registration_path.is_file():
            return [f"prior registration file is missing: {prior_registration_path}"]
        try:
            prior_registration = _load_json(prior_registration_path)
        except ValueError as error:
            return [f"prior registration JSON is invalid: {error}"]
    errors = validate_corpus_metadata(corpus, prior_registration)
    media = corpus.get("media") if isinstance(corpus.get("media"), list) else []
    valid_media: list[dict] = []
    media_id_counts = Counter(entry.get("media_id") for entry in media if isinstance(entry, dict))
    resolved_media_paths: list[str] = []
    for entry in media:
        if not isinstance(entry, dict) or not isinstance(entry.get("relative_path"), str):
            continue
        root = audio_root if entry.get("media_type") == "audio" else video_root
        resolved_media_paths.append(str((root / entry["relative_path"]).resolve()).casefold())
    path_counts = Counter((entry.get("media_type"), str(entry.get("relative_path", "")).replace("/", "\\").casefold()) for entry in media if isinstance(entry, dict))
    resolved_path_counts = Counter(resolved_media_paths)
    for path, count in resolved_path_counts.items():
        if count > 1:
            errors.append(f"duplicate resolved media path: {path}")
    hash_counts = Counter(str(entry.get("sha256", "")).casefold() for entry in media if isinstance(entry, dict))
    for entry in media:
        if not isinstance(entry, dict):
            continue
        resolved_path = str(((audio_root if entry.get("media_type") == "audio" else video_root) / str(entry.get("relative_path", ""))).resolve()).casefold()
        if media_id_counts[entry.get("media_id")] != 1 or path_counts[(entry.get("media_type"), str(entry.get("relative_path", "")).replace("/", "\\").casefold())] != 1 or resolved_path_counts[resolved_path] != 1 or hash_counts[str(entry.get("sha256", "")).casefold()] != 1:
            continue
        valid_media.append(entry)
    if sum(entry.get("media_type") == "audio" for entry in valid_media) < 5:
        errors.append("corpus must contain at least five unique audio mixes")
    if sum(entry.get("media_type") == "video" for entry in valid_media) < 10:
        errors.append("corpus must contain at least ten unique videos")
    media_by_id = {entry["media_id"]: entry for entry in valid_media if _is_nonempty_string(entry.get("media_id"))}
    for entry in valid_media:
        media_id, media_type = entry["media_id"], entry.get("media_type")
        root = audio_root if media_type == "audio" else video_root
        relative_path = entry.get("relative_path")
        if not isinstance(relative_path, str):
            continue
        media_path = root / relative_path
        errors.extend(validate_media_path(media_path, root, media_id))
        if not media_path.is_file():
            errors.append(f"{media_id} media file is missing")
            continue
        try:
            observed_duration, observed_stream = _probe_media(media_path, str(media_type))
            errors.extend(validate_media_snapshot(entry, observed_sha256=_sha256_file(media_path), observed_duration_seconds=observed_duration, observed_stream=observed_stream))
        except RuntimeError as error:
            errors.append(f"{media_id} {error}")
    registrations = corpus.get("annotations") if isinstance(corpus.get("annotations"), list) else []
    annotation_root = corpus_path.parent.resolve()
    resolved_annotation_paths = Counter(
        str((annotation_root / record["relative_path"]).resolve()).casefold()
        for record in registrations
        if isinstance(record, dict) and isinstance(record.get("relative_path"), str)
    )
    for path, count in resolved_annotation_paths.items():
        if count > 1:
            errors.append(f"duplicate resolved annotation path: {path}")
    for record in registrations:
        if not isinstance(record, dict) or not _is_nonempty_string(record.get("media_id")) or not _is_nonempty_string(record.get("relative_path")):
            continue
        media_id = record["media_id"]
        annotation_path = annotation_root / record["relative_path"]
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
            continue
        if annotation.get("media_id") != media_id:
            errors.append(f"annotation media_id mismatch for record {media_id}")
        if annotation.get("media_sha256") != source_media.get("sha256"):
            errors.append(f"{media_id} annotation media hash mismatch")
        if annotation.get("annotation_version") != record.get("annotation_version"):
            errors.append(f"{media_id} annotation version mismatch")
        duration = source_media.get("duration_seconds")
        if _is_finite_number(duration):
            errors.extend(validate_annotation(annotation, float(duration)))
    return errors


def _same_root(left: Path, right: Path) -> bool:
    return left.resolve() == right.resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--audio-root", type=Path, default=DEFAULT_AUDIO_ROOT)
    parser.add_argument("--video-root", type=Path, default=DEFAULT_VIDEO_ROOT)
    parser.add_argument("--prior-registration", type=Path)
    parser.add_argument("--strict", action="store_true", help="Require the approved media roots; external registration remains separate.")
    args = parser.parse_args(argv)
    errors: list[str] = []
    if args.strict and not _same_root(args.audio_root, DEFAULT_AUDIO_ROOT):
        errors.append("--audio-root must equal the approved root in strict mode")
    if args.strict and not _same_root(args.video_root, DEFAULT_VIDEO_ROOT):
        errors.append("--video-root must equal the approved root in strict mode")
    errors.extend(validate_corpus(args.corpus, args.audio_root, args.video_root, args.prior_registration))
    if errors:
        print("OBJ-77 ground truth blocked:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("OBJ-77 ground truth validation passed; external registration is still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
