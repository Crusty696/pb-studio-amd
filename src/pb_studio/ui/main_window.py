import logging
from pathlib import Path
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QStackedWidget, QLabel, QFrame,
                             QMessageBox)
from PyQt6.QtCore import Qt, QTimer

from src.pb_studio.core.system_monitor import SystemMonitor
from src.pb_studio.config_manager import ConfigManager
from src.pb_studio.services.generation_service import GenerationService
from src.pb_studio.data.database_core import DatabaseCore
from src.pb_studio.ui.widgets.dashboard import DashboardWidget
from src.pb_studio.ui.widgets.library_browser import LibraryBrowserWidget
from src.pb_studio.ui.widgets.editor_widget import EditorWidget
from src.pb_studio.ui.widgets.settings_widget import SettingsWidget

# Neue modulare Widgets
from src.pb_studio.ui.widgets.analysis import AnalysisQueueWidget
from src.pb_studio.ui.widgets.generation import GenerationContainer

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PB Studio (AMD Edition)")
        self.resize(1280, 800)
        
        self.config = ConfigManager()
        self.monitor = SystemMonitor()  # Initializes LHM automatically in __init__
        self.generation_service = GenerationService()

        self._init_ui()
        self._load_stylesheet()
        self._start_monitoring()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(220)
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 10, 0, 10)
        sidebar_layout.setSpacing(5)
        
        title_label = QLabel("PB STUDIO")
        title_label.setStyleSheet("font-weight: bold; font-size: 18px; color: #007acc; padding: 15px;")
        sidebar_layout.addWidget(title_label)
        
        self.nav_dashboard = self._create_nav_button("Dashboard", "home")
        self.nav_library = self._create_nav_button("Library", "folder")
        self.nav_editor = self._create_nav_button("Editor", "edit")
        self.nav_analysis = self._create_nav_button("Analysis", "activity")
        self.nav_generate = self._create_nav_button("Generate", "film") # New Tab
        self.nav_settings = self._create_nav_button("Settings", "settings")

        sidebar_layout.addWidget(self.nav_dashboard)
        sidebar_layout.addWidget(self.nav_library)
        sidebar_layout.addWidget(self.nav_editor)
        sidebar_layout.addWidget(self.nav_analysis)
        sidebar_layout.addWidget(self.nav_generate)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(self.nav_settings)
        
        main_layout.addWidget(self.sidebar)

        # 2. Content Area (Stacked)
        self.content_stack = QStackedWidget()
        
        # Pages
        self.dashboard_page = DashboardWidget()
        self.library_page = LibraryBrowserWidget()
        self.editor_page = EditorWidget()
        self.analysis_page = AnalysisQueueWidget()  # NEU: Modulare Analyse-Queue
        self.generation_page = GenerationContainer()  # NEU: Modularer Generation-Container
        self.settings_page = SettingsWidget()
        
        self.content_stack.addWidget(self.dashboard_page) # Index 0
        self.content_stack.addWidget(self.library_page)   # Index 1
        self.content_stack.addWidget(self.editor_page)    # Index 2
        self.content_stack.addWidget(self.analysis_page)  # Index 3
        self.content_stack.addWidget(self.generation_page) # Index 4
        self.content_stack.addWidget(self.settings_page)  # Index 5
        
        main_layout.addWidget(self.content_stack)
        
        # Connect Navigation
        self.nav_dashboard.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))
        self.nav_library.clicked.connect(lambda: self.content_stack.setCurrentIndex(1))
        self.nav_editor.clicked.connect(lambda: self.content_stack.setCurrentIndex(2))
        self.nav_analysis.clicked.connect(lambda: self.content_stack.setCurrentIndex(3))
        self.nav_generate.clicked.connect(lambda: self.content_stack.setCurrentIndex(4)) # Generate
        self.nav_settings.clicked.connect(lambda: self.content_stack.setCurrentIndex(5)) # Settings
        
        # Connect Dashboard project buttons
        self.dashboard_page.projectCreated.connect(self._on_project_switch)
        self.dashboard_page.projectOpened.connect(self._on_project_switch)

        # Connect Library to Editor
        self.library_page.fileSelected.connect(self._open_in_editor)
        self.library_page.filesForAnalysis.connect(self._enqueue_analysis)

        # Connect Analysis Queue (NEU: modulare Signale)
        self.analysis_page.fileAnalyzed.connect(self._on_file_analyzed)
        self.analysis_page.queueComplete.connect(self._on_queue_complete)

        # Connect Generation Widget
        self.generation_page.generateRequested.connect(self._on_generate_requested)

        # 3. Status Bar
        self.status_bar = self.statusBar()
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("StatusLabel")
        
        self.vram_label = QLabel("VRAM: - / -")
        self.vram_label.setObjectName("StatusLabel")
        
        self.cpu_label = QLabel("CPU: -%")
        self.cpu_label.setObjectName("StatusLabel")

        self.status_bar.addWidget(self.status_label, 1) # Stretch
        self.status_bar.addPermanentWidget(self.cpu_label)
        self.status_bar.addPermanentWidget(self.vram_label)

    def _create_nav_button(self, text, icon_name):
        btn = QPushButton(text)
        btn.setObjectName("NavButton")
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        return btn

    def _load_stylesheet(self):
        # Wir nutzen jetzt qt-material in run_ui.py, daher laden wir hier kein altes QSS mehr,
        # um das Theme nicht zu zerstören.
        # Falls spezifische Overrides nötig sind, kommen sie in custom_overrides.css
        pass
        # try:
        #     # Stylesheet relativ zu diesem Modul laden
        #     styles_path = Path(__file__).parent / "styles.qss"
        #     with open(styles_path, "r") as f:
        #         self.setStyleSheet(f.read())
        # except Exception as e:
        #     logger.error(f"Failed to load stylesheet: {e}")

    def _start_monitoring(self):
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._update_stats)
        self.monitor_timer.start(2000) # Update every 2 seconds

    def _update_stats(self):
        if not self.monitor: return
        
        # Read HAL stats
        # HAL returns dict: gpu_load, gpu_temp, gpu_memory_used, gpu_memory_total, ram_load...
        # Wait, my last update to system_monitor.py might have changed keys. Checking memory.
        # It calls 'get_stats()'.
        
        stats = self.monitor.get_stats()
        
        vram_used = stats.get('gpu_memory_used', 0)
        vram_total = stats.get('gpu_memory_total', 0)
        gpu_load = stats.get('gpu_load', 0)
        cpu_load = stats.get('cpu_load', 0)

        self.cpu_label.setText(f"CPU: {cpu_load:.0f}%")
        self.vram_label.setText(f"GPU: {gpu_load:.0f}% | VRAM: {vram_used:.0f} MB")

    def _on_project_switch(self, project_id: int, project_name: str):
        """Wechselt das aktive Projekt in der gesamten App."""
        logger.info(f"Switching to project '{project_name}' (ID: {project_id})")

        # Update Dashboard mit neuem project_id
        self.dashboard_page.current_project_id = project_id

        # Update Library mit neuem project_id
        self.library_page.project_id = project_id
        self.library_page.refresh_view()

        # Window-Titel aktualisieren
        self.setWindowTitle(f"PB Studio (AMD Edition) - {project_name}")

        # Zur Library wechseln
        self.content_stack.setCurrentIndex(1)
        self.nav_library.setChecked(True)

        self.status_label.setText(f"Project: {project_name}")

    def _open_in_editor(self, file_path: str, metadata: dict):
        """Slot: Opens a file in the editor and switches to editor tab."""
        logger.debug(f"Opening in editor. BPM: {metadata.get('ai_data', {}).get('bpm', 'N/A')}")
        logger.info(f"Opening in editor: {file_path}")
        self.editor_page.load_file(file_path, metadata)
        self.content_stack.setCurrentIndex(2) # Switch to Editor
        self.nav_editor.setChecked(True)

    def _enqueue_analysis(self, file_list: list):
        """Slot: Takes list of files from Library and sends to Analysis Queue."""
        # NEU: AnalysisQueueWidget erwartet Liste von Dateipfaden
        # file_list kann dicts mit {id, file_path, metadata} oder nur strings sein
        if file_list and isinstance(file_list[0], dict):
            paths = [item.get("file_path", item) for item in file_list]
        else:
            paths = file_list

        self.analysis_page.add_files(paths)
        self.content_stack.setCurrentIndex(3)  # Switch to Analysis View
        logger.info(f"Enqueued {len(paths)} files for analysis.")

    def _on_file_analyzed(self, result: dict):
        """Slot: Called when a single file analysis completes."""
        file_path = result.get("file_path", "")
        logger.info(f"File analyzed: {Path(file_path).name}")

        # Erstelle metadata-dict fuer Editor-Kompatibilitaet
        audio_res = result.get("audio_result") or {}
        metadata = {
            "file_path": file_path,
            "status": "ready",
            "ai_data": {
                "bpm": audio_res.get("bpm", 0),
                "beat_data": audio_res.get("beat_data", []),
                "scenes": [(s.get("start", 0), s.get("end", 0)) for s in result.get("scenes", [])],
            }
        }

        # Update Editor wenn dieselbe Datei geladen ist
        if self.editor_page.current_file == file_path:
            self.editor_page.check_refresh(metadata)
            logger.info("Editor mit Analyse-Daten aktualisiert.")

        # Library aktualisieren
        if hasattr(self.library_page, 'refresh_view'):
            self.library_page.refresh_view()

    def _on_queue_complete(self, results: list):
        """Slot: Called when entire analysis queue completes."""
        completed = len(results)
        logger.info(f"Analysis queue complete: {completed} files processed.")

        # Library aktualisieren
        if hasattr(self.library_page, 'refresh_view'):
            self.library_page.refresh_view()

        # Status-Meldung
        self.status_label.setText(f"Analysis complete: {completed} files")

    def _on_generate_requested(self, config: dict):
        """Handler for generation request from GenerationContainer."""
        logger.info(f"Starting video generation with config: {config}")

        # NEU: Verwende GenerationContainer's Progress-Widget
        source_count = len(config.get("source_videos", []))
        self.generation_page.startGeneration(total_clips=source_count)

        # Start generation service
        self.generation_service.start_generation(
            config=config,
            on_progress=self._on_generation_progress,
            on_complete=self._on_generation_complete,
            on_error=self._on_generation_error
        )

    def _on_generation_progress(self, data: dict):
        """Update GenerationContainer progress."""
        status = data.get("status", "Processing")
        progress = data.get("progress", 0)
        current = data.get("current", 0)
        total = data.get("total", 0)

        # NEU: Update via GenerationContainer
        self.generation_page.updateProgress(
            progress=int(progress),
            step=status,
            current=current,
            total=total
        )
        logger.debug(f"Generation progress: {status} - {progress}%")

    def _on_generation_complete(self, result: dict):
        """Handle successful generation completion."""
        output_path = result.get("output_path", "Unknown")

        # NEU: Finish via GenerationContainer
        self.generation_page.finishGeneration(
            success=True,
            message=f"Video saved: {Path(output_path).name}"
        )

        QMessageBox.information(
            self,
            "Generation Complete",
            f"Video generated successfully!\n\nOutput: {output_path}"
        )
        logger.info(f"Generation completed: {output_path}")

    def _on_generation_error(self, error_tuple):
        """Handle generation error."""
        exc_type, exc_value, exc_tb = error_tuple
        error_msg = str(exc_value)

        # NEU: Finish via GenerationContainer mit Fehler
        self.generation_page.finishGeneration(
            success=False,
            message=f"Error: {error_msg}"
        )

        QMessageBox.critical(
            self,
            "Generation Failed",
            f"An error occurred during generation:\n\n{error_msg}"
        )
        logger.error(f"Generation error: {error_msg}", exc_info=(exc_type, exc_value, exc_tb))

    def closeEvent(self, event):
        """Cleanup on application close."""
        logger.info("Shutting down application...")

        # Stop monitoring timer
        if hasattr(self, 'monitor_timer'):
            self.monitor_timer.stop()

        # Dashboard-Timer stoppen
        if hasattr(self, 'dashboard_page') and hasattr(self.dashboard_page, 'cleanup'):
            self.dashboard_page.cleanup()

        # Editor-Prozess stoppen (Stem Separation)
        if hasattr(self, 'editor_page') and hasattr(self.editor_page, 'cleanup'):
            self.editor_page.cleanup()

        # Close system monitor
        if hasattr(self, 'monitor') and self.monitor:
            try:
                self.monitor.close()
            except Exception as e:
                logger.error(f"Error closing system monitor: {e}")

        # Free SmartDirector VRAM
        if hasattr(self, 'generation_service'):
            try:
                self.generation_service.unload_models()
            except Exception as e:
                logger.error(f"Error unloading models: {e}")

        # Shutdown database
        try:
            db = DatabaseCore()
            db.shutdown()
        except Exception as e:
            logger.error(f"Error during database shutdown: {e}")

        event.accept()
