"""
Audio Analysis Step Widget

Provides UI for audio analysis including BPM detection and beat tracking.
Uses AudioAnalyzeWorker for background processing.
"""
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool

from ..common.progress_card import ProgressCard
from ..common.result_card import ResultCard
from ....workers.audio.audio_analyze_worker import AudioAnalyzeWorker
from ....models.audio import AudioAnalysisResult

logger = logging.getLogger(__name__)


class AudioAnalysisStep(QFrame):
    """
    Audio analysis step widget.

    Displays progress during BPM analysis and shows results when complete.
    Uses AudioAnalyzeWorker (BeatNet) for beat detection.

    Signals:
        analysisComplete: Emitted when analysis finishes with AudioAnalysisResult
        analysisError: Emitted when analysis fails with error message
    """

    # Signals
    analysisComplete = pyqtSignal(object)  # AudioAnalysisResult
    analysisError = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_path: Optional[str] = None
        self._worker: Optional[AudioAnalyzeWorker] = None
        self._result: Optional[AudioAnalysisResult] = None
        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header with title and button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title = QLabel("Audio Analysis")
        title.setObjectName("StepTitle")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self._analyze_btn = QPushButton("Analyze Audio")
        self._analyze_btn.setObjectName("AnalyzeButton")
        self._analyze_btn.clicked.connect(self._on_analyze_clicked)
        self._analyze_btn.setEnabled(False)
        self._analyze_btn.setFixedWidth(140)
        header_layout.addWidget(self._analyze_btn)

        layout.addLayout(header_layout)

        # Progress card
        self._progress_card = ProgressCard("BPM Detection")
        self._progress_card.set_status("No audio file selected")
        layout.addWidget(self._progress_card)

        # Results row
        results_layout = QHBoxLayout()
        results_layout.setSpacing(12)

        self._bpm_card = ResultCard("BPM", "--")
        results_layout.addWidget(self._bpm_card)

        self._beat_count_card = ResultCard("Beat Count", "--")
        results_layout.addWidget(self._beat_count_card)

        self._confidence_card = ResultCard("Confidence", "--")
        results_layout.addWidget(self._confidence_card)

        layout.addLayout(results_layout)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _apply_styling(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            AudioAnalysisStep {
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
        Set the audio file to analyze.

        Args:
            file_path: Path to WAV file
        """
        self._file_path = file_path
        self._result = None

        file_name = Path(file_path).name
        self._progress_card.reset()
        self._progress_card.set_status(f"Ready: {file_name}")
        self._analyze_btn.setEnabled(True)

        # Reset results
        self._bpm_card.set_value("--")
        self._beat_count_card.set_value("--")
        self._confidence_card.set_value("--")

    def clear_file(self):
        """Clear current file and reset UI."""
        self._file_path = None
        self._result = None
        self._cancel_worker()

        self._progress_card.reset()
        self._progress_card.set_status("No audio file selected")
        self._analyze_btn.setEnabled(False)

        self._bpm_card.set_value("--")
        self._beat_count_card.set_value("--")
        self._confidence_card.set_value("--")

    def get_result(self) -> Optional[AudioAnalysisResult]:
        """Get the current analysis result if available."""
        return self._result

    def is_analyzing(self) -> bool:
        """Check if analysis is currently running."""
        return self._worker is not None

    def _on_analyze_clicked(self):
        """Handle analyze button click."""
        if not self._file_path:
            return

        if self._worker:
            # Cancel current worker
            self._cancel_worker()
            return

        self._start_analysis()

    def _start_analysis(self):
        """Start the audio analysis worker."""
        if not self._file_path:
            return

        logger.info(f"Starting audio analysis: {self._file_path}")

        # Update UI
        self._analyze_btn.setText("Cancel")
        self._progress_card.set_indeterminate(False)
        self._progress_card.set_progress(0)
        self._progress_card.set_status("Initializing...")
        self._progress_card.clear_error()

        # Create and configure worker
        self._worker = AudioAnalyzeWorker(self._file_path)
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

    def _on_result(self, result: AudioAnalysisResult):
        """Handle successful result from worker."""
        self._result = result

        # Update result cards
        self._bpm_card.set_value(f"{result.bpm:.1f}")
        self._beat_count_card.set_value(str(len(result.beat_times)))

        # Format confidence as percentage
        confidence_pct = result.confidence * 100
        self._confidence_card.set_value(f"{confidence_pct:.0f}%")

        # Color code confidence
        if result.confidence >= 0.8:
            self._confidence_card.set_value_color("#4ec9b0")  # Green
        elif result.confidence >= 0.5:
            self._confidence_card.set_value_color("#dcdcaa")  # Yellow
        else:
            self._confidence_card.set_value_color("#f44747")  # Red

        self._progress_card.set_status("Analysis complete")

        logger.info(
            f"Audio analysis complete: BPM={result.bpm:.1f}, "
            f"Beats={len(result.beat_times)}, Confidence={confidence_pct:.0f}%"
        )

        # Emit signal
        self.analysisComplete.emit(result)

    def _on_error(self, error_tuple):
        """Handle error from worker."""
        exc_type, exc_value, exc_tb = error_tuple
        error_msg = str(exc_value)

        logger.error(f"Audio analysis failed: {error_msg}")

        self._progress_card.set_error(error_msg)
        self.analysisError.emit(error_msg)

    def _on_finished(self):
        """Handle worker completion (success or failure)."""
        self._worker = None
        self._analyze_btn.setText("Analyze Audio")
        self._analyze_btn.setEnabled(self._file_path is not None)
