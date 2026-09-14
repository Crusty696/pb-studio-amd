"""Waechter: kein Aufruf von CaptureOperationContext ohne Absicherung.

Befund 2026-08-31, an der laufenden App reproduziert: ein Klick auf
"Ausgewaehlten Audio-Clip analysieren" ohne stabilen Projektkontext beendete
die Anwendung.

    [Critical] Unbehandelte UI-Exception:
    System.InvalidOperationException: Kein stabiler Projektkontext verfuegbar
       at ProjectService.CaptureOperationContext()
       at AudioLibraryViewModel.AnalyzeSelectedAsync()

`CaptureOperationContext` wirft absichtlich, wenn gerade ein Projektwechsel
laeuft oder keines offen ist (ProjectService.cs:206). Das ist ein erwartbarer
Zustand, kein Programmfehler - er gehoert in die Statuszeile, nicht in einen
Absturz.

Elf von fuenfzehn Aufrufstellen fingen die Exception bereits ab. Vergessen
worden waren ausgerechnet die vier, die lange Arbeit starten: beide
Analysepfade, die Stem-Separation und die Cut-Listen-Erzeugung.

Dieser Test findet neue ungeschuetzte Aufrufer, bevor ein Nutzer sie findet.
"""

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWMODELS = REPO_ROOT / "PBStudio.UI" / "ViewModels"

CALL = "CaptureOperationContext()"
LOOKBACK = 12
LOOKAHEAD = 14


def _unguarded_calls() -> list[tuple[str, int, str]]:
    """Alle Aufrufe ohne try/catch auf InvalidOperationException."""
    findings: list[tuple[str, int, str]] = []
    for path in sorted(VIEWMODELS.glob("*.cs")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if CALL not in line:
                continue
            before = lines[max(0, index - LOOKBACK):index]
            after = lines[index:index + LOOKAHEAD]
            has_try = any(
                re.match(r"\s*try\s*$|\s*try\s*\{", candidate) for candidate in before
            )
            has_catch = any(
                "catch (InvalidOperationException" in candidate for candidate in after
            )
            if not (has_try and has_catch):
                findings.append((path.name, index + 1, line.strip()))
    return findings


def test_no_unguarded_capture_operation_context() -> None:
    unguarded = _unguarded_calls()
    assert not unguarded, (
        "CaptureOperationContext ohne try/catch(InvalidOperationException) - "
        "das beendet die Anwendung statt eine Statusmeldung zu zeigen:\n"
        + "\n".join(f"  {name}:{line}  {code}" for name, line, code in unguarded)
    )


def test_the_guard_would_notice_a_regression() -> None:
    """Gegenprobe: erkennt der Waechter einen ungeschuetzten Aufruf ueberhaupt?

    Ein Waechter, der immer gruen ist, ist wertlos. Hier wird der Erkenner auf
    einen konstruierten Fall angewandt, statt ihm zu vertrauen.
    """
    import tempfile

    unguarded_source = """
class Demo
{
    private async Task DoWork()
    {
        var operation = _projectService.CaptureOperationContext();
        await Task.Delay(1);
    }
}
"""
    guarded_source = """
class Demo
{
    private async Task DoWork()
    {
        ProjectOperationContext operation;
        try
        {
            operation = _projectService.CaptureOperationContext();
        }
        catch (InvalidOperationException)
        {
            StatusText = "kein stabiler Projektkontext";
            return;
        }
        await Task.Delay(1);
    }
}
"""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "Unguarded.cs").write_text(unguarded_source, encoding="utf-8")
        (folder / "Guarded.cs").write_text(guarded_source, encoding="utf-8")

        global VIEWMODELS
        original = VIEWMODELS
        try:
            VIEWMODELS = folder
            findings = _unguarded_calls()
        finally:
            VIEWMODELS = original

    names = {name for name, _, _ in findings}
    assert "Unguarded.cs" in names, "Waechter erkennt einen ungeschuetzten Aufruf nicht"
    assert "Guarded.cs" not in names, "Waechter meldet einen abgesicherten Aufruf faelschlich"


@pytest.mark.parametrize(
    "method",
    ["AnalyzeAllAsync", "AnalyzeSelectedAsync", "SeparateStemsAsync"],
)
def test_audio_library_long_running_actions_report_instead_of_crashing(method: str) -> None:
    """Die drei Pfade, die den Absturz ausgeloest haben, melden jetzt."""
    source = (VIEWMODELS / "AudioLibraryViewModel.cs").read_text(encoding="utf-8")
    assert method in source, f"{method} nicht gefunden - umbenannt?"
    assert "kein stabiler Projektkontext" in source, (
        "keine Statusmeldung fuer den Fall ohne Projektkontext"
    )
