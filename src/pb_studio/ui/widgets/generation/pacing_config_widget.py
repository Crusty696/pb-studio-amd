"""
Pacing Configuration Widget for PB Studio AMD.

Provides controls for video pacing, rhythm, and cut timing.
"""

import logging
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QDoubleSpinBox, QGroupBox, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal

logger = logging.getLogger(__name__)


class PacingConfigWidget(QFrame):
    """
    Widget for configuring video pacing parameters.

    Signals:
        configChanged(dict): Emitted when any configuration value changes.
    """

    configChanged = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize the user interface."""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Header
        title = QLabel("Pacing Configuration")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        # --- Basic Pacing Group ---
        basic_group = QGroupBox("Basic Pacing")
        self._style_groupbox(basic_group)
        basic_layout = QVBoxLayout(basic_group)
        basic_layout.setSpacing(12)

        # Pacing Level Slider (1-5)
        pacing_header = QHBoxLayout()
        pacing_header.addWidget(QLabel("Pacing Level"))
        self.pacing_value_label = QLabel("Medium")
        self.pacing_value_label.setStyleSheet("color: #007acc; font-weight: bold;")
        pacing_header.addWidget(self.pacing_value_label)
        pacing_header.addStretch()
        basic_layout.addLayout(pacing_header)

        self.pacing_slider = QSlider(Qt.Orientation.Horizontal)
        self.pacing_slider.setRange(1, 5)
        self.pacing_slider.setValue(3)
        self.pacing_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.pacing_slider.setTickInterval(1)
        basic_layout.addWidget(self.pacing_slider)

        pacing_labels = QHBoxLayout()
        pacing_labels.addWidget(self._hint_label("Slow (Cinematic)"))
        pacing_labels.addStretch()
        pacing_labels.addWidget(self._hint_label("Fast (Hype)"))
        basic_layout.addLayout(pacing_labels)

        layout.addWidget(basic_group)

        # --- Clip Duration Group ---
        duration_group = QGroupBox("Clip Duration")
        self._style_groupbox(duration_group)
        duration_layout = QHBoxLayout(duration_group)
        duration_layout.setSpacing(20)

        # Min Clip Duration (0.5-5s)
        min_layout = QVBoxLayout()
        min_layout.addWidget(QLabel("Min Duration (s)"))
        self.min_duration_spin = QDoubleSpinBox()
        self.min_duration_spin.setRange(0.5, 5.0)
        self.min_duration_spin.setValue(2.0)
        self.min_duration_spin.setSingleStep(0.5)
        self.min_duration_spin.setDecimals(1)
        self._style_spinbox(self.min_duration_spin)
        min_layout.addWidget(self.min_duration_spin)
        duration_layout.addLayout(min_layout)

        # Max Clip Duration (2-15s)
        max_layout = QVBoxLayout()
        max_layout.addWidget(QLabel("Max Duration (s)"))
        self.max_duration_spin = QDoubleSpinBox()
        self.max_duration_spin.setRange(2.0, 15.0)
        self.max_duration_spin.setValue(8.0)
        self.max_duration_spin.setSingleStep(0.5)
        self.max_duration_spin.setDecimals(1)
        self._style_spinbox(self.max_duration_spin)
        max_layout.addWidget(self.max_duration_spin)
        duration_layout.addLayout(max_layout)

        layout.addWidget(duration_group)

        # --- Advanced Settings Toggle ---
        self.advanced_checkbox = QCheckBox("Show Advanced Settings")
        self.advanced_checkbox.setStyleSheet("color: #cccccc; font-weight: bold;")
        self.advanced_checkbox.setChecked(False)
        self.advanced_checkbox.toggled.connect(self._toggle_advanced)
        layout.addWidget(self.advanced_checkbox)

        # --- Advanced Group ---
        self.advanced_group = QGroupBox("Advanced Rhythm Settings")
        self._style_groupbox(self.advanced_group)
        adv_layout = QVBoxLayout(self.advanced_group)
        adv_layout.setSpacing(12)

        # Beat Precision Slider (1-10)
        adv_layout.addWidget(QLabel("Beat Precision"))
        self.beat_precision_slider = self._create_slider(1, 10, 8)
        adv_layout.addWidget(self.beat_precision_slider)
        precision_labels = QHBoxLayout()
        precision_labels.addWidget(self._hint_label("Loose"))
        precision_labels.addStretch()
        precision_labels.addWidget(self._hint_label("Strict (On Beat)"))
        adv_layout.addLayout(precision_labels)

        # Energy Reactivity Slider (0-10)
        adv_layout.addWidget(QLabel("Energy Reactivity"))
        self.energy_slider = self._create_slider(0, 10, 5)
        adv_layout.addWidget(self.energy_slider)
        energy_labels = QHBoxLayout()
        energy_labels.addWidget(self._hint_label("Constant"))
        energy_labels.addStretch()
        energy_labels.addWidget(self._hint_label("Dynamic (Reactive)"))
        adv_layout.addLayout(energy_labels)

        # Chaos Factor Slider (0-10)
        adv_layout.addWidget(QLabel("Chaos / Variation Factor"))
        self.chaos_slider = self._create_slider(0, 10, 2)
        adv_layout.addWidget(self.chaos_slider)
        chaos_labels = QHBoxLayout()
        chaos_labels.addWidget(self._hint_label("Linear"))
        chaos_labels.addStretch()
        chaos_labels.addWidget(self._hint_label("Random / Glitch"))
        adv_layout.addLayout(chaos_labels)

        layout.addWidget(self.advanced_group)
        self.advanced_group.setVisible(False)

        layout.addStretch()

    def _connect_signals(self):
        """Connect all widget signals to emit configChanged."""
        self.pacing_slider.valueChanged.connect(self._on_pacing_change)
        self.min_duration_spin.valueChanged.connect(self._emit_config)
        self.max_duration_spin.valueChanged.connect(self._emit_config)
        self.beat_precision_slider.valueChanged.connect(self._emit_config)
        self.energy_slider.valueChanged.connect(self._emit_config)
        self.chaos_slider.valueChanged.connect(self._emit_config)

    def _on_pacing_change(self, value: int):
        """Update pacing label and emit config."""
        labels = {
            1: "Very Slow",
            2: "Slow",
            3: "Medium",
            4: "Fast",
            5: "Very Fast"
        }
        self.pacing_value_label.setText(labels.get(value, "Medium"))
        self._emit_config()

    def _toggle_advanced(self, checked: bool):
        """Show or hide advanced settings."""
        self.advanced_group.setVisible(checked)

    def _emit_config(self):
        """Emit the current configuration."""
        config = self.get_config()
        logger.debug(f"Pacing config changed: {config}")
        self.configChanged.emit(config)

    def get_config(self) -> dict:
        """
        Get the current pacing configuration.

        Returns:
            dict with all pacing parameters
        """
        return {
            "pacing": self.pacing_slider.value(),
            "min_dur": self.min_duration_spin.value(),
            "max_dur": self.max_duration_spin.value(),
            "precision": self.beat_precision_slider.value(),
            "energy_react": self.energy_slider.value(),
            "chaos": self.chaos_slider.value(),
        }

    def set_config(self, config: dict):
        """
        Set the pacing configuration from a dict.

        Args:
            config: dict with pacing parameters
        """
        # Block signals during update to avoid multiple emissions
        self.blockSignals(True)

        if "pacing" in config:
            self.pacing_slider.setValue(config["pacing"])
            self._on_pacing_change(config["pacing"])
        if "min_dur" in config:
            self.min_duration_spin.setValue(config["min_dur"])
        if "max_dur" in config:
            self.max_duration_spin.setValue(config["max_dur"])
        if "precision" in config:
            self.beat_precision_slider.setValue(config["precision"])
        if "energy_react" in config:
            self.energy_slider.setValue(config["energy_react"])
        if "chaos" in config:
            self.chaos_slider.setValue(config["chaos"])

        self.blockSignals(False)
        self._emit_config()

    def _create_slider(self, min_val: int, max_val: int, default: int) -> QSlider:
        """Create a horizontal slider with given range."""
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        return slider

    def _style_groupbox(self, group: QGroupBox):
        """Apply consistent styling to group boxes."""
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

    def _style_spinbox(self, spinbox: QDoubleSpinBox):
        """Apply consistent styling to spin boxes."""
        spinbox.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                border-radius: 3px;
                padding: 5px;
                color: #ffffff;
            }
            QDoubleSpinBox:focus {
                border-color: #007acc;
            }
        """)

    def _hint_label(self, text: str) -> QLabel:
        """Create a small hint label."""
        label = QLabel(text)
        label.setStyleSheet("color: #666666; font-size: 11px;")
        return label
