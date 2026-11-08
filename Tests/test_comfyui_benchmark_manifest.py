"""T002 benchmark preparation must not silently become a quality pass."""

from copy import deepcopy
import json
from pathlib import Path

from pb_studio.providers.benchmark_manifest import assess_manifest


MANIFEST = Path(__file__).resolve().parents[1] / "specs/00037-comfyui-control-center/reference-manifest.json"


def current_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_current_regression_manifest_is_consistent_but_not_qualified():
    result = assess_manifest(current_manifest())
    assert result.structurally_valid
    assert not result.qualification_ready
    assert {"holdout_missing", "labels_missing", "profiles_missing", "measurements_missing"} <= set(result.reasons)


def test_split_lists_must_match_source_split_and_be_unique():
    manifest = current_manifest()
    manifest["splits"]["holdout"].append("V01")
    result = assess_manifest(manifest)
    assert not result.structurally_valid
    assert "split_mismatch" in result.reasons


def test_related_audio_family_cannot_cross_splits():
    manifest = current_manifest()
    manifest["splits"]["development"].remove("A03")
    manifest["splits"]["holdout"].append("A03")
    next(source for source in manifest["sources"] if source["source_id"] == "A03")["split"] = "holdout"
    result = assess_manifest(manifest)
    assert not result.structurally_valid
    assert "family_crosses_splits" in result.reasons


def test_claimed_qualification_with_missing_evidence_is_invalid():
    manifest = current_manifest()
    manifest["status"] = "QUALIFIED"
    result = assess_manifest(manifest)
    assert not result.structurally_valid
    assert not result.qualification_ready
    assert "unsupported_qualification_claim" in result.reasons


def test_duplicate_ids_and_invalid_hashes_are_rejected():
    manifest = current_manifest()
    duplicate = deepcopy(manifest["sources"][0])
    duplicate["sha256"] = "invalid"
    manifest["sources"].append(duplicate)
    result = assess_manifest(manifest)
    assert not result.structurally_valid
    assert {"duplicate_source_id", "invalid_sha256"} <= set(result.reasons)


def test_non_empty_placeholder_evidence_cannot_qualify():
    manifest = current_manifest()
    manifest["labels"] = [{"source_id": "V01"}]
    manifest["profiles"] = [{"qualified": True, "approved_thresholds": {"f1": 0.8}}]
    manifest["measurements"] = [{"quality_result": "PASS"}]
    result = assess_manifest(manifest)
    assert not result.qualification_ready
    assert {"holdout_missing", "profile_qualification_unproven", "measurement_evidence_incomplete"} <= set(result.reasons)


def test_malformed_split_member_returns_issue_instead_of_crashing():
    manifest = current_manifest()
    manifest["splits"]["development"].append(["V01"])
    result = assess_manifest(manifest)
    assert not result.structurally_valid
    assert "split_mismatch" in result.reasons


def test_malformed_source_id_returns_issue_instead_of_crashing():
    manifest = current_manifest()
    manifest["sources"][0]["source_id"] = ["V01"]
    result = assess_manifest(manifest)
    assert not result.structurally_valid
    assert "invalid_source_id" in result.reasons


def test_plausible_receipt_strings_are_not_evidence_authentication():
    manifest = current_manifest()
    manifest["splits"]["development"].remove("V01")
    manifest["splits"]["holdout"].append("V01")
    source = manifest["sources"][0]
    source.update(split="holdout", split_qualification="qualified_independent_holdout",
                  family_status="confirmed_independent", prior_exposure="confirmed_unexposed",
                  independent_label_receipt="some-path#V01")
    manifest["labels"] = [{"source_id": "V01", "receipt": "some-path#V01"}]
    manifest["profiles"] = [{"qualified": True, "approved_thresholds": {"f1": 0.8},
                             "reference_revision": "v1"}]
    manifest["measurements"] = [{"cache_mode": "fresh-warm", "quality_result": "PASS"}]
    result = assess_manifest(manifest)
    assert result.structurally_valid
    assert not result.qualification_ready
    assert "external_evidence_unverified" in result.reasons
