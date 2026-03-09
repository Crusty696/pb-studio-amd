import logging
import re
import sys
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QSplitter, QPushButton, QProgressBar)
from PyQt6.QtCore import Qt, QProcess

from pb_studio.ui.widgets.player_widget import PlayerWidget
from pb_studio.ui.widgets.waveform_widget import WaveformWidget

logger = logging.getLogger(__name__)

PROGRESS_PATTERN = re.compile(r"(\d+)%?\|.*\| (\d+)/(\d+)")

class EditorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.stem_process = None
        self._cached_metadata = None
        self._init_ui()

    def _on_stem_click(self):
        """Starts stem separation process via QProcess."""
        logger.info(f"Stem button clicked for {self.current_file}")
        if not self.current_file:
            return

        # Pruefe ob bereits ein Prozess laeuft
        if hasattr(self, 'stem_process') and self.stem_process is not None:
            if self.stem_process.state() != QProcess.ProcessState.NotRunning:
                logger.warning("Stem separation already running")
                return

        self.stem_btn.setEnabled(False)
        self.stem_status.setVisible(True)
        self.stem_progress.setVisible(True)
        self.stem_progress.setValue(0)
        self.stem_status.setText("STARTING SUBPROCESS...")
        
        self.stem_process = QProcess()
        self.stem_process.readyReadStandardOutput.connect(self._handle_process_output)
        self.stem_process.readyReadStandardError.connect(self._handle_process_error)
        self.stem_process.finished.connect(self._handle_process_finished)
        
        # Run the runner script (relativ zu diesem Modul)
        script_path = str(Path(__file__).parent.parent.parent / "audio" / "stem_runner.py")
        python_exe = sys.executable
        
        logger.info(f"Launching QProcess: {python_exe} {script_path} {self.current_file}")
        self.stem_process.start(python_exe, [script_path, self.current_file])

    def _handle_process_output(self):
        data = self.stem_process.readAllStandardOutput().data().decode()
        for line in data.splitlines():
            logger.debug(f"Subprocess stdout: {line}")
            if line.startswith("PROGRESS:"):
                # Parse progress
                msg = line[9:]
                match = PROGRESS_PATTERN.search(msg)
                if match:
                    current = int(match.group(2))
                    total = int(match.group(3))
                    if total > 0:
                        pct = (current / total) * 100
                        self.stem_progress.setValue(int(pct))
                        self.stem_status.setText(f"PROCESSING... {pct:.2f}%")
            elif line.startswith("STATUS:"):
                self.stem_status.setText(line[7:])
            elif line.startswith("STEM:"):
                stem_file = line[5:]
                current_text = self.info_details.text()
                if "STEMS:" not in current_text:
                    self.info_details.setText(current_text + "\n\nSTEMS:")
                self.info_details.setText(self.info_details.text() + f"\n{stem_file.split(chr(92))[-1]}")

    def _handle_process_error(self):
        data = self.stem_process.readAllStandardError().data().decode()
        # Log backend errors but don't show all in UI (too spammy)
        if data.strip():
            logger.warning(f"Subprocess stderr: {data.strip()}")

    def _handle_process_finished(self, exit_code, exit_status):
        self.stem_btn.setEnabled(True)
        if exit_code == 0:
            self.stem_status.setText("DONE ✅")
            self.stem_progress.setValue(100)
        else:
            self.stem_status.setText("FAILED ❌")
            logger.error(f"Process failed with code {exit_code}")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        title = QLabel("Editor")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # Main Splitter: Left (Player Content) | Right (Info Panel)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Side: Waveform + Player (Vertical)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        
        # Waveform
        waveform_frame = QFrame()
        waveform_frame.setStyleSheet("background-color: #1e1e1e; border: 1px solid #3e3e42; border-radius: 4px;")
        waveform_frame.setFixedHeight(120)  # Fixed height to prevent collapse
        waveform_layout = QVBoxLayout(waveform_frame)
        waveform_layout.setContentsMargins(5, 5, 5, 5)
        
        waveform_label = QLabel("Waveform")
        waveform_label.setStyleSheet("color: #888888; font-size: 11px; border: none;")
        waveform_layout.addWidget(waveform_label)
        
        self.waveform = WaveformWidget()
        self.waveform.setMinimumHeight(80)
        waveform_layout.addWidget(self.waveform, 1)  # Stretch factor
        
        left_layout.addWidget(waveform_frame)
        
        # Player
        self.player = PlayerWidget()
        left_layout.addWidget(self.player, 1)
        
        main_splitter.addWidget(left_container)

        # Right Side: Info Panel
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #252526; border-radius: 6px;")
        info_frame.setMinimumWidth(250)
        
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(15, 15, 15, 15)
        
        info_title = QLabel("File Info")
        info_title.setStyleSheet("font-weight: bold; font-size: 16px; border: none;")
        info_layout.addWidget(info_title)
        
        self.info_filename = QLabel("No file loaded")
        self.info_filename.setWordWrap(True)
        self.info_filename.setStyleSheet("color: #cccccc; border: none;")
        info_layout.addWidget(self.info_filename)
        
        self.info_details = QLabel("")
        self.info_details.setWordWrap(True)
        self.info_details.setStyleSheet("color: #888888; border: none;")
        info_layout.addWidget(self.info_details)
        
        # Separator between info and actions
        info_layout.addSpacing(20)
        
        # Stem Separation Section
        stem_header = QLabel("Audio Tools")
        stem_header.setStyleSheet("font-weight: bold; font-size: 14px; border: none; color: #007acc;")
        info_layout.addWidget(stem_header)
        
        self.stem_btn = QPushButton("Separate Stems (GPU)")
        self.stem_btn.setStyleSheet("""
            QPushButton {
                background-color: #0e639c;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1177bb; }
            QPushButton:disabled { background-color: #3e3e42; color: #888888; }
        """)
        self.stem_btn.clicked.connect(self._on_stem_click)
        info_layout.addWidget(self.stem_btn)
        
        # Status Label (Replacing Progress Bar for visibility)
        self.stem_status = QLabel("")
        self.stem_status.setStyleSheet("color: #007acc; font-weight: bold; font-size: 12px; border: 1px solid #007acc; padding: 4px; border-radius: 4px;")
        self.stem_status.setVisible(False)
        self.stem_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_layout.addWidget(self.stem_status)

        # Progress Bar
        self.stem_progress = QProgressBar()
        self.stem_progress.setVisible(False)
        self.stem_progress.setFixedHeight(12)
        self.stem_progress.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #1e1e1e;
                border-radius: 6px;
                text-align: center;
                color: white; 
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                border-radius: 6px;
            }
        """)
        info_layout.addWidget(self.stem_progress)
        
        info_layout.addStretch()
        
        main_splitter.addWidget(info_frame)
        main_splitter.setSizes([700, 300])

        layout.addWidget(main_splitter)

    def load_file(self, file_path: str, metadata: dict = None):
        """Loads a file into the editor."""
        # Guard: Ignoriere redundante Aufrufe ohne neue Metadaten
        if metadata is None and self.current_file == file_path:
            logger.debug("Skipping redundant load_file call without metadata")
            return

        # Cache metadata fuer spaetere Aufrufe
        if metadata is not None:
            self._cached_metadata = metadata
        elif hasattr(self, '_cached_metadata') and self._cached_metadata:
            # Verwende gecachte Metadaten wenn keine neuen uebergeben
            metadata = self._cached_metadata

        self.current_file = file_path

        ai_data = metadata.get('ai_data', {}) if metadata else {}
        logger.debug(f"Loading file. BPM: {ai_data.get('bpm', 'N/A')}, Beats: {len(ai_data.get('beat_data', []))}")
        
        self.player.load_media(file_path)
        
        # Load waveform (for audio/video with audio)
        ext = file_path.lower().split(".")[-1]
        if ext in ["mp3", "wav", "flac", "ogg", "aac", "mp4", "mov", "avi", "mkv"]:
            self.waveform.load_audio(file_path)
        
        # Update info panel
        name = file_path.split("\\")[-1].split("/")[-1]
        self.info_filename.setText(name)
        
        if metadata:
            # Info
            dur = metadata.get("duration", 0) or 0
            mins = int(dur // 60)
            secs = int(dur % 60)
            details = f"Duration: {mins:02d}:{secs:02d}\n"
            details += f"Format: {metadata.get('format', 'Unknown')}"
            
            # AI Data (Beats)
            ai_data = metadata.get("ai_data", {})
            if ai_data:
                bpm = ai_data.get("bpm", 0)
                if bpm > 0:
                    details += f"\nBPM: {bpm:.1f}"
                else:
                    details += f"\n(No Audio Track)"
                
                # Check for beat markers
                beats = ai_data.get("beat_data", [])
                if beats:
                    # BeatNet returns [[time, beat_idx], ...]
                    # Sicherheitscheck: Falls flache Liste (nur Zeiten), direkt verwenden
                    if isinstance(beats[0], (list, tuple)):
                        beat_times = [b[0] for b in beats]
                    else:
                        beat_times = beats
                    self.waveform.set_beat_markers(beat_times)
            
            self.info_details.setText(details)

    def cleanup(self):
        """Stem-Prozess beenden falls noch laufend."""
        if self.stem_process is not None and self.stem_process.state() != QProcess.ProcessState.NotRunning:
            self.stem_process.kill()
            self.stem_process.waitForFinished(2000)

    def check_refresh(self, metadata: dict):
        """Refreshes editor if the analyzed file matches the current one."""
        if not self.current_file:
            return
            
        # Match by path
        analyzed_path = metadata.get("file_path", "")
        if not analyzed_path or analyzed_path != self.current_file:
            return
            
        logger.info(f"Auto-refreshing Editor for {self.current_file}")
        
        # Update Info Panel text (append or replace?)
        # For now, let's just re-trigger load logic partially or update specific fields
        # Ideally we just call load_file again with new metadata, but that reloads audio.
        # Let's just update the AI parts.
        
        ai_data = metadata.get("ai_data", {})
        if ai_data:
            bpm = ai_data.get("bpm", 0)
            
            # Update Info Text
            current_text = self.info_details.text()
            if "BPM:" not in current_text:
                self.info_details.setText(f"{current_text}\nBPM: {bpm:.1f}")
            
            # Update Waveform Markers
            beats = ai_data.get("beat_data", [])
            # Support both BeatNet raw [[t, i], ...] and simplified lists if changed
            if beats:
                try:
                    # If it's a list of lists/tuples
                    if isinstance(beats[0], (list, tuple)):
                        beat_times = [b[0] for b in beats]
                    else:
                        beat_times = beats
                    
                    self.waveform.set_beat_markers(beat_times)
                except Exception as e:
                    logger.error(f"Error parsing beats for refresh: {e}")



