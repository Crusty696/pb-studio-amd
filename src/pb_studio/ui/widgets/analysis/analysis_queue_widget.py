"""
Analysis Queue Widget

Provides UI for batch analysis of multiple files.
Coordinates audio, video and AI analysis steps.
"""
import logging
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
    QFileDialog, QAbstractItemView, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool
from PyQt6.QtGui import QColor

from ..common.progress_card import ProgressCard
from ....workers.audio.audio_analyze_worker import AudioAnalyzeWorker
from ....workers.video.video_scene_worker import VideoSceneWorker
from ....workers.video.video_motion_worker import VideoMotionWorker
from ....workers.video.video_vision_worker import VideoVisionWorker
from ....models.audio import AudioAnalysisResult
from ....models.video import SceneInfo, MotionData

logger = logging.getLogger(__name__)


class AnalysisStatus(Enum):
    """Status of file analysis."""
    PENDING = "Pending"
    ANALYZING = "Analyzing"
    COMPLETE = "Complete"
    ERROR = "Error"


@dataclass
class QueueItem:
    """Item in the analysis queue."""
    file_path: str
    file_type: str  # "audio" or "video"
    status: AnalysisStatus = AnalysisStatus.PENDING
    progress: int = 0
    error_msg: str = ""

    # Results
    audio_result: Optional[AudioAnalysisResult] = None
    scenes: list[SceneInfo] = field(default_factory=list)
    motion_data: list[MotionData] = field(default_factory=list)
    captions: dict[int, dict[str, str]] = field(default_factory=dict)

    @property
    def file_name(self) -> str:
        """Get file name from path."""
        return Path(self.file_path).name

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "status": self.status.value,
            "audio_result": self.audio_result.to_dict() if self.audio_result else None,
            "scenes": [s.to_dict() for s in self.scenes],
            "motion_data": [m.to_dict() for m in self.motion_data],
            "captions": self.captions,
        }


class AnalysisQueueWidget(QFrame):
    """
    Analysis queue widget for batch processing multiple files.

    Displays a table with files and their analysis status.
    Coordinates AudioAnalyzeWorker, VideoSceneWorker, VideoMotionWorker,
    and VideoVisionWorker for comprehensive analysis.

    Signals:
        queueComplete: Emitted when all files are processed with list[dict]
        fileAnalyzed: Emitted when a single file completes with dict
    """

    # Signals
    queueComplete = pyqtSignal(list)  # list[dict]
    fileAnalyzed = pyqtSignal(dict)

    # Supported file extensions
    AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}
    VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".wmv"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: list[QueueItem] = []
        self._current_index: int = -1
        self._is_processing: bool = False

        # Current workers
        self._audio_worker: Optional[AudioAnalyzeWorker] = None
        self._scene_worker: Optional[VideoSceneWorker] = None
        self._motion_worker: Optional[VideoMotionWorker] = None
        self._vision_worker: Optional[VideoVisionWorker] = None

        # Analysis options
        self._run_motion: bool = True
        self._run_vision: bool = True

        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header with title and buttons
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        title = QLabel("Analysis Queue")
        title.setObjectName("QueueTitle")
        header_layout.addWidget(title)

        # File count label
        self._count_label = QLabel("0 files")
        self._count_label.setObjectName("CountLabel")
        header_layout.addWidget(self._count_label)

        header_layout.addStretch()

        # Buttons
        self._add_btn = QPushButton("Add Files")
        self._add_btn.setObjectName("AddButton")
        self._add_btn.clicked.connect(self._on_add_files)
        self._add_btn.setFixedWidth(100)
        header_layout.addWidget(self._add_btn)

        self._analyze_btn = QPushButton("Analyze All")
        self._analyze_btn.setObjectName("AnalyzeButton")
        self._analyze_btn.clicked.connect(self._on_analyze_all)
        self._analyze_btn.setEnabled(False)
        self._analyze_btn.setFixedWidth(100)
        header_layout.addWidget(self._analyze_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName("ClearButton")
        self._clear_btn.clicked.connect(self._on_clear)
        self._clear_btn.setEnabled(False)
        self._clear_btn.setFixedWidth(80)
        header_layout.addWidget(self._clear_btn)

        layout.addLayout(header_layout)

        # Overall progress
        self._overall_progress = QProgressBar()
        self._overall_progress.setObjectName("OverallProgress")
        self._overall_progress.setMinimum(0)
        self._overall_progress.setMaximum(100)
        self._overall_progress.setValue(0)
        self._overall_progress.setTextVisible(True)
        self._overall_progress.setFormat("Ready")
        self._overall_progress.setMinimumHeight(24)
        self._overall_progress.setVisible(False)
        layout.addWidget(self._overall_progress)

        # File table
        self._table = QTableWidget()
        self._table.setObjectName("QueueTable")
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["File", "Type", "Status", "Progress"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 80)
        self._table.setColumnWidth(2, 100)
        self._table.setColumnWidth(3, 100)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(200)
        layout.addWidget(self._table)

        # Current file progress
        self._current_progress = ProgressCard("Current File")
        self._current_progress.set_status("No file processing")
        self._current_progress.setVisible(False)
        layout.addWidget(self._current_progress)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    def _apply_styling(self):
        """Apply dark theme styling."""
        self.setStyleSheet("""
            AnalysisQueueWidget {
                background-color: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 8px;
                padding: 16px;
            }
            QLabel#QueueTitle {
                color: #ffffff;
                font-size: 18px;
                font-weight: bold;
            }
            QLabel#CountLabel {
                color: #9d9d9d;
                font-size: 14px;
            }
            QPushButton#AddButton {
                background-color: #2d2d30;
                color: #ffffff;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton#AddButton:hover {
                background-color: #3e3e42;
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
            QPushButton#ClearButton {
                background-color: #2d2d30;
                color: #ffffff;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton#ClearButton:hover {
                background-color: #5a1d1d;
                border-color: #f44747;
            }
            QPushButton#ClearButton:disabled {
                background-color: #2d2d30;
                color: #6e6e6e;
            }
            QTableWidget#QueueTable {
                background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                gridline-color: #3e3e42;
            }
            QTableWidget#QueueTable::item {
                padding: 8px;
                color: #ffffff;
            }
            QTableWidget#QueueTable::item:selected {
                background-color: #094771;
            }
            QHeaderView::section {
                background-color: #2d2d30;
                color: #9d9d9d;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #3e3e42;
            }
            QProgressBar#OverallProgress {
                background-color: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar#OverallProgress::chunk {
                background-color: #007acc;
                border-radius: 3px;
            }
        """)

    def add_files(self, file_paths: list[str]):
        """
        Add files to the analysis queue.

        Args:
            file_paths: List of file paths to add
        """
        for path in file_paths:
            file_ext = Path(path).suffix.lower()

            if file_ext in self.AUDIO_EXTENSIONS:
                file_type = "audio"
            elif file_ext in self.VIDEO_EXTENSIONS:
                file_type = "video"
            else:
                logger.warning(f"Unsupported file type: {path}")
                continue

            # Check for duplicates
            if any(item.file_path == path for item in self._queue):
                logger.info(f"File already in queue: {path}")
                continue

            item = QueueItem(file_path=path, file_type=file_type)
            self._queue.append(item)
            self._add_table_row(item)

        self._update_ui_state()

    def clear_queue(self):
        """Clear all files from the queue."""
        self._cancel_all_workers()
        self._queue.clear()
        self._current_index = -1
        self._table.setRowCount(0)
        self._update_ui_state()

    def get_results(self) -> list[dict]:
        """Get results for all processed files."""
        return [item.to_dict() for item in self._queue if item.status == AnalysisStatus.COMPLETE]

    def is_processing(self) -> bool:
        """Check if queue is currently processing."""
        return self._is_processing

    def set_analysis_options(self, run_motion: bool = True, run_vision: bool = True):
        """
        Set which AI analyses to run on video files.

        Args:
            run_motion: Run motion analysis
            run_vision: Run vision/caption analysis
        """
        self._run_motion = run_motion
        self._run_vision = run_vision

    def _add_table_row(self, item: QueueItem):
        """Add a row to the table for the given item."""
        row = self._table.rowCount()
        self._table.insertRow(row)

        # File name
        name_item = QTableWidgetItem(item.file_name)
        name_item.setToolTip(item.file_path)
        self._table.setItem(row, 0, name_item)

        # File type
        type_item = QTableWidgetItem(item.file_type.capitalize())
        type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 1, type_item)

        # Status
        status_item = QTableWidgetItem(item.status.value)
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 2, status_item)

        # Progress
        progress_item = QTableWidgetItem("0%")
        progress_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 3, progress_item)

    def _update_table_row(self, index: int, item: QueueItem):
        """Update the table row for the given item."""
        if index < 0 or index >= self._table.rowCount():
            return

        # Status with color
        status_item = self._table.item(index, 2)
        if status_item:
            status_item.setText(item.status.value)

            if item.status == AnalysisStatus.COMPLETE:
                status_item.setForeground(QColor("#4ec9b0"))
            elif item.status == AnalysisStatus.ERROR:
                status_item.setForeground(QColor("#f44747"))
            elif item.status == AnalysisStatus.ANALYZING:
                status_item.setForeground(QColor("#dcdcaa"))
            else:
                status_item.setForeground(QColor("#9d9d9d"))

        # Progress
        progress_item = self._table.item(index, 3)
        if progress_item:
            progress_item.setText(f"{item.progress}%")

    def _update_ui_state(self):
        """Update UI based on queue state."""
        has_items = len(self._queue) > 0
        has_pending = any(item.status == AnalysisStatus.PENDING for item in self._queue)

        self._count_label.setText(f"{len(self._queue)} files")
        self._analyze_btn.setEnabled(has_items and has_pending and not self._is_processing)
        self._clear_btn.setEnabled(has_items and not self._is_processing)
        self._add_btn.setEnabled(not self._is_processing)

        if self._is_processing:
            self._analyze_btn.setText("Stop")
            self._analyze_btn.setEnabled(True)
        else:
            self._analyze_btn.setText("Analyze All")

    def _on_add_files(self):
        """Handle add files button click."""
        all_extensions = list(self.AUDIO_EXTENSIONS) + list(self.VIDEO_EXTENSIONS)
        filter_str = f"Media Files (*{' *'.join(all_extensions)})"

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Files to Analysis Queue",
            "",
            filter_str
        )

        if files:
            self.add_files(files)

    def _on_analyze_all(self):
        """Handle analyze all button click."""
        if self._is_processing:
            self._stop_processing()
        else:
            self._start_processing()

    def _on_clear(self):
        """Handle clear button click."""
        self.clear_queue()

    def _start_processing(self):
        """Start processing the queue."""
        if self._is_processing:
            return

        self._is_processing = True
        self._current_index = -1

        # Show progress UI
        self._overall_progress.setVisible(True)
        self._current_progress.setVisible(True)
        self._overall_progress.setValue(0)
        self._overall_progress.setFormat("Starting...")

        self._update_ui_state()
        self._process_next()

    def _stop_processing(self):
        """Stop processing the queue."""
        self._cancel_all_workers()
        self._is_processing = False

        self._overall_progress.setFormat("Stopped")
        self._current_progress.set_status("Processing stopped")

        self._update_ui_state()

    def _process_next(self):
        """Process the next item in the queue."""
        if not self._is_processing:
            return

        # Find next pending item
        self._current_index += 1
        while self._current_index < len(self._queue):
            if self._queue[self._current_index].status == AnalysisStatus.PENDING:
                break
            self._current_index += 1

        if self._current_index >= len(self._queue):
            # Queue complete
            self._on_queue_complete()
            return

        item = self._queue[self._current_index]
        item.status = AnalysisStatus.ANALYZING
        item.progress = 0
        self._update_table_row(self._current_index, item)

        # Update overall progress
        completed = sum(1 for i in self._queue if i.status == AnalysisStatus.COMPLETE)
        total = len(self._queue)
        overall_pct = int((completed / total) * 100)
        self._overall_progress.setValue(overall_pct)
        self._overall_progress.setFormat(f"Processing {self._current_index + 1}/{total}")

        # Update current file progress
        self._current_progress.set_title(item.file_name)
        self._current_progress.reset()
        self._current_progress.set_status("Starting...")

        # Start appropriate analysis
        if item.file_type == "audio":
            self._start_audio_analysis(item)
        else:
            self._start_scene_detection(item)

    def _start_audio_analysis(self, item: QueueItem):
        """Start audio analysis for the item."""
        logger.info(f"Starting audio analysis: {item.file_path}")

        self._audio_worker = AudioAnalyzeWorker(item.file_path)
        self._audio_worker.signals.progress.connect(self._on_worker_progress)
        self._audio_worker.signals.result.connect(self._on_audio_result)
        self._audio_worker.signals.error.connect(self._on_worker_error)
        self._audio_worker.signals.finished.connect(self._on_audio_finished)

        QThreadPool.globalInstance().start(self._audio_worker)

    def _start_scene_detection(self, item: QueueItem):
        """Start scene detection for the item."""
        logger.info(f"Starting scene detection: {item.file_path}")

        self._scene_worker = VideoSceneWorker(item.file_path)
        self._scene_worker.signals.progress.connect(self._on_worker_progress)
        self._scene_worker.signals.result.connect(self._on_scene_result)
        self._scene_worker.signals.error.connect(self._on_worker_error)
        self._scene_worker.signals.finished.connect(self._on_scene_finished)

        QThreadPool.globalInstance().start(self._scene_worker)

    def _start_motion_analysis(self, item: QueueItem):
        """Start motion analysis for the item."""
        if not self._run_motion or not item.scenes:
            self._start_vision_analysis(item)
            return

        logger.info(f"Starting motion analysis: {item.file_path}")

        self._motion_worker = VideoMotionWorker(item.file_path, item.scenes)
        self._motion_worker.signals.progress.connect(self._on_worker_progress)
        self._motion_worker.signals.result.connect(self._on_motion_result)
        self._motion_worker.signals.error.connect(self._on_worker_error)
        self._motion_worker.signals.finished.connect(self._on_motion_finished)

        QThreadPool.globalInstance().start(self._motion_worker)

    def _start_vision_analysis(self, item: QueueItem):
        """Start vision analysis for the item."""
        if not self._run_vision or not item.scenes:
            self._on_item_complete(item)
            return

        logger.info(f"Starting vision analysis: {item.file_path}")

        self._vision_worker = VideoVisionWorker(item.file_path, item.scenes)
        self._vision_worker.signals.progress.connect(self._on_worker_progress)
        self._vision_worker.signals.result.connect(self._on_vision_result)
        self._vision_worker.signals.error.connect(self._on_worker_error)
        self._vision_worker.signals.finished.connect(self._on_vision_finished)

        QThreadPool.globalInstance().start(self._vision_worker)

    def _on_worker_progress(self, data: dict):
        """Handle progress from any worker."""
        if self._current_index < 0 or self._current_index >= len(self._queue):
            return

        percent = data.get("percent", 0)
        message = data.get("message", "")

        item = self._queue[self._current_index]
        item.progress = percent
        self._update_table_row(self._current_index, item)

        self._current_progress.set_progress(percent)
        self._current_progress.set_status(message)

    def _on_worker_error(self, error_tuple):
        """Handle error from any worker."""
        if self._current_index < 0 or self._current_index >= len(self._queue):
            return

        exc_type, exc_value, exc_tb = error_tuple
        error_msg = str(exc_value)

        item = self._queue[self._current_index]
        item.status = AnalysisStatus.ERROR
        item.error_msg = error_msg
        self._update_table_row(self._current_index, item)

        logger.error(f"Analysis error for {item.file_name}: {error_msg}")
        self._current_progress.set_error(error_msg)

    def _on_audio_result(self, result: AudioAnalysisResult):
        """Handle audio analysis result."""
        if self._current_index < 0 or self._current_index >= len(self._queue):
            return

        item = self._queue[self._current_index]
        item.audio_result = result
        logger.info(f"Audio analysis complete: {item.file_name}")

    def _on_audio_finished(self):
        """Handle audio worker completion."""
        self._audio_worker = None

        if self._current_index >= 0 and self._current_index < len(self._queue):
            item = self._queue[self._current_index]
            if item.status != AnalysisStatus.ERROR:
                self._on_item_complete(item)
            else:
                self._process_next()

    def _on_scene_result(self, result: dict):
        """Handle scene detection result."""
        if self._current_index < 0 or self._current_index >= len(self._queue):
            return

        item = self._queue[self._current_index]
        item.scenes = result.get("scenes", [])
        logger.info(f"Scene detection complete: {item.file_name}, {len(item.scenes)} scenes")

    def _on_scene_finished(self):
        """Handle scene worker completion."""
        self._scene_worker = None

        if self._current_index >= 0 and self._current_index < len(self._queue):
            item = self._queue[self._current_index]
            if item.status != AnalysisStatus.ERROR:
                # Continue with motion analysis
                self._current_progress.set_status("Starting motion analysis...")
                self._start_motion_analysis(item)
            else:
                self._process_next()

    def _on_motion_result(self, result: dict):
        """Handle motion analysis result."""
        if self._current_index < 0 or self._current_index >= len(self._queue):
            return

        item = self._queue[self._current_index]
        item.motion_data = result.get("motion_data", [])
        logger.info(f"Motion analysis complete: {item.file_name}")

    def _on_motion_finished(self):
        """Handle motion worker completion."""
        self._motion_worker = None

        if self._current_index >= 0 and self._current_index < len(self._queue):
            item = self._queue[self._current_index]
            if item.status != AnalysisStatus.ERROR:
                # Continue with vision analysis
                self._current_progress.set_status("Starting vision analysis...")
                self._start_vision_analysis(item)
            else:
                self._process_next()

    def _on_vision_result(self, result: dict):
        """Handle vision analysis result."""
        if self._current_index < 0 or self._current_index >= len(self._queue):
            return

        item = self._queue[self._current_index]
        item.captions = result.get("captions", {})
        logger.info(f"Vision analysis complete: {item.file_name}")

    def _on_vision_finished(self):
        """Handle vision worker completion."""
        self._vision_worker = None

        if self._current_index >= 0 and self._current_index < len(self._queue):
            item = self._queue[self._current_index]
            if item.status != AnalysisStatus.ERROR:
                self._on_item_complete(item)
            else:
                self._process_next()

    def _on_item_complete(self, item: QueueItem):
        """Handle completion of a single item."""
        item.status = AnalysisStatus.COMPLETE
        item.progress = 100
        self._update_table_row(self._current_index, item)

        self._current_progress.set_progress(100)
        self._current_progress.set_status("Complete")

        # Emit signal for this file
        self.fileAnalyzed.emit(item.to_dict())

        # Process next
        self._process_next()

    def _on_queue_complete(self):
        """Handle completion of entire queue."""
        self._is_processing = False

        completed = sum(1 for i in self._queue if i.status == AnalysisStatus.COMPLETE)
        errors = sum(1 for i in self._queue if i.status == AnalysisStatus.ERROR)

        self._overall_progress.setValue(100)
        self._overall_progress.setFormat(f"Complete: {completed} processed, {errors} errors")
        self._current_progress.set_status("Queue processing complete")

        self._update_ui_state()

        # Emit results
        results = self.get_results()
        self.queueComplete.emit(results)

        logger.info(f"Queue complete: {completed} files processed, {errors} errors")

    def _cancel_all_workers(self):
        """Cancel all running workers."""
        if self._audio_worker:
            self._audio_worker.cancel()
            self._audio_worker = None

        if self._scene_worker:
            self._scene_worker.cancel()
            self._scene_worker = None

        if self._motion_worker:
            self._motion_worker.cancel()
            self._motion_worker = None

        if self._vision_worker:
            self._vision_worker.cancel()
            self._vision_worker = None
