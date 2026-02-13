"""
Render Progress Widget for PB Studio AMD.

Displays progress during video generation with detailed step tracking.
"""

import logging
from enum import Enum
from typing import Optional

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

logger = logging.getLogger(__name__)


class RenderStep(Enum):
    """Steps in the rendering process."""
    IDLE = "idle"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    RENDERING = "rendering"
    CONCATENATING = "concatenating"
    ENCODING = "encoding"
    COMPLETE = "complete"
    ERROR = "error"
    CANCELLED = "cancelled"


class RenderProgressWidget(QFrame):
    """
    Widget for displaying video rendering progress.

    Features:
    - Overall progress bar
    - Current step indicator
    - ETA and frame count display
    - Cancel button

    Signals:
        cancelRequested: Emitted when user clicks cancel
    """

    cancelRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_step = RenderStep.IDLE
        self._start_time: Optional[float] = None
        self._eta_timer = QTimer(self)
        self._eta_timer.timeout.connect(self._update_eta)
        self._total_frames = 0
        self._current_frame = 0
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Rendering Progress")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        header.addWidget(title)
        header.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #d9534f;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 6px 15px;
            }
            QPushButton:hover {
                background-color: #c9302c;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
        """)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self.cancel_btn.setEnabled(False)
        header.addWidget(self.cancel_btn)

        layout.addLayout(header)

        # Overall Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3e3e42;
                border-radius: 4px;
                background-color: #1e1e1e;
                height: 24px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Status Row
        status_row = QHBoxLayout()

        # Current Step
        step_container = QVBoxLayout()
        step_label = QLabel("Current Step")
        step_label.setStyleSheet("color: #888888; font-size: 11px;")
        step_container.addWidget(step_label)
        self.step_value = QLabel("Idle")
        self.step_value.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")
        step_container.addWidget(self.step_value)
        status_row.addLayout(step_container)

        status_row.addStretch()

        # ETA
        eta_container = QVBoxLayout()
        eta_label = QLabel("Estimated Time")
        eta_label.setStyleSheet("color: #888888; font-size: 11px;")
        eta_container.addWidget(eta_label)
        self.eta_value = QLabel("--:--")
        self.eta_value.setStyleSheet("color: #ffffff; font-size: 14px;")
        eta_container.addWidget(self.eta_value)
        status_row.addLayout(eta_container)

        status_row.addStretch()

        # Frame Count
        frame_container = QVBoxLayout()
        frame_label = QLabel("Progress")
        frame_label.setStyleSheet("color: #888888; font-size: 11px;")
        frame_container.addWidget(frame_label)
        self.frame_value = QLabel("0 / 0")
        self.frame_value.setStyleSheet("color: #ffffff; font-size: 14px;")
        frame_container.addWidget(self.frame_value)
        status_row.addLayout(frame_container)

        layout.addLayout(status_row)

        # Sub-step Progress
        self.substep_widget = QWidget()
        substep_layout = QVBoxLayout(self.substep_widget)
        substep_layout.setContentsMargins(0, 10, 0, 0)
        substep_layout.setSpacing(8)

        substep_header = QLabel("Sub-Steps")
        substep_header.setStyleSheet("color: #888888; font-size: 11px;")
        substep_layout.addWidget(substep_header)

        # Step indicators
        self.step_indicators = {}
        steps = [
            (RenderStep.ANALYZING, "Audio Analysis"),
            (RenderStep.PLANNING, "Planning Cuts"),
            (RenderStep.RENDERING, "Rendering Segments"),
            (RenderStep.CONCATENATING, "Concatenating"),
            (RenderStep.ENCODING, "Final Encoding"),
        ]

        for step, label_text in steps:
            step_row = QHBoxLayout()
            indicator = QLabel("○")
            indicator.setStyleSheet("color: #555555; font-size: 14px;")
            step_row.addWidget(indicator)
            label = QLabel(label_text)
            label.setStyleSheet("color: #888888;")
            step_row.addWidget(label)
            step_row.addStretch()
            substep_layout.addLayout(step_row)
            self.step_indicators[step] = (indicator, label)

        layout.addWidget(self.substep_widget)

        # Status Message
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888888; font-style: italic;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def start(self, total_items: int = 0):
        """
        Start the progress tracking.

        Args:
            total_items: Total number of items to process (e.g., clips)
        """
        import time
        self._start_time = time.time()
        self._total_frames = total_items
        self._current_frame = 0
        self._current_step = RenderStep.IDLE

        self.progress_bar.setValue(0)
        self.cancel_btn.setEnabled(True)
        self.frame_value.setText(f"0 / {total_items}" if total_items else "0 / ?")
        self.eta_value.setText("Calculating...")
        self.status_label.setText("Starting...")

        # Reset step indicators
        for indicator, label in self.step_indicators.values():
            indicator.setStyleSheet("color: #555555; font-size: 14px;")
            indicator.setText("○")
            label.setStyleSheet("color: #888888;")

        self._eta_timer.start(1000)

    def set_step(self, step: RenderStep):
        """
        Update the current rendering step.

        Args:
            step: The current RenderStep
        """
        self._current_step = step

        step_names = {
            RenderStep.IDLE: "Idle",
            RenderStep.ANALYZING: "Analyzing Audio",
            RenderStep.PLANNING: "Planning Cuts",
            RenderStep.RENDERING: "Rendering Segments",
            RenderStep.CONCATENATING: "Concatenating",
            RenderStep.ENCODING: "Final Encoding",
            RenderStep.COMPLETE: "Complete!",
            RenderStep.ERROR: "Error",
            RenderStep.CANCELLED: "Cancelled",
        }

        self.step_value.setText(step_names.get(step, str(step)))

        # Update step indicators
        step_order = [
            RenderStep.ANALYZING,
            RenderStep.PLANNING,
            RenderStep.RENDERING,
            RenderStep.CONCATENATING,
            RenderStep.ENCODING,
        ]

        try:
            current_index = step_order.index(step)
        except ValueError:
            current_index = -1

        for i, s in enumerate(step_order):
            if s in self.step_indicators:
                indicator, label = self.step_indicators[s]
                if i < current_index:
                    # Completed
                    indicator.setText("✓")
                    indicator.setStyleSheet("color: #5cb85c; font-size: 14px;")
                    label.setStyleSheet("color: #5cb85c;")
                elif i == current_index:
                    # Current
                    indicator.setText("●")
                    indicator.setStyleSheet("color: #007acc; font-size: 14px;")
                    label.setStyleSheet("color: #007acc; font-weight: bold;")
                else:
                    # Pending
                    indicator.setText("○")
                    indicator.setStyleSheet("color: #555555; font-size: 14px;")
                    label.setStyleSheet("color: #888888;")

    def set_progress(self, value: int, current_item: int = 0, total_items: int = 0):
        """
        Update the progress bar.

        Args:
            value: Progress percentage (0-100)
            current_item: Current item number
            total_items: Total items
        """
        self.progress_bar.setValue(value)

        if total_items > 0:
            self._total_frames = total_items
            self._current_frame = current_item
            self.frame_value.setText(f"{current_item} / {total_items}")

    def set_status(self, message: str):
        """Update the status message."""
        self.status_label.setText(message)

    def finish(self, success: bool = True, message: str = ""):
        """
        Mark the rendering as complete.

        Args:
            success: Whether rendering succeeded
            message: Optional completion message
        """
        self._eta_timer.stop()
        self.cancel_btn.setEnabled(False)

        if success:
            self.progress_bar.setValue(100)
            self.set_step(RenderStep.COMPLETE)
            self.eta_value.setText("Done")

            # Mark all steps as complete
            for indicator, label in self.step_indicators.values():
                indicator.setText("✓")
                indicator.setStyleSheet("color: #5cb85c; font-size: 14px;")
                label.setStyleSheet("color: #5cb85c;")

            self.status_label.setText(message or "Rendering complete!")
            self.status_label.setStyleSheet("color: #5cb85c; font-style: italic;")
        else:
            self.set_step(RenderStep.ERROR)
            self.status_label.setText(message or "Rendering failed")
            self.status_label.setStyleSheet("color: #d9534f; font-style: italic;")

    def cancel(self):
        """Handle cancellation (called externally after cancel is processed)."""
        self._eta_timer.stop()
        self.cancel_btn.setEnabled(False)
        self.set_step(RenderStep.CANCELLED)
        self.status_label.setText("Rendering cancelled by user")
        self.status_label.setStyleSheet("color: #f0ad4e; font-style: italic;")

    def reset(self):
        """Reset the widget to initial state."""
        self._eta_timer.stop()
        self._current_step = RenderStep.IDLE
        self._start_time = None
        self._total_frames = 0
        self._current_frame = 0

        self.progress_bar.setValue(0)
        self.cancel_btn.setEnabled(False)
        self.step_value.setText("Idle")
        self.eta_value.setText("--:--")
        self.frame_value.setText("0 / 0")
        self.status_label.setText("")
        self.status_label.setStyleSheet("color: #888888; font-style: italic;")

        for indicator, label in self.step_indicators.values():
            indicator.setText("○")
            indicator.setStyleSheet("color: #555555; font-size: 14px;")
            label.setStyleSheet("color: #888888;")

    def _on_cancel_clicked(self):
        """Handle cancel button click."""
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("Cancelling...")
        self.cancelRequested.emit()

    def _update_eta(self):
        """Update the ETA display."""
        import time

        if self._start_time is None:
            return

        elapsed = time.time() - self._start_time
        progress = self.progress_bar.value()

        if progress > 0 and progress < 100:
            # Estimate remaining time
            total_estimated = elapsed / (progress / 100.0)
            remaining = total_estimated - elapsed

            if remaining > 0:
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                self.eta_value.setText(f"{minutes:02d}:{seconds:02d}")
            else:
                self.eta_value.setText("< 1 min")
        elif progress >= 100:
            self.eta_value.setText("Done")
            self._eta_timer.stop()
