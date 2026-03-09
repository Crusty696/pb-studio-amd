"""
Stem Separator Widget

UI widget for audio stem separation with progress tracking.
Uses AudioStemWorker for background processing.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QRunnable, QThreadPool
from PyQt6.QtGui import QIcon

from pb_studio.core.worker_signals import WorkerSignals

logger = logging.getLogger(__name__)

# Progress pattern from stem_runner output
PROGRESS_PATTERN = re.compile(r"(\d+)%?\|.*\| (\d+)/(\d+)")


@dataclass
class StemResult:
    """Result container for stem separation."""
    success: bool = False
    stems: List[str] = field(default_factory=list)  # List of stem file paths
    error: Optional[str] = None
    source_file: Optional[str] = None


class AudioStemWorker(QRunnable):
    """
    Worker thread for stem separation.

    Runs stem separation in background and emits progress signals.
    """

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        self.signals = WorkerSignals()
        self._is_cancelled = False

    def run(self):
        """Execute stem separation."""
        try:
            self.signals.status.emit("Initializing separator...")

            # Import here to avoid loading heavy dependencies at module load
            from pb_studio.audio.separator import StemSeparator

            self.signals.status.emit("Loading model...")
            separator = StemSeparator()

            if self._is_cancelled:
                self.signals.status.emit("Cancelled")
                return

            self.signals.status.emit("Separating stems...")

            # Run separation
            result = separator.separate(self.file_path)

            if self._is_cancelled:
                self.signals.status.emit("Cancelled")
                return

            # Process result
            if "error" in result:
                stem_result = StemResult(
                    success=False,
                    error=result["error"],
                    source_file=self.file_path
                )
            else:
                stem_result = StemResult(
                    success=True,
                    stems=result.get("stems", []),
                    source_file=self.file_path
                )

            self.signals.result.emit(stem_result)
            self.signals.finished.emit()

        except Exception as e:
            logger.exception(f"Stem separation failed: {e}")
            self.signals.error.emit((type(e), e, str(e)))

    def cancel(self):
        """Request cancellation of the worker."""
        self._is_cancelled = True


class StemSeparatorWidget(QFrame):
    """
    Widget for stem separation with progress tracking.

    Provides:
    - "Separate Stems" button
    - Progress bar with status
    - List of generated stem files

    Signals:
        separationComplete(StemResult): Emitted when separation finishes
    """

    separationComplete = pyqtSignal(object)  # StemResult

    def __init__(self, parent=None):
        super().__init__(parent)

        self._current_file: Optional[str] = None
        self._worker: Optional[AudioStemWorker] = None
        self._thread_pool = QThreadPool.globalInstance()

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            StemSeparatorWidget {
                background-color: #252526;
                border-radius: 6px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Header
        header = QLabel("Stem Separation")
        header.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            color: #007acc;
        """)
        layout.addWidget(header)

        # Description
        desc = QLabel("Separate audio into individual stems (vocals, drums, bass, other)")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(desc)

        # Separate button
        self.separate_btn = QPushButton("Separate Stems (GPU)")
        self.separate_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1177bb;
            }
            QPushButton:disabled {
                background-color: #3e3e42;
                color: #888888;
            }
        """)
        self.separate_btn.clicked.connect(self._on_separate_click)
        self.separate_btn.setEnabled(False)  # Disabled until file is set
        layout.addWidget(self.separate_btn)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("""
            color: #007acc;
            font-weight: bold;
            font-size: 12px;
            padding: 4px;
            border: 1px solid #007acc;
            border-radius: 4px;
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #1e1e1e;
                border-radius: 6px;
                text-align: center;
                color: white;
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Cancel button (hidden by default)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6e3636;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #8a4444;
            }
        """)
        self.cancel_btn.clicked.connect(self._on_cancel_click)
        self.cancel_btn.setVisible(False)
        layout.addWidget(self.cancel_btn)

        # Output stems list
        self.output_header = QLabel("Generated Stems:")
        self.output_header.setStyleSheet("""
            font-weight: bold;
            font-size: 12px;
            color: #cccccc;
            margin-top: 10px;
        """)
        self.output_header.setVisible(False)
        layout.addWidget(self.output_header)

        self.output_list = QListWidget()
        self.output_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                color: #cccccc;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #2d2d30;
            }
            QListWidget::item:hover {
                background-color: #2d2d30;
            }
        """)
        self.output_list.setMaximumHeight(120)
        self.output_list.setVisible(False)
        layout.addWidget(self.output_list)

        layout.addStretch()

    def set_file(self, file_path: str):
        """
        Set the audio file to separate.

        Args:
            file_path: Path to the audio file
        """
        self._current_file = file_path
        self.separate_btn.setEnabled(bool(file_path))

        # Reset state
        self.status_label.setVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.output_header.setVisible(False)
        self.output_list.setVisible(False)
        self.output_list.clear()

    def _on_separate_click(self):
        """Handle separate button click."""
        if not self._current_file:
            return

        logger.info(f"Starting stem separation for: {self._current_file}")

        # Update UI state
        self.separate_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.status_label.setText("STARTING...")
        self.status_label.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.output_header.setVisible(False)
        self.output_list.setVisible(False)
        self.output_list.clear()

        # Create and start worker
        self._worker = AudioStemWorker(self._current_file)
        self._worker.signals.status.connect(self._on_status)
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.result.connect(self._on_result)
        self._worker.signals.error.connect(self._on_error)
        self._worker.signals.finished.connect(self._on_finished)

        self._thread_pool.start(self._worker)

    def _on_cancel_click(self):
        """Handle cancel button click."""
        if self._worker:
            self._worker.cancel()
            self.status_label.setText("CANCELLING...")

    def _on_status(self, status: str):
        """Handle status update from worker."""
        self.status_label.setText(status.upper())

    def _on_progress(self, progress):
        """Handle progress update from worker."""
        if isinstance(progress, int):
            self.progress_bar.setValue(progress)
        elif isinstance(progress, dict):
            pct = progress.get("percent", 0)
            self.progress_bar.setValue(int(pct))
            if "message" in progress:
                self.status_label.setText(progress["message"].upper())

    def _on_result(self, result: StemResult):
        """Handle separation result."""
        if result.success:
            self.status_label.setText("DONE")
            self.status_label.setStyleSheet("""
                color: #4ec9b0;
                font-weight: bold;
                font-size: 12px;
                padding: 4px;
                border: 1px solid #4ec9b0;
                border-radius: 4px;
            """)
            self.progress_bar.setValue(100)

            # Show output stems
            if result.stems:
                self.output_header.setVisible(True)
                self.output_list.setVisible(True)

                for stem_path in result.stems:
                    filename = Path(stem_path).name
                    item = QListWidgetItem(filename)
                    item.setToolTip(stem_path)
                    self.output_list.addItem(item)
        else:
            self.status_label.setText(f"FAILED: {result.error or 'Unknown error'}")
            self.status_label.setStyleSheet("""
                color: #f14c4c;
                font-weight: bold;
                font-size: 12px;
                padding: 4px;
                border: 1px solid #f14c4c;
                border-radius: 4px;
            """)

        self.separationComplete.emit(result)

    def _on_error(self, error_tuple):
        """Handle error from worker."""
        exc_type, exc_value, exc_tb = error_tuple
        error_msg = str(exc_value) if exc_value else "Unknown error"

        self.status_label.setText(f"ERROR: {error_msg}")
        self.status_label.setStyleSheet("""
            color: #f14c4c;
            font-weight: bold;
            font-size: 12px;
            padding: 4px;
            border: 1px solid #f14c4c;
            border-radius: 4px;
        """)

        result = StemResult(
            success=False,
            error=error_msg,
            source_file=self._current_file
        )
        self.separationComplete.emit(result)

    def _on_finished(self):
        """Handle worker finished."""
        self.separate_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self._worker = None

    def is_processing(self) -> bool:
        """Check if separation is currently in progress."""
        return self._worker is not None
