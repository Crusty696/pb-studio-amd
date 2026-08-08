"""
Verdrahtungs-Guard fuer TriggerSettings (Audit 2026-08-05, H-1/H-3/H-4).

Warum es diesen Test gibt
-------------------------
Der WPF-Konstruktoraufruf fuer ``TriggerSettings`` setzte 10 von 13 Feldern.
``ClipLengthVariation``, ``MaxCutInterval`` und ``BeatTriggerMode`` fehlten
einfach — und weil C#-``record`` mit optionalen Parametern arbeitet, warnt der
Compiler nicht. Die Folge: ``beat_trigger_mode`` war Engine-seitig vollstaendig
implementiert (``downbeat_only``/``strong_only``), ueber die Oberflaeche aber
prinzipiell unerreichbar.

Zusaetzlich hatten fuenf Properties (Snare, HiHat, Min/MaxClipLength,
OnsetSensitivity) zwar Werte im ViewModel, aber kein XAML-Element — der User
konnte sie nicht bedienen.

Der Test prueft die komplette Kette pro Feld:
    1. Backend-Schema kennt das Feld
    2. WPF-Record deklariert es
    3. WPF-ViewModel uebergibt es im Konstruktoraufruf
    4. XAML bindet die zugehoerige Property (ausser bewusste Ausnahmen)
    5. Die Pacing-Engine liest es

Lehre aus dem Audit (docs/LOG_AUDIT_2026-08-05.md, Abschnitt 9): Tests, die
ihren eigenen Store befuellen, beweisen keine Verdrahtung. Deshalb prueft dieser
Test die realen Quelldateien.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

SCHEMA_FILE = REPO_ROOT / "backend" / "schemas" / "pacing_schemas.py"
API_CLIENT_FILE = REPO_ROOT / "PBStudio.UI" / "Services" / "ApiClient.cs"
VIEW_MODEL_FILE = (
    REPO_ROOT / "PBStudio.UI" / "ViewModels" / "DirectorViewModel.cs"
)
VIEW_FILE = REPO_ROOT / "PBStudio.UI" / "Views" / "DirectorView.xaml"
ENGINE_FILE = (
    REPO_ROOT / "src" / "pb_studio" / "pacing" / "advanced_pacing_engine.py"
)

# snake_case (Backend) -> PascalCase (WPF)
TRIGGER_FIELDS: dict[str, str] = {
    "beat_weight": "BeatWeight",
    "onset_weight": "OnsetWeight",
    "kick_weight": "KickWeight",
    "snare_weight": "SnareWeight",
    "hihat_weight": "HihatWeight",
    "energy_weight": "EnergyWeight",
    "energy_threshold": "EnergyThreshold",
    "min_clip_length": "MinClipLength",
    "max_clip_length": "MaxClipLength",
    "onset_sensitivity": "OnsetSensitivity",
    "clip_length_variation": "ClipLengthVariation",
    "max_cut_interval": "MaxCutInterval",
    "beat_trigger_mode": "BeatTriggerMode",
}

# Felder, die die Engine bewusst (noch) nicht liest. Jeder Eintrag braucht eine
# Begruendung -- diese Liste ist die ehrliche Buchfuehrung ueber offene Enden,
# nicht ein Freibrief.
ENGINE_READ_EXCEPTIONS: dict[str, str] = {
    # Audit 2026-08-05 (H-2): max_cut_interval hat repo-weit keinen Leser; der
    # Kommentar in pacing_models.py behauptete faelschlich eine Nutzung durch
    # _enforce_clip_lengths. Bis zur Entscheidung (T4) bleibt das Feld
    # durchgereicht, aber wirkungslos -- hier dokumentiert statt verschwiegen.
    "max_cut_interval": "Kein Engine-Leser; Entscheidung T4 offen.",
    # Audit 2026-08-05 (M-6): onset_sensitivity wird von der Stem-Extraktion
    # nicht gelesen (librosa.onset_detect laeuft mit Defaults).
    "onset_sensitivity": "Kein Engine-Leser; Entscheidung T4 offen.",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def sources() -> dict[str, str]:
    return {
        "schema": _read(SCHEMA_FILE),
        "client": _read(API_CLIENT_FILE),
        "view_model": _read(VIEW_MODEL_FILE),
        "view": _read(VIEW_FILE),
        "engine": _read(ENGINE_FILE),
    }


@pytest.fixture(scope="module")
def constructor_call(sources: dict[str, str]) -> str:
    """Extrahiert den `new TriggerSettings(...)`-Aufruf aus dem ViewModel."""
    match = re.search(
        r"new TriggerSettings\((.*?)\n\s*\),",
        sources["view_model"],
        re.DOTALL,
    )
    assert match, (
        "Kein 'new TriggerSettings(...)'-Aufruf in DirectorViewModel.cs "
        "gefunden — der Test kann die Verdrahtung nicht pruefen."
    )
    return match.group(1)


@pytest.mark.parametrize("snake, pascal", sorted(TRIGGER_FIELDS.items()))
def test_field_declared_in_backend_schema(
    snake: str, pascal: str, sources: dict[str, str]
) -> None:
    assert f"{snake}:" in sources["schema"], (
        f"{snake} fehlt in TriggerSettingsSchema — Backend kennt das Feld nicht."
    )


@pytest.mark.parametrize("snake, pascal", sorted(TRIGGER_FIELDS.items()))
def test_field_declared_in_wpf_record(
    snake: str, pascal: str, sources: dict[str, str]
) -> None:
    assert pascal in sources["client"], (
        f"{pascal} fehlt im C#-TriggerSettings-Record."
    )


@pytest.mark.parametrize("snake, pascal", sorted(TRIGGER_FIELDS.items()))
def test_field_is_sent_by_view_model(
    snake: str, pascal: str, constructor_call: str
) -> None:
    """
    Der eigentliche Kern des Audits: ein ausgelassenes Feld nimmt still den
    Record-Default an, ohne dass der Compiler warnt.
    """
    assert f"{pascal}:" in constructor_call, (
        f"{pascal} wird im 'new TriggerSettings(...)'-Aufruf nicht gesetzt. "
        f"Der C#-Record-Default gewinnt dann still — genau der Fehler, den "
        f"Audit 2026-08-05 (H-1) fuer ClipLengthVariation, MaxCutInterval und "
        f"BeatTriggerMode gefunden hat."
    )


@pytest.mark.parametrize("snake, pascal", sorted(TRIGGER_FIELDS.items()))
def test_field_is_bindable_in_xaml(
    snake: str, pascal: str, sources: dict[str, str]
) -> None:
    """
    Der letzte Meter: ein Wert, den die UI nicht anbietet, ist fuer den User
    nicht existent. Im Projekt bereits mehrfach aufgetreten.
    """
    assert f"Binding {pascal}" in sources["view"], (
        f"{pascal} hat kein XAML-Binding in DirectorView.xaml — der Regler ist "
        f"fuer den User unbedienbar und bleibt konstant auf seinem Default."
    )


@pytest.mark.parametrize("snake, pascal", sorted(TRIGGER_FIELDS.items()))
def test_field_has_engine_reader(
    snake: str, pascal: str, sources: dict[str, str]
) -> None:
    if snake in ENGINE_READ_EXCEPTIONS:
        pytest.skip(
            f"{snake}: bewusst ohne Engine-Leser — "
            f"{ENGINE_READ_EXCEPTIONS[snake]}"
        )
    assert snake in sources["engine"], (
        f"{snake} wird von advanced_pacing_engine.py nicht gelesen. Entweder "
        f"verdrahten oder in ENGINE_READ_EXCEPTIONS mit Begruendung eintragen."
    )
