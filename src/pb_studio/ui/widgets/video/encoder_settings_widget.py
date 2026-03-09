"""
Encoder Settings Widget for PB Studio AMD.

Provides UI controls for configuring AMD AMF video encoder settings.
"""

import logging
from typing import Dict, Any

from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QCheckBox,
    QGroupBox,
    QFormLayout,
)
from PyQt6.QtCore import pyqtSignal

# Import encoder utilities
from pb_studio.video.encoder_utils import get_encoder_info, check_amf_available

logger = logging.getLogger(__name__)


class EncoderSettingsWidget(QFrame):
    """
    Widget for configuring video encoder settings.

    Features:
    - Codec selection (h264_amf, hevc_amf, av1_amf, libx264)
    - Quality preset (speed, balanced, quality)
    - Output resolution (1080p, 720p, 4K, Original)
    - Hardware encoding toggle

    Automatically detects AMD AMF availability and shows appropriate options.

    Signals:
        settingsChanged(dict): Emitted when any setting changes
    """

    settingsChanged = pyqtSignal(dict)

    # Codec definitions
    CODECS = {
        "h264_amf": ("H.264 (AMD AMF)", True),
        "hevc_amf": ("H.265/HEVC (AMD AMF)", True),
        "av1_amf": ("AV1 (AMD AMF - RDNA3+)", True),
        "libx264": ("H.264 (Software)", False),
        "libx265": ("H.265/HEVC (Software)", False),
        "libsvtav1": ("AV1 (Software)", False),
    }

    # Quality presets
    QUALITY_PRESETS = {
        "speed": "Speed (Fast encoding, lower quality)",
        "balanced": "Balanced (Recommended)",
        "quality": "Quality (Slow encoding, best quality)",
    }

    # Resolution presets
    RESOLUTIONS = {
        "original": "Original",
        "4k": "4K (3840x2160)",
        "1440p": "1440p (2560x1440)",
        "1080p": "1080p (1920x1080)",
        "720p": "720p (1280x720)",
        "480p": "480p (854x480)",
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        # Check encoder availability
        self._encoder_info = get_encoder_info()
        self._amf_available = self._encoder_info.get("amf_available", False)
        self._av1_available = self._encoder_info.get("av1_amf_available", False)

        self._setup_ui()
        self._connect_signals()
        self._update_codec_list()

    def _setup_ui(self):
        """Set up the widget UI."""
        self.setStyleSheet("""
            EncoderSettingsWidget {
                background-color: #1e1e1e;
                border: none;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: #ffffff;
            }
            QComboBox {
                background-color: #3c3c3c;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 6px 12px;
                color: #ffffff;
                min-width: 200px;
            }
            QComboBox:hover {
                border-color: #007acc;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #888888;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                selection-background-color: #094770;
            }
            QCheckBox {
                color: #ffffff;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #3e3e42;
                border-radius: 3px;
                background-color: #3c3c3c;
            }
            QCheckBox::indicator:checked {
                background-color: #007acc;
                border-color: #007acc;
            }
            QLabel {
                color: #cccccc;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        # Encoder status indicator
        self._status_frame = self._create_status_frame()
        main_layout.addWidget(self._status_frame)

        # Encoding settings group
        encoder_group = QGroupBox("Encoding Settings")
        encoder_layout = QFormLayout(encoder_group)
        encoder_layout.setSpacing(12)
        encoder_layout.setContentsMargins(12, 16, 12, 12)

        # Codec selection
        self._codec_combo = QComboBox()
        encoder_layout.addRow("Codec:", self._codec_combo)

        # Quality preset
        self._quality_combo = QComboBox()
        for key, label in self.QUALITY_PRESETS.items():
            self._quality_combo.addItem(label, key)
        self._quality_combo.setCurrentIndex(1)  # Default: balanced
        encoder_layout.addRow("Quality:", self._quality_combo)

        # Resolution
        self._resolution_combo = QComboBox()
        for key, label in self.RESOLUTIONS.items():
            self._resolution_combo.addItem(label, key)
        self._resolution_combo.setCurrentIndex(3)  # Default: 1080p
        encoder_layout.addRow("Resolution:", self._resolution_combo)

        # Hardware encoding toggle
        self._hardware_checkbox = QCheckBox("Use Hardware Encoding (AMD AMF)")
        self._hardware_checkbox.setChecked(self._amf_available)
        self._hardware_checkbox.setEnabled(self._amf_available)
        encoder_layout.addRow("", self._hardware_checkbox)

        main_layout.addWidget(encoder_group)

        # Additional info label
        self._info_label = QLabel()
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet("color: #888888; font-size: 11px; padding: 8px;")
        main_layout.addWidget(self._info_label)

        main_layout.addStretch()

        # Update info text
        self._update_info_label()

    def _create_status_frame(self) -> QFrame:
        """Create the encoder status indicator frame."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 8px;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)

        # Status icon (colored circle)
        self._status_icon = QLabel()
        self._status_icon.setFixedSize(12, 12)
        layout.addWidget(self._status_icon)

        # Status text
        self._status_text = QLabel()
        layout.addWidget(self._status_text)

        layout.addStretch()

        # Update status display
        self._update_status_display()

        return frame

    def _update_status_display(self):
        """Update the encoder status indicator."""
        if self._amf_available:
            self._status_icon.setStyleSheet("""
                background-color: #4ec9b0;
                border-radius: 6px;
            """)
            self._status_text.setText("AMD AMF Hardware Encoding Available")
            self._status_text.setStyleSheet("color: #4ec9b0; font-weight: bold;")
        else:
            self._status_icon.setStyleSheet("""
                background-color: #f48771;
                border-radius: 6px;
            """)
            self._status_text.setText("Software Encoding Only (AMF not detected)")
            self._status_text.setStyleSheet("color: #f48771; font-weight: bold;")

    def _update_codec_list(self):
        """Update codec combo based on availability."""
        self._codec_combo.clear()

        for codec_id, (label, is_hardware) in self.CODECS.items():
            # Skip hardware codecs if not available
            if is_hardware:
                if codec_id == "av1_amf" and not self._av1_available:
                    continue
                if not self._amf_available:
                    continue

            self._codec_combo.addItem(label, codec_id)

        # Set default based on availability
        if self._amf_available:
            # Default to h264_amf
            idx = self._codec_combo.findData("h264_amf")
            if idx >= 0:
                self._codec_combo.setCurrentIndex(idx)
        else:
            # Default to libx264
            idx = self._codec_combo.findData("libx264")
            if idx >= 0:
                self._codec_combo.setCurrentIndex(idx)

    def _update_info_label(self):
        """Update the info label based on current selection."""
        codec = self._codec_combo.currentData()

        info_texts = {
            "h264_amf": "H.264 provides best compatibility. Recommended for most uses.",
            "hevc_amf": "HEVC offers 25-50% better compression than H.264. May not play on older devices.",
            "av1_amf": "AV1 provides best compression but requires RDNA3+ GPU and modern players.",
            "libx264": "Software H.264 encoding. Slower but works on any system.",
            "libx265": "Software HEVC encoding. Very slow but good compression.",
            "libsvtav1": "Software AV1 encoding. Slow but excellent quality.",
        }

        self._info_label.setText(info_texts.get(codec, ""))

    def _connect_signals(self):
        """Connect internal signals."""
        self._codec_combo.currentIndexChanged.connect(self._on_setting_changed)
        self._codec_combo.currentIndexChanged.connect(self._update_info_label)
        self._quality_combo.currentIndexChanged.connect(self._on_setting_changed)
        self._resolution_combo.currentIndexChanged.connect(self._on_setting_changed)
        self._hardware_checkbox.stateChanged.connect(self._on_hardware_changed)

    def _on_setting_changed(self):
        """Handle any setting change."""
        self.settingsChanged.emit(self.get_settings())

    def _on_hardware_changed(self, state: int):
        """Handle hardware encoding toggle."""
        use_hardware = state == 2  # Qt.Checked

        # Update codec list based on hardware toggle
        self._update_codec_list()

        self.settingsChanged.emit(self.get_settings())

    def get_settings(self) -> Dict[str, Any]:
        """
        Get current encoder settings.

        Returns:
            Dictionary with encoder configuration:
            - codec: Codec identifier (e.g., "h264_amf")
            - quality: Quality preset ("speed", "balanced", "quality")
            - resolution: Resolution preset ("1080p", "4k", etc.)
            - use_hardware: Whether to use hardware encoding
            - resolution_width: Actual width in pixels
            - resolution_height: Actual height in pixels
        """
        resolution = self._resolution_combo.currentData()

        # Map resolution to actual dimensions
        resolution_map = {
            "original": (None, None),
            "4k": (3840, 2160),
            "1440p": (2560, 1440),
            "1080p": (1920, 1080),
            "720p": (1280, 720),
            "480p": (854, 480),
        }

        width, height = resolution_map.get(resolution, (1920, 1080))

        return {
            "codec": self._codec_combo.currentData() or "libx264",
            "quality": self._quality_combo.currentData() or "balanced",
            "resolution": resolution or "1080p",
            "use_hardware": self._hardware_checkbox.isChecked(),
            "resolution_width": width,
            "resolution_height": height,
        }

    def set_settings(self, settings: Dict[str, Any]):
        """
        Apply settings to the widget.

        Args:
            settings: Dictionary with encoder configuration
        """
        # Block signals during update
        self._codec_combo.blockSignals(True)
        self._quality_combo.blockSignals(True)
        self._resolution_combo.blockSignals(True)
        self._hardware_checkbox.blockSignals(True)

        try:
            # Codec
            codec = settings.get("codec")
            if codec:
                idx = self._codec_combo.findData(codec)
                if idx >= 0:
                    self._codec_combo.setCurrentIndex(idx)

            # Quality
            quality = settings.get("quality")
            if quality:
                idx = self._quality_combo.findData(quality)
                if idx >= 0:
                    self._quality_combo.setCurrentIndex(idx)

            # Resolution
            resolution = settings.get("resolution")
            if resolution:
                idx = self._resolution_combo.findData(resolution)
                if idx >= 0:
                    self._resolution_combo.setCurrentIndex(idx)

            # Hardware toggle
            use_hardware = settings.get("use_hardware", self._amf_available)
            self._hardware_checkbox.setChecked(use_hardware and self._amf_available)

        finally:
            self._codec_combo.blockSignals(False)
            self._quality_combo.blockSignals(False)
            self._resolution_combo.blockSignals(False)
            self._hardware_checkbox.blockSignals(False)

        self._update_info_label()

    def is_hardware_available(self) -> bool:
        """Check if hardware encoding is available."""
        return self._amf_available

    def refresh_encoder_status(self):
        """Re-check encoder availability and update UI."""
        from pb_studio.video.encoder_utils import reset_availability_cache

        # Reset cache and re-check
        reset_availability_cache()
        self._encoder_info = get_encoder_info()
        self._amf_available = self._encoder_info.get("amf_available", False)
        self._av1_available = self._encoder_info.get("av1_amf_available", False)

        # Update UI
        self._update_status_display()
        self._update_codec_list()
        self._hardware_checkbox.setEnabled(self._amf_available)
        self._hardware_checkbox.setChecked(self._amf_available)

        logger.info(f"Encoder status refreshed: AMF={self._amf_available}, AV1={self._av1_available}")
