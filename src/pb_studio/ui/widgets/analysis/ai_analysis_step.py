"""
AI Analysis Step Widget

Provides UI for AI-powered video analysis including motion and vision analysis.
Uses VideoMotionWorker and VideoVisionWorker for background processing.
"""
import logging
from pathlib import Path
from typing import Optional, Any

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSizePolicy, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool

from ..common.progress_card import ProgressCard
from ..common.result_card import ResultCard
from ....workers.video.video_motion_worker import VideoMotionWorker
from ....workers.video.video_vision_worker import VideoVisionWorker
from ....models.video import SceneInfo, MotionData

logger = logging.getLogger(__name__)


class AIAnalysisStep(QFrame):
    """
    AI analysis step widget.

    Displays progress during motion and vision analysis and shows results when complete.
    Uses VideoMotionWorker (RAFT optical flow) and VideoVisionWorker (Moondream VLM).

    Requires scenes from VideoAnalysisStep to be provided first.

    Signals:
        analysisComplete: Emitted when all analyses finish with combined results dict
        analysisError: Emitted when analysis fails with error message
    """

    # Signals
    analysisComplete = pyqtSignal(dict)
    analysisError = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_path: Optional[str] = None
        self._scenes: list[SceneInfo] = []
        self._motion_worker: Optional[VideoMotionWorker] = None
        self._vision_worker: Optional[VideoVisionWorker] = None

        # Results
        self._motion_data: list[MotionData] = []
        self._captions: dict[int, dict[str, str]] = {}

        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header with title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title = QLabel("AI Analysis")
        title.setObjectName("StepTitle")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # GPU preference checkbox
        self._gpu_checkbox = QCheckBox("Prefer GPU")
        self._gpu_checkbox.setObjectName("GpuCheckbox")
        self._gpu_checkbox.setChecked(True)
        self._gpu_checkbox.setToolTip(
            "Use GPU (DirectML) when available.\n"
            "Uncheck to force CPU processing."
        )
        header_layout.addWidget(self._gpu_checkbox)

        layout.addLayout(header_layout)

        # Motion Analysis Section
        motion_header = QHBoxLayout()
        motion_header.setSpacing(12)

        motion_label = QLabel("Motion Analysis")
        motion_label.setObjectName("SectionTitle")
        motion_header.addWidget(motion_label)

        motion_header.addStretch()

        self._motion_btn = QPushButton("Analyze Motion")
        self._motion_btn.setObjectName("AnalyzeButton")
        self._motion_btn.clicked.connect(self._on_motion_clicked)
        self._motion_btn.setEnabled(False)
        self._motion_btn.setFixedWidth(140)
        motion_header.addWidget(self._motion_btn)

        layout.addLayout(motion_header)

        # Motion progress card
        self._motion_progress = ProgressCard("Optical Flow Analysis")
        self._motion_progress.set_status("Requires scene detection first")
        layout.addWidget(self._motion_progress)

        # Motion results row
        motion_results = QHBoxLayout()
        motion_results.setSpacing(12)

        self._avg_motion_card = ResultCard("Avg Motion", "--")
        motion_results.addWidget(self._avg_motion_card)

        self._max_motion_card = ResultCard("Max Motion", "--")
        motion_results.addWidget(self._max_motion_card)

        self._high_motion_card = ResultCard("High Motion Scenes", "--")
        motion_results.addWidget(self._high_motion_card)

        layout.addLayout(motion_results)

        # Vision Analysis Section
        vision_header = QHBoxLayout()
        vision_header.setSpacing(12)

        vision_label = QLabel("Vision Analysis")
        vision_label.setObjectName("SectionTitle")
        vision_header.addWidget(vision_label)

        vision_header.addStretch()

        # Detailed analysis checkbox
        self._detailed_checkbox = QCheckBox("Detailed")
        self._detailed_checkbox.setObjectName("DetailedCheckbox")
        self._detailed_checkbox.setChecked(False)
        self._detailed_checkbox.setToolTip(
            "Generate detailed captions including:\n"
            "- Scene description\n"
            "- Mood/atmosphere\n"
            "- Objects detected\n"
            "- Actions happening"
        )
        vision_header.addWidget(self._detailed_checkbox)

        self._vision_btn = QPushButton("Generate Captions")
        self._vision_btn.setObjectName("AnalyzeButton")
        self._vision_btn.clicked.connect(self._on_vision_clicked)
        self._vision_btn.setEnabled(False)
        self._vision_btn.setFixedWidth(140)
        vision_header.addWidget(self._vision_btn)

        layout.addLayout(vision_header)

        # Vision progress card
        self._vision_progress = ProgressCard("Scene Captioning")
        self._vision_progress.set_status("Requires scene detection first")
        layout.addWidget(self._vision_progress)

        # Vision results row
        vision_results = QHBoxLayout()
        vision_results.setSpacing(12)

        self._captions_card = ResultCard("Captions Generated", "--")
        vision_results.addWidget(self._captions_card)

        self._model_card = ResultCard("Model", "--")
        vision_results.addWidget(self._model_card)

        self._scenes_analyzed_card = ResultCard("Scenes Analyzed", "--")
        vision_results.addWidget(self._scenes_analyzed_card)

        layout.addLayout(vision_results)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _apply_styling(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            AIAnalysisStep {
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
            QLabel#SectionTitle {
                color: #cccccc;
                font-size: 14px;
                font-weight: bold;
            }
            QCheckBox#GpuCheckbox, QCheckBox#DetailedCheckbox {
                color: #9d9d9d;
                font-size: 13px;
            }
            QCheckBox#GpuCheckbox::indicator, QCheckBox#DetailedCheckbox::indicator {
                width: 16px;
                height: 16px;
            }
            QPushButton#AnalyzeButton {
                background-color: #007acc;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton#AnalyzeButton:hover {
                background-color: #1c97ea;
            }
            QPushButton#AnalyzeButton:disabled {
                background-color: #3e3e42;
                color: #6e6e6e;
            }
            QPushButton#AnalyzeButton:pressed {
                background-color: #005a9e;
            }
        """)

    def set_file(self, file_path: str):
        """
        Set the video file for analysis.

        Args:
            file_path: Path to video file
        """
        self._file_path = file_path
        self._motion_data = []
        self._captions = {}

        file_name = Path(file_path).name

        # Update progress cards
        if self._scenes:
            self._motion_progress.reset()
            self._motion_progress.set_status(f"Ready: {file_name}")
            self._motion_btn.setEnabled(True)

            self._vision_progress.reset()
            self._vision_progress.set_status(f"Ready: {file_name}")
            self._vision_btn.setEnabled(True)
        else:
            self._motion_progress.set_status("Requires scene detection first")
            self._vision_progress.set_status("Requires scene detection first")

        # Reset results
        self._reset_results()

    def set_scenes(self, scenes: list[SceneInfo]):
        """
        Set the scenes to analyze.

        Must be called after scene detection completes.

        Args:
            scenes: List of SceneInfo from VideoAnalysisStep
        """
        self._scenes = scenes
        self._motion_data = []
        self._captions = {}

        if scenes and self._file_path:
            file_name = Path(self._file_path).name
            self._motion_progress.reset()
            self._motion_progress.set_status(f"Ready: {len(scenes)} scenes")
            self._motion_btn.setEnabled(True)

            self._vision_progress.reset()
            self._vision_progress.set_status(f"Ready: {len(scenes)} scenes")
            self._vision_btn.setEnabled(True)
        else:
            self._motion_progress.set_status("Requires scene detection first")
            self._vision_progress.set_status("Requires scene detection first")
            self._motion_btn.setEnabled(False)
            self._vision_btn.setEnabled(False)

        self._reset_results()

    def clear_file(self):
        """Clear current file and reset UI."""
        self._file_path = None
        self._scenes = []
        self._motion_data = []
        self._captions = {}
        self._cancel_workers()

        self._motion_progress.reset()
        self._motion_progress.set_status("Requires scene detection first")
        self._motion_btn.setEnabled(False)

        self._vision_progress.reset()
        self._vision_progress.set_status("Requires scene detection first")
        self._vision_btn.setEnabled(False)

        self._reset_results()

    def _reset_results(self):
        """Reset all result cards to default state."""
        self._avg_motion_card.set_value("--")
        self._max_motion_card.set_value("--")
        self._high_motion_card.set_value("--")

        self._captions_card.set_value("--")
        self._model_card.set_value("--")
        self._scenes_analyzed_card.set_value("--")

    def get_result(self) -> dict[str, Any]:
        """
        Get the combined analysis results.

        Returns:
            Dictionary with motion_data and captions
        """
        return {
            "motion_data": self._motion_data,
            "captions": self._captions,
        }

    def is_analyzing(self) -> bool:
        """Check if any analysis is currently running."""
        return self._motion_worker is not None or self._vision_worker is not None

    # Motion Analysis

    def _on_motion_clicked(self):
        """Handle motion analyze button click."""
        if not self._file_path or not self._scenes:
            return

        if self._motion_worker:
            self._cancel_motion_worker()
            return

        self._start_motion_analysis()

    def _start_motion_analysis(self):
        """Start the motion analysis worker."""
        if not self._file_path or not self._scenes:
            return

        prefer_gpu = self._gpu_checkbox.isChecked()
        logger.info(f"Starting motion analysis: {self._file_path} (GPU={prefer_gpu})")

        # Update UI
        self._motion_btn.setText("Cancel")
        self._gpu_checkbox.setEnabled(False)
        self._motion_progress.set_indeterminate(False)
        self._motion_progress.set_progress(0)
        self._motion_progress.set_status("Initializing...")
        self._motion_progress.clear_error()

        # Create and configure worker
        self._motion_worker = VideoMotionWorker(
            self._file_path,
            self._scenes,
            prefer_gpu=prefer_gpu
        )
        self._motion_worker.signals.progress.connect(self._on_motion_progress)
        self._motion_worker.signals.result.connect(self._on_motion_result)
        self._motion_worker.signals.error.connect(self._on_motion_error)
        self._motion_worker.signals.finished.connect(self._on_motion_finished)

        # Start worker
        QThreadPool.globalInstance().start(self._motion_worker)

    def _cancel_motion_worker(self):
        """Cancel the motion worker if running."""
        if self._motion_worker:
            self._motion_worker.cancel()
            self._motion_worker = None

    def _on_motion_progress(self, data: dict):
        """Handle motion progress updates."""
        percent = data.get("percent", 0)
        message = data.get("message", "")

        self._motion_progress.set_progress(percent)
        self._motion_progress.set_status(message)

    def _on_motion_result(self, result: dict):
        """Handle motion analysis result."""
        motion_data: list[MotionData] = result.get("motion_data", [])
        analyzer_type = result.get("analyzer_type", "Unknown")

        self._motion_data = motion_data

        # Calculate statistics
        if motion_data:
            all_avg = [m.avg_motion for m in motion_data]
            all_max = [m.max_motion for m in motion_data]
            high_motion_count = sum(1 for m in motion_data if m.is_high_motion)

            overall_avg = sum(all_avg) / len(all_avg) if all_avg else 0
            overall_max = max(all_max) if all_max else 0

            self._avg_motion_card.set_value(f"{overall_avg:.2f}")
            self._max_motion_card.set_value(f"{overall_max:.2f}")
            self._high_motion_card.set_value(str(high_motion_count))
        else:
            self._avg_motion_card.set_value("0")
            self._max_motion_card.set_value("0")
            self._high_motion_card.set_value("0")

        self._motion_progress.set_status(f"Complete ({analyzer_type})")

        logger.info(f"Motion analysis complete: {len(motion_data)} scenes analyzed")

        self._check_complete()

    def _on_motion_error(self, error_tuple):
        """Handle motion analysis error."""
        exc_type, exc_value, exc_tb = error_tuple
        error_msg = str(exc_value)

        logger.error(f"Motion analysis failed: {error_msg}")

        self._motion_progress.set_error(error_msg)
        self.analysisError.emit(f"Motion: {error_msg}")

    def _on_motion_finished(self):
        """Handle motion worker completion."""
        self._motion_worker = None
        self._motion_btn.setText("Analyze Motion")
        self._motion_btn.setEnabled(self._file_path is not None and bool(self._scenes))
        self._gpu_checkbox.setEnabled(True)

    # Vision Analysis

    def _on_vision_clicked(self):
        """Handle vision analyze button click."""
        if not self._file_path or not self._scenes:
            return

        if self._vision_worker:
            self._cancel_vision_worker()
            return

        self._start_vision_analysis()

    def _start_vision_analysis(self):
        """Start the vision analysis worker."""
        if not self._file_path or not self._scenes:
            return

        detailed = self._detailed_checkbox.isChecked()
        logger.info(f"Starting vision analysis: {self._file_path} (detailed={detailed})")

        # Update UI
        self._vision_btn.setText("Cancel")
        self._detailed_checkbox.setEnabled(False)
        self._vision_progress.set_indeterminate(False)
        self._vision_progress.set_progress(0)
        self._vision_progress.set_status("Initializing...")
        self._vision_progress.clear_error()

        # Create and configure worker
        self._vision_worker = VideoVisionWorker(
            self._file_path,
            self._scenes,
            detailed_analysis=detailed
        )
        self._vision_worker.signals.progress.connect(self._on_vision_progress)
        self._vision_worker.signals.result.connect(self._on_vision_result)
        self._vision_worker.signals.error.connect(self._on_vision_error)
        self._vision_worker.signals.finished.connect(self._on_vision_finished)

        # Start worker
        QThreadPool.globalInstance().start(self._vision_worker)

    def _cancel_vision_worker(self):
        """Cancel the vision worker if running."""
        if self._vision_worker:
            self._vision_worker.cancel()
            self._vision_worker = None

    def _on_vision_progress(self, data: dict):
        """Handle vision progress updates."""
        percent = data.get("percent", 0)
        message = data.get("message", "")

        self._vision_progress.set_progress(percent)
        self._vision_progress.set_status(message)

    def _on_vision_result(self, result: dict):
        """Handle vision analysis result."""
        captions: dict[int, dict[str, str]] = result.get("captions", {})
        model_type = result.get("model_type", "Unknown")

        self._captions = captions

        # Update result cards
        caption_count = len(captions)
        self._captions_card.set_value(str(caption_count))
        self._model_card.set_value(model_type)
        self._scenes_analyzed_card.set_value(str(len(self._scenes)))

        self._vision_progress.set_status(f"Complete ({model_type})")

        logger.info(f"Vision analysis complete: {caption_count} captions generated")

        self._check_complete()

    def _on_vision_error(self, error_tuple):
        """Handle vision analysis error."""
        exc_type, exc_value, exc_tb = error_tuple
        error_msg = str(exc_value)

        logger.error(f"Vision analysis failed: {error_msg}")

        self._vision_progress.set_error(error_msg)
        self.analysisError.emit(f"Vision: {error_msg}")

    def _on_vision_finished(self):
        """Handle vision worker completion."""
        self._vision_worker = None
        self._vision_btn.setText("Generate Captions")
        self._vision_btn.setEnabled(self._file_path is not None and bool(self._scenes))
        self._detailed_checkbox.setEnabled(True)

    # Utility

    def _cancel_workers(self):
        """Cancel all workers."""
        self._cancel_motion_worker()
        self._cancel_vision_worker()

    def _check_complete(self):
        """Check if all analyses are complete and emit signal."""
        # Only emit if we have both results (or no workers running)
        if self._motion_data and self._captions:
            result = self.get_result()
            self.analysisComplete.emit(result)
