from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QGridLayout, QFrame, QPushButton, QProgressBar,
                             QInputDialog, QDialog, QDialogButtonBox,
                             QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from src.pb_studio.services.media_service import MediaService
from src.pb_studio.core.system_monitor import SystemMonitor
from src.pb_studio.data.repositories.project_repository import ProjectRepository

import logging

logger = logging.getLogger(__name__)


class ProjectSelectDialog(QDialog):
    """Dialog zum Auswählen eines vorhandenen Projekts."""

    def __init__(self, projects: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Project")
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)
        self.selected_project = None

        layout = QVBoxLayout(self)

        info = QLabel("Select a project to open:")
        info.setStyleSheet("font-size: 14px; margin-bottom: 8px;")
        layout.addWidget(info)

        self.list_widget = QListWidget()
        for proj in projects:
            item = QListWidgetItem(f"{proj['name']}  (ID: {proj['id']})")
            item.setData(Qt.ItemDataRole.UserRole, proj['id'])
            self.list_widget.addItem(item)
        self.list_widget.doubleClicked.connect(self.accept)
        layout.addWidget(self.list_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        current = self.list_widget.currentItem()
        if current:
            self.selected_project = current.data(Qt.ItemDataRole.UserRole)
        super().accept()


class DashboardWidget(QWidget):
    # Signals für Projekt-Aktionen
    projectCreated = pyqtSignal(int, str)   # project_id, project_name
    projectOpened = pyqtSignal(int, str)    # project_id, project_name

    def __init__(self):
        super().__init__()
        self.media_service = MediaService()
        self.monitor = SystemMonitor()
        self.project_repo = ProjectRepository()
        self._init_ui()
        
        # Timer für Live-Updates (System Stats)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_live_data)
        self.timer.start(2000) # Alle 2 Sekunden

    def _init_ui(self):
        # Hauptlayout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # 1. Header Area
        header = QHBoxLayout()
        
        # Begrüßung
        title_box = QVBoxLayout()
        welcome = QLabel("PB Studio Dashboard")
        welcome.setStyleSheet("font-size: 28px; font-weight: bold; color: #ffffff;")
        subtitle = QLabel("AMD Radeon Edition • High Performance Mode")
        subtitle.setStyleSheet("font-size: 14px; color: #007acc;")
        title_box.addWidget(welcome)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        
        header.addStretch()
        
        # Schnell-Aktionen (Quick Actions)
        action_box = QHBoxLayout()
        self.btn_new = self._create_action_btn("New Project", "#2d8cf0")
        self.btn_open = self._create_action_btn("Open Project", "#3e3e42")

        self.btn_new.clicked.connect(self._on_new_project)
        self.btn_open.clicked.connect(self._on_open_project)

        action_box.addWidget(self.btn_new)
        action_box.addWidget(self.btn_open)
        header.addLayout(action_box)
        
        main_layout.addLayout(header)

        # 2. Stats Grid
        grid = QGridLayout()
        grid.setSpacing(15)

        # Card 1: Library Stats
        self.card_library = self._create_info_card("Media Library", "Loading...", "files")
        grid.addWidget(self.card_library, 0, 0)

        # Card 2: Analysis Status
        self.card_analysis = self._create_info_card("Analysis Queue", "Idle", "tasks")
        grid.addWidget(self.card_analysis, 0, 1)

        # Card 3: Storage
        self.card_storage = self._create_info_card("Project Storage", "Calculating...", "GB")
        grid.addWidget(self.card_storage, 0, 2)

        main_layout.addLayout(grid)

        # 3. System Monitor Section
        sys_frame = QFrame()
        sys_frame.setStyleSheet("background-color: #1e1e1e; border-radius: 8px; padding: 15px;")
        sys_layout = QVBoxLayout(sys_frame)
        
        sys_title = QLabel("System Performance")
        sys_title.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        sys_layout.addWidget(sys_title)
        
        # CPU Bar
        cpu_box = QHBoxLayout()
        cpu_lbl = QLabel("CPU Load:")
        cpu_lbl.setFixedWidth(80)
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setStyleSheet("QProgressBar { border: 0px; background: #333; height: 8px; border-radius: 4px; } QProgressBar::chunk { background: #007acc; border-radius: 4px; }")
        self.cpu_bar.setTextVisible(False)
        self.cpu_val = QLabel("0%")
        cpu_box.addWidget(cpu_lbl)
        cpu_box.addWidget(self.cpu_bar)
        cpu_box.addWidget(self.cpu_val)
        sys_layout.addLayout(cpu_box)

        # GPU Bar
        gpu_box = QHBoxLayout()
        gpu_lbl = QLabel("GPU Load:")
        gpu_lbl.setFixedWidth(80)
        self.gpu_bar = QProgressBar()
        self.gpu_bar.setStyleSheet("QProgressBar { border: 0px; background: #333; height: 8px; border-radius: 4px; } QProgressBar::chunk { background: #e03c31; border-radius: 4px; }") # AMD Red
        self.gpu_bar.setTextVisible(False)
        self.gpu_val = QLabel("0%")
        gpu_box.addWidget(gpu_lbl)
        gpu_box.addWidget(self.gpu_bar)
        gpu_box.addWidget(self.gpu_val)
        sys_layout.addLayout(gpu_box)
        
        # VRAM Info
        self.vram_lbl = QLabel("VRAM Usage: - / - MB")
        self.vram_lbl.setStyleSheet("color: #aaaaaa; font-size: 12px; margin-top: 5px;")
        sys_layout.addWidget(self.vram_lbl)

        main_layout.addWidget(sys_frame)
        main_layout.addStretch()
        
        # Init Data
        self._update_library_stats()

    def _create_action_btn(self, text, color):
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color}dd;
            }}
        """)
        return btn

    def _create_info_card(self, title, value, unit):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3e3e42;
                border-radius: 8px;
            }
        """)
        vbox = QVBoxLayout(frame)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #aaaaaa; font-size: 14px; border: none;")
        
        lbl_value = QLabel(f"{value} {unit}")
        lbl_value.setStyleSheet("color: white; font-size: 24px; font-weight: bold; border: none;")
        # Tag für Updates speichern
        frame.value_label = lbl_value 
        
        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_value)
        return frame

    def _update_library_stats(self):
        """Holt echte Daten aus der DB."""
        try:
            project_id = getattr(self, 'current_project_id', 1)
            files = self.media_service.get_project_files(project_id)
            count = len(files)
            # Update Card
            self.card_library.value_label.setText(f"{count}")
            
            # Storage Calc (Dummy für jetzt, könnte Dateigrößen summieren)
            # total_size = sum(f.get('size', 0) for f in files) / (1024**3)
            self.card_storage.value_label.setText(f"{count * 0.05:.1f} GB") # Schätzung
            
        except Exception as e:
            self.card_library.value_label.setText("Error")

    def _update_live_data(self):
        """System Stats aktualisieren."""
        try:
            stats = self.monitor.get_stats()
        except Exception:
            return
        
        cpu = int(stats.get('cpu_load', 0))
        gpu = int(stats.get('gpu_load', 0))
        vram_used = int(stats.get('gpu_memory_used', 0))
        vram_total = int(stats.get('gpu_memory_total', 0))
        
        self.cpu_bar.setValue(cpu)
        self.cpu_val.setText(f"{cpu}%")
        
        self.gpu_bar.setValue(gpu)
        self.gpu_val.setText(f"{gpu}%")
        
        self.vram_lbl.setText(f"VRAM Usage: {vram_used} / {vram_total} MB")
        
        # Auch Library Stats periodisch refreshen (falls Import im Hintergrund läuft)
        self._update_library_stats()

    def _on_new_project(self):
        """Erstellt ein neues Projekt via InputDialog."""
        name, ok = QInputDialog.getText(
            self, "New Project", "Project name:",
            text="My Project"
        )
        if ok and name.strip():
            name = name.strip()
            project_id = self.project_repo.create_project(name)
            if project_id > 0:
                logger.info(f"Created project '{name}' (ID: {project_id})")
                self.projectCreated.emit(project_id, name)
            else:
                logger.error(f"Failed to create project '{name}'")

    def cleanup(self):
        """Timer stoppen bei Widget-Zerstoerung."""
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()

    def hideEvent(self, event):
        """Timer stoppen wenn Dashboard nicht sichtbar."""
        if hasattr(self, 'timer'):
            self.timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        """Timer starten wenn Dashboard sichtbar."""
        if hasattr(self, 'timer') and not self.timer.isActive():
            self.timer.start(2000)
        super().showEvent(event)

    def _on_open_project(self):
        """Zeigt vorhandene Projekte zum Auswählen."""
        projects = self.project_repo.get_all()
        if not projects:
            logger.info("No projects found in database")
            return

        dlg = ProjectSelectDialog(projects, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_project:
            proj_id = dlg.selected_project
            proj = self.project_repo.get_by_id(proj_id)
            proj_name = proj['name'] if proj else f"Project {proj_id}"
            logger.info(f"Opened project '{proj_name}' (ID: {proj_id})")
            self.projectOpened.emit(proj_id, proj_name)

