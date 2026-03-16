"""
PB Studio WPF GUI-Test mit pywinauto
Testet alle 8 Tabs, Buttons, und UI-Elemente
"""
import time
import sys
from pywinauto import Application


PASSED = []
ERRORS = []


def check(name, success, detail=""):
    if success:
        PASSED.append(f"PASS: {name}")
        print(f"  [PASS] {name}" + (f" - {detail}" if detail else ""))
    else:
        ERRORS.append(f"FAIL: {name} - {detail}")
        print(f"  [FAIL] {name} - {detail}")


def find_button_by_child_text(win, text):
    """Find a WPF button by its child TextBlock text (MaterialDesign pattern)."""
    buttons = win.descendants(control_type="Button")
    for btn in buttons:
        try:
            for child in btn.descendants():
                if child.window_text() == text:
                    return btn
        except Exception:
            pass
    return None


def has_text_element(win, text):
    """Check if a text element with given content exists."""
    texts = win.descendants(control_type="Text")
    for t in texts:
        try:
            if text in t.window_text():
                return True
        except Exception:
            pass
    return False


def main():
    print("=" * 60)
    print("PB STUDIO WPF GUI-TEST (v2 - mit Tab-Content)")
    print("=" * 60)

    # === 1: App verbinden ===
    print("\n[1] App verbinden...")
    try:
        app = Application(backend="uia").connect(title_re=".*PB Studio.*", timeout=10)
        win = app.window(title_re=".*PB Studio.*")
        win.wait("visible", timeout=10)
        title = win.window_text()
        check("App verbunden", True, f"Titel: {title!r}")
    except Exception as e:
        check("App verbunden", False, str(e))
        sys.exit(1)

    # === 2: Fenster sichtbar ===
    print("\n[2] Fenster pruefen...")
    rect = win.rectangle()
    check("Fenster sichtbar", rect.width() > 100, f"{rect.width()}x{rect.height()}")

    # === 3: Header-Buttons (nach Child-Text) ===
    print("\n[3] Header-Buttons pruefen...")
    for btn_text in ["Neu", "\u00d6ffnen", "Speichern", "Schlie\u00dfen"]:
        btn = find_button_by_child_text(win, btn_text)
        check(f"Header-Button {btn_text!r}", btn is not None)

    # === 4: Status-Texte ===
    print("\n[4] Status-Texte pruefen...")
    check("GPU-Status sichtbar", has_text_element(win, "GPU:"))
    check("Backend-Status sichtbar", has_text_element(win, "Backend:"))

    # === 5: Alle 8 Tabs durchklicken ===
    print("\n[5] Alle 8 Tabs durchklicken...")
    tab_names = [
        "IMPORT", "AUDIO", "VIDEO", "ANCHORS",
        "DIRECTOR", "TIMELINE", "PRODUKTION", "SETTINGS",
    ]
    for tab_name in tab_names:
        try:
            tab = win.child_window(title=tab_name, control_type="TabItem")
            if tab.exists(timeout=3):
                tab.click_input()
                time.sleep(0.5)
                check(f"Tab {tab_name!r} klickbar", True)
            else:
                check(f"Tab {tab_name!r} klickbar", False, "Nicht gefunden")
        except Exception as e:
            check(f"Tab {tab_name!r} klickbar", False, str(e)[:80])

    # === 6: IMPORT-Tab Content ===
    print("\n[6] IMPORT-Tab Content pruefen...")
    win.child_window(title="IMPORT", control_type="TabItem").click_input()
    time.sleep(1)
    btn = find_button_by_child_text(win, "Audio importieren")
    check("Import: Button 'Audio importieren'", btn is not None)
    btn = find_button_by_child_text(win, "Video importieren")
    check("Import: Button 'Video importieren'", btn is not None)
    check("Import: 'AUDIO-DATEIEN' Sektion", has_text_element(win, "AUDIO-DATEIEN"))
    check("Import: 'VIDEO-DATEIEN' Sektion", has_text_element(win, "VIDEO-DATEIEN"))
    check("Import: ListView vorhanden", len(win.descendants(control_type="DataGrid")) > 0)

    # === 7: AUDIO-Tab Content ===
    print("\n[7] AUDIO-Tab Content pruefen...")
    win.child_window(title="AUDIO", control_type="TabItem").click_input()
    time.sleep(1)
    for btn_text in ["Alle", "Keine", "Alle analysieren", "Analysieren", "Stems trennen"]:
        btn = find_button_by_child_text(win, btn_text)
        check(f"Audio: Button {btn_text!r}", btn is not None)
    check("Audio: 'AUDIO-CLIPS' Sektion", has_text_element(win, "AUDIO-CLIPS"))
    check("Audio: 'ANALYSE-ERGEBNISSE' Sektion", has_text_element(win, "ANALYSE-ERGEBNISSE"))

    # === 8: VIDEO-Tab Content ===
    print("\n[8] VIDEO-Tab Content pruefen...")
    win.child_window(title="VIDEO", control_type="TabItem").click_input()
    time.sleep(1)
    for btn_text in ["Aktualisieren", "Analysieren", "Alle analysieren"]:
        btn = find_button_by_child_text(win, btn_text)
        check(f"Video: Button {btn_text!r}", btn is not None)

    # === 9: ANCHORS-Tab Content ===
    print("\n[9] ANCHORS-Tab Content pruefen...")
    win.child_window(title="ANCHORS", control_type="TabItem").click_input()
    time.sleep(1)
    check("Anchors: 'AUDIO TIMELINE' Sektion", has_text_element(win, "AUDIO TIMELINE"))
    check("Anchors: 'ANCHOR-PUNKTE' Sektion", has_text_element(win, "ANCHOR-PUNKTE"))
    for btn_text in ["Hinzuf\u00fcgen", "Entfernen"]:
        btn = find_button_by_child_text(win, btn_text)
        check(f"Anchors: Button {btn_text!r}", btn is not None)

    # === 10: DIRECTOR-Tab Content ===
    print("\n[10] DIRECTOR-Tab Content pruefen...")
    win.child_window(title="DIRECTOR", control_type="TabItem").click_input()
    time.sleep(1)
    check("Director: 'AUDIO-QUELLE' Sektion", has_text_element(win, "AUDIO-QUELLE"))
    check("Director: 'VIDEO-CLIPS' Sektion", has_text_element(win, "VIDEO-CLIPS"))
    check("Director: 'PACING' Sektion", has_text_element(win, "PACING"))
    btn = find_button_by_child_text(win, "CUT-LISTE GENERIEREN")
    check("Director: Generate-Button", btn is not None)
    check("Director: 'CUT-LISTE' Ergebnis-Sektion", has_text_element(win, "CUT-LISTE"))

    # === 11: TIMELINE-Tab Content ===
    print("\n[11] TIMELINE-Tab Content pruefen...")
    win.child_window(title="TIMELINE", control_type="TabItem").click_input()
    time.sleep(1)
    btn = find_button_by_child_text(win, "Timeline laden")
    check("Timeline: Load-Button", btn is not None)
    # Zurueck/Weiter buttons
    for btn_text in ["Zur\u00fcck", "Weiter"]:
        btn = find_button_by_child_text(win, btn_text)
        check(f"Timeline: Button {btn_text!r}", btn is not None)

    # === 12: PRODUKTION-Tab Content ===
    print("\n[12] PRODUKTION-Tab Content pruefen...")
    win.child_window(title="PRODUKTION", control_type="TabItem").click_input()
    time.sleep(1)
    check("Produktion: 'RENDER SETTINGS' Sektion", has_text_element(win, "RENDER SETTINGS"))
    btn = find_button_by_child_text(win, "Render starten")
    check("Produktion: Render-Button", btn is not None)
    btn = find_button_by_child_text(win, "Log leeren")
    check("Produktion: Log-leeren-Button", btn is not None)
    check("Produktion: 'RENDER LOG' Sektion", has_text_element(win, "RENDER LOG"))

    # === 13: SETTINGS-Tab Content ===
    print("\n[13] SETTINGS-Tab Content pruefen...")
    win.child_window(title="SETTINGS", control_type="TabItem").click_input()
    time.sleep(1)
    check("Settings: 'GPU STATUS' Sektion", has_text_element(win, "GPU STATUS"))
    check("Settings: 'BACKEND STATUS' Sektion", has_text_element(win, "BACKEND STATUS"))
    check("Settings: 'PB STUDIO AMD EDITION' Info", has_text_element(win, "PB STUDIO AMD EDITION"))
    btn = find_button_by_child_text(win, "Refresh")
    check("Settings: Refresh-Button", btn is not None)
    btn = find_button_by_child_text(win, "Cleanup")
    check("Settings: Cleanup-Button", btn is not None)

    # Tatsaechlich Refresh klicken
    btn = find_button_by_child_text(win, "Refresh")
    if btn:
        btn.click_input()
        time.sleep(2)
        check("Settings: Refresh ausgefuehrt", True)

    # GPU-Daten pruefen nach Refresh
    check("Settings: GPU-Daten geladen", has_text_element(win, "MB"))

    # === ERGEBNIS ===
    print("\n" + "=" * 60)
    print(f"GUI-TEST ERGEBNIS: {len(PASSED)} PASSED, {len(ERRORS)} FAILED")
    print("=" * 60)
    for p in PASSED:
        print(f"  {p}")
    if ERRORS:
        print(f"\nFEHLER:")
        for e in ERRORS:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("\nALLE GUI-TESTS BESTANDEN!")


if __name__ == "__main__":
    main()
