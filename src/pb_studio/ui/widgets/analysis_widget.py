import logging
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTableWidget, QTableWidgetItem, 
                             QFrame, QHeaderView, QProgressBar)
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal

from src.pb_studio.services.analysis_service import AnalysisService
from src.pb_studio.data.repositories.media_repository import MediaRepository

logger = logging.getLogger(__name__)

class AnalysisWidget(QWidget):
    # Signals
    analysisCompleted = pyqtSignal(dict)  # Emits full results (metadata + ai_data)

    def __init__(self):
        super().__init__()
        self.analysis_service = AnalysisService()
        self.media_repo = MediaRepository()
        self.current_media_id = None
        self.current_file_path = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        title_layout = QHBoxLayout()
        title = QLabel("Analysis")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        title_layout.addWidget(title)
        
        title_layout.addStretch()
        
        # Queue Status
        self.queue_label = QLabel("Queue: 0 pending")
        self.queue_label.setStyleSheet("color: #888888; font-weight: bold;")
        title_layout.addWidget(self.queue_label)
        
        layout.addLayout(title_layout)

        # Current File Info
        self.file_label = QLabel("No file processing.")
        self.file_label.setStyleSheet("color: #cccccc;")
        layout.addWidget(self.file_label)

        # Analyze Button (Hidden mostly now if batch usage, but kept for manual)
        btn_layout = QHBoxLayout()
        self.analyze_btn = QPushButton("Analyze Current")
        self.analyze_btn.clicked.connect(self._on_analyze_click)
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setVisible(False) # Hide for cleaner batch UI
        btn_layout.addWidget(self.analyze_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Progress
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Results Cards (Grid)
        results_layout = QHBoxLayout()
        
        # BPM Card
        self.bpm_card = self._create_result_card("BPM", "-")
        results_layout.addWidget(self.bpm_card)
        
        # Key Card
        self.key_card = self._create_result_card("Key", "-")
        results_layout.addWidget(self.key_card)
        
        # Scenes Card
        self.scenes_card = self._create_result_card("Scenes", "-")
        results_layout.addWidget(self.scenes_card)
        
        layout.addLayout(results_layout)

        # Scenes Table
        scenes_label = QLabel("Detected Scenes (Last Result)")
        scenes_label.setStyleSheet("font-weight: bold; font-size: 16px; margin-top: 20px;")
        layout.addWidget(scenes_label)
        
        self.scenes_table = QTableWidget()
        self.scenes_table.setColumnCount(3)
        self.scenes_table.setHorizontalHeaderLabels(["#", "Start", "End"])
        self.scenes_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.scenes_table)
        
        self.queue = []
        self.is_processing = False

    def enqueue_files(self, file_list: list):
        """Adds files to queue. file_list = [{id, file_path, metadata}, ...]"""
        self.queue.extend(file_list)
        self.queue_label.setText(f"Queue: {len(self.queue)} pending")
        
        if not self.is_processing:
            self._process_next()
            
    def _process_next(self):
        if not self.queue:
            self.is_processing = False
            self.file_label.setText("Batch analysis complete.")
            self.progress.setVisible(False)
            return
            
        self.is_processing = True
        item = self.queue.pop(0)
        self.queue_label.setText(f"Queue: {len(self.queue)} pending")
        
        self.current_media_id = item["id"]
        self.current_file_path = item["file_path"]
        
        self.file_label.setText(f"Processing: {Path(self.current_file_path).name}")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0) # Indeterminate
        
        self.analysis_service.analyze_media(
            self.current_media_id,
            self.current_file_path,
            on_complete=self._on_analysis_complete,
            on_error=self._on_analysis_error
        )

    def _create_result_card(self, title, value):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        vbox = QVBoxLayout(frame)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 12px; color: #888888; border: none;")
        
        lbl_value = QLabel(value)
        lbl_value.setObjectName(f"value_{title}")
        lbl_value.setStyleSheet("font-size: 28px; font-weight: bold; border: none;")
        
        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_value)
        
        return frame

    def set_file(self, media_id: int, file_path: str, metadata: dict = None):
        """Called when a file is selected for analysis."""
        self.current_media_id = media_id
        self.current_file_path = file_path
        
        name = file_path.split("\\")[-1].split("/")[-1]
        self.file_label.setText(f"Selected: {name}")
        self.analyze_btn.setEnabled(True)
        
        # Check if already analyzed
        if metadata and metadata.get("status") == "ready":
            self._display_results(metadata.get("ai_data", {}))

    def _on_analyze_click(self):
        if not self.current_file_path:
            return
            
        self.analyze_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0) # Indeterminate
        
        self.analysis_service.analyze_media(
            self.current_media_id,
            self.current_file_path,
            on_complete=self._on_analysis_complete,
            on_error=self._on_analysis_error
        )

    def _on_analysis_complete(self, results):
        # Log summary instead of full data to prevent UI freeze with massive beat arrays
        bpm = results.get('bpm', 'N/A')
        beat_count = len(results.get('beats', []))
        scene_count = len(results.get('scenes', []))
        logger.info(f"Analysis complete: BPM={bpm}, Beats={beat_count}, Scenes={scene_count}")
        
        self.progress.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self._display_results(results)
        
        # Emit signal for other widgets (e.g. Editor)
        updated_metadata = {
            "id": self.current_media_id,
            "file_path": self.current_file_path,
            "status": "ready",
            "ai_data": results
        }
        self.analysisCompleted.emit(updated_metadata)
        
        # Next
        self._process_next()

    def _on_analysis_error(self, error_tuple):
        logger.error(f"Analysis error: {error_tuple}")
        self.progress.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self.file_label.setText(f"Error: {error_tuple[1]}")
        
        # Ensure queue continues even on error
        self._process_next()

    def _display_results(self, results):
        # BPM
        bpm = results.get("bpm", 0)
        bpm_label = self.bpm_card.findChild(QLabel, "value_BPM")
        if bpm_label:
            bpm_label.setText(f"{bpm:.1f}" if bpm else "-")
        
        # Scenes Count
        scenes = results.get("scenes", [])
        scenes_label = self.scenes_card.findChild(QLabel, "value_Scenes")
        if scenes_label:
            scenes_label.setText(str(len(scenes)))
        
        # Populate scenes table
        self.scenes_table.setRowCount(0)
        for i, (start, end) in enumerate(scenes):
            self.scenes_table.insertRow(i)
            self.scenes_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.scenes_table.setItem(i, 1, QTableWidgetItem(f"{start:.2f}s"))
            self.scenes_table.setItem(i, 2, QTableWidgetItem(f"{end:.2f}s"))
