"""
Result Card Widget

Displays a label-value pair with optional icon.
Used for showing analysis results like BPM, Key, etc.
"""
import logging
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap

logger = logging.getLogger(__name__)


class ResultCard(QFrame):
    """
    A card widget displaying a label-value pair.

    Features:
    - Optional icon
    - Label (e.g., "BPM")
    - Value (e.g., "128")
    - Dark theme styling
    """

    def __init__(self, label: str = "Label", value: str = "--", parent=None):
        super().__init__(parent)
        self._setup_ui(label, value)
        self._apply_styling()

    def _setup_ui(self, label: str, value: str):
        """Initialize UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Icon label (hidden by default)
        self._icon_label = QLabel()
        self._icon_label.setObjectName("ResultCardIcon")
        self._icon_label.setFixedSize(32, 32)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setVisible(False)
        layout.addWidget(self._icon_label)

        # Text container
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        # Label
        self._label = QLabel(label)
        self._label.setObjectName("ResultCardLabel")
        text_layout.addWidget(self._label)

        # Value
        self._value_label = QLabel(value)
        self._value_label.setObjectName("ResultCardValue")
        text_layout.addWidget(self._value_label)

        layout.addLayout(text_layout)
        layout.addStretch()

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(70)

    def _apply_styling(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            ResultCard {
                background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 8px;
            }
            QLabel#ResultCardLabel {
                color: #9d9d9d;
                font-size: 12px;
                font-weight: normal;
            }
            QLabel#ResultCardValue {
                color: #ffffff;
                font-size: 24px;
                font-weight: bold;
            }
            QLabel#ResultCardIcon {
                background-color: #1e1e1e;
                border-radius: 4px;
            }
        """)

    def set_label(self, text: str):
        """
        Set label text.

        Args:
            text: Label to display (e.g., "BPM")
        """
        self._label.setText(text)

    def get_label(self) -> str:
        """Get current label text."""
        return self._label.text()

    def set_value(self, value):
        """
        Set value to display.

        Args:
            value: Value to display (str, int, or float)
        """
        if isinstance(value, float):
            # Format floats with 2 decimal places
            text = f"{value:.2f}"
        else:
            text = str(value)
        self._value_label.setText(text)

    def get_value(self) -> str:
        """Get current value text."""
        return self._value_label.text()

    def set_icon(self, icon: QIcon):
        """
        Set icon from QIcon.

        Args:
            icon: QIcon to display
        """
        pixmap = icon.pixmap(24, 24)
        self._icon_label.setPixmap(pixmap)
        self._icon_label.setVisible(True)

    def set_icon_from_path(self, path: str):
        """
        Set icon from file path.

        Args:
            path: Path to icon file
        """
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                24, 24,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self._icon_label.setPixmap(scaled)
            self._icon_label.setVisible(True)
        else:
            logger.warning(f"Failed to load icon: {path}")

    def set_icon_text(self, text: str, color: str = "#007acc"):
        """
        Set text as icon (emoji or single character).

        Args:
            text: Text to show as icon (e.g., emoji)
            color: Text color (hex)
        """
        self._icon_label.setText(text)
        self._icon_label.setStyleSheet(f"""
            QLabel#ResultCardIcon {{
                background-color: #1e1e1e;
                border-radius: 4px;
                color: {color};
                font-size: 18px;
            }}
        """)
        self._icon_label.setVisible(True)

    def hide_icon(self):
        """Hide the icon."""
        self._icon_label.setVisible(False)

    def set_value_color(self, color: str):
        """
        Set value text color.

        Args:
            color: Color in hex format (e.g., "#00ff00")
        """
        self._value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")

    def set_compact(self, compact: bool = True):
        """
        Enable compact mode with smaller text.

        Args:
            compact: True for compact mode
        """
        if compact:
            self._value_label.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold;")
            self.setMinimumHeight(56)
        else:
            self._value_label.setStyleSheet("color: #ffffff; font-size: 24px; font-weight: bold;")
            self.setMinimumHeight(70)
