"""
File Drop Mixin

Mixin class to add drag-and-drop file support to any QWidget.
Accepts audio and video files.
"""
import logging
from pathlib import Path
from typing import List, Set
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent

logger = logging.getLogger(__name__)


class FileDropMixin:
    """
    Mixin class for adding drag-and-drop file support to QWidget subclasses.

    Usage:
        class MyWidget(QWidget, FileDropMixin):
            def __init__(self):
                super().__init__()
                self.init_file_drop()  # Call this in __init__
                self.filesDropped.connect(self.handle_files)

    Signals:
        filesDropped(list[str]): Emitted when files are dropped (list of file paths)

    Features:
        - Filters for audio and video file types
        - Visual feedback on drag enter/leave
        - Multiple file support
    """

    # Signal for dropped files - defined at class level
    # Note: This needs to be redefined in the actual class that uses this mixin
    # because PyQt signals must be defined in the class that inherits from QObject

    # Supported file extensions
    AUDIO_EXTENSIONS: Set[str] = {
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a',
        '.wma', '.aiff', '.alac', '.opus', '.webm'
    }

    VIDEO_EXTENSIONS: Set[str] = {
        '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
        '.webm', '.m4v', '.mpeg', '.mpg', '.3gp'
    }

    def init_file_drop(self,
                       accept_audio: bool = True,
                       accept_video: bool = True,
                       custom_extensions: Set[str] = None):
        """
        Initialize file drop functionality.

        Must be called in the __init__ of the class using this mixin.

        Args:
            accept_audio: Accept audio file types
            accept_video: Accept video file types
            custom_extensions: Additional extensions to accept (e.g., {'.json', '.xml'})
        """
        # Store configuration
        self._drop_accept_audio = accept_audio
        self._drop_accept_video = accept_video
        self._drop_custom_extensions = custom_extensions or set()

        # Track drag state for visual feedback
        self._drop_drag_active = False

        # Store original stylesheet for restoration
        self._drop_original_style = ""

        # Enable drops
        if isinstance(self, QWidget):
            self.setAcceptDrops(True)

    def _get_accepted_extensions(self) -> Set[str]:
        """Get the set of all accepted file extensions."""
        extensions = set()

        if self._drop_accept_audio:
            extensions.update(self.AUDIO_EXTENSIONS)
        if self._drop_accept_video:
            extensions.update(self.VIDEO_EXTENSIONS)
        extensions.update(self._drop_custom_extensions)

        return extensions

    def _is_valid_file(self, path: str) -> bool:
        """Check if a file path has an accepted extension."""
        ext = Path(path).suffix.lower()
        return ext in self._get_accepted_extensions()

    def _filter_valid_files(self, paths: List[str]) -> List[str]:
        """Filter list of paths to only valid files."""
        return [p for p in paths if self._is_valid_file(p)]

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            # Check if any dropped file is valid
            urls = event.mimeData().urls()
            paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
            valid_paths = self._filter_valid_files(paths)

            if valid_paths:
                event.acceptProposedAction()
                self._drop_drag_active = True
                self._show_drop_feedback(True)
                return

        event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        """Handle drag leave event."""
        self._drop_drag_active = False
        self._show_drop_feedback(False)
        event.accept()

    def dropEvent(self, event: QDropEvent):
        """Handle drop event."""
        self._drop_drag_active = False
        self._show_drop_feedback(False)

        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
            valid_paths = self._filter_valid_files(paths)

            if valid_paths:
                logger.info(f"Files dropped: {valid_paths}")
                event.acceptProposedAction()

                # Emit signal if available
                if hasattr(self, 'filesDropped'):
                    self.filesDropped.emit(valid_paths)
                return

        event.ignore()

    def _show_drop_feedback(self, active: bool):
        """Show visual feedback when dragging over widget."""
        if not isinstance(self, QWidget):
            return

        if active:
            # Store original style
            self._drop_original_style = self.styleSheet()

            # Add drop highlight
            highlight_style = """
                border: 2px dashed #007acc;
                background-color: rgba(0, 122, 204, 0.1);
            """
            self.setStyleSheet(self._drop_original_style + highlight_style)
        else:
            # Restore original style
            if self._drop_original_style:
                self.setStyleSheet(self._drop_original_style)

    def get_accepted_formats_text(self) -> str:
        """Get a human-readable string of accepted file formats."""
        extensions = self._get_accepted_extensions()
        sorted_ext = sorted(extensions)
        return ", ".join(ext.upper().lstrip('.') for ext in sorted_ext)


class DropZoneWidget(QWidget, FileDropMixin):
    """
    A ready-to-use drop zone widget.

    Example widget that combines QWidget with FileDropMixin.
    Shows a drop zone with text prompt.
    """

    # Define the signal here since we inherit from QObject via QWidget
    filesDropped = pyqtSignal(list)

    def __init__(self,
                 prompt_text: str = "Drop files here",
                 accept_audio: bool = True,
                 accept_video: bool = True,
                 parent=None):
        super().__init__(parent)

        self._prompt_text = prompt_text
        self.init_file_drop(accept_audio=accept_audio, accept_video=accept_video)
        self._apply_styling()

    def _apply_styling(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            DropZoneWidget {
                background-color: #252526;
                border: 2px dashed #3e3e42;
                border-radius: 8px;
                min-height: 100px;
            }
            DropZoneWidget:hover {
                border-color: #007acc;
            }
        """)
        self.setMinimumHeight(100)

    def paintEvent(self, event):
        """Draw the drop zone prompt."""
        from PyQt6.QtGui import QPainter, QFont

        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Center text
        font = QFont("Segoe UI", 12)
        painter.setFont(font)

        if self._drop_drag_active:
            painter.setPen(Qt.GlobalColor.white)
            text = "Release to drop"
        else:
            painter.setPen(Qt.GlobalColor.gray)
            text = self._prompt_text

        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

        # Show accepted formats
        if not self._drop_drag_active:
            font.setPointSize(9)
            painter.setFont(font)
            formats = self.get_accepted_formats_text()
            rect = self.rect().adjusted(0, 30, 0, 0)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"({formats})")
