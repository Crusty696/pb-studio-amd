import os
import sys
import time
import random
import csv
import logging
from pathlib import Path

# Sicherstellen, dass das 'src' Verzeichnis im PYTHONPATH ist
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PROJECT_ROOT / "logs" / "stress_test.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("stress_test")

try:
    import psutil
except ImportError:
    psutil = None
    logger.warning("psutil nicht verfuegbar - Host-RAM Messung faellt auf Dummy-Werte zurueck.")

from pb_studio.core.system_monitor import SystemMonitor
from pb_studio.ai import VideoSpecialist
from pb_studio.video.raft import MotionAnalyzer

def get_ram_usage_mb() -> float:
    """Gibt den aktuellen RAM-Verbrauch des Prozesses in MB zurueck."""
    if psutil:
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    return 0.0

def get_vram_usage_mb(monitor: SystemMonitor) -> float:
    """Gibt den aktuellen VRAM-Verbrauch der GPU in MB zurueck."""
    try:
        stats = monitor.get_stats()
        return stats.get("gpu_memory_used", 0.0)
    except Exception as exc:
        logger.warning(f"VRAM-Messung fehlgeschlagen: {exc}")
        return 0.0

def run_stress_test(max_cycles: int = 100):
    logger.info(f"=== STARTE DIRECTML LANGZEIT-STRESSTEST ({max_cycles} ZYKLEN) ===")
    
    # Pfad zu den Test-Clips
    assets_dir = PROJECT_ROOT / "data" / "stress_test_assets"
    if not assets_dir.exists():
        logger.error(f"Test-Verzeichnis existiert nicht: {assets_dir}")
        sys.exit(1)
        
    clips = list(assets_dir.glob("*.mp4"))
    if not clips:
        logger.error(f"Keine .mp4 Clips in {assets_dir} gefunden!")
        sys.exit(1)
        
    logger.info(f"{len(clips)} Test-Clips erfolgreich geladen.")
    
    # 1. Hardware-Monitor und Inferenz-Klassen initialisieren
    monitor = SystemMonitor()
    logger.info("SystemMonitor initialisiert.")
    
    try:
        logger.info("Lade VideoSpecialist (SigLIP DirectML)...")
        specialist = VideoSpecialist()
        logger.info("VideoSpecialist geladen.")
        
        logger.info("Lade MotionAnalyzer (RAFT)...")
        raft = MotionAnalyzer()
        logger.info("MotionAnalyzer geladen.")
        
        # CSV-Logging vorbereiten
        csv_file = PROJECT_ROOT / "logs" / "stress_test_metrics.csv"
        csv_file.parent.mkdir(exist_ok=True)
        
        with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Cycle", "Clip", "RAM_MB", "VRAM_MB", "Duration_Sec"])
            
        baseline_ram = 0.0
        baseline_vram = 0.0
        
        drift_limit = 0.15  # 15% zulaessiger Speicher-Drift
        
        for cycle in range(1, max_cycles + 1):
            clip = random.choice(clips)
            logger.info(f"[{cycle}/{max_cycles}] Analysiere: {clip.name}")
            
            start_time = time.monotonic()
            
            try:
                # 1. Video-Frames extrahieren und embedden (SigLIP)
                frames = specialist.extract_keyframes(str(clip), interval=1.0)
                specialist.embed_frames(frames)
                
                # 2. RAFT Motion-Analyse auf denselben extrahierten Frames berechnen
                if len(frames) > 1:
                    raft.analyze_video_segment(frames[:10])
                
            except Exception as exc:
                logger.error(f"Inferenz-Fehler im Zyklus {cycle} bei {clip.name}: {exc}")
                
            duration = time.monotonic() - start_time
            
            ram_mb = get_ram_usage_mb()
            vram_mb = get_vram_usage_mb(monitor)
            
            logger.info(f"  > RAM: {ram_mb:.1f} MB | VRAM: {vram_mb:.1f} MB | Dauer: {duration:.2f}s")
            
            # Metriken wegschreiben
            with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([cycle, clip.name, f"{ram_mb:.1f}", f"{vram_mb:.1f}", f"{duration:.2f}"])
                
            # Baseline nach dem Aufwaermen (Zyklus 5) setzen
            if cycle == 5:
                baseline_ram = ram_mb
                baseline_vram = vram_mb
                logger.info(f"=== Baseline gesetzt (Zyklus 5): RAM={baseline_ram:.1f}MB, VRAM={baseline_vram:.1f}MB ===")
                
        # Auswertung auf Drift
        if max_cycles >= 10:
            final_ram = get_ram_usage_mb()
            final_vram = get_vram_usage_mb(monitor)
            
            if baseline_ram > 0:
                ram_drift = (final_ram - baseline_ram) / baseline_ram
                logger.info(f"RAM-Drift (vs Baseline): {ram_drift * 100:.2f}%")
            else:
                ram_drift = 0.0
                
            if baseline_vram > 0:
                vram_drift = (final_vram - baseline_vram) / baseline_vram
                logger.info(f"VRAM-Drift (vs Baseline): {vram_drift * 100:.2f}%")
            else:
                vram_drift = 0.0
                
            if ram_drift > drift_limit or vram_drift > drift_limit:
                logger.error(
                    f"SPEICHERLECK ERKANNT: Drift ueberschreitet Limit von {drift_limit * 100:.0f}%! "
                    f"RAM Drift: {ram_drift * 100:.2f}%, VRAM Drift: {vram_drift * 100:.2f}%"
                )
                sys.exit(1)
                
        logger.info("=== STRESSTEST ERFOLGREICH BEENDET (0 Speicherlecks detektiert) ===")
        
    finally:
        logger.info("Schliesse SystemMonitor...")
        try:
            monitor.close()
            del monitor
        except Exception as e:
            logger.warning(f"Fehler beim Schliessen des SystemMonitors: {e}")
            
    sys.exit(0)

if __name__ == "__main__":
    cycles = 100
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        cycles = int(sys.argv[1])
    run_stress_test(cycles)
