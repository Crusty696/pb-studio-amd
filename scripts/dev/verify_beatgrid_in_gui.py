"""Prueft in der LAUFENDEN App, ob das Beatgrid angezeigt wird.

Warum dieses Skript ueberhaupt:

Ein Binding im XAML beweist nur, dass die Zeile existiert - nicht, dass Text
erscheint. Zwischen `{Binding BeatGridText}` und sichtbarem Text liegen drei
Stellen, die still scheitern:

  * ein Tippfehler im Property-Namen (WPF meldet das nur im Debug-Output,
    nicht als Fehler),
  * der `NullToVisibilityConverter`, der bei leerem String auf `Collapsed`
    schaltet,
  * `ApplyBeatGrid`, das bei unerwarteter JSON-Struktur frueh zurueckkehrt.

Alle drei liefern eine leere Anzeige ohne jede Fehlermeldung. Genau dieses
Muster ist in diesem Projekt zweimal unbemerkt geblieben (BrainViewModel,
Timeline-StatusText: Property gesetzt, an nichts gebunden).

Der Ablauf hat deshalb eine GEGENPROBE: vor der Analyse muss der Text
ABWESEND sein. Ein Pruefwerkzeug, das immer "gefunden" meldet, ist wertlos.

    1. an das laufende Fenster andocken
    2. AUDIO-Tab, ersten Clip waehlen
    3. Gegenprobe: "Beatgrid:" darf JETZT nicht im UIA-Baum stehen
    4. Analyse ueber die Oberflaeche ausloesen (nicht per API - sonst wird der
       Pfad ApiClient -> ViewModel -> Binding gar nicht durchlaufen)
    5. auf den Text warten, Screenshot und JSON als Beleg schreiben

Voraussetzung: Backend laeuft, Projekt mit mindestens einem Audioclip ist
geoeffnet, App laeuft (Fenstertitel "PB Studio AMD").

Aufruf:
    python scripts/dev/verify_beatgrid_in_gui.py --out docs/evidence/beatgrid-gui
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import win32gui  # noqa: E402
from pywinauto import Application  # noqa: E402

from run_gui_release_gate import capture_window  # noqa: E402

WINDOW_TITLE = "PB Studio AMD"
# Der Anzeigetext, NICHT das Wort aus der Logzeile: der TERMINAL-Tab zeigt
# das Backend-Log im selben Fenster, und "Beatgrid:" kommt dort ebenfalls
# vor. Ein zu unspezifischer Marker meldet dann einen Treffer, der nichts
# mit der Anzeige zu tun hat.
MARKER = "Zweitschätzung:"


def _collect_texts(window) -> list[str]:
    """Alle sichtbaren Textwerte des UIA-Baums."""
    values: list[str] = []
    for control in window.descendants():
        for value in (control.element_info.name, control.window_text()):
            text = str(value or "").strip()
            if text:
                values.append(text)
    return values


def _find_marker(window) -> list[str]:
    """Nur echte Anzeigetexte, keine Logzeilen aus dem TERMINAL-Tab.

    Der Terminal zeigt das Backend-Log im selben Fenster; ein Treffer dort
    beweist nichts ueber die Anzeige. Erkennbar an Zeitstempel-Praefix und
    Mehrzeiligkeit.
    """
    hits = []
    for text in _collect_texts(window):
        if MARKER not in text:
            continue
        if "\n" in text or text.lstrip().startswith("["):
            continue
        hits.append(text)
    return sorted(set(hits))


def _wait_for_marker(
    window, timeout: float, different_from: list[str] | None = None
) -> list[str]:
    """Wartet auf den Marker - optional auf einen ANDEREN als den bisherigen.

    Ohne `different_from` zaehlt ein stehengebliebener alter Text als Treffer.
    Genau daran ist die erste Fassung dieses Skripts gescheitert: sie meldete
    "present", obwohl die Anzeige den Wert der vorigen Analyse zeigte und sich
    gar nicht aktualisiert hatte.
    """
    baseline = set(different_from or [])
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found = _find_marker(window)
        if found and not (set(found) <= baseline):
            return found
        time.sleep(1.0)
    return _find_marker(window)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument(
        "--skip-analysis", action="store_true",
        help="nur nachsehen, ob der Text schon da ist (kein Klick auf Analyse)",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    handle = win32gui.FindWindow(None, WINDOW_TITLE)
    if not handle:
        print(f"Fenster '{WINDOW_TITLE}' nicht gefunden - laeuft die App?",
              file=sys.stderr)
        return 2

    app = Application(backend="uia").connect(handle=handle, timeout=20)
    spec = app.window(handle=handle)
    spec.wait("visible enabled ready", timeout=30)
    # `child_window` gehoert zum WindowSpecification, `descendants` zum
    # Wrapper. Beide werden gebraucht.
    window = spec.wrapper_object()

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "marker": MARKER,
        "window_title": WINDOW_TITLE,
    }

    # AUDIO-Tab
    try:
        spec.child_window(title="AUDIO", control_type="TabItem").select()
        time.sleep(1.5)
    except Exception as exc:  # noqa: BLE001
        print(f"AUDIO-Tab nicht waehlbar: {exc}", file=sys.stderr)
        receipt["error"] = f"tab: {exc}"
        (args.out / "result.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return 2

    # Gegenprobe VOR der Analyse - ohne sie sagt ein Treffer nichts aus.
    before = _find_marker(window)
    receipt["before_analysis"] = before
    capture_window(handle, args.out / "01-vor-analyse.png")
    print(f"vor der Analyse gefunden: {before or '(nichts)'}")

    if args.skip_analysis:
        receipt["mode"] = "skip_analysis"
        receipt["after_analysis"] = before
        receipt["verdict"] = "present" if before else "absent"
        (args.out / "result.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return 0 if before else 1

    # Ersten Clip in der Liste waehlen
    selected = False
    for list_name in ("AudioClipList", "Audio-Clips", "Clips"):
        try:
            clip_list = spec.child_window(
                auto_id=list_name, control_type="List"
            )
            items = clip_list.children()
            if items:
                items[0].select()
                selected = True
                receipt["clip_list"] = list_name
                break
        except Exception:  # noqa: BLE001 - naechsten Namen probieren
            continue
    if not selected:
        # Fallback: irgendeine Liste mit Eintraegen
        for control in window.descendants(control_type="List"):
            children = control.children()
            if children:
                try:
                    children[0].select()
                    selected = True
                    receipt["clip_list"] = str(
                        control.element_info.automation_id or "unbenannt"
                    )
                    break
                except Exception:  # noqa: BLE001
                    continue
    receipt["clip_selected"] = selected
    time.sleep(1.0)

    # Analyse ueber die Oberflaeche ausloesen
    triggered = False
    # Die echten Beschriftungen, aus dem UIA-Baum der laufenden App gelesen -
    # geraten hatte ich "Analysieren", was es nicht gibt.
    for title in (
        "Ausgewählten Audio-Clip analysieren",
        "Alle Audio-Clips analysieren",
    ):
        try:
            button = spec.child_window(title=title, control_type="Button")
            if button.exists() and button.is_enabled():
                button.click_input()
                triggered = True
                receipt["analyse_button"] = title
                break
        except Exception:  # noqa: BLE001
            continue
    receipt["analysis_triggered"] = triggered
    if not triggered:
        receipt["available_buttons"] = sorted({
            str(b.window_text() or "").strip()
            for b in window.descendants(control_type="Button")
            if str(b.window_text() or "").strip()
        })[:40]
        print("Analyse-Schaltflaeche nicht gefunden; verfuegbare Buttons im "
              "Beleg", file=sys.stderr)

    found = (
        _wait_for_marker(window, args.timeout, different_from=before)
        if triggered else _find_marker(window)
    )
    receipt["after_analysis"] = found
    capture_window(handle, args.out / "02-nach-analyse.png")

    # Urteil: der Text muss NACH der Analyse da sein. War er schon vorher da,
    # ist die Gegenprobe wertlos und das wird ausdruecklich vermerkt.
    changed = bool(found) and set(found) != set(before)
    receipt["changed"] = changed
    if found and not before:
        # Sauberster Fall: vorher nichts, nachher Text.
        receipt["verdict"] = "present"
    elif changed:
        # Vorher ein anderer Wert, jetzt ein neuer - die Anzeige aktualisiert.
        receipt["verdict"] = "present_and_updated"
    elif found:
        # Text da, aber unveraendert. Beweist NICHT, dass die Anzeige den
        # neuen Wert uebernimmt - sie koennte am alten haengen.
        receipt["verdict"] = "present_but_stale"
    else:
        receipt["verdict"] = "absent"

    (args.out / "result.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    # "present_but_stale" ist KEIN Bestehen - der Wert koennte alt sein.
    return 0 if receipt["verdict"] in {"present", "present_and_updated"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
