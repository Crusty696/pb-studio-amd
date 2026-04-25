import time
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from pywinauto import Application

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ViewTester")

BASE_DIR = Path(__file__).parent.resolve()
SCREENSHOT_DIR = BASE_DIR / "test_reports" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

class ViewTester:
    def __init__(self):
        self.app = None
        self.main_win = None
        self.exe_path = BASE_DIR / "PBStudio.UI" / "bin" / "Release" / "net9.0-windows" / "PBStudio.UI.exe"

    def start_app(self):
        logger.info(f"Starting app: {self.exe_path}")
        self.app = Application(backend="uia").start(str(self.exe_path))
        time.sleep(10) # Wait for startup
        
        try:
            self.main_win = self.app.window(title_re=".*PB Studio.*")
            self.main_win.set_focus()
            logger.info("Main window connected.")
            return True
        except Exception as e:
            logger.error(f"Could not connect to main window: {e}")
            return False

    def test_views(self):
        # List of tabs to click
        tabs = ["AUDIO", "VIDEO", "IMPORT", "ANCHORS", "DIRECTOR", "TIMELINE", "PRODUKTION", "SETTINGS"]
        
        results = {}
        
        # Take screenshot of MainWindow initial state
        self.take_screenshot("00_MainWindow_Initial")
        
        for tab_name in tabs:
            logger.info(f"Testing view: {tab_name}")
            try:
                tab_item = self.main_win.child_window(title=tab_name, control_type="TabItem")
                tab_item.click_input()
                time.sleep(2) # Wait for view to load/transition
                
                self.take_screenshot(f"View_{tab_name}")
                results[tab_name] = "PASS"
                logger.info(f"View {tab_name} OK.")
            except Exception as e:
                logger.error(f"Failed to test view {tab_name}: {e}")
                results[tab_name] = f"FAIL: {e}"
        
        return results

    def take_screenshot(self, name):
        path = SCREENSHOT_DIR / f"{name}.png"
        try:
            self.main_win.capture_as_image().save(path)
            logger.info(f"Screenshot saved: {path}")
        except Exception as e:
            logger.warning(f"Failed to take screenshot {name}: {e}")

    def stop_app(self):
        if self.app:
            logger.info("Closing app...")
            self.app.kill()

if __name__ == "__main__":
    tester = ViewTester()
    if tester.start_app():
        results = tester.test_views()
        logger.info("Test Results:")
        for view, status in results.items():
            logger.info(f"  {view}: {status}")
    tester.stop_app()
