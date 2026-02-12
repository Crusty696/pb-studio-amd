import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QFrame, QFormLayout,
                             QGroupBox, QFileDialog)
from PyQt6.QtCore import Qt

from src.pb_studio.config_manager import ConfigManager
from src.pb_studio.core.system_monitor import SystemMonitor

logger = logging.getLogger(__name__)

class SettingsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.monitor = SystemMonitor()
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # System Info Group
        sys_group = QGroupBox("System Information")
        sys_layout = QFormLayout(sys_group)
        
        # GPU Info
        try:
            stats = self.monitor.get_stats()
            gpu_name = self.monitor.gpu_sensor.Name if self.monitor.gpu_sensor else "Not detected"
            vram_total = stats.get("gpu_memory_total", 0)
            gpu_info = f"{gpu_name} ({vram_total:.0f} MB VRAM)"
        except Exception:
            gpu_info = "Not available"
        
        sys_layout.addRow("GPU:", QLabel(gpu_info))
        sys_layout.addRow("Python:", QLabel("3.11.9"))
        sys_layout.addRow("Backend:", QLabel("DirectML (ONNX Runtime)"))
        
        layout.addWidget(sys_group)

        # Paths Group
        paths_group = QGroupBox("Paths")
        paths_layout = QFormLayout(paths_group)
        
        self.models_path = QLineEdit()
        self.models_path.setPlaceholderText("./models")
        models_browse = QPushButton("Browse...")
        models_browse.clicked.connect(lambda: self._browse_dir(self.models_path))
        models_row = QHBoxLayout()
        models_row.addWidget(self.models_path)
        models_row.addWidget(models_browse)
        paths_layout.addRow("Models Directory:", models_row)
        
        self.temp_path = QLineEdit()
        self.temp_path.setPlaceholderText("./temp")
        temp_browse = QPushButton("Browse...")
        temp_browse.clicked.connect(lambda: self._browse_dir(self.temp_path))
        temp_row = QHBoxLayout()
        temp_row.addWidget(self.temp_path)
        temp_row.addWidget(temp_browse)
        paths_layout.addRow("Temp Directory:", temp_row)
        
        layout.addWidget(paths_group)

        # Save Button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()

    def _load_settings(self):
        paths = self.config.get("paths", {})
        self.models_path.setText(paths.get("models_dir", "./models"))
        self.temp_path.setText(paths.get("temp_dir", "./temp"))

    def _save_settings(self):
        # Bestehende Pfade beibehalten (ffmpeg_bin, lhm_lib, etc.)
        existing_paths = self.config.get("paths", {}).copy()
        existing_paths["models_dir"] = self.models_path.text() or "./models"
        existing_paths["temp_dir"] = self.temp_path.text() or "./temp"
        self.config.set("paths", existing_paths)
        self.config.save_config()
        logger.info("Settings saved.")

    def _browse_dir(self, line_edit: QLineEdit):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_path:
            line_edit.setText(dir_path)
