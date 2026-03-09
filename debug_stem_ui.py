import sys
import logging
import time
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QTextEdit
from PyQt6.QtCore import QThread, pyqtSignal, Qt

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Mock StemSeparator to isolate UI issues vs Backend issues
class MockStemSeparator:
    def separate(self, file_path):
        import time
        logger.info("Mock Separator: Starting work...")
        time.sleep(2) # Simulate work
        logger.info("Mock Separator: Done.")
        return {"stems": ["vocal.wav", "drums.wav"]}

# Real StemSeparator Import (Try/Except)
try:
    from src.pb_studio.audio.separator import StemSeparator
    HAS_REAL_BACKEND = True
except ImportError:
    HAS_REAL_BACKEND = False
    StemSeparator = MockStemSeparator # Fallback

import re

# Pattern to catch tqdm output: "  3%|...| 43/1279"
PROGRESS_PATTERN = re.compile(r"(\d+)%?\|.*\| (\d+)/(\d+)")

class LogProgressHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        try:
            msg = self.format(record)
            # Simulate real log message format if testing with mock
            # Real lib output: "  1%|          | 8/1279 [00:12<32:39,  1.54s/it]"
            match = PROGRESS_PATTERN.search(msg)
            if match:
                current = int(match.group(2))
                total = int(match.group(3))
                if total > 0:
                    percent = (current / total) * 100
                    self.callback(percent, msg)
        except Exception:
            pass 

class StemWorker(QThread):
    progress = pyqtSignal(str)
    progress_percent = pyqtSignal(float)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self._log_handler = None
        
    def _handle_log(self, pct, msg):
        self.progress_percent.emit(pct)

    def run(self):
        try:
            self.progress.emit("Initializing...")
            
            # Attach Handler
            target = logging.getLogger("audio_separator.separator.separator") # Real target
            # Also attach to local logger if using Mock
            local_target = logging.getLogger(__name__)
            
            self._log_handler = LogProgressHandler(self._handle_log)
            target.addHandler(self._log_handler)
            local_target.addHandler(self._log_handler)
            
            # Use real backend if available
            separator = StemSeparator()
            
            self.progress.emit("Separating (Heavy Task)...")
            res = separator.separate(self.file_path)
            
            self.finished.emit(res)
        except Exception as e:
            logger.error(f"Worker Error: {e}")
            self.error.emit(str(e))
        finally:
             if self._log_handler:
                logging.getLogger("audio_separator.separator.separator").removeHandler(self._log_handler)
                logging.getLogger(__name__).removeHandler(self._log_handler)

class DebugWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.resize(400, 300)
        layout = QVBoxLayout(self)
        
        self.label = QLabel("Status: Idle")
        self.label.setStyleSheet("font-size: 16px; font-weight: bold; color: blue;")
        layout.addWidget(self.label)
        
        self.btn = QPushButton("Start Separation")
        self.btn.clicked.connect(self.start_work)
        layout.addWidget(self.btn)
        
        self.log_view = QTextEdit()
        layout.addWidget(self.log_view)
        
        self.worker = None
        
        # Test File Path (Hardcoded for test)
        self.test_file = r"C:\Users\david\Videos\Music-Video_Clips\AV\Audio\Psy-Set\recording-2020-07-18-040817.wav"

    def log(self, text):
        self.log_view.append(text)
        print(text)

    def start_work(self):
        self.btn.setEnabled(False)
        self.label.setText("STARTING...")
        self.log("Button Clicked. Starting Thread.")
        
        self.worker = StemWorker(self.test_file)
        self.worker.progress.connect(self.update_status)
        self.worker.finished.connect(self.on_done)
        self.worker.error.connect(self.on_error)
        self.worker.start()
        
    def update_status(self, msg):
        self.log(f"Signal Received: {msg}")
        self.label.setText(msg)
        
    def on_done(self, res):
        self.log(f"Done! Result: {res}")
        self.label.setText("DONE ✅")
        self.btn.setEnabled(True)
        
    def on_error(self, err):
        self.log(f"Error: {err}")
        self.label.setText(f"ERROR: {err}")
        self.btn.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = DebugWindow()
    win.show()
    print(f"Backend Available: {HAS_REAL_BACKEND}")
    
    # Auto-start after 2 seconds
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(2000, win.start_work)
    
    # Auto-close after 60 seconds (timeout)
    QTimer.singleShot(60000, app.quit)
    
    sys.exit(app.exec())
