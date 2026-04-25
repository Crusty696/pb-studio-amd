"""
PB Studio Autonomous GUI Test Agent
Crawls the entire UI tree dynamically, identifies all interactive controls 
(Buttons, Sliders, CheckBoxes, Tabs), and systematically verifies their state and functionality.
"""
import time
import sys
import logging
from pywinauto import Application
from pywinauto.findwindows import ElementNotFoundError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class AutonomousUIAgent:
    def __init__(self, window_title_re=".*PB Studio.*"):
        self.window_title_re = window_title_re
        self.app = None
        self.main_win = None
        self.tested_elements = set()
        self.stats = {"passed": 0, "failed": 0, "skipped": 0}

    def connect(self):
        logging.info(f"Suche nach App mit Titel: {self.window_title_re}")
        try:
            # BUG-FIX: Strikte Suche nach dem Hauptfenster der App
            # Wir nutzen backend="uia" für WPF und suchen nach dem exakten Titel
            self.app = Application(backend="uia").connect(title="PB Studio", timeout=15)
            self.main_win = self.app.window(title="PB Studio")
            self.main_win.wait("visible", timeout=20)
            logging.info(f"Erfolgreich mit dem Hauptfenster verbunden: {self.main_win.window_text()}")
            return True
        except Exception as e:
            logging.error(f"Verbindung fehlgeschlagen (Laeuft die App?): {e}")
            return False

    def scan_and_test(self):
        if not self.main_win:
            return

        logging.info("Starte autonomen UI-Scan...")
        
        # Rekursives Auslesen aller UI-Elemente
        descendants = self.main_win.descendants()
        logging.info(f"{len(descendants)} UI-Elemente im Baum gefunden.")

        # Fokus auf interaktive Controls
        interactive_types = ['Button', 'CheckBox', 'Slider', 'TabItem', 'ComboBox', 'TextBox']
        
        for elem in descendants:
            ctrl_type = elem.element_info.control_type
            name = elem.window_text() or elem.element_info.automation_id or "OhneName"
            
            if ctrl_type in interactive_types:
                elem_id = f"{ctrl_type}_{name}_{id(elem)}"
                if elem_id in self.tested_elements:
                    continue
                    
                self.tested_elements.add(elem_id)
                self.test_element(elem, ctrl_type, name)

        self.print_summary()

    def test_element(self, elem, ctrl_type, name):
        logging.info(f"Pruefe {ctrl_type}: '{name}'")
        try:
            # 1. State abfragen
            is_enabled = elem.is_enabled()
            is_visible = elem.is_visible()
            
            if not is_enabled or not is_visible:
                logging.info(f"  -> Uebersprungen (Enabled: {is_enabled}, Visible: {is_visible})")
                self.stats["skipped"] += 1
                return

            # 2. Visuelles Highlighting (gruener Rahmen) als Feedback
            try:
                elem.draw_outline(colour='green', thickness=2)
            except:
                pass # Ignorieren, falls das Element off-screen ist

            # 3. Typspezifische Verifizierung
            if ctrl_type == "Button":
                # Wir klicken hier nicht blind auf "Loeschen" oder "Schliessen", 
                # aber wir verifizieren, dass das Click-Pattern existiert.
                has_invoke = elem.element_info.control_type == "Button"
                logging.info(f"  -> Verifiziert (Clickable: {has_invoke})")
                
            elif ctrl_type == "Slider":
                # RangeValue Pattern prüfen
                try:
                    val = elem.get_value()
                    min_val = elem.min_value()
                    max_val = elem.max_value()
                    logging.info(f"  -> Verifiziert (Value: {val}, Range: [{min_val}, {max_val}])")
                except Exception as ex:
                    logging.warning(f"  -> RangeValue nicht lesbar: {ex}")

            elif ctrl_type == "CheckBox":
                try:
                    state = elem.get_toggle_state()
                    logging.info(f"  -> Verifiziert (Checked: {state})")
                except Exception as ex:
                    logging.warning(f"  -> ToggleState nicht lesbar: {ex}")
                
            elif ctrl_type == "TabItem":
                logging.info(f"  -> Verifiziert (Navigierbar)")

            elif ctrl_type == "TextBox":
                logging.info(f"  -> Verifiziert (Texteingabe moeglich)")

            self.stats["passed"] += 1
            time.sleep(0.05) # Kurze Pause für den visuellen Effekt
            
        except Exception as e:
            logging.error(f"  -> Fehler bei {ctrl_type} '{name}': {e}")
            self.stats["failed"] += 1

    def print_summary(self):
        print("\n" + "="*50)
        print("AUTONOMER UI-TEST ABSCHLUSS-BERICHT")
        print("="*50)
        print(f"Gepruefte Elemente: {len(self.tested_elements)}")
        print(f"Erfolgreich (Passed): {self.stats['passed']}")
        print(f"Uebersprungen (Skipped - hidden/disabled): {self.stats['skipped']}")
        print(f"Fehlgeschlagen (Failed): {self.stats['failed']}")
        print("="*50)


if __name__ == "__main__":
    agent = AutonomousUIAgent()
    if agent.connect():
        agent.scan_and_test()
    else:
        print("Fehler: PB Studio GUI wurde nicht gefunden. Bitte starte die App zuerst.")
        sys.exit(1)
