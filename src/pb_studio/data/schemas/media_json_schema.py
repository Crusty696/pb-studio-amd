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

from typing import Any, Callable

# Aktuelle Schema-Version. Bei Neuanlegen eines Feldes:
# 1. CURRENT_SCHEMA_VERSION inkrementieren
# 2. migrate_{audio,video}_{metadata,ai_data}_v{X-1}_to_v{X} schreiben
# 3. unten in der MIGRATION_CHAIN registrieren
CURRENT_SCHEMA_VERSION = 1

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


AUDIO_METADATA_CHAIN = {
    0: _v0_to_v1_audio_metadata,
}

AUDIO_AI_DATA_CHAIN = {
    0: _v0_to_v1_audio_ai_data,
}


def migrate_audio_metadata(blob: dict[str, Any]) -> dict[str, Any]:
    return _migrate_with_chain(blob, AUDIO_METADATA_CHAIN)


def migrate_audio_ai_data(blob: dict[str, Any]) -> dict[str, Any]:
    return _migrate_with_chain(blob, AUDIO_AI_DATA_CHAIN)


# -------------------------------------------------------------------------
# Video Metadata + AI-Data
# -------------------------------------------------------------------------

def _v0_to_v1_video_metadata(blob: dict[str, Any]) -> dict[str, Any]:
    """Legacy -> v1: Defaults fuer video_hash, thumbnail_path."""
    blob.setdefault("video_hash", "")
    blob.setdefault("thumbnail_path", "")
    return blob


def _v0_to_v1_video_ai_data(blob: dict[str, Any]) -> dict[str, Any]:
    """Legacy -> v1: Defaults fuer Per-Frame-Curves + Tags + Embedding-Dim."""
    blob.setdefault("brightness_curve", [])
    blob.setdefault("saturation_curve", [])
    blob.setdefault("color_temp_curve", [])
    blob.setdefault("motion_curve", [])
    blob.setdefault("mood_tags", [])
    blob.setdefault("style_tags", [])
    blob.setdefault("object_tags", [])
    blob.setdefault("dominant_colors", [])
    blob.setdefault("embedding_dim", 0)
    blob.setdefault("embedding_samples", 0)
    blob.setdefault("has_embedding", False)
    return blob


VIDEO_METADATA_CHAIN = {
    0: _v0_to_v1_video_metadata,
}

VIDEO_AI_DATA_CHAIN = {
    0: _v0_to_v1_video_ai_data,
}


def migrate_video_metadata(blob: dict[str, Any]) -> dict[str, Any]:
    return _migrate_with_chain(blob, VIDEO_METADATA_CHAIN)


def migrate_video_ai_data(blob: dict[str, Any]) -> dict[str, Any]:
    return _migrate_with_chain(blob, VIDEO_AI_DATA_CHAIN)
