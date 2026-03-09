"""Schneller Import-Test fuer Audio/Video Analyzer."""
import sys
import os

PROJECT = r"C:\Users\david\Dokumente\Pb_studio_AMD_version"
sys.path.insert(0, os.path.join(PROJECT, "src"))
os.chdir(PROJECT)

errors = []

tests = [
    ("AudioAnalyzer", "from pb_studio.audio.analyzer import AudioAnalyzer"),
    ("BeatDetector", "from pb_studio.audio.beat_detector import BeatDetector, BEATNET_AVAILABLE"),
    ("StructureAnalyzer", "from pb_studio.audio.structure_analyzer import StructureAnalyzer"),
    ("SpectralAnalyzer", "from pb_studio.audio.spectral_analyzer import SpectralAnalyzer"),
    ("KeyDetector", "from pb_studio.audio.key_detector import KeyDetector"),
    ("WaveformAnalyzer", "from pb_studio.audio.waveform_analyzer import WaveformAnalyzer"),
    ("SceneDetector", "from pb_studio.video.scene_detect import SceneDetector"),
    ("MotionAnalyzer", "from pb_studio.video.raft import MotionAnalyzer"),
    ("FastAPI app", "from backend.main import app"),
]

for name, stmt in tests:
    try:
        exec(stmt)
        extra = ""
        if name == "BeatDetector":
            extra = f" (BeatNet={'JA' if BEATNET_AVAILABLE else 'NEIN - Librosa Fallback'})"
        print(f"OK: {name}{extra}")
    except Exception as e:
        errors.append(f"{name}: {e}")
        print(f"FAIL: {name}: {e}")

print()
if errors:
    print(f"FEHLER: {len(errors)} Module konnten nicht geladen werden!")
    for e in errors:
        print(f"  - {e}")
else:
    print("ALLE IMPORTS OK")
