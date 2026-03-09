"""
Production Widget - Finale Videoausgabe und Export.

Hier kann der User:
- Timeline als FFmpeg Concat exportieren
- Timeline als DaVinci Resolve EDL exportieren
- Finales Video rendern
- Preview generieren
"""

import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QComboBox, QProgressBar,
    QFileDialog, QLineEdit
)
from PyQt6.QtCore import pyqtSignal

logger = logging.getLogger(__name__)


class ProductionWidget(QWidget):
    """Production Tab - Export und Rendering."""
    
    renderRequested = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header
        title = QLabel("Production")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        subtitle = QLabel("Export und Rendering der finalen Timeline")
        subtitle.setStyleSheet("font-size: 13px; color: #888;")
        layout.addWidget(subtitle)
        
        # Export-Optionen
        export_group = QGroupBox("Export-Format")
        export_layout = QFormLayout()
        
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "MP4 (H.264 AMF)",
            "MP4 (H.265/HEVC AMF)",
            "MP4 (AV1 AMF)",
            "FFmpeg Concat File",
            "DaVinci Resolve EDL",
        ])
        export_layout.addRow("Format:", self.format_combo)
        
        # Auflösung
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems([
            "1920x1080 (Full HD)",
            "2560x1440 (2K)",
            "3840x2160 (4K)",
            "Original beibehalten",
        ])
        export_layout.addRow("Auflösung:", self.resolution_combo)
        
        # Framerate
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["25", "30", "50", "60"])
        export_layout.addRow("Framerate:", self.fps_combo)
        
        # Ausgabepfad
        path_row = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Ausgabedatei wählen...")
        path_row.addWidget(self.output_path)
        
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(40)
        browse_btn.clicked.connect(self._on_browse_output)
        path_row.addWidget(browse_btn)
        export_layout.addRow("Ausgabe:", path_row)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        export_btn = QPushButton("Exportieren")
        export_btn.setStyleSheet(
            "QPushButton { padding: 10px 30px; font-size: 14px; "
            "background-color: #28a745; color: white; border-radius: 5px; }"
        )
        export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(export_btn)
        
        render_btn = QPushButton("Rendern")
        render_btn.setStyleSheet(
            "QPushButton { padding: 10px 30px; font-size: 14px; "
            "background-color: #007acc; color: white; border-radius: 5px; }"
        )
        render_btn.clicked.connect(self._on_render)
        btn_layout.addWidget(render_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
    
    def _on_browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Ausgabedatei wählen", "",
            "Video (*.mp4);;EDL (*.edl);;Concat (*.txt);;All (*)"
        )
        if path:
            self.output_path.setText(path)
    
    def _on_export(self):
        """Exportiert die Timeline."""
        config = self._get_config()
        config["action"] = "export"
        logger.info(f"Export gestartet: {config}")
        self.renderRequested.emit(config)
    
    def _on_render(self):
        """Rendert das finale Video."""
        config = self._get_config()
        config["action"] = "render"
        logger.info(f"Render gestartet: {config}")
        self.renderRequested.emit(config)
    
    def _get_config(self) -> dict:
        return {
            "format": self.format_combo.currentText(),
            "resolution": self.resolution_combo.currentText(),
            "fps": int(self.fps_combo.currentText()),
            "output_path": self.output_path.text(),
        }
