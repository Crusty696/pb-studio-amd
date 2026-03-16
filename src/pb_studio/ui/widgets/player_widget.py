from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlayerWidget(QWidget):
    """Minimal placeholder media player widget for verification/import stability."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_media = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self.status_label = QLabel("No media loaded")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #cccccc; background-color: #1e1e1e; border: 1px solid #3e3e42; border-radius: 4px; padding: 16px;")
        layout.addWidget(self.status_label)

    def load_media(self, file_path: str):
        self.current_media = file_path
        self.status_label.setText(f"Loaded media:\n{file_path}")
