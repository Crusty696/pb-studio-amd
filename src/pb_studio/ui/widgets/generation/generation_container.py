"""
Generation Container Widget for PB Studio AMD.

Main container that combines all generation-related widgets:
- Pacing Configuration
- Clip Selector
- Encoder Settings
- Render Progress
"""

import logging
from typing import Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QFrame, QGroupBox,
    QComboBox, QCheckBox, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon

from .pacing_config_widget import PacingConfigWidget
from .clip_selector_widget import ClipSelectorWidget
from .render_progress_widget import RenderProgressWidget, RenderStep

logger = logging.getLogger(__name__)


class EncoderSettingsWidget(QFrame):
    """Widget for AMD AMF encoder settings."""

    settingsChanged = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Header
        title = QLabel("Encoder Settings")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        # Codec Selection
        codec_layout = QHBoxLayout()
        codec_layout.addWidget(QLabel("Output Codec:"))
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["H.264 (Best Compatibility)", "H.265/HEVC (Better Compression)", "AV1 (Best Quality, RDNA3+)"])
        self.codec_combo.setCurrentIndex(0)
        self._style_combo(self.codec_combo)
        codec_layout.addWidget(self.codec_combo)
        codec_layout.addStretch()
        layout.addLayout(codec_layout)

        # Quality Preset
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Quality Preset:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Speed (Fast)", "Balanced", "Quality (Slow)"])
        self.quality_combo.setCurrentIndex(1)
        self._style_combo(self.quality_combo)
        quality_layout.addWidget(self.quality_combo)
        quality_layout.addStretch()
        layout.addLayout(quality_layout)

        # Hardware Encoding Checkbox
        self.hw_checkbox = QCheckBox("Use AMD AMF Hardware Encoding")
        self.hw_checkbox.setChecked(True)
        self.hw_checkbox.setStyleSheet("color: #ffffff;")
        layout.addWidget(self.hw_checkbox)

        # Info label
        self.info_label = QLabel("AMD AMF provides fast hardware-accelerated encoding")
        self.info_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.info_label)

        layout.addStretch()

    def _connect_signals(self):
        self.codec_combo.currentIndexChanged.connect(self._emit_settings)
        self.quality_combo.currentIndexChanged.connect(self._emit_settings)
        self.hw_checkbox.toggled.connect(self._emit_settings)

    def _emit_settings(self):
        settings = self.get_settings()
        self.settingsChanged.emit(settings)

    def get_settings(self) -> dict:
        """Get the current encoder settings."""
        codec_map = {0: "h264", 1: "hevc", 2: "av1"}
        quality_map = {0: "speed", 1: "balanced", 2: "quality"}

        return {
            "output_codec": codec_map.get(self.codec_combo.currentIndex(), "h264"),
            "output_quality": quality_map.get(self.quality_combo.currentIndex(), "balanced"),
            "use_hardware_encoding": self.hw_checkbox.isChecked(),
        }

    def set_settings(self, settings: dict):
        """Set encoder settings from dict."""
        self.blockSignals(True)

        codec_rmap = {"h264": 0, "hevc": 1, "av1": 2}
        if "output_codec" in settings:
            self.codec_combo.setCurrentIndex(codec_rmap.get(settings["output_codec"], 0))

        quality_rmap = {"speed": 0, "balanced": 1, "quality": 2}
        if "output_quality" in settings:
            self.quality_combo.setCurrentIndex(quality_rmap.get(settings["output_quality"], 1))

        if "use_hardware_encoding" in settings:
            self.hw_checkbox.setChecked(settings["use_hardware_encoding"])

        self.blockSignals(False)

    def _style_combo(self, combo: QComboBox):
        combo.setStyleSheet("""
            QComboBox {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                border-radius: 3px;
                padding: 5px;
                color: #ffffff;
                min-width: 200px;
            }
            QComboBox:hover {
                border-color: #007acc;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d30;
                border: 1px solid #3e3e42;
                color: #ffffff;
                selection-background-color: #007acc;
            }
        """)


class GenerationContainer(QWidget):
    """
    Main container for video generation configuration.

    Combines:
    - PacingConfigWidget: Pacing and rhythm settings
    - ClipSelectorWidget: Source video selection
    - EncoderSettingsWidget: AMD AMF encoder settings
    - RenderProgressWidget: Progress tracking

    Uses a tabbed interface for organization.

    Signals:
        generateRequested(dict): Emitted when user clicks Generate.
            Contains full configuration including:
            - pacing config
            - source videos
            - encoder settings
            - output path
            - master audio path
    """

    generateRequested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._master_audio: Optional[str] = None
        self._output_path: Optional[str] = None
        self._is_generating = False
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header = QHBoxLayout()
        title = QLabel("Video Generation")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        description = QLabel("Configure pacing, select clips, and generate your video")
        description.setStyleSheet("color: #cccccc; font-size: 14px;")
        layout.addWidget(description)

        # Audio/Output Selection
        io_group = QGroupBox("Input/Output")
        self._style_groupbox(io_group)
        io_layout = QVBoxLayout(io_group)

        # Master Audio
        audio_row = QHBoxLayout()
        audio_row.addWidget(QLabel("Master Audio:"))
        self.audio_label = QLabel("No audio selected")
        self.audio_label.setStyleSheet("color: #888888;")
        audio_row.addWidget(self.audio_label, 1)
        self.audio_btn = QPushButton("Browse...")
        self.audio_btn.setStyleSheet(self._button_style())
        self.audio_btn.clicked.connect(self._browse_audio)
        audio_row.addWidget(self.audio_btn)
        io_layout.addLayout(audio_row)

        # Output Path
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Output File:"))
        self.output_label = QLabel("No output selected")
        self.output_label.setStyleSheet("color: #888888;")
        output_row.addWidget(self.output_label, 1)
        self.output_btn = QPushButton("Browse...")
        self.output_btn.setStyleSheet(self._button_style())
        self.output_btn.clicked.connect(self._browse_output)
        output_row.addWidget(self.output_btn)
        io_layout.addLayout(output_row)

        # AI Smart Director toggle
        self.ai_checkbox = QCheckBox("Use AI Smart Director (CLAP + SigLIP)")
        self.ai_checkbox.setChecked(False)
        self.ai_checkbox.setToolTip(
            "Enables AI-powered audio mood analysis (CLAP) and video content "
            "matching (SigLIP) for intelligent clip selection and timeline generation. "
            "Requires more VRAM and processing time."
        )
        self.ai_checkbox.setStyleSheet("color: #ffffff; font-weight: bold;")
        io_layout.addWidget(self.ai_checkbox)

        layout.addWidget(io_group)

        # Tab Widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3e3e42;
                border-radius: 4px;
                background-color: #252526;
            }
            QTabBar::tab {
                background-color: #2d2d30;
                color: #cccccc;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #007acc;
                color: #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background-color: #3e3e42;
            }
        """)

        # Create widgets
        self.pacing_widget = PacingConfigWidget()
        self.clip_selector = ClipSelectorWidget()
        self.encoder_widget = EncoderSettingsWidget()
        self.progress_widget = RenderProgressWidget()

        # Add tabs
        self.tab_widget.addTab(self.clip_selector, "Source Clips")
        self.tab_widget.addTab(self.pacing_widget, "Pacing")
        self.tab_widget.addTab(self.encoder_widget, "Encoder")
        self.tab_widget.addTab(self.progress_widget, "Progress")

        layout.addWidget(self.tab_widget)

        # Generate Button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.generate_btn = QPushButton("Generate Video")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 15px 40px;
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
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.clicked.connect(self._on_generate_clicked)
        button_layout.addWidget(self.generate_btn)

        layout.addLayout(button_layout)

    def _connect_signals(self):
        """Connect internal widget signals."""
        self.pacing_widget.configChanged.connect(self._on_config_changed)
        self.clip_selector.selectionChanged.connect(self._on_selection_changed)
        self.encoder_widget.settingsChanged.connect(self._on_encoder_changed)
        self.progress_widget.cancelRequested.connect(self._on_cancel_requested)

    def _on_config_changed(self, config: dict):
        """Handle pacing config change."""
        logger.debug(f"Pacing config changed: {config}")

    def _on_selection_changed(self, clips: list):
        """Handle clip selection change."""
        logger.debug(f"Clip selection changed: {len(clips)} clips")
        self._update_generate_button()

    def _on_encoder_changed(self, settings: dict):
        """Handle encoder settings change."""
        logger.debug(f"Encoder settings changed: {settings}")

    def _on_cancel_requested(self):
        """Handle cancel request from progress widget."""
        logger.info("Cancel requested")
        self.cancelGeneration()

    def _on_generate_clicked(self):
        """Handle generate button click."""
        # Validate inputs
        if not self._master_audio:
            QMessageBox.warning(self, "Missing Input", "Please select a master audio file.")
            return

        if not self._output_path:
            QMessageBox.warning(self, "Missing Input", "Please select an output file location.")
            return

        clips = self.clip_selector.get_selected_clips()
        if not clips:
            QMessageBox.warning(self, "Missing Input", "Please add and select at least one source video clip.")
            return

        # Collect full configuration
        config = self.get_full_config()

        logger.info(f"Generate requested with config: {config}")

        # Switch to progress tab
        self.tab_widget.setCurrentWidget(self.progress_widget)

        # Emit signal
        self.generateRequested.emit(config)

    def get_full_config(self) -> dict:
        """
        Get the complete generation configuration.

        Returns:
            dict with all configuration parameters
        """
        pacing = self.pacing_widget.get_config()
        encoder = self.encoder_widget.get_settings()
        clips = self.clip_selector.get_selected_clips()

        return {
            # Pacing settings
            "pacing": pacing["pacing"],
            "min_dur": pacing["min_dur"],
            "max_dur": pacing["max_dur"],
            "precision": pacing["precision"],
            "energy_react": pacing["energy_react"],
            "chaos": pacing["chaos"],
            # Source videos
            "source_videos": clips,
            # Encoder settings
            "output_codec": encoder["output_codec"],
            "output_quality": encoder["output_quality"],
            "use_hardware_encoding": encoder["use_hardware_encoding"],
            # AI Smart Director
            "use_smart_director": self.ai_checkbox.isChecked(),
            # Paths
            "master_audio": self._master_audio,
            "output_path": self._output_path,
        }

    def set_master_audio(self, path: str):
        """Set the master audio file path."""
        self._master_audio = path
        filename = Path(path).name if path else "No audio selected"
        self.audio_label.setText(filename)
        self.audio_label.setStyleSheet("color: #ffffff;" if path else "color: #888888;")
        self._update_generate_button()

    def set_output_path(self, path: str):
        """Set the output file path."""
        self._output_path = path
        filename = Path(path).name if path else "No output selected"
        self.output_label.setText(filename)
        self.output_label.setStyleSheet("color: #ffffff;" if path else "color: #888888;")
        self._update_generate_button()

    def add_source_clips(self, paths: list[str]):
        """Add source video clips."""
        self.clip_selector.add_clips(paths)

    def startGeneration(self, total_clips: int = 0):
        """
        Start the generation process (call from external controller).

        Args:
            total_clips: Number of clips to process
        """
        self._is_generating = True
        self.generate_btn.setEnabled(False)
        self.progress_widget.start(total_clips)

    def updateProgress(self, progress: int, step: str = "", current: int = 0, total: int = 0):
        """
        Update generation progress (call from external controller).

        Args:
            progress: Overall progress (0-100)
            step: Current step name
            current: Current item number
            total: Total items
        """
        self.progress_widget.set_progress(progress, current, total)

        if step:
            step_map = {
                "analyzing": RenderStep.ANALYZING,
                "planning": RenderStep.PLANNING,
                "rendering": RenderStep.RENDERING,
                "concatenating": RenderStep.CONCATENATING,
                "encoding": RenderStep.ENCODING,
            }
            render_step = step_map.get(step.lower(), RenderStep.RENDERING)
            self.progress_widget.set_step(render_step)

    def finishGeneration(self, success: bool = True, message: str = ""):
        """
        Finish the generation process (call from external controller).

        Args:
            success: Whether generation succeeded
            message: Completion message
        """
        self._is_generating = False
        self.generate_btn.setEnabled(True)
        self.progress_widget.finish(success, message)

    def cancelGeneration(self):
        """Cancel the current generation."""
        if self._is_generating:
            self._is_generating = False
            self.generate_btn.setEnabled(True)
            self.progress_widget.cancel()

    def _browse_audio(self):
        """Open file dialog for master audio."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Master Audio",
            "",
            "Audio Files (*.mp3 *.wav *.flac *.ogg *.m4a);;All Files (*)"
        )
        if path:
            self.set_master_audio(path)

    def _browse_output(self):
        """Open file dialog for output path."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Output Video",
            "",
            "Video Files (*.mp4);;All Files (*)"
        )
        if path:
            if not path.lower().endswith('.mp4'):
                path += '.mp4'
            self.set_output_path(path)

    def _update_generate_button(self):
        """Update generate button enabled state."""
        has_audio = bool(self._master_audio)
        has_output = bool(self._output_path)
        has_clips = len(self.clip_selector.get_selected_clips()) > 0

        self.generate_btn.setEnabled(has_audio and has_output and has_clips and not self._is_generating)

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

    def _button_style(self) -> str:
        """Get button stylesheet."""
        return """
            QPushButton {
                background-color: #3e3e42;
                color: #ffffff;
                border: none;
                border-radius: 3px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #4e4e52;
            }
            QPushButton:pressed {
                background-color: #2d2d30;
            }
        """
