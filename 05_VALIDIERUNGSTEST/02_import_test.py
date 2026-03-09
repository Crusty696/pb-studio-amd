"""
PB Studio AMD - Import & Funktionstest
Ausführen NACH 01_install_test.ps1
Testet ob alle Pakete laden und grundlegend funktionieren
"""

import sys
import os
from datetime import datetime

# Report-Datei
TEST_DIR = r"C:\Temp\pb_studio_amd_test"
REPORT_FILE = os.path.join(TEST_DIR, "IMPORT_REPORT.txt")

results = []
errors = []

def log(msg, status="INFO"):
    """Logging mit Status"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] [{status}] {msg}"
    print(line)
    results.append(line)

def test_import(name, import_stmt, test_func=None):
    """Testet Import und optionale Funktion"""
    try:
        exec(import_stmt)
        log(f"{name}: Import OK", "OK")
        
        if test_func:
            test_func()
            log(f"{name}: Funktionstest OK", "OK")
        return True
    except Exception as e:
        log(f"{name}: FEHLER - {str(e)}", "FAIL")
        errors.append(f"{name}: {str(e)}")
        return False

# ============================================
# TESTS
# ============================================

print("=" * 50)
print("PB Studio AMD - Import & Funktionstest")
print("=" * 50)
print(f"Python: {sys.version}")
print(f"Zeitpunkt: {datetime.now()}")
print("=" * 50 + "\n")

results.append(f"Python: {sys.version}")
results.append(f"Zeitpunkt: {datetime.now()}")
results.append("")

# 1. Basis
print("\n--- BASIS ---")
test_import("numpy", "import numpy as np", 
            lambda: exec("import numpy as np; arr = np.array([1,2,3]); assert arr.sum() == 6"))

test_import("pillow", "from PIL import Image",
            lambda: exec("from PIL import Image; img = Image.new('RGB', (10,10))"))

# 2. AMD DirectML
print("\n--- AMD DIRECTML ---")
test_import("onnxruntime-genai", "import onnxruntime_genai as og")

# DirectML Provider prüfen
try:
    import onnxruntime as ort
    providers = ort.get_available_providers()
    if "DmlExecutionProvider" in providers:
        log("DirectML Provider: Verfügbar", "OK")
    else:
        log(f"DirectML Provider: NICHT gefunden (verfügbar: {providers})", "WARN")
except Exception as e:
    log(f"ONNX Runtime Provider Check: {e}", "WARN")

# 3. Audio
print("\n--- AUDIO ---")
test_import("librosa", "import librosa",
            lambda: exec("import librosa; assert hasattr(librosa, 'load')"))

test_import("soundfile", "import soundfile as sf")

# 4. Video
print("\n--- VIDEO ---")
test_import("opencv", "import cv2",
            lambda: exec("import cv2; assert cv2.__version__.startswith('4.')"))

test_import("scenedetect", "from scenedetect import detect, ContentDetector")

test_import("transformers", "from transformers import CLIPProcessor, CLIPModel")

# 5. Datenbank
print("\n--- DATENBANK ---")
test_import("chromadb", "import chromadb",
            lambda: exec("import chromadb; client = chromadb.Client()"))

# 6. FFmpeg
print("\n--- FFMPEG ---")
test_import("ffmpeg-python", "import ffmpeg")

# FFmpeg Binary prüfen
try:
    import subprocess
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    if "ffmpeg version" in result.stdout:
        # AMF Support prüfen
        if "h264_amf" in result.stdout or "amf" in result.stdout.lower():
            log("FFmpeg AMF: Verfügbar", "OK")
        else:
            log("FFmpeg: Installiert, aber AMF-Support nicht erkannt", "WARN")
    else:
        log("FFmpeg Binary: Nicht gefunden", "WARN")
except FileNotFoundError:
    log("FFmpeg Binary: Nicht im PATH", "WARN")
except Exception as e:
    log(f"FFmpeg Check: {e}", "WARN")

# 7. Utilities
print("\n--- UTILITIES ---")
test_import("tqdm", "from tqdm import tqdm")
test_import("click", "import click")
test_import("pydantic", "from pydantic import BaseModel")

# ============================================
# ZUSAMMENFASSUNG
# ============================================

print("\n" + "=" * 50)
print("ZUSAMMENFASSUNG")
print("=" * 50)

ok_count = sum(1 for r in results if "[OK]" in r)
fail_count = len(errors)
warn_count = sum(1 for r in results if "[WARN]" in r)

summary = f"""
Erfolgreich: {ok_count}
Warnungen:   {warn_count}
Fehler:      {fail_count}
"""
print(summary)

if errors:
    print("\nFEHLER DETAILS:")
    for e in errors:
        print(f"  - {e}")

# Report schreiben
with open(REPORT_FILE, "w", encoding="utf-8") as f:
    f.write("# PB Studio AMD - Import Report\n")
    f.write(f"# Erstellt: {datetime.now()}\n")
    f.write("=" * 50 + "\n\n")
    f.write("\n".join(results))
    f.write("\n\n" + "=" * 50 + "\n")
    f.write("ZUSAMMENFASSUNG\n")
    f.write(summary)
    if errors:
        f.write("\nFEHLER:\n")
        for e in errors:
            f.write(f"  - {e}\n")

print(f"\nReport gespeichert: {REPORT_FILE}")

# Exit Code
if fail_count > 0:
    print("\n❌ TEST FEHLGESCHLAGEN")
    sys.exit(1)
else:
    print("\n✅ ALLE TESTS BESTANDEN")
    sys.exit(0)
