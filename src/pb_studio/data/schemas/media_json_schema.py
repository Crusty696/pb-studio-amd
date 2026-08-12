"""C4-Fix (S-C1, 2026-05-19): Versioned schema for SQLite JSON-blob columns.

Vor diesem Modul wurden `media.metadata_json` und `media.ai_data_json` als
freie dict ohne Schema-Versionierung geschrieben. Folge: Schema-Drift
unsichtbar — neue Felder (audio_hash L-N2, video_hash L-VIDEO-3,
stems_paths L-AUDIO-8, embedding_dim L-M8) erscheinen ohne Migration,
alte Rows haben sie nicht, code-defensive `.get()` ueberall.

Mit `__schema_version` in jeder Blob-Spalte und einer `migrate_*`-Kette
ist Roll-Forward moeglich: beim Lesen wird die Blob-Version geprueft und
ggf. on-the-fly migriert.

API:
    from pb_studio.data.schemas.media_json_schema import (
        CURRENT_SCHEMA_VERSION,
        migrate_audio_metadata, migrate_audio_ai_data,
        migrate_video_metadata, migrate_video_ai_data,
        bump_schema, has_schema_version,
    )

    raw = json.loads(row["ai_data_json"])
    migrated = migrate_audio_ai_data(raw)   # garantiert __schema_version = CURRENT
    repo.update_status(..., ai_data=migrated)
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any, Callable

from pb_studio.core.stage_receipts import (
    RECEIPT_VERSION,
    canonical_sha256,
    derive_analysis_status,
    project_legacy_stage_receipts,
    receipt_to_dict,
    transition_stage_receipt,
    validate_receipt_artifact,
    validate_receipt_map,
)

# Aktuelle Schema-Version. Bei Neuanlegen eines Feldes:
# 1. CURRENT_SCHEMA_VERSION inkrementieren
# 2. migrate_{audio,video}_{metadata,ai_data}_v{X-1}_to_v{X} schreiben
# 3. unten in der MIGRATION_CHAIN registrieren
CURRENT_SCHEMA_VERSION = 2

SCHEMA_VERSION_KEY = "__schema_version"


def has_schema_version(blob: dict[str, Any]) -> bool:
    """True wenn blob ein __schema_version-Feld trägt."""
    return isinstance(blob, dict) and SCHEMA_VERSION_KEY in blob


def bump_schema(blob: dict[str, Any], version: int = CURRENT_SCHEMA_VERSION) -> dict[str, Any]:
    """Setzt __schema_version. Mutates IN-PLACE und gibt blob zurueck."""
    blob[SCHEMA_VERSION_KEY] = version
    return blob


def _migrate_with_chain(
    blob: dict[str, Any],
    chain: dict[int, Callable[[dict[str, Any]], dict[str, Any]]],
) -> dict[str, Any]:
    """Wendet Migrationen v{X} -> v{X+1} sequenziell an bis CURRENT erreicht.

    Args:
        blob: JSON-dict (kann __schema_version haben oder nicht — vor v1 = legacy).
        chain: dict von source-version -> migrate-callable. Callable empfaengt
               blob in version X, gibt blob in version X+1 zurueck.

    Returns:
        Migrated blob mit __schema_version = CURRENT_SCHEMA_VERSION.
    """
    if not isinstance(blob, dict):
        return bump_schema({}, CURRENT_SCHEMA_VERSION)

    # Reading a row is a projection operation.  Keep the source object (and
    # nested legacy payloads) byte-for-byte untouched until a caller performs
    # an explicit persistence write.
    blob = deepcopy(blob)

    # Legacy-Blob (kein __schema_version) -> als v0 behandeln
    current_v = blob.get(SCHEMA_VERSION_KEY, 0)
    if not isinstance(current_v, int):
        current_v = 0

    while current_v < CURRENT_SCHEMA_VERSION:
        migrator = chain.get(current_v)
        if migrator is None:
            # Keine Migration registriert — als v_target markieren und stoppen
            break
        blob = migrator(blob)
        current_v += 1

    bump_schema(blob, CURRENT_SCHEMA_VERSION)
    return blob


# -------------------------------------------------------------------------
# Audio Metadata + AI-Data
# -------------------------------------------------------------------------

def _v0_to_v1_audio_metadata(blob: dict[str, Any]) -> dict[str, Any]:
    """Legacy -> v1: Defaults fuer audio_hash + stems_paths.

    Legacy-Schema (vor 2026-05-11): kein audio_hash, kein stems_paths.
    L-N2 + L-AUDIO-8 haben sie eingefuehrt aber Migration unterlassen.
    """
    blob.setdefault("audio_hash", "")
    blob.setdefault("stems_paths", {})
    return blob


def _v0_to_v1_audio_ai_data(blob: dict[str, Any]) -> dict[str, Any]:
    """Legacy -> v1: Defaults fuer subtrack_segments, tempo_curve, spectral_data."""
    blob.setdefault("subtrack_segments", [])
    blob.setdefault("tempo_curve", [])
    blob.setdefault("spectral_data", {})
    return blob


def _v1_to_v2_metadata(blob: dict[str, Any]) -> dict[str, Any]:
    """v2 adds no metadata fields; keep the chain explicit and idempotent."""

    return blob


def _ensure_stage_receipts(blob: dict[str, Any]) -> dict[str, Any]:
    if "stage_receipts" in blob:
        return blob
    stage_status = blob.get("stage_status")
    stage_errors = blob.get("stage_errors")
    if not isinstance(stage_status, dict):
        blob["stage_receipts"] = {}
        return blob
    projected = project_legacy_stage_receipts(
        stage_status=stage_status,
        stage_errors=stage_errors if isinstance(stage_errors, dict) else None,
    )
    blob["stage_receipts"] = {
        stage_id: receipt_to_dict(receipt)
        for stage_id, receipt in projected.items()
    }
    return blob


def _v1_to_v2_audio_ai_data(blob: dict[str, Any]) -> dict[str, Any]:
    """Return-only V0 receipt projection for legacy audio stage truth."""

    return _ensure_stage_receipts(blob)


AUDIO_METADATA_CHAIN = {
    0: _v0_to_v1_audio_metadata,
    1: _v1_to_v2_metadata,
}

AUDIO_AI_DATA_CHAIN = {
    0: _v0_to_v1_audio_ai_data,
    1: _v1_to_v2_audio_ai_data,
}


def migrate_audio_metadata(blob: dict[str, Any]) -> dict[str, Any]:
    return _migrate_with_chain(blob, AUDIO_METADATA_CHAIN)


def migrate_audio_ai_data(blob: dict[str, Any]) -> dict[str, Any]:
    return _ensure_stage_receipts(_migrate_with_chain(blob, AUDIO_AI_DATA_CHAIN))


# -------------------------------------------------------------------------
# Video Metadata + AI-Data
# -------------------------------------------------------------------------

def _v0_to_v1_video_metadata(blob: dict[str, Any]) -> dict[str, Any]:
    """Legacy -> v1: Defaults fuer video_hash, thumbnail_path."""
    blob.setdefault("video_hash", "")
    blob.setdefault("thumbnail_path", "")
    return blob


def _v0_to_v1_video_ai_data(blob: dict[str, Any]) -> dict[str, Any]:
    """
    Legacy -> v1: Defaults fuer Tags, Farben und Embedding-Metadaten.

    Audit 2026-08-05 (H-1/T5): Sieben Defaults sind hier entfernt worden.

    Fuenf Felder hatten weder einen Producer noch einen Consumer — verifiziert
    per repo-weitem Grep (0 Schreibstellen, 0 Lesestellen) und empirisch: in
    1359 analysierten Rows waren sie 1359-mal vorhanden und 0-mal gefuellt.
    Ein Audit vom 2026-05-11 (L-VIDEO-4) hatte bereits gefordert, sie entweder
    zu verdrahten oder zu entfernen; verdrahtet wurden damals nur ``mood_tags``
    und die ``avg_*``-Felder:
        brightness_curve, saturation_curve, color_temp_curve,
        style_tags, object_tags

    Dazu ``motion_curve``: dieser Default war aktiv schaedlich. Der echte Wert
    liegt verschachtelt unter ``motion.motion_curve``; der Brain-Adapter hatte
    einen Fallback darauf, prueft aber mit ``is None`` — und ein
    Migrations-Default ``[]`` ist nicht None. Der Fallback griff deshalb NIE,
    und das Brain sah bei allen Clips leere Motion-Kurven, obwohl die Daten
    danebenlagen. Die Truthiness-Pruefung im Adapter ist gefixt (T2.5); ohne
    diesen Default gibt es das irrefuehrende Duplikat gar nicht mehr.

    ``mood_tags`` bleibt: seit dem 2026-07-10 gibt es dafuer einen echten
    Producer (``compute_color_features``).
    """
    blob.setdefault("mood_tags", [])
    blob.setdefault("dominant_colors", [])
    blob.setdefault("embedding_dim", 0)
    blob.setdefault("embedding_samples", 0)
    blob.setdefault("has_embedding", False)
    return blob


def _v1_to_v2_video_ai_data(blob: dict[str, Any]) -> dict[str, Any]:
    """Return-only V0 receipt projection for legacy video stage truth."""

    return _ensure_stage_receipts(blob)


VIDEO_METADATA_CHAIN = {
    0: _v0_to_v1_video_metadata,
    1: _v1_to_v2_metadata,
}

VIDEO_AI_DATA_CHAIN = {
    0: _v0_to_v1_video_ai_data,
    1: _v1_to_v2_video_ai_data,
}


def migrate_video_metadata(blob: dict[str, Any]) -> dict[str, Any]:
    return _migrate_with_chain(blob, VIDEO_METADATA_CHAIN)


def migrate_video_ai_data(blob: dict[str, Any]) -> dict[str, Any]:
    return _ensure_stage_receipts(_migrate_with_chain(blob, VIDEO_AI_DATA_CHAIN))


_AUDIO_STAGE_ARTIFACT_REFS = {
    "beats": "ai_data_json.beats_json",
    "structure": "ai_data_json.structure_segments",
    "spectral": "ai_data_json.spectral_data",
    "key": "ai_data_json.key",
}

_AUDIO_STAGE_FIELDS = {
    "beats": (
        "bpm",
        "beat_count",
        "beats_json",
        "energy_curve",
        "downbeats",
        "downbeat_provenance",
        "onset_times",
        "kick_times",
        "snare_times",
        "hihat_times",
        "chunk_evidence",
    ),
    "structure": ("structure_segments",),
    "spectral": ("spectral_data",),
    "key": ("key",),
}

_VIDEO_STAGE_FIELDS = {
    "scenes": ("scene_count", "scenes"),
    "motion": ("avg_motion", "motion"),
    "embedding": ("embedding_dim", "embedding_samples", "has_embedding"),
    "colors": (
        "dominant_colors",
        "mood_tags",
        "avg_brightness",
        "avg_saturation",
        "avg_color_temp",
    ),
    "captions": ("tags", "tag_source"),
    "audio_key": ("audio_key",),
}


def _video_canonical_stage_artifact(
    stage_id: str,
    blob: dict[str, Any],
) -> dict[str, Any] | None:
    fields = _VIDEO_STAGE_FIELDS.get(stage_id)
    if fields is None or any(field not in blob for field in fields):
        return None
    artifact = {field: deepcopy(blob[field]) for field in fields}
    if stage_id == "embedding":
        stage_artifacts = blob.get("stage_artifacts")
        locator = (
            stage_artifacts.get("embedding")
            if isinstance(stage_artifacts, dict)
            else None
        )
        if not isinstance(locator, dict):
            return None
        artifact.update(
            {
                "store": "faiss_cpu",
                "media_id": locator.get("media_id"),
                "faiss_id": locator.get("faiss_id"),
                "media_sha256": blob.get("media_sha256"),
            }
        )
    return artifact


def _completed_artifact_is_valid(
    stage_id: str,
    receipt,
    blob: dict[str, Any],
    *,
    is_video: bool,
) -> bool:
    if not validate_receipt_artifact(receipt, blob):
        return False

    if not is_video:
        expected_ref = _AUDIO_STAGE_ARTIFACT_REFS.get(stage_id)
        return expected_ref is None or receipt.artifact_ref == expected_ref

    if stage_id not in _VIDEO_STAGE_FIELDS:
        return True
    expected_ref = f"ai_data_json.stage_artifacts.{stage_id}"
    if receipt.artifact_ref != expected_ref:
        return False
    stage_artifacts = blob.get("stage_artifacts")
    persisted = (
        stage_artifacts.get(stage_id)
        if isinstance(stage_artifacts, dict)
        else None
    )
    canonical = _video_canonical_stage_artifact(stage_id, blob)
    if not isinstance(persisted, dict) or canonical is None:
        return False
    return (
        canonical_sha256(persisted) == receipt.artifact_sha256
        and canonical_sha256(canonical) == receipt.artifact_sha256
    )


def _quarantine_stage_payload(
    blob: dict[str, Any],
    stage_id: str,
    *,
    is_video: bool,
) -> None:
    """Remove only one invalid stage's canonical persisted payload."""

    fields = (
        _VIDEO_STAGE_FIELDS.get(stage_id, ())
        if is_video
        else _AUDIO_STAGE_FIELDS.get(stage_id, ())
    )
    for field in fields:
        blob.pop(field, None)

    stage_artifacts = blob.get("stage_artifacts")
    if isinstance(stage_artifacts, dict) and stage_id in stage_artifacts:
        retained = dict(stage_artifacts)
        retained.pop(stage_id, None)
        blob["stage_artifacts"] = retained


def normalize_analysis_ai_data(
    blob: dict[str, Any],
    *,
    is_video: bool,
    recovered_at_utc: str,
) -> tuple[dict[str, Any], bool]:
    """Return startup-safe analysis truth without mutating ``blob``.

    V1 requested stages left ``running`` by a dead backend are terminalized as
    ``interrupted``. Completed V1 receipts are accepted only when their
    persisted artifact still matches the receipt hash and, for known video
    stages, the canonical top-level fields. Legacy V0 and unrequested receipts
    remain unchanged.
    """

    if not isinstance(blob, dict):
        raise TypeError("analysis ai_data_json must decode to an object")
    migrated = (
        migrate_video_ai_data(blob)
        if is_video
        else migrate_audio_ai_data(blob)
    )
    raw_receipts = migrated.get("stage_receipts")
    if not isinstance(raw_receipts, dict):
        raise TypeError("stage_receipts must be an object")
    receipts = validate_receipt_map(raw_receipts)

    if not receipts:
        normalized = dict(migrated)
        legacy_status = str(normalized.get("analysis_status") or "").strip().lower()
        if legacy_status not in {
            "unavailable",
            "running",
            "completed",
            "partial",
            "failed",
        }:
            legacy_status = (
                "completed" if bool(normalized.get("is_analyzed")) else "unavailable"
            )
        normalized["analysis_status"] = legacy_status
        normalized["stage_status"] = (
            dict(normalized["stage_status"])
            if isinstance(normalized.get("stage_status"), dict)
            else {}
        )
        normalized["stage_errors"] = (
            dict(normalized["stage_errors"])
            if isinstance(normalized.get("stage_errors"), dict)
            else {}
        )
        normalized["is_analyzed"] = legacy_status == "completed"
        return normalized, normalized != blob

    recovered = {}
    for stage_id, receipt in receipts.items():
        next_receipt = receipt
        if (
            receipt.receipt_version == RECEIPT_VERSION
            and receipt.requested
            and receipt.status == "running"
        ):
            next_receipt = transition_stage_receipt(
                receipt,
                "interrupted",
                error_code="startup_interrupted",
                error_message="Analysis interrupted by backend restart",
                timestamp_utc=recovered_at_utc,
            )
        elif (
            receipt.receipt_version != RECEIPT_VERSION
            and receipt.requested
            and receipt.status == "running"
        ):
            next_receipt = project_legacy_stage_receipts(
                stage_status={stage_id: "interrupted"},
                stage_errors={
                    stage_id: "Analysis interrupted by backend restart"
                },
            )[stage_id]
        elif (
            receipt.artifact_valid is True
            and not _completed_artifact_is_valid(
                stage_id,
                receipt,
                migrated,
                is_video=is_video,
            )
        ):
            _quarantine_stage_payload(
                migrated,
                stage_id,
                is_video=is_video,
            )
            if receipt.receipt_version == RECEIPT_VERSION and not receipt.requested:
                next_receipt = replace(
                    receipt,
                    status="unavailable",
                    artifact_valid=False,
                    finished_at_utc=recovered_at_utc,
                    error_code="artifact_invalid",
                    error_message=(
                        f"Persisted artifact for stage {stage_id} failed validation"
                    ),
                )
            else:
                next_receipt = replace(
                    receipt,
                    status="failed",
                    artifact_valid=False,
                    finished_at_utc=recovered_at_utc,
                    error_code="artifact_invalid",
                    error_message=(
                        f"Persisted artifact for stage {stage_id} failed validation"
                    ),
                )
        recovered[stage_id] = next_receipt

    normalized = dict(migrated)
    normalized["stage_receipts"] = {
        stage_id: receipt_to_dict(receipt)
        for stage_id, receipt in recovered.items()
    }
    normalized["analysis_status"] = derive_analysis_status(recovered)
    normalized["stage_status"] = {
        stage_id: receipt.status
        for stage_id, receipt in recovered.items()
    }
    normalized["stage_errors"] = {
        stage_id: receipt.error_message
        for stage_id, receipt in recovered.items()
        if receipt.error_message
    }
    normalized["is_analyzed"] = normalized["analysis_status"] == "completed"
    return normalized, normalized != blob
