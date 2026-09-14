"""Waechter: kein Dict-Literal im Produktionscode darf einen String-Key doppelt fuehren.

Audit 2026-08-29: `spectral_analyzer.py` fuehrte "mel_bands" zweimal im selben Literal,
die zweite Zeile zusaetzlich falsch eingerueckt. Python akzeptiert das (letzter gewinnt),
der Wert wird aber zweimal berechnet. Fingerabdruck eines fehlgeschlagenen Edits.

Review-Nacharbeit 2026-08-29 (I-1/I-2/M-1):
- Wurzeln werden von __file__ abgeleitet, nicht vom CWD. Ein Wurzelverzeichnis, das
  nicht existiert, laesst rglob() still leer zurueckkommen -- das wuerde den Waechter
  unabhaengig vom Repo-Zustand gruen machen. Deshalb fail-fast, wenn eine Wurzel fehlt.
- Ein Positivtest pinnt den Detektor selbst fest, unabhaengig vom aktuellen Repo-Zustand.
- Der fruehere ui_legacy_archived-Ausschluss ist entfernt: ast.parse() importiert nichts,
  die Begruendung "gebrochene Imports" war sachlich falsch. Gegengeprueft: alle Dateien
  dort parsen fehlerfrei und enthalten keine doppelten Keys, der Ausschluss kaufte nichts.
"""

import ast
import pathlib

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ROOTS = [_REPO_ROOT / "src", _REPO_ROOT / "backend"]


def _duplicate_string_keys(tree: ast.AST) -> list[tuple[int, list[str]]]:
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [
            k.value
            for k in node.keys
            if isinstance(k, ast.Constant) and isinstance(k.value, str)
        ]
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        if dupes:
            findings.append((node.lineno, dupes))
    return findings


def _python_files() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for root in ROOTS:
        if not root.is_dir():
            raise AssertionError(
                f"Wurzelverzeichnis fehlt: {root} -- ein leerer Scan darf nicht als Erfolg durchgehen"
            )
        files.extend(root.rglob("*.py"))
    return files


def test_no_dict_literal_repeats_a_string_key():
    offenders = []
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as exc:  # pragma: no cover - defekte Datei ist ein eigener Fehler
            pytest.fail(f"{path} laesst sich nicht parsen: {exc}")
        for lineno, dupes in _duplicate_string_keys(tree):
            offenders.append(f"{path}:{lineno} fuehrt {dupes} mehrfach")

    assert not offenders, "Doppelte Dict-Keys gefunden:\n  " + "\n  ".join(offenders)


def test_detector_finds_a_duplicate():
    tree = ast.parse('{"a": 1, "b": 2, "a": 3}')
    assert _duplicate_string_keys(tree) == [(1, ["a"])]
