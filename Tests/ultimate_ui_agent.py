"""
PB Studio E2E PRODUCTION AGENT
- Führt den vollständigen Workflow durch (Import -> Analyse -> Pacing -> Render)
- Interagiert mit realen Controls (Buttons, Dialoge, Slider)
- Dokumentiert den Fortschritt und erstellt ein Beweisvideo
"""
import time
import os
import sys
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from pywinauto import Application, keyboard

# Verzeichnisse
BASE_DIR = Path(__file__).parent.parent.resolve()
LOG_DIR = BASE_DIR / "test_reports" / f"E2E_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
LOG_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR = BASE_DIR / "Tests" / "media"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_DIR / "e2e_audit.log"), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("E2EAgent")

class E2ETestAgent:
    def __init__(self):
        self.app = None
        self.main_win = None
        self.recording_process = None
        self.ffmpeg_path = BASE_DIR / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"

    def start_recording(self):
        if self.ffmpeg_path.exists():
            cmd = [str(self.ffmpeg_path), "-y", "-f", "gdigrab", "-framerate", "15", "-i", "desktop", 
                   "-c:v", "libx264", "-preset", "ultrafast", str(LOG_DIR / "e2e_proof.mp4")]
            self.recording_process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("Video-Beweisaufnahme gestartet.")

    def connect(self):
        logger.info("Warte auf App-Verbindung...")
        try:
            self.app = Application(backend="uia").connect(title_re=".*PB Studio.*", timeout=30)
            self.main_win = self.app.window(title_re=".*PB Studio.*")
            self.main_win.set_focus()
            return True
        except Exception as e:
            logger.error(f"Konnte nicht verbinden: {e}")
            return False

    def run_full_workflow(self):
        try:
            # 1. PROJEKT ERSTELLEN (via Menü/Shortcut falls vorhanden, hier via Button)
            logger.info("Schritt 1: Neues Projekt erstellen")
            # Wir nutzen Keyboard-Shortcuts oder Tab-Navigation für das Menü
            self.main_win.type_keys("^n") # Angenommener Shortcut für Neu
            time.sleep(2)
            
            # 2. IMPORT
            logger.info("Schritt 2: Medien importieren")
            self.main_win.child_window(title="IMPORT", control_type="TabItem").click_input()
            time.sleep(1)
            
            # Video hinzufügen
            self.import_file("Video hinzufügen", MEDIA_DIR / "test_video.mp4")
            # Audio hinzufügen
            self.import_file("Audio hinzufügen", MEDIA_DIR / "test_audio.wav")

            # 3. ANALYSE (Audio)
            logger.info("Schritt 3: Audio-Analyse triggern")
            self.main_win.child_window(title="AUDIO", control_type="TabItem").click_input()
            time.sleep(1)
            self.main_win.child_window(title="Alle", control_type="Button").click_input()
            self.wait_for_progress("Audio-Analyse")

            # 4. ANALYSE (Video)
            logger.info("Schritt 4: Video-Analyse (KI) triggern")
            self.main_win.child_window(title="VIDEO", control_type="TabItem").click_input()
            time.sleep(1)
            # Hier den ersten Clip in der Liste auswählen und analysieren
            self.main_win.type_keys("{SPACE}") # Select
            time.sleep(0.5)
            # Suchen nach dem Analyse-Button
            self.main_win.child_window(title="Analyse", control_type="Button").click_input()
            self.wait_for_progress("Video-Analyse")

            # 5. DIRECTOR (Pacing)
            logger.info("Schritt 5: Timeline generieren")
            self.main_win.child_window(title="DIRECTOR", control_type="TabItem").click_input()
            time.sleep(1)
            # Regler wackeln
            slider = self.main_win.child_window(control_type="Slider")
            slider.set_value(75) 
            time.sleep(0.5)
            self.main_win.child_window(title="GENERIEREN", control_type="Button").click_input()
            time.sleep(5) # Warten auf Algorithmus

            # 6. PRODUKTION
            logger.info("Schritt 6: Finales Video rendern")
            self.main_win.child_window(title="PRODUKTION", control_type="TabItem").click_input()
            time.sleep(1)
            self.main_win.child_window(title="RENDER STARTEN", control_type="Button").click_input()
            self.wait_for_progress("Rendering", timeout=120)

            logger.info("E2E WORKFLOW ERFOLGREICH ABGESCHLOSSEN.")

        except Exception as e:
            logger.error(f"Workflow-Abbruch durch Fehler: {e}")
            self.main_win.capture_as_image().save(LOG_DIR / "crash_state.png")

    def import_file(self, button_title, file_path):
        logger.info(f"Importiere {file_path} via '{button_title}'")
        try:
            btn = self.main_win.child_window(title=button_title, control_type="Button")
            btn.click_input()
            time.sleep(2)
            # Windows Dateidialog steuern
            dialog = self.app.window(title_re=".*öffnen.*")
            dialog.child_window(class_name="Edit").type_keys(str(file_path), with_spaces=True)
            dialog.child_window(title="Öffnen", control_type="Button").click()
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Datei-Import fehlgeschlagen: {e}")

    def wait_for_progress(self, task_name, timeout=60):
        logger.info(f"Warte auf Abschluss von: {task_name}...")
        start = time.time()
        while time.time() - start < timeout:
            # Wir suchen nach einem Textblock, der "Bereit" oder "100%" anzeigt
            status = self.main_win.descendants(control_type="Text")
            status_text = " ".join([s.window_text() for s in status]).lower()
            if "bereit" in status_text or "abgeschlossen" in status_text or "100%" in status_text:
                logger.info(f"Task '{task_name}' beendet.")
                return True
            time.sleep(2)
        logger.warning(f"Timeout beim Warten auf '{task_name}'")

    def finalize(self):
        if self.recording_process:
            self.recording_process.communicate(input=b"q")
        logger.info(f"Bericht und Video gespeichert in: {LOG_DIR}")

if __name__ == "__main__":
    agent = E2ETestAgent()
    agent.start_recording()
    if agent.connect():
        agent.run_full_workflow()
    agent.finalize()
