"""
Director Widget - Smart Director Steuerung.

Hier kann der User die Timeline-Generierung konfigurieren und starten.
Nutzt den PacingSmartDirector aus pacing/smart_director.py.
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QGroupBox, QFormLayout, QComboBox, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal

logger = logging.getLogger(__name__)


class DirectorWidget(QWidget):
    """Smart Director Tab - Timeline-Generierung."""
    
    generateRequested = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header
        title = QLabel("Smart Director")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        subtitle = QLabel("Automatische Timeline-Generierung mit KI-gesteuertem Pacing")
        subtitle.setStyleSheet("font-size: 13px; color: #888;")
        layout.addWidget(subtitle)
        
        # Pacing Config
        pacing_group = QGroupBox("Pacing-Einstellungen")
        pacing_layout = QFormLayout()
        
        # Energy Sensitivity
        self.energy_slider = QSlider(Qt.Orientation.Horizontal)
        self.energy_slider.setRange(0, 100)
        self.energy_slider.setValue(50)
        self.energy_label = QLabel("50%")
        self.energy_slider.valueChanged.connect(
            lambda v: self.energy_label.setText(f"{v}%"))
        energy_row = QHBoxLayout()
        energy_row.addWidget(self.energy_slider)
        energy_row.addWidget(self.energy_label)
        pacing_layout.addRow("Energy Sensitivity:", energy_row)
        
        # Visual Flow
        self.flow_slider = QSlider(Qt.Orientation.Horizontal)
        self.flow_slider.setRange(0, 100)
        self.flow_slider.setValue(50)
        self.flow_label = QLabel("50%")
        self.flow_slider.valueChanged.connect(
            lambda v: self.flow_label.setText(f"{v}%"))
        flow_row = QHBoxLayout()
        flow_row.addWidget(self.flow_slider)
        flow_row.addWidget(self.flow_label)
        pacing_layout.addRow("Visual Flow:", flow_row)
        
        # Min Clip Length
        self.min_clip_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_clip_slider.setRange(3, 50)  # 0.3s bis 5.0s
        self.min_clip_slider.setValue(10)
        self.min_clip_label = QLabel("1.0s")
        self.min_clip_slider.valueChanged.connect(
            lambda v: self.min_clip_label.setText(f"{v/10:.1f}s"))
        clip_row = QHBoxLayout()
        clip_row.addWidget(self.min_clip_slider)
        clip_row.addWidget(self.min_clip_label)
        pacing_layout.addRow("Min Clip-Länge:", clip_row)
        
        # Mood
        self.mood_combo = QComboBox()
        self.mood_combo.addItems([
            "energetic music video",
            "calm atmospheric",
            "dark moody cinematic",
            "bright colorful pop",
            "aggressive intense",
            "dreamy ethereal",
        ])
        pacing_layout.addRow("Stimmung:", self.mood_combo)
        
        pacing_group.setLayout(pacing_layout)
        layout.addWidget(pacing_group)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.generate_btn = QPushButton("Timeline generieren")
        self.generate_btn.setStyleSheet(
            "QPushButton { padding: 10px 30px; font-size: 14px; "
            "background-color: #007acc; color: white; border-radius: 5px; }"
        )
        self.generate_btn.clicked.connect(self._on_generate)
        btn_layout.addWidget(self.generate_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
    
    def _on_generate(self):
        config = {
            "energy_sensitivity": self.energy_slider.value(),
            "visual_flow": self.flow_slider.value(),
            "min_clip_length": self.min_clip_slider.value() / 10.0,
            "mood": self.mood_combo.currentText(),
        }
        self.generateRequested.emit(config)
