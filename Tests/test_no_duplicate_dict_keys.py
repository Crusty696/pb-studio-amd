"""Waechter: kein Dict-Literal im Produktionscode darf einen String-Key doppelt fuehren.

Audit 2026-08-29: `spectral_analyzer.py` fuehrte "mel_bands" zweimal im selben Literal,
die zweite Zeile zusaetzlich falsch eingerueckt. Python akzeptiert das (letzter gewinnt),
der Wert wird aber zweimal berechnet. Fingerabdruck eines fehlgeschlagenen Edits.
"""

import ast
import pathlib

import pytest

ROOTS = [pathlib.Path("src"), pathlib.Path("backend")]


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
        files.extend(
            p for p in root.rglob("*.py") if "ui_legacy_archived" not in p.parts
        )
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
