"""
PB Studio GUI Click Audit & Automation Script
Startet die App, klickt alle Tabs und interaktiven Elemente durch und loggt jeden Klick detailliert in eine Datei.
"""
import time
import sys
import os
import datetime
import subprocess
import ctypes
from pywinauto import Application
from pywinauto.keyboard import send_keys

# DPI-Awareness setzen für korrekte Koordinaten
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Log-Dateiname mit Timestamp erzeugen
ts = datetime.datetime.now().strftime("%yyyy%m%d_%H%M%S")
log_path = os.path.join(LOGS_DIR, f"click_audit_{ts}.log")

def log_action(msg):
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S.%f]")[:-3]
    full_msg = f"{timestamp} {msg}"
    print(full_msg)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")

def log_click(element_name, element_type, title, rect):
    rect_str = f"({rect.left},{rect.top},{rect.right},{rect.bottom})" if rect else "None"
    log_action(f"[CLICK] Element: '{element_name}', Type: {element_type}, Title: '{title}', Rect: {rect_str}")

def main():
    log_action("============================================================")
    log_action("PB STUDIO GUI CLICK AUDIT START")
    log_action("============================================================")
    log_action(f"Audit Log-Datei: {os.path.abspath(log_path)}")

    # 1. Start der App über launch.ps1 im Hintergrund
    log_action("[1/5] Starte App über launch.ps1...")
    project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    
    # Startet launch.ps1 im Hintergrund
    process = subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "launch.ps1"],
        cwd=project_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    log_action(f"  PowerShell Launcher gestartet (PID: {process.pid})")

    # Warte bis das Hauptfenster bereit ist (maximal 25 Sekunden)
    log_action("  Warte auf Erscheinen des Hauptfensters 'PB Studio AMD'...")
    hwnd = 0
    user32 = ctypes.windll.user32
    for attempt in range(25):
        time.sleep(1.0)
        hwnd = user32.FindWindowW(None, "PB Studio AMD")
        if hwnd:
            log_action(f"  Hauptfenster gefunden! HWND: {hwnd}")
            break
    
    if not hwnd:
        log_action("  [ABORT] Hauptfenster wurde nicht gefunden!")
        process.terminate()
        sys.exit(1)

    # Fenster wiederherstellen und in den Vordergrund bringen
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    time.sleep(0.5)
    user32.SetForegroundWindow(hwnd)
    time.sleep(1.5)

    # 2. Verbindung mit pywinauto herstellen
    log_action("[2/5] Verbinde Automations-Schnittstelle...")
    try:
        app = Application(backend="uia").connect(title_re=".*PB Studio.*", timeout=15)
        win = app.window(title_re=".*PB Studio.*")
        win.wait("visible", timeout=5)
        log_action("  Verbindung hergestellt.")
    except Exception as e:
        log_action(f"  [ABORT] Verbindung fehlgeschlagen: {e}")
        process.terminate()
        sys.exit(1)

    # 3. Klick-Audit über alle Tabs ausführen
    log_action("[3/5] Starte Klick-Lauf über alle Tabs...")
    tabs = [
        "PROJEKT", "AUDIO", "VIDEO", "KI-REGIE", "TIMELINE", 
        "EXPORT", "HIRN", "SETTINGS", "PERFORMANCE", "MODELLE", "CHAT"
    ]

    for i, tab_name in enumerate(tabs):
        try:
            log_action(f"\n--- [Tab {i+1}/11] Wechsel zu '{tab_name}' ---")
            tab_item = win.child_window(title=tab_name, control_type="TabItem")
            rect = tab_item.rectangle()
            
            # Klick loggen
            log_click(f"TabItem_{tab_name}", "TabItem", tab_name, rect)
            
            # Reale Klick-Aktion durchführen
            tab_item.select()
            time.sleep(1.5) # Warte auf Rendering-Durchlauf

            # Tab-spezifische Zusatzklicks
            if tab_name == "PERFORMANCE":
                log_action("  Spezial-Interaktion: Performance-Interaktionen...")
                try:
                    # Klick auf den GPU-Cleanup-Button (falls vorhanden)
                    cleanup_btn = win.child_window(title="VRAM aufräumen", control_type="Button", auto_id="BtnCleanup")
                    if cleanup_btn.exists():
                        log_click("BtnCleanup", "Button", "VRAM aufräumen", cleanup_btn.rectangle())
                        cleanup_btn.click()
                        time.sleep(1.0)
                except Exception as ex:
                    log_action(f"    (Kein Cleanup-Button gefunden: {ex})")

            elif tab_name == "CHAT":
                log_action("  Spezial-Interaktion: Sende eine Testnachricht im Chat...")
                try:
                    # Suche Chat-Eingabefeld und sende eine harmlose Frage
                    chat_input = win.child_window(control_type="TextBox", auto_id="TxtChatInput")
                    if chat_input.exists():
                        log_click("TxtChatInput", "TextBox", "Chat Eingabe", chat_input.rectangle())
                        chat_input.click()
                        time.sleep(0.5)
                        send_keys("Hallo PB Studio, wie läuft die AMD-Optimierung?{ENTER}")
                        log_action("    Testnachricht an Chat gesendet.")
                        time.sleep(2.0)
                except Exception as ex:
                    log_action(f"    (Chat-Eingabefeld nicht gefunden/interaktiv: {ex})")

        except Exception as e:
            log_action(f"  [WARNUNG] Fehler beim Klicken des Tabs '{tab_name}': {e}")

    # 4. Sauberes Beenden der App
    log_action("\n[4/5] Beende die App sauber...")
    try:
        # Schließe das Fenster, dies triggert den Shutdown des Backends über launch.ps1
        log_click("CloseButton", "WindowClose", "PB Studio AMD beenden", win.rectangle())
        win.close()
        time.sleep(2.0)
        log_action("  WPF-Fenster geschlossen.")
    except Exception as e:
        log_action(f"  Fehler beim Schließen des Fensters: {e}")

    # Falls der Powershell-Prozess noch läuft, hart beenden
    if process.poll() is None:
        log_action("  Launcher-Prozess läuft noch, beende ihn...")
        process.terminate()

    log_action("\n============================================================")
    log_action("PB STUDIO GUI CLICK AUDIT COMPLETED")
    log_action("============================================================")

if __name__ == "__main__":
    main()
