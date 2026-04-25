"""
Library Container - Audio/Video getrennte Medien-Bibliothek.

Ersetzt die gemischte LibraryBrowserWidget durch zwei Unter-Tabs:
- Audio Library (MP3, WAV, FLAC, OGG, M4A)
- Video Library (MP4, MOV, AVI, MKV, WEBM, etc.)
"""

import logging
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QPushButton,
    QHeaderView, QLabel, QFileDialog
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from pb_studio.services.media_service import MediaService

logger = logging.getLogger(__name__)

# Datei-Extensions nach Typ
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.wma', '.aac'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.mpg', '.mpeg',
                    '.m4v', '.ts', '.mts', '.wmv'}
ALL_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


class MediaTableWidget(QWidget):
    """Wiederverwendbare Medien-Tabelle für Audio oder Video."""
    
    fileSelected = pyqtSignal(str, dict)
    filesForAnalysis = pyqtSignal(list)
    
    def __init__(self, media_type: str, parent=None):
        """
        Args:
            media_type: "audio" oder "video"
        """
        super().__init__(parent)
        self.media_type = media_type
        self.project_id = 1
        self.media_service = MediaService()
        self._file_cache = {}
        
        if media_type == "audio":
            self._extensions = AUDIO_EXTENSIONS
            self._filter_str = "Audio Files (*.mp3 *.wav *.flac *.ogg *.m4a *.wma *.aac);;All Files (*)"
            self._title = "Audio Library"
        else:
            self._extensions = VIDEO_EXTENSIONS
            self._filter_str = "Video Files (*.mp4 *.mov *.avi *.mkv *.webm *.mpg *.mpeg *.m4v *.ts *.mts *.wmv);;All Files (*)"
            self._title = "Video Library"
        
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Header mit Buttons
        header = QHBoxLayout()
        
        count_label = QLabel(self._title)
        count_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(count_label)
        self._count_label = count_label
        
        header.addStretch()
        
        import_btn = QPushButton(f"Import {self.media_type.title()}...")
        import_btn.clicked.connect(self._on_import_click)
        header.addWidget(import_btn)
        
        import_folder_btn = QPushButton("Import Folder...")
        import_folder_btn.clicked.connect(self._on_import_folder_click)
        header.addWidget(import_folder_btn)
        
        analyze_btn = QPushButton("Analyze Selected")
        analyze_btn.clicked.connect(self._on_analyze_click)
        header.addWidget(analyze_btn)
        
        layout.addLayout(header)
        
        # Tabelle
        self.table = QTableWidget()
        
        if self.media_type == "audio":
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(["ID", "Filename", "Duration", "BPM", "Status"])
        else:
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(["ID", "Filename", "Duration", "Resolution", "Status"])
        
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_double_click)
        
        self.setAcceptDrops(True)
        
        layout.addWidget(self.table)
    
    def refresh_view(self):
        """Lädt Medien aus DB in Tabelle."""
        self._load_data()
    
    def _load_data(self):
        """Lädt Medien gefiltert nach Typ."""
        self.table.setRowCount(0)
        self._file_cache.clear()
        
        all_files = self.media_service.get_project_files(self.project_id)
        
        row_idx = 0
        for media in all_files:
            fp = media.get("file_path", "")
            ext = Path(fp).suffix.lower()
            
            # Filtern nach Typ
            if ext not in self._extensions:
                continue
            
            media_id = media.get("id", -1)
            self._file_cache[row_idx] = media
            
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(media_id)))
            
            name = Path(fp).name
            self.table.setItem(row_idx, 1, QTableWidgetItem(name))
            
            dur = media.get("duration_sec", 0) or 0
            mins = int(dur // 60)
            secs = int(dur % 60)
            self.table.setItem(row_idx, 2, QTableWidgetItem(f"{mins:02d}:{secs:02d}"))
            
            # Typ-spezifische Spalte
            ai_data = {}
            raw_json = media.get("ai_data_json")
            if raw_json:
                try:
                    ai_data = json.loads(raw_json)
                except Exception:
                    pass
            
            if self.media_type == "audio":
                bpm = ai_data.get("bpm", "")
                self.table.setItem(row_idx, 3, QTableWidgetItem(str(bpm) if bpm else "-"))
            else:
                res = ai_data.get("resolution", "")
                self.table.setItem(row_idx, 3, QTableWidgetItem(str(res) if res else "-"))
            
            self.table.setItem(row_idx, 4, QTableWidgetItem(media.get("status", "?")))
            row_idx += 1
        
        self._count_label.setText(f"{self._title} ({row_idx} files)")
    
    def _on_double_click(self, index):
        row = index.row()
        if row in self._file_cache:
            media = self._file_cache[row]
            file_path = media.get("file_path", "")
            
            ai_data = {}
            raw_json = media.get("ai_data_json")
            if raw_json:
                try:
                    ai_data = json.loads(raw_json)
                except Exception:
                    pass
            
            metadata = {
                "id": media.get("id"),
                "duration": media.get("duration_sec", 0),
                "format": "",
                "status": media.get("status", "pending"),
                "ai_data": ai_data,
                "media_type": self.media_type
            }
            self.fileSelected.emit(file_path, metadata)
    
    def _on_import_click(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, f"Select {self.media_type.title()} Files", "", self._filter_str
        )
        if files:
            self._import_files(files)
    
    def _on_import_folder_click(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Import")
        if folder:
            path = Path(folder)
            files = [str(p) for p in path.rglob("*")
                     if p.is_file() and p.suffix.lower() in self._extensions]
            if files:
                logger.info(f"Found {len(files)} {self.media_type} files in '{folder}'")
                self._import_files(files)
    
    def _on_analyze_click(self):
        selected_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        if not selected_rows:
            return
        
        batch = []
        for row in selected_rows:
            if row in self._file_cache:
                media = self._file_cache[row]
                batch.append({
                    "id": media.get("id"),
                    "file_path": media.get("file_path"),
                    "metadata": {
                        "id": media.get("id"),
                        "duration": media.get("duration_sec", 0),
                        "status": media.get("status", "pending")
                    }
                })
        
        if batch:
            self.filesForAnalysis.emit(batch)
    
    def _import_files(self, file_paths: list):
        logger.info(f"Importing {len(file_paths)} {self.media_type} files...")
        try:
            results = self.media_service.import_files(self.project_id, file_paths)
            logger.info(f"Import: {results}")
        except Exception as e:
            logger.error(f"Import failed: {e}")
        finally:
            self._load_data()
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        file_paths = []
        for url in urls:
            if url.isLocalFile():
                fp = url.toLocalFile()
                if Path(fp).suffix.lower() in self._extensions:
                    file_paths.append(fp)
        if file_paths:
            self._import_files(file_paths)


class LibraryContainer(QWidget):
    """
    Container mit Audio/Video Tabs.
    Ersetzt das alte gemischte LibraryBrowserWidget.
    """
    
    fileSelected = pyqtSignal(str, dict)
    filesForAnalysis = pyqtSignal(list)
    
    def __init__(self, project_id: int = 1):
        super().__init__()
        self.project_id = project_id
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        
        # Audio Tab
        self.audio_tab = MediaTableWidget("audio")
        self.audio_tab.fileSelected.connect(self.fileSelected)
        self.audio_tab.filesForAnalysis.connect(self.filesForAnalysis)
        self.tabs.addTab(self.audio_tab, "🎵 Audio")
        
        # Video Tab
        self.video_tab = MediaTableWidget("video")
        self.video_tab.fileSelected.connect(self.fileSelected)
        self.video_tab.filesForAnalysis.connect(self.filesForAnalysis)
        self.tabs.addTab(self.video_tab, "🎬 Video")
        
        layout.addWidget(self.tabs)
    
    def refresh_view(self):
        """Aktualisiert beide Tabs."""
        self.audio_tab.project_id = self.project_id
        self.video_tab.project_id = self.project_id
        self.audio_tab.refresh_view()
        self.video_tab.refresh_view()
