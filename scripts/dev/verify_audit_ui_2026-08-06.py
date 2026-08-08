"""
Live-Verifikation der UI-Elemente aus dem Audit 2026-08-05.

Warum dieses Skript
-------------------
Alle Fixes waren bis hierher nur ueber Tests, Builds und DB-Empirie belegt.
IRON RULE 10 verlangt Live-Verifikation: "Build OK != laeuft". Die acht neuen
Director-Regler, die Kontextfenster-Anzeige und das persist_error-Banner hatte
niemand je gerendert gesehen.

Der Driver (`.claude/skills/run-pb-studio/driver.ps1`) kann nur den
Standard-Tab aufnehmen. Dieses Skript schaltet per UI-Automation gezielt auf
KI-REGIE und MODELLE und prueft die erwarteten Beschriftungen im UIA-Baum —
also nicht nur "Fenster da", sondern "Element wirklich vorhanden".

Aufruf (Backend und WPF muessen laufen, z.B. via driver.ps1 -Command start-full):
    .\.venv\Scripts\python.exe scripts\dev\verify_audit_ui_2026-08-06.py
"""

from __future__ import annotations

import sys
import time

from pywinauto import Application, Desktop

# Beschriftungen, die es vor dem Audit NICHT gab.
EXPECTED_DIRECTOR = [
    "Snare-Gewichtung:",
    "HiHat-Gewichtung:",
    "Onset-Empfindlichkeit:",
    "Min. Clip-Länge:",
    "Max. Clip-Länge:",
    "Clip-Längen-Variation:",
    "Max. Schnittabstand:",
    "Beat-Trigger-Modus:",
]
EXPECTED_MODELS = ["KONTEXT", "ARCH"]


def _texts(window) -> set[str]:
    found: set[str] = set()
    for element in window.descendants():
        try:
            text = (element.window_text() or "").strip()
        except Exception:  # noqa: BLE001 - einzelne Elemente duerfen scheitern
            continue
        if text:
            found.add(text)
    return found


def _select_tab(window, name: str) -> bool:
    for element in window.descendants():
        try:
            if (element.window_text() or "").strip().upper() != name.upper():
                continue
            if element.element_info.control_type != "TabItem":
                continue
            element.select()
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def main() -> int:
    try:
        app = Application(backend="uia").connect(title_re=".*PB Studio.*", timeout=20)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: WPF-Fenster nicht gefunden: {exc}")
        print("Hinweis: driver.ps1 -Command start-full zuerst ausfuehren.")
        return 2

    window = app.top_window()
    window.wait("visible ready", timeout=30)
    print(f"Fenster: {window.window_text()!r}")

    tabs = [
        e.window_text().strip()
        for e in window.descendants()
        if e.element_info.control_type == "TabItem"
    ]
    print(f"Tabs im UIA-Baum ({len(tabs)}): {tabs}")

    failures: list[str] = []

    for tab_name, expected in (("KI-REGIE", EXPECTED_DIRECTOR), ("MODELLE", EXPECTED_MODELS)):
        print(f"\n=== Tab {tab_name} ===")
        if not _select_tab(window, tab_name):
            failures.append(f"{tab_name}: Tab nicht selektierbar")
            print("  FAIL: Tab nicht gefunden")
            continue
        time.sleep(2.0)  # XAML-Render abwarten
        texts = _texts(window)
        for label in expected:
            hit = any(label in text for text in texts)
            print(f"  {'OK  ' if hit else 'FEHLT'}  {label}")
            if not hit:
                failures.append(f"{tab_name}: {label}")

    print("\n" + "=" * 60)
    if failures:
        print(f"ERGEBNIS: {len(failures)} Element(e) NICHT gefunden:")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("ERGEBNIS: alle erwarteten UI-Elemente live im UIA-Baum vorhanden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
