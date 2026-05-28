"""
PB Studio GUI Manual Click Logger (Polling-Edition)
Startet die App und zeichnet jeden manuellen Klick des Benutzers in Echtzeit in einer Logdatei auf.
Nutzt einen robusten Win32-Polling-Ansatz anstelle von WH_MOUSE_LL, um Windows-Sicherheitssperren zu umgehen.
"""
import ctypes
from ctypes import wintypes
import time
import sys
import os
import datetime
import subprocess
import threading
from pywinauto import Application

# DPI-Awareness setzen für korrekte Maus-Koordinaten
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Log-Dateiname mit Timestamp erzeugen
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = os.path.join(LOGS_DIR, f"click_manual_{ts}.log")

# Globale Variablen
pb_studio_hwnd = None
pywinauto_win = None
is_running = True

# Win32 Konstanten
VK_LBUTTON = 0x01
GA_ROOT = 2

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def log_action(msg):
    timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S.%f]")[:-3]
    full_msg = f"{timestamp} {msg}"
    try:
        print(full_msg)
    except UnicodeEncodeError:
        # Robustes Fallback fuer Windows CP1252-Terminals bei Unicode-Zeichen wie ↻
        try:
            enc = sys.stdout.encoding or 'utf-8'
            print(full_msg.encode(enc, errors='replace').decode(enc))
        except Exception:
            # Letztes Fallback: Einfaches ASCII
            print(full_msg.encode('ascii', errors='replace').decode('ascii'))
    sys.stdout.flush()
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(full_msg + "\n")

def resolve_element_at_point(x, y):
    """Löst die UIA-UI-Elementdetails an den Mauskoordinaten auf."""
    if not pywinauto_win:
        return "Unknown", "Unknown", "Unknown"
    try:
        elem = pywinauto_win.from_point(x, y)
        if elem:
            name = elem.element_info.name or "Unbenannt"
            control_type = elem.element_info.control_type or "Unknown"
            auto_id = elem.element_info.automation_id or "None"
            return name, control_type, auto_id
    except Exception:
        pass
    return "Element außerhalb des Trees", "Unknown", "None"

def monitor_app_lifetime():
    """Überwacht, ob das WPF-Fenster geschlossen wurde."""
    global is_running
    log_action("  Lebensdauer-Überwachung des WPF-Fensters aktiv...")
    while is_running:
        time.sleep(1.0)
        hwnd = user32.FindWindowW(None, "PB Studio AMD")
        if not hwnd:
            log_action("  [INFO] WPF-Hauptfenster geschlossen. Beende Klick-Protokollierung...")
            is_running = False
            break

def start_polling_loop():
    """Überwacht den Zustand der linken Maustaste per Win32 API."""
    global is_running
    log_action("  [OK] Polling-basierter Click-Logger gestartet. Warte auf Klicks...")
    
    # Startet Lebensdauer-Überwachung in separatem Thread
    t = threading.Thread(target=monitor_app_lifetime, daemon=True)
    t.start()

    last_state = 0
    pt = POINT()
    
    while is_running:
        # Abfragen, ob linke Maustaste gedrückt ist (Bit 15 gesetzt = gedrückt)
        state = user32.GetAsyncKeyState(VK_LBUTTON)
        is_pressed = (state & 0x8000) != 0
        
        if is_pressed:
            if not last_state: # Flankenwechsel von "nicht gedrückt" zu "gedrückt"
                # Aktuelle Mausposition holen
                user32.GetCursorPos(ctypes.byref(pt))
                
                # HWND an Position ermitteln
                hwnd_point = user32.WindowFromPoint(pt)
                if hwnd_point:
                    root_hwnd = user32.GetAncestor(hwnd_point, GA_ROOT)
                    
                    # Prüfen, ob der Klick zum PB Studio Hauptfenster gehört
                    if root_hwnd == pb_studio_hwnd:
                        name, control_type, auto_id = resolve_element_at_point(pt.x, pt.y)
                        log_action(f"[CLICK] X:{pt.x}, Y:{pt.y} | Element: '{name}' | Type: {control_type} | AutoId: '{auto_id}'")
                        
            last_state = True
        else:
            last_state = False
            
        time.sleep(0.05) # 50ms Polling für hohe Präzision und extrem niedrige CPU-Last

def main():
    global pb_studio_hwnd, pywinauto_win
    
    log_action("============================================================")
    log_action("PB STUDIO MANUAL TEST CLICK LOGGER START (POLLING-EDITION)")
    log_action("============================================================")
    log_action(f"Manuelle Test-Logdatei: {os.path.abspath(log_path)}")
    log_action("Bitte testen Sie die App jetzt manuell. Jeder Klick wird aufgezeichnet.")
    log_action("Schließen Sie die App nach dem Test, um die Aufzeichnung zu beenden.")
    log_action("------------------------------------------------------------")

    # 1. Start der App über launch.ps1 im Hintergrund
    log_action("[1/3] Starte App über launch.ps1...")
    project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    
    process = subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "launch.ps1"],
        cwd=project_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    log_action(f"  PowerShell Launcher gestartet (PID: {process.pid})")

    # Warte bis das Hauptfenster bereit ist (maximal 25 Sekunden)
    log_action("  Warte auf Erscheinen des Hauptfensters 'PB Studio AMD'...")
    for attempt in range(25):
        time.sleep(1.0)
        pb_studio_hwnd = user32.FindWindowW(None, "PB Studio AMD")
        if pb_studio_hwnd:
            log_action(f"  Hauptfenster gefunden! HWND: {pb_studio_hwnd}")
            break
    
    if not pb_studio_hwnd:
        log_action("  [ABORT] Hauptfenster wurde nicht gefunden!")
        process.terminate()
        sys.exit(1)

    # Fenster wiederherstellen und in den Vordergrund bringen
    user32.ShowWindow(pb_studio_hwnd, 9)  # SW_RESTORE
    time.sleep(0.5)
    user32.SetForegroundWindow(pb_studio_hwnd)
    time.sleep(1.5)

    # 2. Verbindung mit pywinauto herstellen für Element-Auflösung
    log_action("[2/3] Verbinde UIA-Schnittstelle...")
    try:
        app = Application(backend="uia").connect(title_re=".*PB Studio.*", timeout=15)
        pywinauto_win = app.window(title_re=".*PB Studio.*")
        pywinauto_win.wait("visible", timeout=5)
        log_action("  UIA-Schnittstelle verbunden.")
    except Exception as e:
        log_action(f"  [WARNUNG] UIA-Verbindung fehlgeschlagen (Elementdetails evtl. eingeschränkt): {e}")

    # 3. Polling Loop starten (blockiert den Thread)
    log_action("[3/3] Registriere Maus-Protokollierung...")
    start_polling_loop()

    # Nach dem Schließen: aufräumen
    log_action("\n[Cleanup] Räume Systemressourcen auf...")
    if process.poll() is None:
        process.terminate()
        
    log_action("============================================================")
    log_action("PB STUDIO MANUAL TEST CLICK LOGGER COMPLETED")
    log_action("============================================================")

if __name__ == "__main__":
    main()
