"""Regression-Test fuer S-C1 (Audit 2026-05-19):
metadata_json + ai_data_json hatten kein versioniertes Schema. Neue Felder
(audio_hash, video_hash, stems_paths, embedding_dim) erschienen ohne Migration.

Fix: media_json_schema.py mit __schema_version + migrate_*-Kette.
"""
from __future__ import annotations

from pb_studio.data.schemas.media_json_schema import (
    CURRENT_SCHEMA_VERSION,
    SCHEMA_VERSION_KEY,
    bump_schema,
    has_schema_version,
    migrate_audio_ai_data,
    migrate_audio_metadata,
    migrate_video_ai_data,
    migrate_video_metadata,
)


def test_legacy_audio_metadata_gets_default_fields():
    """Legacy-Blob ohne __schema_version: audio_hash + stems_paths werden befuellt."""
    legacy = {"path": "test.wav", "duration": 60.0}
    migrated = migrate_audio_metadata(legacy)
    assert migrated["audio_hash"] == ""
    assert migrated["stems_paths"] == {}
    assert migrated["path"] == "test.wav"  # Original-Felder erhalten
    assert migrated[SCHEMA_VERSION_KEY] == CURRENT_SCHEMA_VERSION


def test_legacy_audio_ai_data_gets_default_fields():
    """Legacy-Blob: subtrack_segments + tempo_curve + spectral_data werden befuellt."""
    legacy = {"bpm": 128.0, "key": "C major"}
    migrated = migrate_audio_ai_data(legacy)
    assert migrated["subtrack_segments"] == []
    assert migrated["tempo_curve"] == []
    assert migrated["spectral_data"] == {}
    assert migrated["bpm"] == 128.0
    assert migrated[SCHEMA_VERSION_KEY] == CURRENT_SCHEMA_VERSION


def test_legacy_video_metadata_gets_default_fields():
    legacy = {"path": "test.mp4", "duration": 30.0}
    migrated = migrate_video_metadata(legacy)
    assert migrated["video_hash"] == ""
    assert migrated["thumbnail_path"] == ""
    assert migrated[SCHEMA_VERSION_KEY] == CURRENT_SCHEMA_VERSION


def test_legacy_video_ai_data_gets_default_fields():
    legacy = {"scene_count": 5}
    migrated = migrate_video_ai_data(legacy)
    assert migrated["mood_tags"] == []
    assert migrated["dominant_colors"] == []
    assert migrated["embedding_dim"] == 0
    assert migrated["embedding_samples"] == 0
    assert migrated["has_embedding"] is False
    assert migrated[SCHEMA_VERSION_KEY] == CURRENT_SCHEMA_VERSION


def test_legacy_video_ai_data_has_no_producerless_defaults():
    """
    Audit 2026-08-05 (H-1/T5): Diese Felder duerfen nicht mehr als Default
    angelegt werden.

    Fuenf davon hatten weder Producer noch Consumer — empirisch in 1359
    analysierten Rows 1359-mal vorhanden und 0-mal gefuellt. Ein Default ohne
    Producer ist eine Luege: Code, der mit ``.get(feld, [])`` prueft, sieht
    einen vorhandenen Key und haelt die Praesenz fuer aussagekraeftig.

    ``motion_curve`` war der schaedlichste Fall: der echte Wert liegt
    verschachtelt unter ``motion.motion_curve``, und der ``is None``-Fallback im
    Brain-Adapter griff wegen des ``[]``-Defaults nie — das Brain sah dauerhaft
    leere Motion-Kurven.
    """
    migrated = migrate_video_ai_data({"scene_count": 5})
    for field in (
        "brightness_curve",
        "saturation_curve",
        "color_temp_curve",
        "style_tags",
        "object_tags",
        "motion_curve",
    ):
        assert field not in migrated, (
            f"{field} wird wieder als Migrations-Default angelegt, obwohl es "
            f"keinen Producer hat. Entweder verdrahten oder Default weglassen."
        )


def test_already_current_version_no_double_migration():
    """Blob mit aktueller Version sollte nicht doppelt migriert werden."""
    blob = {"audio_hash": "abc123", "stems_paths": {"vocals": "v.wav"}}
    bump_schema(blob, CURRENT_SCHEMA_VERSION)
    pre_migrate_audio_hash = blob["audio_hash"]
    migrated = migrate_audio_metadata(blob)
    assert migrated["audio_hash"] == pre_migrate_audio_hash, \
        "Migration darf existierende Werte NICHT ueberschreiben"
    assert migrated[SCHEMA_VERSION_KEY] == CURRENT_SCHEMA_VERSION


def test_has_schema_version():
    assert has_schema_version({SCHEMA_VERSION_KEY: 1, "x": 1}) is True
    assert has_schema_version({"x": 1}) is False
    assert has_schema_version(None) is False  # type: ignore
    assert has_schema_version("not-a-dict") is False  # type: ignore


def test_non_dict_blob_returns_empty_schemaed_dict():
    """Defensive: blob ist None oder string -> empty dict mit __schema_version."""
    assert migrate_audio_metadata(None)[SCHEMA_VERSION_KEY] == CURRENT_SCHEMA_VERSION  # type: ignore
    assert migrate_video_ai_data("garbage")[SCHEMA_VERSION_KEY] == CURRENT_SCHEMA_VERSION  # type: ignore


def test_partial_legacy_blob_keeps_existing_audio_hash():
    """Wenn audio_hash schon gesetzt, soll Migration ihn NICHT auf '' ueberschreiben."""
    blob = {"audio_hash": "sha256:xyz", "path": "old.wav"}
    migrated = migrate_audio_metadata(blob)
    assert migrated["audio_hash"] == "sha256:xyz", \
        "setdefault muss existierende Werte respektieren"
    assert migrated["stems_paths"] == {}, "Fehlende Felder defaulten"
