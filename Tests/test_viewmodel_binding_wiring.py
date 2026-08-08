"""
Binding-Guard fuer WPF-ViewModel-Properties (Audit 2026-08-05, T3b.2).

Warum es diesen Test gibt
-------------------------
Im Projekt ist dreimal derselbe Fehler passiert: eine ``[ObservableProperty]``
wurde im ViewModel gesetzt, aber von keinem XAML-Element gebunden. Der Wert
reiste bis zur UI und versickerte dort. Dokumentiert im CHANGELOG fuer
``BrainViewModel`` und den Timeline-``StatusText``; das Audit 2026-08-05 fand
weitere 27 Faelle, darunter sechs Fortschrittsanzeigen
(``IsDeleting``, ``IsLoadingClips``, ``IsCleaningGpu``) — deshalb bekam der User
bei laufenden Aktionen keinerlei Rueckmeldung.

Der Test kehrt die Beweislast um: **jede** ObservableProperty muss entweder ein
XAML-Binding haben oder hier mit Begruendung eingetragen sein. Eine neue,
unbeabsichtigt ungebundene Property faellt damit sofort auf.

Die Ausnahmenliste ist bewusst als ehrliche Buchfuehrung gestaltet und nicht als
Freibrief: sie unterscheidet Properties, die reine Steuerlogik sind, von solchen,
die ueber einen zusammengesetzten (und selbst gebundenen) Text in die UI kommen,
und von echten Altlasten ohne jede Verwendung.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWMODEL_DIR = REPO_ROOT / "PBStudio.UI" / "ViewModels"
UI_ROOT = REPO_ROOT / "PBStudio.UI"

# ---------------------------------------------------------------------------
# Bewusst ungebundene Properties -> Begruendung.
#
# "Steuerlogik"      = wird nur programmatisch gelesen (CanExecute, Guards,
#                      Zustandsmaschinen). Ein Binding waere sinnlos.
# "via <Property>"   = Wert erreicht die UI ueber einen zusammengesetzten Text,
#                      der selbst gebunden ist. Kein Datenverlust.
# "Altlast"          = keine weitere Verwendung im ViewModel. Kandidat fuer
#                      Entfernung; bis dahin hier sichtbar statt still.
# ---------------------------------------------------------------------------
INTENTIONALLY_UNBOUND: dict[str, str] = {
    "AnchorViewModel.VideoClipId": "Altlast — keine weitere Verwendung im ViewModel",
    "AudioLibraryViewModel.DurationSeconds": "Steuerlogik — Anzeige laeuft ueber AudioClipModel je Zeile",
    "ChatViewModel.CurrentModel": "Altlast — pro Nachricht wird ModelName gebunden, global redundant",
    "DirectorViewModel.SelectedVideoClipCount": "Steuerlogik — steuert CanExecute der Generierung",
    "LearningSessionViewModel.IsPlaying": "Steuerlogik — interner Playback-Zustand",
    "MainViewModel.IsBackendConnected": "Altlast — gebunden wird IsBackendUnreachable",
    "ModelManagerViewModel.BaseUrl": "via StatusText",
    "ModelManagerViewModel.OllamaAvailable": "Steuerlogik — Provider-Verfuegbarkeit",
    "ModelManagerViewModel.LmStudioAvailable": "Steuerlogik — Provider-Verfuegbarkeit",
    "ModelManagerViewModel.ActiveProvider": "via StatusText",
    "ModelManagerViewModel.HasActiveTasks": "Altlast — keine weitere Verwendung",
    "ModelManagerViewModel.CompletedBytes": "Altlast — Download-Fortschritt laeuft ueber ProgressText",
    "ModelManagerViewModel.TotalBytes": "Altlast — Download-Fortschritt laeuft ueber ProgressText",
    "ModelManagerViewModel.SizeEstimateGb": "via zusammengesetzten Kartentext",
    "ProductionViewModel.AudioPath": "via StatusText und Render-Request",
    "ProductionViewModel.HasProject": "Steuerlogik — CanStartRender",
    "TimelineViewModel.AudioPath": "Steuerlogik — Quelle fuer Waveform-Laden",
    "TimelineViewModel.SelectedTimelinePosition": "Steuerlogik — Playhead-Zustand",
    "TimelineViewModel.HorizontalOffset": "Altlast — Scroll-Zustand, nie an ScrollViewer gehaengt",
    "TimelineViewModel.PreviewVideoPath": "Altlast — Preview-Player nicht verdrahtet",
    "VramTelemetryViewModel.TotalObservations": "via StatusText",
    "VramTelemetryViewModel.TotalSuccess": "via StatusText",
    "VramTelemetryViewModel.TotalFailure": "via StatusText",
}

OBSERVABLE_PROPERTY_PATTERN = re.compile(
    r"\[ObservableProperty\][^;]*?\b_(\w+)\s*(?:=|;)", re.DOTALL
)


def _pascal_case(field_name: str) -> str:
    """``_isDeleting`` -> ``IsDeleting`` (Namenskonvention des MVVM-Generators)."""
    return field_name[0].upper() + field_name[1:] if field_name else field_name


def _all_xaml_text() -> str:
    return " ".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in UI_ROOT.rglob("*.xaml")
        if "obj" not in path.parts and "bin" not in path.parts
    )


def _collect_properties() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for view_model in sorted(VIEWMODEL_DIR.glob("*.cs")):
        source = view_model.read_text(encoding="utf-8", errors="replace")
        for field in OBSERVABLE_PROPERTY_PATTERN.findall(source):
            found.append((view_model.stem, _pascal_case(field)))
    return found


@pytest.fixture(scope="module")
def xaml_text() -> str:
    return _all_xaml_text()


@pytest.fixture(scope="module")
def properties() -> list[tuple[str, str]]:
    collected = _collect_properties()
    assert collected, "Keine ObservableProperties gefunden — Regex oder Pfad kaputt."
    return collected


def test_every_observable_property_is_bound_or_documented(
    properties: list[tuple[str, str]], xaml_text: str
) -> None:
    """Kern des Guards: kein stilles Versickern mehr."""
    undocumented: list[str] = []
    for view_model, prop in properties:
        if f"Binding {prop}" in xaml_text:
            continue
        key = f"{view_model}.{prop}"
        if key in INTENTIONALLY_UNBOUND:
            continue
        undocumented.append(key)

    assert not undocumented, (
        "Diese ObservableProperties haben kein XAML-Binding und stehen auch nicht "
        "in INTENTIONALLY_UNBOUND:\n  "
        + "\n  ".join(sorted(undocumented))
        + "\n\nEntweder ein Binding ergaenzen oder mit Begruendung eintragen. "
        "Im Projekt ist genau dieser Fehler bereits mehrfach aufgetreten "
        "(Audit 2026-08-05, T3b.2)."
    )


def test_exception_list_has_no_stale_entries(
    properties: list[tuple[str, str]], xaml_text: str
) -> None:
    """
    Haelt die Ausnahmenliste ehrlich: wird eine Property nachtraeglich gebunden
    oder entfernt, muss der Eintrag verschwinden. Sonst verwaest die Liste und
    verliert ihre Aussagekraft.
    """
    existing = {f"{view_model}.{prop}" for view_model, prop in properties}
    stale: list[str] = []
    for key in INTENTIONALLY_UNBOUND:
        if key not in existing:
            stale.append(f"{key} (Property existiert nicht mehr)")
            continue
        prop = key.split(".", 1)[1]
        if f"Binding {prop}" in xaml_text:
            stale.append(f"{key} (inzwischen gebunden — Eintrag entfernen)")

    assert not stale, (
        "Veraltete Eintraege in INTENTIONALLY_UNBOUND:\n  " + "\n  ".join(sorted(stale))
    )


def test_progress_indicators_are_bound(xaml_text: str) -> None:
    """
    Regression fuer den konkreten Nutzerbefund: laufende Aktionen brauchen
    sichtbares Feedback. Diese vier waren ungebunden, weshalb Loeschen,
    Bibliothek-Laden und GPU-Cleanup ohne jede Rueckmeldung liefen.
    """
    for prop in ("IsDeleting", "IsLoadingClips", "IsCleaningGpu"):
        assert f"Binding {prop}" in xaml_text, (
            f"{prop} braucht ein XAML-Binding — ohne Fortschrittsanzeige wirkt "
            f"die Aktion fuer den User wie ein nicht reagierender Button."
        )
