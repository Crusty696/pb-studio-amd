"""
Scene List Widget for PB Studio AMD.

Displays detected video scenes in a table format with selection support.
"""

import logging
from dataclasses import dataclass
from typing import Optional, List

from PyQt6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QLabel,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QBrush, QPixmap, QImage

logger = logging.getLogger(__name__)


@dataclass
class SceneInfo:
    """Data class for scene information."""
    index: int
    start_time: float  # Seconds
    end_time: float    # Seconds
    thumbnail: Optional[bytes] = None  # JPEG/PNG bytes (optional)
    label: str = ""

    @property
    def duration(self) -> float:
        """Calculate scene duration in seconds."""
        return self.end_time - self.start_time


class SceneListWidget(QTableWidget):
    """
    Table widget displaying detected video scenes.

    Features:
    - Columns: #, Start, End, Duration, Thumbnail (optional)
    - Single and multi-selection support
    - Scene highlighting
    - Double-click to seek to scene

    Signals:
        sceneClicked(int): Emitted when a scene row is clicked (index)
        sceneSelected(list[int]): Emitted when selection changes (list of indices)
        sceneDoubleClicked(int): Emitted on double-click (index)
    """

    sceneClicked = pyqtSignal(int)
    sceneSelected = pyqtSignal(list)
    sceneDoubleClicked = pyqtSignal(int)

    # Column indices
    COL_INDEX = 0
    COL_START = 1
    COL_END = 2
    COL_DURATION = 3
    COL_THUMBNAIL = 4

    def __init__(self, parent=None, show_thumbnails: bool = False):
        """
        Initialize the scene list widget.

        Args:
            parent: Parent widget
            show_thumbnails: Whether to show thumbnail column
        """
        super().__init__(parent)

        self._scenes: List[SceneInfo] = []
        self._show_thumbnails = show_thumbnails
        self._highlighted_scene: int = -1

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Configure table appearance and behavior."""
        # Set column count based on thumbnail visibility
        col_count = 5 if self._show_thumbnails else 4
        self.setColumnCount(col_count)

        # Set headers
        headers = ["#", "Start", "End", "Duration"]
        if self._show_thumbnails:
            headers.append("Thumbnail")
        self.setHorizontalHeaderLabels(headers)

        # Configure header
        header = self.horizontalHeader()
        header.setSectionResizeMode(self.COL_INDEX, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(self.COL_START, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_END, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_DURATION, QHeaderView.ResizeMode.Stretch)

        if self._show_thumbnails:
            header.setSectionResizeMode(self.COL_THUMBNAIL, QHeaderView.ResizeMode.Fixed)
            self.setColumnWidth(self.COL_THUMBNAIL, 120)

        # Fixed widths
        self.setColumnWidth(self.COL_INDEX, 50)

        # Selection behavior
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # Disable editing
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Row height for thumbnails
        if self._show_thumbnails:
            self.verticalHeader().setDefaultSectionSize(68)
        else:
            self.verticalHeader().setDefaultSectionSize(30)

        # Hide vertical header (row numbers)
        self.verticalHeader().setVisible(False)

        # Alternating row colors
        self.setAlternatingRowColors(True)

        # Style
        self.setStyleSheet("""
            QTableWidget {
                background-color: #252526;
                gridline-color: #3e3e42;
                border: none;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #094770;
            }
            QTableWidget::item:hover {
                background-color: #2a2d2e;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                padding: 5px;
                border: none;
                border-right: 1px solid #3e3e42;
            }
        """)

    def _connect_signals(self):
        """Connect internal signals."""
        self.cellClicked.connect(self._on_cell_clicked)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.itemSelectionChanged.connect(self._on_selection_changed)

    def _on_cell_clicked(self, row: int, col: int):
        """Handle cell click."""
        if 0 <= row < len(self._scenes):
            scene_index = self._scenes[row].index
            self.sceneClicked.emit(scene_index)

    def _on_cell_double_clicked(self, row: int, col: int):
        """Handle cell double-click."""
        if 0 <= row < len(self._scenes):
            scene_index = self._scenes[row].index
            self.sceneDoubleClicked.emit(scene_index)

    def _on_selection_changed(self):
        """Handle selection change."""
        selected_rows = set(item.row() for item in self.selectedItems())
        selected_indices = [
            self._scenes[row].index
            for row in selected_rows
            if 0 <= row < len(self._scenes)
        ]
        self.sceneSelected.emit(selected_indices)

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as MM:SS.mmm"""
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:06.3f}"

    def set_scenes(self, scenes: List[SceneInfo]):
        """
        Set the list of scenes to display.

        Args:
            scenes: List of SceneInfo objects
        """
        self._scenes = scenes
        self._highlighted_scene = -1

        # Clear and rebuild table
        self.setRowCount(0)
        self.setRowCount(len(scenes))

        for row, scene in enumerate(scenes):
            # Index column
            index_item = QTableWidgetItem(str(scene.index + 1))
            index_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, self.COL_INDEX, index_item)

            # Start time
            start_item = QTableWidgetItem(self._format_time(scene.start_time))
            start_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, self.COL_START, start_item)

            # End time
            end_item = QTableWidgetItem(self._format_time(scene.end_time))
            end_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, self.COL_END, end_item)

            # Duration
            duration_item = QTableWidgetItem(f"{scene.duration:.2f}s")
            duration_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, self.COL_DURATION, duration_item)

            # Thumbnail (if enabled)
            if self._show_thumbnails and scene.thumbnail:
                self._set_thumbnail(row, scene.thumbnail)

        logger.info(f"Scene list updated: {len(scenes)} scenes")

    def _set_thumbnail(self, row: int, thumbnail_data: bytes):
        """Set thumbnail image for a row."""
        try:
            # Create QImage from bytes
            image = QImage()
            if image.loadFromData(thumbnail_data):
                # Scale to fit cell
                pixmap = QPixmap.fromImage(image).scaled(
                    110, 62,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )

                # Create label to hold pixmap
                label = QLabel()
                label.setPixmap(pixmap)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setStyleSheet("background-color: transparent;")

                self.setCellWidget(row, self.COL_THUMBNAIL, label)
        except Exception as e:
            logger.debug(f"Failed to set thumbnail: {e}")

    def highlight_scene(self, scene_index: int):
        """
        Highlight a specific scene row.

        Args:
            scene_index: Index of scene to highlight (-1 to clear)
        """
        # Clear previous highlight
        if self._highlighted_scene >= 0:
            for row, scene in enumerate(self._scenes):
                if scene.index == self._highlighted_scene:
                    self._set_row_background(row, None)
                    break

        self._highlighted_scene = scene_index

        # Apply new highlight
        if scene_index >= 0:
            for row, scene in enumerate(self._scenes):
                if scene.index == scene_index:
                    self._set_row_background(row, QColor("#2d5a2d"))  # Green tint

                    # Scroll to make visible
                    self.scrollToItem(
                        self.item(row, 0),
                        QAbstractItemView.ScrollHint.PositionAtCenter
                    )
                    break

    def _set_row_background(self, row: int, color: Optional[QColor]):
        """Set background color for entire row."""
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item:
                if color:
                    item.setBackground(QBrush(color))
                else:
                    # Reset to default
                    item.setBackground(QBrush())

    def get_selected_scenes(self) -> List[SceneInfo]:
        """Get list of currently selected scenes."""
        selected_rows = set(item.row() for item in self.selectedItems())
        return [
            self._scenes[row]
            for row in sorted(selected_rows)
            if 0 <= row < len(self._scenes)
        ]

    def get_scene_at_time(self, time_sec: float) -> Optional[SceneInfo]:
        """
        Find scene containing the specified time.

        Args:
            time_sec: Time in seconds

        Returns:
            SceneInfo if found, None otherwise
        """
        for scene in self._scenes:
            if scene.start_time <= time_sec < scene.end_time:
                return scene
        return None

    def clear_scenes(self):
        """Clear all scenes from the list."""
        self._scenes = []
        self._highlighted_scene = -1
        self.setRowCount(0)
