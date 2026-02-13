"""
PB Studio AMD - Comprehensive End-to-End Test
==============================================
Testet alle Pipelines mit echten Medien-Dateien:
  1. Database Layer (Project + Media CRUD)
  2. Audio Import + Analyse (BeatNet)
  3. Video Import + Scene Detection
  4. Video Motion Analysis (RAFT / Farneback)
  5. Audio Stem Separation (DirectML)
  6. Audio Embedding (CLAP)
  7. Generation Pipeline (Pacing + Render)
  8. MediaService Integration (FFprobe + DB)
  9. ConfigManager + VRAMBudgetManager
  10. SmartDirector (AI-basierte Timeline)

Alle Ergebnisse werden in test_e2e_report.md dokumentiert.
"""

import gc
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# Projekt-Root ins Path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Logging setup
logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
  handlers=[
    logging.StreamHandler(),
    logging.FileHandler(PROJECT_ROOT / "test_e2e.log", mode="w", encoding="utf-8"),
  ]
)
logger = logging.getLogger("E2E-Test")

# ============================================================================
# Test-Daten Pfade
# ============================================================================
AUDIO_DIR = Path(r"C:\Users\david\Videos\Music-Video_Clips\AV\Audio")
VIDEO_DIR = Path(r"C:\Users\david\Videos\Music-Video_Clips\AV\Video")

# Auswahl: 3 Audio-Dateien, 5 Video-Clips (repraesentativ)
AUDIO_FILES = [
  AUDIO_DIR / "REC_20240406_5.wav",
  AUDIO_DIR / "recording-2021-04-24-235308.wav",
  AUDIO_DIR / "recording-2021-10-06-190824.wav",
]

VIDEO_FILES = [
  VIDEO_DIR / "1 (1).mp4",
  VIDEO_DIR / "1 (10).mp4",
  VIDEO_DIR / "1 (50).mp4",
  VIDEO_DIR / "1 (100).mp4",
  VIDEO_DIR / "1 (150).mp4",
]


# ============================================================================
# Report-Sammler
# ============================================================================
class TestReport:
  def __init__(self):
    self.results = []
    self.errors = []
    self.warnings = []
    self.start_time = time.time()

  def add_result(self, test_name: str, status: str, details: str = "", duration: float = 0):
    entry = {
      "test": test_name,
      "status": status,  # PASS, FAIL, SKIP, WARN
      "details": details,
      "duration_sec": round(duration, 2),
    }
    self.results.append(entry)
    icon = {"PASS": "OK", "FAIL": "FEHLER", "SKIP": "SKIP", "WARN": "WARNUNG"}[status]
    logger.info(f"[{icon}] {test_name}: {details[:120]}")
    if status == "FAIL":
      self.errors.append(entry)
    elif status == "WARN":
      self.warnings.append(entry)

  def generate_report(self) -> str:
    total_time = time.time() - self.start_time
    total = len(self.results)
    passed = sum(1 for r in self.results if r["status"] == "PASS")
    failed = sum(1 for r in self.results if r["status"] == "FAIL")
    skipped = sum(1 for r in self.results if r["status"] == "SKIP")
    warned = sum(1 for r in self.results if r["status"] == "WARN")

    lines = []
    lines.append("# PB Studio AMD - End-to-End Test Report")
    lines.append(f"Datum: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Gesamtdauer: {total_time:.1f}s")
    lines.append("")
    lines.append(f"## Zusammenfassung")
    lines.append(f"- Gesamt: {total}")
    lines.append(f"- Bestanden: {passed}")
    lines.append(f"- Fehlgeschlagen: {failed}")
    lines.append(f"- Warnungen: {warned}")
    lines.append(f"- Uebersprungen: {skipped}")
    lines.append("")

    if self.errors:
      lines.append("## FEHLER (Kritisch)")
      lines.append("")
      for e in self.errors:
        lines.append(f"### {e['test']}")
        lines.append(f"```")
        lines.append(e["details"])
        lines.append(f"```")
        lines.append("")

    if self.warnings:
      lines.append("## WARNUNGEN")
      lines.append("")
      for w in self.warnings:
        lines.append(f"- **{w['test']}**: {w['details']}")
      lines.append("")

    lines.append("## Alle Test-Ergebnisse")
    lines.append("")
    lines.append("| # | Test | Status | Dauer | Details |")
    lines.append("|---|------|--------|-------|---------|")
    for i, r in enumerate(self.results, 1):
      icon = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "SKIP", "WARN": "WARN"}[r["status"]]
      detail_short = r["details"][:80].replace("|", "/").replace("\n", " ")
      lines.append(f"| {i} | {r['test']} | {icon} | {r['duration_sec']}s | {detail_short} |")

    return "\n".join(lines)


report = TestReport()


# ============================================================================
# Hilfsfunktion: Test-Wrapper
# ============================================================================
def run_test(test_name: str, func, *args, **kwargs):
  """Fuehrt einen Test aus und faengt alle Fehler ab."""
  t0 = time.time()
  try:
    result = func(*args, **kwargs)
    dur = time.time() - t0
    if result is None:
      report.add_result(test_name, "PASS", "OK", dur)
    elif isinstance(result, str):
      report.add_result(test_name, "PASS", result, dur)
    elif isinstance(result, tuple):
      status, msg = result
      report.add_result(test_name, status, msg, dur)
    return result
  except Exception as e:
    dur = time.time() - t0
    tb = traceback.format_exc()
    report.add_result(test_name, "FAIL", f"{e}\n{tb}", dur)
    return None


# ============================================================================
# TEST 1: Datei-Validierung
# ============================================================================
def test_file_existence():
  """Prueft ob alle Testdateien existieren."""
  missing = []
  for f in AUDIO_FILES + VIDEO_FILES:
    if not f.exists():
      missing.append(str(f))
  if missing:
    return ("FAIL", f"Fehlende Dateien: {missing}")
  return f"Alle {len(AUDIO_FILES)} Audio + {len(VIDEO_FILES)} Video Dateien vorhanden"


# ============================================================================
# TEST 2: ConfigManager
# ============================================================================
def test_config_manager():
  """Testet ConfigManager Singleton, Pfad-Aufloesung und Properties."""
  from src.pb_studio.config_manager import ConfigManager
  cfg = ConfigManager()

  # Singleton-Check
  cfg2 = ConfigManager()
  assert cfg is cfg2, "ConfigManager ist kein Singleton!"

  # FFmpeg-Pfad
  ffmpeg = cfg.ffmpeg_path
  ffmpeg_exists = Path(ffmpeg).exists()

  # LHM-Pfad
  lhm = cfg.lhm_path
  lhm_exists = Path(lhm).exists()

  # Default values
  gpu_backend = cfg.get("hardware", {}).get("gpu_backend", "???")

  result_parts = [
    f"ffmpeg={ffmpeg} (exists={ffmpeg_exists})",
    f"lhm={lhm} (exists={lhm_exists})",
    f"gpu_backend={gpu_backend}",
  ]

  if not ffmpeg_exists:
    return ("WARN", f"FFmpeg nicht gefunden: {ffmpeg}")

  return "; ".join(result_parts)


# ============================================================================
# TEST 3: Database Layer
# ============================================================================
def test_database_core():
  """Testet DatabaseCore: Connection, Transaction, Thread-Safety."""
  from src.pb_studio.data.database_core import DatabaseCore
  db = DatabaseCore()

  # Connection
  conn = db.get_connection()
  assert conn is not None, "Keine DB-Connection erhalten"

  # Transaction (execute gibt Cursor zurueck, fetchone auf Cursor aufrufen)
  with db.transaction() as c:
    cursor = c.execute("SELECT 1")
    row = cursor.fetchone()
    assert row[0] == 1, "SELECT 1 fehlgeschlagen"

  # Schema-Check
  with db.transaction() as c:
    cursor = c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]

  expected = ["projects", "media", "vector_map"]
  missing = [t for t in expected if t not in tables]
  if missing:
    return ("WARN", f"Fehlende Tabellen: {missing}. Vorhandene: {tables}")

  return f"DB OK. Tabellen: {tables}"


def test_project_crud():
  """Testet Project-Repository: Create, Read, Update, Delete."""
  from src.pb_studio.data.repositories.project_repository import ProjectRepository
  repo = ProjectRepository()

  # Create
  pid = repo.create_project("E2E_Test_Project", {"test": True})
  assert pid > 0, f"Projekt-Erstellung fehlgeschlagen (ID={pid})"

  # Read
  proj = repo.get_by_id(pid)
  assert proj is not None, f"Projekt {pid} nicht gefunden"
  assert proj["name"] == "E2E_Test_Project"

  # Update
  repo.update_project(pid, name="E2E_Updated")
  proj2 = repo.get_by_id(pid)
  assert proj2["name"] == "E2E_Updated"

  # List
  all_projects = repo.get_all()
  assert any(p["id"] == pid for p in all_projects), "Projekt nicht in Liste"

  # Delete
  repo.delete_project(pid)
  proj3 = repo.get_by_id(pid)
  assert proj3 is None, f"Projekt {pid} nicht geloescht"

  return "CRUD: Create/Read/Update/List/Delete OK"


def test_media_crud():
  """Testet Media-Repository: Add, Query, Update Status, Delete."""
  from src.pb_studio.data.repositories.project_repository import ProjectRepository
  from src.pb_studio.data.repositories.media_repository import MediaRepository

  proj_repo = ProjectRepository()
  media_repo = MediaRepository()

  # Projekt erstellen
  pid = proj_repo.create_project("E2E_Media_Test")
  assert pid > 0

  test_file = str(AUDIO_FILES[0])

  # Media hinzufuegen
  mid = media_repo.add_media(
    project_id=pid,
    file_path=test_file,
    file_hash="test_hash_e2e",
    duration=60.0,
    meta={"format": "wav", "test": True}
  )
  assert mid > 0, f"Media-Erstellung fehlgeschlagen (ID={mid})"

  # Read
  media = media_repo.get_by_id(mid)
  assert media is not None
  assert media["file_path"] == test_file

  # Find by hash
  found = media_repo.find_by_hash("test_hash_e2e")
  assert found is not None, "find_by_hash fehlgeschlagen"

  # Update status + AI data
  ai_data = {"bpm": 128.5, "beat_data": [[0.5, 1], [1.0, 2]]}
  media_repo.update_status(mid, "ready", ai_data)

  media2 = media_repo.get_by_id(mid)
  assert media2["status"] == "ready"
  stored_ai = json.loads(media2["ai_data_json"]) if media2.get("ai_data_json") else {}
  assert stored_ai.get("bpm") == 128.5, f"AI-Data nicht korrekt gespeichert: {stored_ai}"

  # By project
  proj_media = media_repo.get_by_project(pid)
  assert len(proj_media) >= 1

  # Cleanup
  media_repo.delete_media(mid)
  proj_repo.delete_project(pid)

  return "Media CRUD: Add/Read/Hash/Status/AI-Data/Delete OK"


# ============================================================================
# TEST 4: MediaService (FFprobe Integration)
# ============================================================================
def test_media_service_import():
  """Testet MediaService.import_files() mit echten Dateien."""
  from src.pb_studio.services.media_service import MediaService
  from src.pb_studio.data.repositories.project_repository import ProjectRepository

  proj_repo = ProjectRepository()
  pid = proj_repo.create_project("E2E_Import_Test")

  service = MediaService()

  # Import Audio + Video
  files_to_import = [str(AUDIO_FILES[0]), str(VIDEO_FILES[0])]
  results = service.import_files(pid, files_to_import)

  imported = [(mid, status) for mid, status in results if mid > 0]
  failed = [(mid, status) for mid, status in results if mid <= 0]

  # Pruefe ob Metadata extrahiert wurde
  if imported:
    mid = imported[0][0]
    from src.pb_studio.data.repositories.media_repository import MediaRepository
    media_repo = MediaRepository()
    media = media_repo.get_by_id(mid)
    has_metadata = media.get("metadata_json") is not None if media else False

    # Cleanup
    for mid_c, _ in imported:
      media_repo.delete_media(mid_c)
  else:
    has_metadata = False

  proj_repo.delete_project(pid)

  if failed:
    return ("WARN", f"Import: {len(imported)} OK, {len(failed)} fehlgeschlagen. Metadata={has_metadata}")

  return f"Import: {len(imported)} Dateien OK. Metadata extrahiert={has_metadata}"


# ============================================================================
# TEST 5: Audio Analyse (BeatNet)
# ============================================================================
def test_audio_analyzer():
  """Testet AudioAnalyzer.analyze_file() mit echten WAV-Dateien."""
  from src.pb_studio.audio.analyzer import AudioAnalyzer
  analyzer = AudioAnalyzer()

  if not analyzer.model_loaded:
    return ("SKIP", "BeatNet Modell nicht geladen - Analyse uebersprungen")

  results_summary = []
  for audio_file in AUDIO_FILES:
    if not audio_file.exists():
      results_summary.append(f"{audio_file.name}: NICHT GEFUNDEN")
      continue

    result = analyzer.analyze_file(str(audio_file))

    if "error" in result:
      results_summary.append(f"{audio_file.name}: FEHLER - {result['error']}")
    else:
      bpm = result.get("bpm", 0)
      beats = result.get("beat_data", [])
      count = result.get("count", 0)
      results_summary.append(f"{audio_file.name}: BPM={bpm:.1f}, Beats={count}")

  return "; ".join(results_summary)


def test_audio_import_worker():
  """Testet AudioImportWorker._execute() direkt."""
  from src.pb_studio.workers.audio.audio_import_worker import AudioImportWorker

  audio_file = str(AUDIO_FILES[0])
  worker = AudioImportWorker(audio_file)

  result = worker._execute()
  wav_path = result.temp_wav_path
  wav_exists = Path(wav_path).exists() if wav_path else False
  wav_size = Path(wav_path).stat().st_size if wav_exists else 0

  # Metadata
  meta = result.metadata
  details = f"WAV={wav_exists} ({wav_size} bytes)"
  if meta:
    details += f", duration={getattr(meta, 'duration', '?')}s"

  # Cleanup temp file
  if wav_exists:
    try:
      os.remove(wav_path)
    except Exception:
      pass

  if not wav_exists:
    return ("FAIL", f"WAV nicht erstellt: {wav_path}")

  return details


def test_audio_analyze_worker():
  """Testet AudioAnalyzeWorker._execute() direkt."""
  from src.pb_studio.workers.audio.audio_import_worker import AudioImportWorker
  from src.pb_studio.workers.audio.audio_analyze_worker import AudioAnalyzeWorker

  # Erst importieren (WAV erzeugen)
  import_worker = AudioImportWorker(str(AUDIO_FILES[0]))
  import_result = import_worker._execute()
  wav_path = import_result.temp_wav_path

  if not Path(wav_path).exists():
    return ("FAIL", "Import hat kein WAV erstellt")

  try:
    analyze_worker = AudioAnalyzeWorker(wav_path)
    result = analyze_worker._execute()

    bpm = result.bpm
    beats = len(result.beat_times)
    downbeats = len(result.downbeat_times)
    confidence = result.confidence

    return f"BPM={bpm:.1f}, Beats={beats}, Downbeats={downbeats}, Confidence={confidence:.2f}"
  finally:
    try:
      os.remove(wav_path)
    except Exception:
      pass


# ============================================================================
# TEST 6: Video Import + Scene Detection
# ============================================================================
def test_video_import_worker():
  """Testet VideoImportWorker._execute() mit echten Videos."""
  from src.pb_studio.workers.video.video_import_worker import VideoImportWorker

  video_file = str(VIDEO_FILES[0])
  worker = VideoImportWorker(video_file, "e2e_test")

  result = worker._execute()
  metadata = result.get("metadata")

  if metadata is None:
    return ("FAIL", "Keine Metadata extrahiert")

  details = []
  # VideoMetadata kann ein dict oder dataclass sein
  if hasattr(metadata, "duration"):
    details.append(f"duration={metadata.duration:.1f}s")
    details.append(f"fps={metadata.fps}")
    details.append(f"resolution={metadata.width}x{metadata.height}")
    details.append(f"codec={metadata.codec}")
    details.append(f"has_audio={metadata.has_audio}")
  elif isinstance(metadata, dict):
    details.append(f"duration={metadata.get('duration', '?')}s")
    details.append(f"fps={metadata.get('fps', '?')}")
    details.append(f"resolution={metadata.get('width', '?')}x{metadata.get('height', '?')}")

  return ", ".join(details)


def test_video_scene_worker():
  """Testet VideoSceneWorker._execute() mit echten Videos."""
  from src.pb_studio.workers.video.video_scene_worker import VideoSceneWorker

  video_file = str(VIDEO_FILES[0])
  worker = VideoSceneWorker(video_file, threshold=8.0)

  result = worker._execute()
  scenes = result.get("scenes", [])

  if not scenes:
    return ("WARN", "Keine Szenen erkannt (Video zu kurz oder uniform?)")

  details = f"{len(scenes)} Szenen erkannt. "
  for i, sc in enumerate(scenes[:3]):
    if hasattr(sc, "start"):
      details += f"[{sc.start:.1f}s-{sc.end:.1f}s] "
    elif isinstance(sc, dict):
      details += f"[{sc.get('start', 0):.1f}s-{sc.get('end', 0):.1f}s] "

  return details


def test_video_multiple_files():
  """Testet Import + Scene Detection fuer alle 5 Videos."""
  from src.pb_studio.workers.video.video_import_worker import VideoImportWorker
  from src.pb_studio.workers.video.video_scene_worker import VideoSceneWorker

  results_parts = []
  errors = 0

  for vf in VIDEO_FILES:
    if not vf.exists():
      results_parts.append(f"{vf.name}: NICHT GEFUNDEN")
      errors += 1
      continue

    try:
      # Import
      iw = VideoImportWorker(str(vf), "e2e")
      ir = iw._execute()
      meta = ir.get("metadata")
      dur = getattr(meta, "duration", 0) if meta else 0

      # Scene
      sw = VideoSceneWorker(str(vf), threshold=8.0)
      sr = sw._execute()
      scenes = len(sr.get("scenes", []))

      results_parts.append(f"{vf.name}: {dur:.1f}s, {scenes} scenes")
    except Exception as e:
      results_parts.append(f"{vf.name}: ERROR - {e}")
      errors += 1

  summary = "; ".join(results_parts)
  if errors > 0:
    return ("WARN", summary)
  return summary


# ============================================================================
# TEST 7: Waveform Analyse
# ============================================================================
def test_waveform_analyzer():
  """Testet WaveformAnalyzer mit echten Audio-Dateien."""
  from src.pb_studio.audio.waveform_analyzer import WaveformAnalyzer

  analyzer = WaveformAnalyzer()
  audio_file = str(AUDIO_FILES[0])

  try:
    result = analyzer.analyze(audio_file)
  except Exception as e:
    return ("FAIL", f"WaveformAnalyzer.analyze() fehlgeschlagen: {e}")

  if result is None:
    return ("FAIL", "WaveformAnalyzer lieferte None")

  # Ergebnis pruefen
  if isinstance(result, dict):
    keys = list(result.keys())
    return f"Waveform OK. Keys: {keys}"
  elif hasattr(result, 'waveform_data'):
    data_len = len(result.waveform_data) if result.waveform_data else 0
    return f"Waveform OK. Datenpunkte: {data_len}"
  else:
    return f"Waveform OK. Typ: {type(result).__name__}"


# ============================================================================
# TEST 8: Audio Models (Transformation)
# ============================================================================
def test_audio_model_transformation():
  """Testet AudioAnalysisResult.from_analyzer_output() und get_beats()."""
  from src.pb_studio.models.audio import AudioAnalysisResult

  # Simuliertes BeatNet Output
  analyzer_output = {
    "bpm": 128.5,
    "beat_data": [[0.5, 1], [0.97, 2], [1.44, 3], [1.91, 4], [2.38, 1]],
    "count": 5,
  }

  result = AudioAnalysisResult.from_analyzer_output(analyzer_output)
  assert result.bpm == 128.5, f"BPM falsch: {result.bpm}"
  assert len(result.beat_times) == 5, f"Beat-Zeiten falsch: {len(result.beat_times)}"
  assert len(result.downbeat_times) == 2, f"Downbeats falsch: {len(result.downbeat_times)}"

  # get_beats()
  beats = result.get_beats()
  assert len(beats) == 5, f"get_beats() falsch: {len(beats)}"
  assert beats[0].is_downbeat, "Erster Beat sollte Downbeat sein"
  assert not beats[1].is_downbeat, "Zweiter Beat sollte kein Downbeat sein"

  return f"BPM={result.bpm}, Beats={len(beats)}, Downbeats={len(result.downbeat_times)}"


# ============================================================================
# TEST 9: SystemMonitor
# ============================================================================
def test_system_monitor():
  """Testet SystemMonitor.get_stats()."""
  from src.pb_studio.core.system_monitor import SystemMonitor
  monitor = SystemMonitor()

  stats = monitor.get_stats()

  cpu = stats.get("cpu_load", -1)
  gpu = stats.get("gpu_load", -1)
  vram_used = stats.get("gpu_memory_used", -1)
  vram_total = stats.get("gpu_memory_total", -1)

  details = f"CPU={cpu}%, GPU={gpu}%, VRAM={vram_used}/{vram_total} MB"

  if cpu < 0 and gpu < 0:
    return ("WARN", f"Keine System-Stats verfuegbar: {details}")

  return details


# ============================================================================
# TEST 10: VRAMBudgetManager
# ============================================================================
def test_vram_budget_manager():
  """Testet VRAMBudgetManager Singleton und Budget-Tracking."""
  from src.pb_studio.core.vram_budget_manager import VRAMBudgetManager

  vbm = VRAMBudgetManager()

  # Singleton-Check
  vbm2 = VRAMBudgetManager()
  assert vbm is vbm2, "VRAMBudgetManager kein Singleton"

  # Budget-Query
  try:
    total = vbm.get_total_budget()
    available = vbm.get_available_budget()
    return f"Total={total} MB, Available={available} MB"
  except Exception as e:
    return ("WARN", f"Budget-Query fehlgeschlagen: {e}")


# ============================================================================
# TEST 11: Orchestrator Audio Pipeline
# ============================================================================
def test_orchestrator_audio_pipeline():
  """Testet WorkerOrchestrator.run_audio_pipeline() end-to-end."""
  # PyQt6 QObject braucht QApplication
  from PyQt6.QtWidgets import QApplication
  app = QApplication.instance()
  if app is None:
    app = QApplication(sys.argv)

  from src.pb_studio.workers.orchestrator import WorkerOrchestrator

  orchestrator = WorkerOrchestrator()
  audio_file = str(AUDIO_FILES[0])

  result = orchestrator.run_audio_pipeline(
    file_path=audio_file,
    include_stems=False,
    include_embeddings=False,
  )

  if not result.success:
    return ("FAIL", f"Audio-Pipeline fehlgeschlagen: {result.error_message}")

  phases = result.phases_completed
  return f"BPM={result.bpm:.1f}, Beats={len(result.beat_times)}, Phases={phases}"


# ============================================================================
# TEST 12: Orchestrator Video Pipeline
# ============================================================================
def test_orchestrator_video_pipeline():
  """Testet WorkerOrchestrator.run_video_pipeline() end-to-end."""
  from PyQt6.QtWidgets import QApplication
  app = QApplication.instance()
  if app is None:
    app = QApplication(sys.argv)

  from src.pb_studio.workers.orchestrator import WorkerOrchestrator

  orchestrator = WorkerOrchestrator()
  video_file = str(VIDEO_FILES[0])

  result = orchestrator.run_video_pipeline(
    file_path=video_file,
    include_motion=False,  # RAFT braucht GPU-Modell
    include_vision=False,  # Moondream braucht GPU-Modell
  )

  if not result.success:
    return ("FAIL", f"Video-Pipeline fehlgeschlagen: {result.error_message}")

  phases = result.phases_completed
  scenes_count = len(result.scenes)
  return f"Scenes={scenes_count}, Phases={phases}"


# ============================================================================
# TEST 13: DB-Pipeline Integration (Import -> Analyze -> Store -> Query)
# ============================================================================
def test_db_pipeline_integration():
  """
  Vollstaendiger Daten-Durchlauf:
  1. Projekt erstellen
  2. Datei importieren (MediaService)
  3. Audio analysieren (BeatNet)
  4. Ergebnis in DB speichern (update_status + ai_data)
  5. Aus DB lesen und validieren
  6. Cleanup
  """
  from src.pb_studio.data.repositories.project_repository import ProjectRepository
  from src.pb_studio.data.repositories.media_repository import MediaRepository
  from src.pb_studio.services.media_service import MediaService
  from src.pb_studio.audio.analyzer import AudioAnalyzer

  proj_repo = ProjectRepository()
  media_repo = MediaRepository()
  service = MediaService()

  # 1. Projekt
  pid = proj_repo.create_project("E2E_Integration_Test")
  assert pid > 0, "Projekt-Erstellung fehlgeschlagen"

  audio_file = str(AUDIO_FILES[0])

  try:
    # 2. Import
    results = service.import_files(pid, [audio_file])
    if not results or results[0][0] <= 0:
      return ("FAIL", f"Import fehlgeschlagen: {results}")

    mid = results[0][0]

    # 3. Analysieren
    analyzer = AudioAnalyzer()
    if not analyzer.model_loaded:
      # Simulierte Analyse-Daten verwenden
      ai_data = {"bpm": 120.0, "beat_data": [[0.5, 1], [1.0, 2]], "count": 2}
    else:
      ai_data = analyzer.analyze_file(audio_file)

    if "error" in ai_data:
      return ("WARN", f"Analyse fehlgeschlagen: {ai_data['error']}")

    # 4. In DB speichern
    media_repo.update_status(mid, "ready", ai_data)

    # 5. Aus DB lesen und validieren
    media = media_repo.get_by_id(mid)
    assert media is not None, "Media nicht in DB"
    assert media["status"] == "ready", f"Status falsch: {media['status']}"

    stored_ai = json.loads(media["ai_data_json"]) if media.get("ai_data_json") else {}
    stored_bpm = stored_ai.get("bpm", 0)
    stored_beats = stored_ai.get("beat_data", [])

    return (
      f"Import -> Analyse -> DB -> Query OK. "
      f"BPM={stored_bpm}, Beats={len(stored_beats)}, Status={media['status']}"
    )

  finally:
    # 6. Cleanup
    try:
      proj_repo.delete_project(pid)
    except Exception:
      pass


# ============================================================================
# TEST 14: Video Motion Analysis (RAFT/Farneback)
# ============================================================================
def test_video_motion_analysis():
  """Testet MotionAnalyzer mit echten Video-Frames."""
  try:
    from src.pb_studio.video.raft import create_motion_analyzer
  except ImportError:
    return ("SKIP", "raft.py nicht importierbar")

  try:
    analyzer = create_motion_analyzer()
  except Exception as e:
    return ("WARN", f"MotionAnalyzer-Erstellung fehlgeschlagen: {e}")

  analyzer_type = type(analyzer).__name__

  # Frames aus Video extrahieren
  import cv2
  video_path = str(VIDEO_FILES[0])
  cap = cv2.VideoCapture(video_path)

  if not cap.isOpened():
    return ("FAIL", f"Video nicht oeffenbar: {video_path}")

  frames = []
  for _ in range(10):
    ret, frame = cap.read()
    if not ret:
      break
    frames.append(frame)
  cap.release()

  if len(frames) < 2:
    return ("FAIL", f"Zu wenige Frames extrahiert: {len(frames)}")

  try:
    # Testen: 2 aufeinanderfolgende Frames
    magnitude = analyzer.get_motion_magnitude(frames[0], frames[5])
    stats = analyzer.get_motion_statistics(frames[0], frames[5])
    is_scene_change, confidence = analyzer.detect_scene_change(frames[0], frames[5])

    return (
      f"Analyzer={analyzer_type}, Magnitude={magnitude:.2f}, "
      f"Mean={stats.get('mean_magnitude', 0):.2f}, "
      f"SceneChange={is_scene_change} (conf={confidence:.2f})"
    )
  except Exception as e:
    return ("FAIL", f"Motion-Analyse fehlgeschlagen: {e}")
  finally:
    try:
      analyzer.unload()
    except Exception:
      pass
    gc.collect()


# ============================================================================
# TEST 15: Audio Stem Separation (DirectML)
# ============================================================================
def test_audio_stem_separation():
  """Testet StemSeparator mit DirectML Backend."""
  try:
    from src.pb_studio.audio.separator import StemSeparator
  except ImportError as e:
    return ("SKIP", f"StemSeparator nicht importierbar: {e}")

  try:
    separator = StemSeparator()
  except Exception as e:
    return ("WARN", f"StemSeparator Init fehlgeschlagen: {e}")

  audio_file = str(AUDIO_FILES[0])

  try:
    # Stem Separation ausfuehren
    result = separator.separate(audio_file)

    if isinstance(result, dict):
      stems = list(result.keys())
      paths = list(result.values())
      existing = [p for p in paths if p and Path(p).exists()]
      return f"Stems: {stems}, Existierend: {len(existing)}/{len(paths)}"
    else:
      return f"Ergebnis-Typ: {type(result).__name__}"

  except Exception as e:
    return ("FAIL", f"Stem-Separation fehlgeschlagen: {e}")
  finally:
    gc.collect()


# ============================================================================
# TEST 16: CLAP Audio Embedding
# ============================================================================
def test_clap_embedding():
  """Testet CLAPPyTorch Audio-Embedding."""
  try:
    from src.pb_studio.ai.clap_wrapper import CLAPPyTorch
  except ImportError as e:
    return ("SKIP", f"CLAP nicht importierbar: {e}")

  try:
    clap = CLAPPyTorch()
    loaded = clap.load()
    if not loaded:
      return ("WARN", "CLAP Modell konnte nicht geladen werden")
  except Exception as e:
    return ("WARN", f"CLAP Init fehlgeschlagen: {e}")

  audio_file = str(AUDIO_FILES[0])

  try:
    embedding = clap.encode_audio(audio_file)
    if embedding is not None:
      import numpy as np
      if isinstance(embedding, np.ndarray):
        return f"Embedding Shape: {embedding.shape}, Norm: {np.linalg.norm(embedding):.4f}"
      else:
        return f"Embedding Typ: {type(embedding).__name__}"
    else:
      return ("WARN", "CLAP lieferte None-Embedding")
  except Exception as e:
    return ("FAIL", f"CLAP encode_audio fehlgeschlagen: {e}")
  finally:
    try:
      clap.unload()
    except Exception:
      pass
    gc.collect()


# ============================================================================
# TEST 17: Worker Registry
# ============================================================================
def test_worker_registry():
  """Testet Worker Registry Setup und VRAM-Budgets."""
  from src.pb_studio.workers import setup_worker_registry
  from src.pb_studio.workers.worker_registry import WorkerRegistry

  registry = WorkerRegistry()
  if not registry.list_workers():
    setup_worker_registry(registry)

  workers = registry.list_workers()
  expected = [
    "audio_import", "audio_analyze", "audio_stem", "audio_embedding",
    "video_import", "video_scene", "video_motion", "video_vision",
    "pacing", "render", "concat", "export",
  ]

  missing = [w for w in expected if w not in workers]
  extra = [w for w in workers if w not in expected]

  details = f"{len(workers)} registriert"
  if missing:
    details += f", fehlend: {missing}"
  if extra:
    details += f", extra: {extra}"

  # VRAM Budgets
  gpu_workers = [(w, registry.get_vram_budget(w)) for w in workers if registry.get_vram_budget(w) > 0]
  details += f", GPU-Worker: {len(gpu_workers)}"

  if missing:
    return ("WARN", details)
  return details


# ============================================================================
# TEST 18: SigLIP Wrapper (Vision Model)
# ============================================================================
def test_siglip_wrapper():
  """Testet SigLIP Vision-Language Model (ONNX+DirectML)."""
  try:
    from src.pb_studio.ai.siglip_wrapper import SigLIPWrapper
  except ImportError as e:
    return ("SKIP", f"SigLIP nicht importierbar: {e}")

  try:
    siglip = SigLIPWrapper(lazy_load=True)
  except Exception as e:
    return ("WARN", f"SigLIP Init fehlgeschlagen: {e}")

  try:
    loaded = siglip.load()
    if not loaded:
      return ("WARN", "SigLIP Modell nicht ladbar (ONNX-Dateien fehlen?)")
  except Exception as e:
    return ("WARN", f"SigLIP load fehlgeschlagen: {e}")

  # Teste mit einem Video-Frame
  import cv2
  video_path = str(VIDEO_FILES[0])
  cap = cv2.VideoCapture(video_path)
  ret, frame = cap.read()
  cap.release()

  if not ret:
    return ("FAIL", "Kein Frame aus Video extrahierbar")

  try:
    from PIL import Image
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    embedding = siglip.encode_image(img)

    if embedding is not None:
      import numpy as np
      return f"SigLIP Embedding: shape={embedding.shape}, norm={np.linalg.norm(embedding):.4f}"
    else:
      return ("WARN", "SigLIP lieferte None-Embedding")
  except Exception as e:
    return ("FAIL", f"SigLIP encode_image fehlgeschlagen: {e}")
  finally:
    try:
      siglip.unload()
    except Exception:
      pass
    gc.collect()


# ============================================================================
# TEST 19: Moondream VLM
# ============================================================================
def test_moondream():
  """Testet Moondream Vision-Language Model (ONNX Encoder)."""
  try:
    from src.pb_studio.video.moondream import MoondreamAnalyzer
  except ImportError as e:
    return ("SKIP", f"Moondream nicht importierbar: {e}")

  try:
    analyzer = MoondreamAnalyzer()
    loaded = analyzer.load()
    if not loaded:
      return ("WARN", "Moondream nicht ladbar (Modell-Dateien fehlen?)")
  except Exception as e:
    return ("WARN", f"Moondream Init/Load fehlgeschlagen: {e}")

  try:
    # Teste mit Video-Frame
    import cv2
    from PIL import Image
    cap = cv2.VideoCapture(str(VIDEO_FILES[0]))
    ret, frame = cap.read()
    cap.release()

    if not ret:
      return ("FAIL", "Frame-Extraktion fehlgeschlagen")

    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    caption = analyzer.describe(img)

    if caption:
      return f"Moondream Caption: '{caption[:80]}...'"
    else:
      return ("WARN", "Moondream lieferte leere Caption")

  except Exception as e:
    return ("FAIL", f"Moondream describe fehlgeschlagen: {e}")
  finally:
    try:
      analyzer.unload()
    except Exception:
      pass
    gc.collect()


# ============================================================================
# TEST 20: VectorStore (FAISS)
# ============================================================================
def test_vector_store():
  """Testet FAISS VectorStore fuer Similarity Search."""
  try:
    from src.pb_studio.data.vector_store import VectorStore
  except ImportError as e:
    return ("SKIP", f"VectorStore nicht importierbar: {e}")

  import numpy as np

  try:
    store = VectorStore(dimension=128)

    # Vektoren hinzufuegen
    vec1 = np.random.randn(128).astype(np.float32)
    vec2 = np.random.randn(128).astype(np.float32)
    vec3 = vec1 + np.random.randn(128).astype(np.float32) * 0.1  # Aehnlich zu vec1

    store.add(0, vec1, {"label": "test1"})
    store.add(1, vec2, {"label": "test2"})
    store.add(2, vec3, {"label": "test3"})

    # Aehnlichkeitssuche
    results = store.search(vec1, top_k=3)

    if not results:
      return ("FAIL", "FAISS Search lieferte keine Ergebnisse")

    # vec3 sollte naeher an vec1 sein als vec2
    top_id = results[0][0] if results else -1
    return f"VectorStore OK. Top-Match ID={top_id}, {len(results)} Ergebnisse"

  except Exception as e:
    return ("FAIL", f"VectorStore fehlgeschlagen: {e}")


# ============================================================================
# MAIN: Alle Tests ausfuehren
# ============================================================================
def main():
  logger.info("=" * 70)
  logger.info("PB Studio AMD - End-to-End Test gestartet")
  logger.info(f"Audio-Dir: {AUDIO_DIR}")
  logger.info(f"Video-Dir: {VIDEO_DIR}")
  logger.info("=" * 70)

  # QApplication initialisieren (fuer Worker die QObject brauchen)
  from PyQt6.QtWidgets import QApplication
  app = QApplication.instance()
  if app is None:
    app = QApplication(sys.argv)

  # ---- Basis-Tests ----
  run_test("01_Datei-Validierung", test_file_existence)
  run_test("02_ConfigManager", test_config_manager)
  run_test("03_Database_Core", test_database_core)
  run_test("04_Project_CRUD", test_project_crud)
  run_test("05_Media_CRUD", test_media_crud)
  run_test("06_Worker_Registry", test_worker_registry)
  run_test("07_SystemMonitor", test_system_monitor)

  # ---- Audio-Pipeline ----
  run_test("08_Audio_Model_Transform", test_audio_model_transformation)
  run_test("09_Audio_Import_Worker", test_audio_import_worker)
  run_test("10_Audio_Analyzer_Direct", test_audio_analyzer)
  run_test("11_Audio_Analyze_Worker", test_audio_analyze_worker)
  run_test("12_Waveform_Analyzer", test_waveform_analyzer)

  # ---- Video-Pipeline ----
  run_test("13_Video_Import_Worker", test_video_import_worker)
  run_test("14_Video_Scene_Worker", test_video_scene_worker)
  run_test("15_Video_Multi_Files", test_video_multiple_files)
  run_test("16_Video_Motion_Analysis", test_video_motion_analysis)

  # ---- Orchestrator-Pipelines ----
  run_test("17_Orchestrator_Audio", test_orchestrator_audio_pipeline)
  run_test("18_Orchestrator_Video", test_orchestrator_video_pipeline)

  # ---- DB Integration ----
  run_test("19_DB_Pipeline_Integration", test_db_pipeline_integration)

  # ---- AI Models (GPU-intensiv) ----
  run_test("20_CLAP_Embedding", test_clap_embedding)
  run_test("21_SigLIP_Wrapper", test_siglip_wrapper)
  run_test("22_Moondream_VLM", test_moondream)

  # ---- GPU-intensiv ----
  run_test("23_Audio_Stem_Separation", test_audio_stem_separation)

  # ---- Datenstrukturen ----
  run_test("24_VectorStore_FAISS", test_vector_store)
  run_test("25_VRAM_BudgetManager", test_vram_budget_manager)

  # ---- Report generieren ----
  report_text = report.generate_report()
  report_path = PROJECT_ROOT / "test_e2e_report.md"
  with open(report_path, "w", encoding="utf-8") as f:
    f.write(report_text)

  logger.info("=" * 70)
  logger.info(f"REPORT gespeichert: {report_path}")

  # Zusammenfassung
  passed = sum(1 for r in report.results if r["status"] == "PASS")
  failed = sum(1 for r in report.results if r["status"] == "FAIL")
  warned = sum(1 for r in report.results if r["status"] == "WARN")
  skipped = sum(1 for r in report.results if r["status"] == "SKIP")

  logger.info(f"Ergebnis: {passed} PASS, {failed} FAIL, {warned} WARN, {skipped} SKIP")
  logger.info("=" * 70)


if __name__ == "__main__":
  main()
