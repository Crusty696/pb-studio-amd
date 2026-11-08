"""Offline T002 manifest checks; this does not attest the underlying evidence."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SPLITS = ("development", "validation", "holdout")


@dataclass(frozen=True)
class ManifestAssessment:
    structurally_valid: bool
    qualification_ready: bool
    reasons: tuple[str, ...]


def assess_manifest(manifest: Mapping[str, Any]) -> ManifestAssessment:
    """Check split integrity and reject a qualification claim without prerequisites.

    V1 has no trusted evidence verifier, so readiness always fails closed.
    Structural validity cannot prove labels, independence or runtime quality.
    """
    structural: set[str] = set()
    missing: set[str] = set()
    sources = manifest.get("sources")
    split_lists = manifest.get("splits")
    if manifest.get("schema_version") != 1 or not isinstance(sources, list) or not isinstance(split_lists, dict):
        return ManifestAssessment(False, False, ("invalid_manifest_shape",))

    ids: set[str] = set()
    family_splits: dict[str, set[str]] = {}
    for source in sources:
        if not isinstance(source, dict):
            structural.add("invalid_source")
            continue
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            structural.add("invalid_source_id")
        elif source_id in ids:
            structural.add("duplicate_source_id")
        else:
            ids.add(source_id)
        source_hash = source.get("sha256")
        if not isinstance(source_hash, str) or not _SHA256.fullmatch(source_hash):
            structural.add("invalid_sha256")
        family = source.get("source_family_id")
        split = source.get("split")
        if not isinstance(family, str) or not family or split not in _SPLITS:
            structural.add("invalid_family_or_split")
        else:
            family_splits.setdefault(family, set()).add(split)

    listed: dict[str, str] = {}
    for split in _SPLITS:
        members = split_lists.get(split)
        if not isinstance(members, list):
            structural.add("invalid_split_list")
            continue
        for source_id in members:
            if not isinstance(source_id, str) or source_id not in ids or source_id in listed:
                structural.add("split_mismatch")
            else:
                listed[source_id] = split
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_id = source.get("source_id")
        if isinstance(source_id, str) and listed.get(source_id) != source.get("split"):
            structural.add("split_mismatch")
    if any(len(splits) > 1 for splits in family_splits.values()):
        structural.add("family_crosses_splits")

    holdout = split_lists.get("holdout")
    if not holdout:
        missing.add("holdout_missing")
    if not manifest.get("labels"):
        missing.add("labels_missing")
    if not manifest.get("profiles"):
        missing.add("profiles_missing")
    if not manifest.get("measurements"):
        missing.add("measurements_missing")

    holdout_sources = [s for s in sources if isinstance(s, dict) and s.get("split") == "holdout"]
    if holdout_sources and any(
        not s.get("independent_label_receipt")
        or s.get("split_qualification") != "qualified_independent_holdout"
        or s.get("family_status") != "confirmed_independent"
        or s.get("prior_exposure") != "confirmed_unexposed"
        for s in holdout_sources
    ):
        missing.add("holdout_independence_unproven")

    profiles = manifest.get("profiles")
    if profiles and (not isinstance(profiles, list) or any(
        not isinstance(profile, dict)
        or profile.get("qualified") is not True
        or not isinstance(profile.get("approved_thresholds"), dict)
        or not profile["approved_thresholds"]
        or not profile.get("reference_revision")
        for profile in profiles
    )):
        missing.add("profile_qualification_unproven")
    measurements = manifest.get("measurements")
    if measurements and (not isinstance(measurements, list) or any(
        not isinstance(item, dict) or not item.get("cache_mode") or not item.get("quality_result")
        for item in measurements
    )):
        missing.add("measurement_evidence_incomplete")

    # This module has no trusted receipt verifier or source/media attestation.
    # Even a syntactically complete v1 manifest cannot authorize qualification.
    if not missing:
        missing.add("external_evidence_unverified")
    ready = False
    if manifest.get("status") == "QUALIFIED" and not ready:
        structural.add("unsupported_qualification_claim")
    return ManifestAssessment(not structural, ready, tuple(sorted(structural | missing)))
