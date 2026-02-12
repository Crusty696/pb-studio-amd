import logging
import json
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QPushButton, QHeaderView, QLabel, QFileDialog)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from src.pb_studio.services.media_service import MediaService

logger = logging.getLogger(__name__)

class LibraryBrowserWidget(QWidget):
    # Signal emitted when user double-clicks a file (sends file_path, metadata_dict)
    fileSelected = pyqtSignal(str, dict)
    # Signal for batch analysis (list of (media_id, filepath, metadata))
    filesForAnalysis = pyqtSignal(list)
    
    def __init__(self, project_id: int = 1):
        super().__init__()
        self.project_id = project_id
        self.media_service = MediaService()
        self._file_cache = {} # media_id -> file_info dict
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Media Library")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        import_btn = QPushButton("Import Files...")
        import_btn.clicked.connect(self._on_import_click)
        header_layout.addWidget(import_btn)
        
        # Neuer Button für Ordner-Import
        import_folder_btn = QPushButton("Import Folder...")
        import_folder_btn.clicked.connect(self._on_import_folder_click)
        header_layout.addWidget(import_folder_btn)
        
        self.analyze_btn = QPushButton("Analyze Selected")
        self.analyze_btn.clicked.connect(self._on_analyze_selected_click)
        header_layout.addWidget(self.analyze_btn)
        
        layout.addLayout(header_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Filename", "Duration", "Status"])
        
        # Stretching
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection) # Allow multiple
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_double_click)
        
        # Enable Drag and Drop
        self.setAcceptDrops(True)
        
        layout.addWidget(self.table)

    def refresh_view(self):
        """Loads media from DB into table (Public alias)."""
        self._load_data()

    def _load_data(self):
        """Loads media from DB into table."""
        self.table.setRowCount(0)
        self._file_cache.clear()
        
        files = self.media_service.get_project_files(self.project_id)
        for row_idx, media in enumerate(files):
            media_id = media.get("id", -1)
            self._file_cache[row_idx] = media # Cache by row for quick lookup
            
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(media_id)))
            
            # Extract just filename from full path
            fp = media.get("file_path", "")
            name = fp.split("\\")[-1].split("/")[-1]
            self.table.setItem(row_idx, 1, QTableWidgetItem(name))
            
            dur = media.get("duration_sec", 0) or 0
            mins = int(dur // 60)
            secs = int(dur % 60)
            self.table.setItem(row_idx, 2, QTableWidgetItem(f"{mins:02d}:{secs:02d}"))
            
            self.table.setItem(row_idx, 3, QTableWidgetItem(media.get("status", "?")))

    def _on_double_click(self, index):
        """Handles double-click on table row."""
        row = index.row()
        if row in self._file_cache:
            media = self._file_cache[row]
            file_path = media.get("file_path", "")
            
            # Parse AI data if available
            ai_data = {}
            raw_json = media.get("ai_data_json")
            if raw_json:
                try:
                    ai_data = json.loads(raw_json)
                except Exception as e:
                    logger.error(f"Failed to parse ai_data_json: {e}")

            metadata = {
                "id": media.get("id"),
                "duration": media.get("duration_sec", 0), 
                "format": "",
                "status": media.get("status", "pending"),
                "ai_data": ai_data
            }
            logger.debug(f"Emitting fileSelected. BPM in ai_data: {ai_data.get('bpm', 'N/A')}")
            logger.info(f"File selected: {file_path}")
            self.fileSelected.emit(file_path, metadata)

    def _on_import_click(self):
        """Opens file dialog to select files."""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Media Files",
            "",
            "Media Files (*.mp3 *.wav *.flac *.mp4 *.mov *.avi *.mkv *.m4a *.ogg *.wmv *.webm *.mpg *.mpeg *.m4v *.ts *.mts);;All Files (*)"
        )
        
        if files:
            self._import_files(files)

    def _on_import_folder_click(self):
        """Opens directory dialog to import recursively."""
        # Hinweis: Zeigt nur Ordner an, keine Dateien!
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Import")
        if folder:
            self._import_folder_recursive(folder)

    def _import_folder_recursive(self, folder_path):
        """Scans folder recursively for media files."""
        path = Path(folder_path)
        if not path.exists():
            return
            
        extensions = {'.mp3', '.wav', '.flac', '.mp4', '.mov', '.avi', '.mkv', '.m4a', '.ogg', '.wmv', '.webm', '.mpg', '.mpeg', '.m4v', '.ts', '.mts'}
        files = []
        
        # Rekursiv suchen
        for p in path.rglob("*"):
            if p.is_file() and p.suffix.lower() in extensions:
                files.append(str(p))
        
        if files:
            logger.info(f"Found {len(files)} media files in folder '{folder_path}'")
            self._import_files(files)
        else:
            logger.info(f"No media files found in folder '{folder_path}'")
                
    def _on_analyze_selected_click(self):
        """Standard 'Analyze Selected' button."""
        selected_rows = sorted(set(index.row() for index in self.table.selectedIndexes()))
        if not selected_rows:
            return

        batch_list = []
        for row in selected_rows:
            if row in self._file_cache:
                media = self._file_cache[row]
                item_data = {
                    "id": media.get("id"),
                    "file_path": media.get("file_path"),
                    "metadata": {
                        "id": media.get("id"),
                        "duration": media.get("duration_sec", 0), 
                        "status": media.get("status", "pending")
                    }
                }
                batch_list.append(item_data)
        
        if batch_list:
            logger.info(f"Sending {len(batch_list)} files for analysis.")
            self.filesForAnalysis.emit(batch_list)
            
    def _import_files(self, file_paths: list):
        """Imports files via MediaService."""
        logger.info(f"Importing {len(file_paths)} files...")
        results = self.media_service.import_files(self.project_id, file_paths)
        logger.info(f"Import results: {results}")
        self._load_data() # Refresh table

    # --- Drag and Drop ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        file_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        if file_paths:
            self._import_files(file_paths)
