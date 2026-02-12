"""
Progress Card Widget

Displays a card with title, progress bar and status text.
Styled for dark theme consistency with PB Studio.
"""
import logging
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


class ProgressCard(QFrame):
    """
    A card widget displaying progress information.

    Features:
    - Title label
    - Progress bar (0-100)
    - Status text label
    - Dark theme styling
    """

    def __init__(self, title: str = "Progress", parent=None):
        super().__init__(parent)
        self._setup_ui(title)
        self._apply_styling()

    def _setup_ui(self, title: str):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title label
        self._title_label = QLabel(title)
        self._title_label.setObjectName("ProgressCardTitle")
        layout.addWidget(self._title_label)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("ProgressCardBar")
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setMinimumHeight(24)
        layout.addWidget(self._progress_bar)

        # Status label
        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("ProgressCardStatus")
        layout.addWidget(self._status_label)

        # Stretch to push content to top
        layout.addStretch()

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(120)

    def _apply_styling(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            ProgressCard {
                background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 8px;
            }
            QLabel#ProgressCardTitle {
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
            }
            QLabel#ProgressCardStatus {
                color: #9d9d9d;
                font-size: 13px;
            }
            QProgressBar#ProgressCardBar {
                background-color: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar#ProgressCardBar::chunk {
                background-color: #007acc;
                border-radius: 3px;
            }
        """)

    def set_progress(self, value: int):
        """
        Set progress bar value.

        Args:
            value: Progress value (0-100)
        """
        clamped = max(0, min(100, value))
        self._progress_bar.setValue(clamped)

    def get_progress(self) -> int:
        """Get current progress value."""
        return self._progress_bar.value()

    def set_status(self, text: str):
        """
        Set status text.

        Args:
            text: Status message to display
        """
        self._status_label.setText(text)

    def get_status(self) -> str:
        """Get current status text."""
        return self._status_label.text()

    def set_title(self, text: str):
        """
        Set title text.

        Args:
            text: Title to display
        """
        self._title_label.setText(text)

    def get_title(self) -> str:
        """Get current title text."""
        return self._title_label.text()

    def reset(self):
        """Reset card to initial state."""
        self._progress_bar.setValue(0)
        self._status_label.setText("Ready")

    def set_indeterminate(self, enabled: bool = True):
        """
        Enable/disable indeterminate mode (bouncing progress).

        Args:
            enabled: True for indeterminate, False for determinate
        """
        if enabled:
            self._progress_bar.setMinimum(0)
            self._progress_bar.setMaximum(0)
        else:
            self._progress_bar.setMinimum(0)
            self._progress_bar.setMaximum(100)

    def set_error(self, message: str):
        """
        Set card to error state.

        Args:
            message: Error message to display
        """
        self._status_label.setText(f"Error: {message}")
        self._status_label.setStyleSheet("color: #f44747;")

    def clear_error(self):
        """Clear error state and restore normal styling."""
        self._status_label.setStyleSheet("color: #9d9d9d;")
