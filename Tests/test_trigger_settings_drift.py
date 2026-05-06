"""Drift-Test: TriggerSettings dataclass <-> TriggerSettingsSchema.

Plan Phase 0 #4 + #3. Stellt sicher dass:
1. Alle Felder in beiden Klassen identisch (Drift-Check).
2. from_dict akzeptiert alle Felder ohne Datenverlust.
"""

from __future__ import annotations

from dataclasses import asdict, fields

from backend.schemas.pacing_schemas import TriggerSettingsSchema
from pb_studio.pacing.pacing_models import TriggerSettings


def test_field_sets_match():
    dc_fields = {f.name for f in fields(TriggerSettings)}
    schema_fields = set(TriggerSettingsSchema.model_fields.keys())
    assert dc_fields == schema_fields, (
        f"Drift: only_dc={dc_fields - schema_fields}, "
        f"only_schema={schema_fields - dc_fields}"
    )


def test_from_dict_full_roundtrip():
    payload = {
        "beat_weight": 1.5,
        "onset_weight": 0.7,
        "kick_weight": 1.0,
        "snare_weight": 0.8,
        "hihat_weight": 0.4,
        "energy_weight": 0.9,
        "energy_threshold": 0.5,
        "min_clip_length": 0.5,
        "max_clip_length": 6.0,
        "onset_sensitivity": 0.6,
        "clip_length_variation": 0.2,
        "min_cut_interval": 0.4,
        "max_cut_interval": 8.0,
        "beat_trigger_mode": "downbeat_only",
    }
    settings = TriggerSettings.from_dict(payload)
    assert asdict(settings) == payload


def test_schema_accepts_full_payload():
    payload = {
        "beat_weight": 1.5,
        "onset_weight": 0.7,
        "kick_weight": 1.0,
        "snare_weight": 0.8,
        "hihat_weight": 0.4,
        "energy_weight": 0.9,
        "energy_threshold": 0.5,
        "min_clip_length": 0.5,
        "max_clip_length": 6.0,
        "onset_sensitivity": 0.6,
        "clip_length_variation": 0.2,
        "min_cut_interval": 0.4,
        "max_cut_interval": 8.0,
        "beat_trigger_mode": "downbeat_only",
    }
    schema = TriggerSettingsSchema(**payload)
    assert schema.model_dump() == payload
