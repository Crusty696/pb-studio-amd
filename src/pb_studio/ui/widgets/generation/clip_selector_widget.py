"""
Clip Selector Widget for PB Studio AMD.

Provides a list of source videos with thumbnails, drag-and-drop ordering,
and include/exclude toggles.
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QAbstractItemView, QFileDialog, QCheckBox, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QIcon

logger = logging.getLogger(__name__)


class ClipItemWidget(QWidget):
    """Custom widget for displaying a clip item with thumbnail and checkbox."""

    toggled = pyqtSignal(str, bool)  # path, included

    def __init__(self, path: str, thumbnail: Optional[QPixmap] = None, parent=None):
        super().__init__(parent)
        self.path = path
        self._init_ui(thumbnail)

    def _init_ui(self, thumbnail: Optional[QPixmap]):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        self.checkbox.toggled.connect(lambda checked: self.toggled.emit(self.path, checked))
        layout.addWidget(self.checkbox)

        # Thumbnail
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(64, 36)
        self.thumb_label.setStyleSheet("background-color: #1e1e1e; border: 1px solid #3e3e42;")
        self.thumb_label.setScaledContents(True)
        if thumbnail:
            self.thumb_label.setPixmap(thumbnail)
        layout.addWidget(self.thumb_label)

        # Filename
        filename = Path(self.path).name
        self.name_label = QLabel(filename)
        self.name_label.setStyleSheet("color: #ffffff;")
        self.name_label.setToolTip(self.path)
        layout.addWidget(self.name_label, 1)

    def is_included(self) -> bool:
        """Check if this clip is included."""
        return self.checkbox.isChecked()

    def set_included(self, included: bool):
        """Set the inclusion state."""
        self.checkbox.setChecked(included)

    def set_thumbnail(self, pixmap: QPixmap):
        """Update the thumbnail."""
        self.thumb_label.setPixmap(pixmap)


class ClipSelectorWidget(QFrame):
    """
    Widget for selecting and ordering source video clips.

    Features:
    - List of available source videos with thumbnails
    - Drag and drop reordering
    - Include/exclude checkbox for each clip
    - Add/remove clips buttons

    Signals:
        selectionChanged(list[str]): Emitted when selection or order changes.
            Contains only the paths of included clips in order.
    """

    selectionChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clips: dict[str, ClipItemWidget] = {}
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        title = QLabel("Source Videos")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        header.addWidget(title)
        header.addStretch()

        # Buttons
        self.add_btn = QPushButton("Add")
        self.add_btn.setStyleSheet(self._button_style())
        self.add_btn.clicked.connect(self._on_add_clicked)
        header.addWidget(self.add_btn)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setStyleSheet(self._button_style())
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        header.addWidget(self.remove_btn)

        layout.addLayout(header)

        # Instruction
        instruction = QLabel("Drag to reorder. Uncheck to exclude from generation.")
        instruction.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(instruction)

        # Clip list
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 4px;
            }
            QListWidget::item {
                border-bottom: 1px solid #3e3e42;
                padding: 2px;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
            QListWidget::item:hover {
                background-color: #2d2d30;
            }
        """)
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_widget.model().rowsMoved.connect(self._on_order_changed)
        layout.addWidget(self.list_widget)

        # Selection info
        self.info_label = QLabel("0 clips selected")
        self.info_label.setStyleSheet("color: #888888;")
        layout.addWidget(self.info_label)

    def add_clip(self, path: str, generate_thumbnail: bool = True):
        """
        Add a video clip to the selector.

        Args:
            path: Path to the video file
            generate_thumbnail: Whether to generate a thumbnail
        """
        if path in self._clips:
            logger.debug(f"Clip already added: {path}")
            return

        # Generate thumbnail
        thumbnail = None
        if generate_thumbnail:
            thumbnail = self._generate_thumbnail(path)

        # Create item widget
        item_widget = ClipItemWidget(path, thumbnail)
        item_widget.toggled.connect(self._on_clip_toggled)

        # Add to list
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 50))
        item.setData(Qt.ItemDataRole.UserRole, path)

        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, item_widget)

        self._clips[path] = item_widget
        self._update_info()
        self._emit_selection()

    def add_clips(self, paths: list[str]):
        """Add multiple video clips."""
        for path in paths:
            self.add_clip(path)

    def remove_clip(self, path: str):
        """Remove a clip from the selector."""
        if path not in self._clips:
            return

        # Find and remove the item
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                self.list_widget.takeItem(i)
                break

        del self._clips[path]
        self._update_info()
        self._emit_selection()

    def clear_clips(self):
        """Remove all clips."""
        self.list_widget.clear()
        self._clips.clear()
        self._update_info()
        self._emit_selection()

    def get_selected_clips(self) -> list[str]:
        """
        Get the list of included clips in order.

        Returns:
            List of paths for included clips
        """
        result = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            path = item.data(Qt.ItemDataRole.UserRole)
            widget = self._clips.get(path)
            if widget and widget.is_included():
                result.append(path)
        return result

    def get_all_clips(self) -> list[str]:
        """
        Get all clips in order (including excluded ones).

        Returns:
            List of all clip paths
        """
        result = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            result.append(item.data(Qt.ItemDataRole.UserRole))
        return result

    def _generate_thumbnail(self, path: str) -> Optional[QPixmap]:
        """Generate a thumbnail for a video file using FFmpeg."""
        try:
            import tempfile
            thumb_path = Path(tempfile.gettempdir()) / f"pb_thumb_{hash(path)}.jpg"

            # Extract frame at 1 second
            from src.pb_studio.config_manager import ConfigManager
            ffmpeg_path = ConfigManager().ffmpeg_path
            cmd = [
                ffmpeg_path, "-y",
                "-ss", "1",
                "-i", str(path),
                "-vframes", "1",
                "-vf", "scale=128:72",
                str(thumb_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=5
            )

            if result.returncode == 0 and thumb_path.exists():
                pixmap = QPixmap(str(thumb_path))
                thumb_path.unlink()  # Clean up
                return pixmap

        except Exception as e:
            logger.debug(f"Failed to generate thumbnail for {path}: {e}")

        return None

    def _on_add_clicked(self):
        """Handle add button click."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video Files",
            "",
            "Video Files (*.mp4 *.avi *.mkv *.mov *.webm);;All Files (*)"
        )
        if files:
            self.add_clips(files)

    def _on_remove_clicked(self):
        """Handle remove button click."""
        current = self.list_widget.currentItem()
        if current:
            path = current.data(Qt.ItemDataRole.UserRole)
            self.remove_clip(path)

    def _on_clip_toggled(self, path: str, included: bool):
        """Handle clip checkbox toggle."""
        logger.debug(f"Clip {'included' if included else 'excluded'}: {path}")
        self._update_info()
        self._emit_selection()

    def _on_order_changed(self):
        """Handle drag-drop reordering."""
        logger.debug("Clip order changed")
        self._emit_selection()

    def _update_info(self):
        """Update the info label."""
        selected = len(self.get_selected_clips())
        total = len(self._clips)
        self.info_label.setText(f"{selected} of {total} clips selected")

    def _emit_selection(self):
        """Emit the current selection."""
        selection = self.get_selected_clips()
        self.selectionChanged.emit(selection)

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
