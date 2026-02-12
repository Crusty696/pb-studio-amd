import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QFrame, QSlider, QSpinBox,
                             QDoubleSpinBox, QGroupBox, QComboBox, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal

logger = logging.getLogger(__name__)

class GenerationWidget(QWidget):
    generateRequested = pyqtSignal(dict)  # Signal emits generation config

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header
        title = QLabel("Generation & Pacing")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)
        
        description = QLabel("Configure how the video is assembled. Adjust pacing and logic.")
        description.setStyleSheet("color: #cccccc; font-size: 14px;")
        layout.addWidget(description)

        # --- Basic Controls ---
        basic_group = QGroupBox("Basic Pacing Control")
        self._style_groupbox(basic_group)
        basic_layout = QVBoxLayout(basic_group)
        basic_layout.setSpacing(15)
        
        # Pacing Slider
        pacing_label_layout = QHBoxLayout()
        pacing_label_layout.addWidget(QLabel("Cut Frequency (Pacing)"))
        self.pacing_value_label = QLabel("Medium")
        self.pacing_value_label.setStyleSheet("color: #007acc; font-weight: bold;")
        pacing_label_layout.addWidget(self.pacing_value_label)
        pacing_label_layout.addStretch()
        
        basic_layout.addLayout(pacing_label_layout)
        
        self.pacing_slider = QSlider(Qt.Orientation.Horizontal)
        self.pacing_slider.setRange(1, 5) 
        self.pacing_slider.setValue(3)
        self.pacing_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.pacing_slider.valueChanged.connect(self._on_pacing_change)
        basic_layout.addWidget(self.pacing_slider)
        
        pacing_desc = QHBoxLayout()
        pacing_desc.addWidget(self._style_hint(QLabel("Slow (Cinematic)")))
        pacing_desc.addStretch()
        pacing_desc.addWidget(self._style_hint(QLabel("Fast (Hype)")))
        basic_layout.addLayout(pacing_desc)

        layout.addWidget(basic_group)

        # --- Advanced Controls ---
        # Toggle for Advanced
        self.chk_advanced = QCheckBox("Show Advanced Settings")
        self.chk_advanced.setStyleSheet("color: #cccccc; font-weight: bold;")
        self.chk_advanced.setChecked(False)
        self.chk_advanced.toggled.connect(self._toggle_advanced)
        layout.addWidget(self.chk_advanced)

        self.advanced_group = QGroupBox("Advanced Logic Engine")
        self._style_groupbox(self.advanced_group)
        adv_layout = QVBoxLayout(self.advanced_group)
        adv_layout.setSpacing(15)
        
        # 1. Rhythm Precision
        adv_layout.addWidget(QLabel("Rhythm Precision (Beat Snap)"))
        self.precision_slider = self._create_slider(1, 10, 8)
        adv_layout.addWidget(self.precision_slider)
        
        prec_desc = QHBoxLayout()
        prec_desc.addWidget(self._style_hint(QLabel("Loose")))
        prec_desc.addStretch()
        prec_desc.addWidget(self._style_hint(QLabel("Strict (On Beat)")))
        adv_layout.addLayout(prec_desc)

        # 2. Energy Reactivity
        adv_layout.addWidget(QLabel("Energy Reactivity"))
        self.energy_slider = self._create_slider(0, 10, 5)
        adv_layout.addWidget(self.energy_slider)
        
        energy_desc = QHBoxLayout()
        energy_desc.addWidget(self._style_hint(QLabel("Constant")))
        energy_desc.addStretch()
        energy_desc.addWidget(self._style_hint(QLabel("Dynamic (Reactive)")))
        adv_layout.addLayout(energy_desc)

        # 3. Chaos Factor
        adv_layout.addWidget(QLabel("Chaos / Variation Factor"))
        self.chaos_slider = self._create_slider(0, 10, 2)
        adv_layout.addWidget(self.chaos_slider)
        
        chaos_desc = QHBoxLayout()
        chaos_desc.addWidget(self._style_hint(QLabel("Linear")))
        chaos_desc.addStretch()
        chaos_desc.addWidget(self._style_hint(QLabel("Random / Glitch")))
        adv_layout.addLayout(chaos_desc)
        
        # 4. Clip Duration Constraints (Moved here or duplicated?)
        # Let's keep them here as detailed tuning.
        clip_layout = QHBoxLayout()
        
        # Min Length
        min_layout = QVBoxLayout()
        min_layout.addWidget(QLabel("Min Clip Length (sec)"))
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(0.5, 30.0)
        self.min_spin.setValue(2.0)
        self.min_spin.setSingleStep(0.5)
        min_layout.addWidget(self.min_spin)
        clip_layout.addLayout(min_layout)
        
        # Max Length
        max_layout = QVBoxLayout()
        max_layout.addWidget(QLabel("Max Clip Length (sec)"))
        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(1.0, 60.0)
        self.max_spin.setValue(8.0)
        self.max_spin.setSingleStep(0.5)
        max_layout.addWidget(self.max_spin)
        clip_layout.addLayout(max_layout)
        
        adv_layout.addLayout(clip_layout)

        layout.addWidget(self.advanced_group)
        self.advanced_group.setVisible(False) # Start hidden

        layout.addStretch()
        
        # Footer Action
        action_layout = QHBoxLayout()
        self.btn_generate = QPushButton("Generate Video Preview")
        self.btn_generate.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                font-size: 16px;
                padding: 15px 30px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0062a3;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #666666;
            }
        """)
        self.btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate.clicked.connect(self._on_generate_click)
        action_layout.addStretch()
        action_layout.addWidget(self.btn_generate)

        layout.addLayout(action_layout)

    def _style_groupbox(self, group):
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3e3e42;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #007acc;
            }
        """)

    def _style_hint(self, label):
        label.setStyleSheet("color: #666666; font-size: 11px;")
        return label
        
    def _create_slider(self, min_val, max_val, default):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        return slider

    def _on_pacing_change(self, value):
        labels = {1: "Very Slow", 2: "Slow", 3: "Medium", 4: "Fast", 5: "Very Fast"}
        self.pacing_value_label.setText(labels.get(value, "Medium"))
        
    def _toggle_advanced(self, checked):
        self.advanced_group.setVisible(checked)

    def _on_generate_click(self):
        """Collect configuration and emit signal for generation."""
        config = {
            "pacing": self.pacing_slider.value(),
            "precision": self.precision_slider.value() if hasattr(self, 'precision_slider') else 8,
            "energy": self.energy_slider.value() if hasattr(self, 'energy_slider') else 5,
            "chaos": self.chaos_slider.value() if hasattr(self, 'chaos_slider') else 2,
            "min_clip_length": self.min_spin.value() if hasattr(self, 'min_spin') else 2.0,
            "max_clip_length": self.max_spin.value() if hasattr(self, 'max_spin') else 8.0,
        }
        logger.info(f"Generation requested with config: {config}")
        self.generateRequested.emit(config)
