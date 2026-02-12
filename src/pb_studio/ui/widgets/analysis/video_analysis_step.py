"""
Video Analysis Step Widget

Provides UI for video scene detection.
Uses VideoSceneWorker for background processing.
"""
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSizePolicy, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool

from ..common.progress_card import ProgressCard
from ..common.result_card import ResultCard
from ....workers.video.video_scene_worker import VideoSceneWorker
from ....models.video import SceneInfo

logger = logging.getLogger(__name__)


class VideoAnalysisStep(QFrame):
    """
    Video analysis step widget.

    Displays progress during scene detection and shows results when complete.
    Uses VideoSceneWorker (PySceneDetect) for scene boundary detection.

    Signals:
        analysisComplete: Emitted when analysis finishes with list[SceneInfo]
        analysisError: Emitted when analysis fails with error message
    """

    # Signals
    analysisComplete = pyqtSignal(list)  # list[SceneInfo]
    analysisError = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_path: Optional[str] = None
        self._worker: Optional[VideoSceneWorker] = None
        self._scenes: list[SceneInfo] = []
        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header with title, threshold and button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title = QLabel("Scene Detection")
        title.setObjectName("StepTitle")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Threshold control
        threshold_label = QLabel("Threshold:")
        threshold_label.setObjectName("ThresholdLabel")
        header_layout.addWidget(threshold_label)

        self._threshold_spin = QDoubleSpinBox()
        self._threshold_spin.setObjectName("ThresholdSpin")
        self._threshold_spin.setRange(1.0, 50.0)
        self._threshold_spin.setValue(8.0)
        self._threshold_spin.setSingleStep(1.0)
        self._threshold_spin.setDecimals(1)
        self._threshold_spin.setToolTip(
            "Lower = more sensitive (more scenes)\n"
            "Higher = less sensitive (fewer scenes)\n"
            "Default: 8.0"
        )
        self._threshold_spin.setFixedWidth(70)
        header_layout.addWidget(self._threshold_spin)

        self._detect_btn = QPushButton("Detect Scenes")
        self._detect_btn.setObjectName("DetectButton")
        self._detect_btn.clicked.connect(self._on_detect_clicked)
        self._detect_btn.setEnabled(False)
        self._detect_btn.setFixedWidth(140)
        header_layout.addWidget(self._detect_btn)

        layout.addLayout(header_layout)

        # Progress card
        self._progress_card = ProgressCard("Scene Analysis")
        self._progress_card.set_status("No video file selected")
        layout.addWidget(self._progress_card)

        # Results row
        results_layout = QHBoxLayout()
        results_layout.setSpacing(12)

        self._scene_count_card = ResultCard("Scenes", "--")
        results_layout.addWidget(self._scene_count_card)

        self._avg_duration_card = ResultCard("Avg Duration", "--")
        results_layout.addWidget(self._avg_duration_card)

        self._total_duration_card = ResultCard("Total Duration", "--")
        results_layout.addWidget(self._total_duration_card)

        layout.addLayout(results_layout)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _apply_styling(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            VideoAnalysisStep {
                background-color: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 8px;
                padding: 16px;
            }
            QLabel#StepTitle {
                color: #ffffff;
                font-size: 18px;
                font-weight: bold;
            }
            QLabel#ThresholdLabel {
                color: #9d9d9d;
                font-size: 13px;
            }
            QDoubleSpinBox#ThresholdSpin {
                background-color: #252526;
                color: #ffffff;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton#DetectButton {
                background-color: #007acc;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton#DetectButton:hover {
                background-color: #1c97ea;
            }
            QPushButton#DetectButton:disabled {
                background-color: #3e3e42;
                color: #6e6e6e;
            }
            QPushButton#DetectButton:pressed {
                background-color: #005a9e;
            }
        """)

    def set_file(self, file_path: str):
        """
        Set the video file to analyze.

        Args:
            file_path: Path to video file
        """
        self._file_path = file_path
        self._scenes = []

        file_name = Path(file_path).name
        self._progress_card.reset()
        self._progress_card.set_status(f"Ready: {file_name}")
        self._detect_btn.setEnabled(True)

        # Reset results
        self._scene_count_card.set_value("--")
        self._avg_duration_card.set_value("--")
        self._total_duration_card.set_value("--")

    def clear_file(self):
        """Clear current file and reset UI."""
        self._file_path = None
        self._scenes = []
        self._cancel_worker()

        self._progress_card.reset()
        self._progress_card.set_status("No video file selected")
        self._detect_btn.setEnabled(False)

        self._scene_count_card.set_value("--")
        self._avg_duration_card.set_value("--")
        self._total_duration_card.set_value("--")

    def get_scenes(self) -> list[SceneInfo]:
        """Get the detected scenes."""
        return self._scenes

    def is_analyzing(self) -> bool:
        """Check if analysis is currently running."""
        return self._worker is not None

    def get_threshold(self) -> float:
        """Get current threshold value."""
        return self._threshold_spin.value()

    def set_threshold(self, value: float):
        """Set threshold value."""
        self._threshold_spin.setValue(value)

    def _on_detect_clicked(self):
        """Handle detect button click."""
        if not self._file_path:
            return

        if self._worker:
            # Cancel current worker
            self._cancel_worker()
            return

        self._start_detection()

    def _start_detection(self):
        """Start the scene detection worker."""
        if not self._file_path:
            return

        threshold = self._threshold_spin.value()
        logger.info(f"Starting scene detection: {self._file_path} (threshold={threshold})")

        # Update UI
        self._detect_btn.setText("Cancel")
        self._threshold_spin.setEnabled(False)
        self._progress_card.set_indeterminate(False)
        self._progress_card.set_progress(0)
        self._progress_card.set_status("Initializing...")
        self._progress_card.clear_error()

        # Create and configure worker
        self._worker = VideoSceneWorker(self._file_path, threshold=threshold)
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.result.connect(self._on_result)
        self._worker.signals.error.connect(self._on_error)
        self._worker.signals.finished.connect(self._on_finished)

        # Start worker
        QThreadPool.globalInstance().start(self._worker)

    def _cancel_worker(self):
        """Cancel the current worker if running."""
        if self._worker:
            self._worker.cancel()
            self._worker = None

    def _on_progress(self, data: dict):
        """Handle progress updates from worker."""
        percent = data.get("percent", 0)
        message = data.get("message", "")

        self._progress_card.set_progress(percent)
        self._progress_card.set_status(message)

    def _on_result(self, result: dict):
        """Handle successful result from worker."""
        scenes: list[SceneInfo] = result.get("scenes", [])
        self._scenes = scenes

        scene_count = len(scenes)
        self._scene_count_card.set_value(str(scene_count))

        # Calculate statistics
        if scenes:
            total_duration = sum(s.duration for s in scenes)
            avg_duration = total_duration / scene_count

            self._avg_duration_card.set_value(f"{avg_duration:.1f}s")
            self._total_duration_card.set_value(self._format_duration(total_duration))
        else:
            self._avg_duration_card.set_value("--")
            self._total_duration_card.set_value("--")

        self._progress_card.set_status(f"Detected {scene_count} scenes")

        logger.info(f"Scene detection complete: {scene_count} scenes found")

        # Emit signal
        self.analysisComplete.emit(scenes)

    def _on_error(self, error_tuple):
        """Handle error from worker."""
        exc_type, exc_value, exc_tb = error_tuple
        error_msg = str(exc_value)

        logger.error(f"Scene detection failed: {error_msg}")

        self._progress_card.set_error(error_msg)
        self.analysisError.emit(error_msg)

    def _on_finished(self):
        """Handle worker completion (success or failure)."""
        self._worker = None
        self._detect_btn.setText("Detect Scenes")
        self._detect_btn.setEnabled(self._file_path is not None)
        self._threshold_spin.setEnabled(True)

    def _format_duration(self, seconds: float) -> str:
        """Format seconds as MM:SS or HH:MM:SS."""
        if seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}:{secs:02d}"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours}:{mins:02d}:{secs:02d}"
