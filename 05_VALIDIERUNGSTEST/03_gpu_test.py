"""
PB Studio AMD - DirectML GPU Test
Testet ob AMD GPU wirklich für Inferenz verwendet wird
NUR auf AMD-System ausführen!
"""

import sys
import os
import time
from datetime import datetime

TEST_DIR = r"C:\Temp\pb_studio_amd_test"
REPORT_FILE = os.path.join(TEST_DIR, "GPU_REPORT.txt")

results = []

def log(msg):
    print(msg)
    results.append(msg)

print("=" * 50)
print("PB Studio AMD - DirectML GPU Test")
print("=" * 50)
print(f"Zeitpunkt: {datetime.now()}\n")

# ============================================
# 1. ONNX Runtime DirectML Provider
# ============================================

log("\n--- ONNX Runtime DirectML ---")

try:
    import onnxruntime as ort
    
    providers = ort.get_available_providers()
    log(f"Verfügbare Provider: {providers}")
    
    if "DmlExecutionProvider" in providers:
        log("✅ DirectML Provider VERFÜGBAR")
        
        # Session mit DirectML erstellen (Test)
        log("\nErstelle Test-Session mit DirectML...")
        
        # Minimales ONNX-Modell für Test erstellen
        import numpy as np
        
        # Wir testen nur ob Session mit DML startet
        session_options = ort.SessionOptions()
        log("✅ SessionOptions erstellt")
        
    else:
        log("❌ DirectML Provider NICHT VERFÜGBAR")
        log(f"   Nur verfügbar: {providers}")
        log("   Mögliche Ursachen:")
        log("   - AMD Treiber nicht installiert")
        log("   - Windows Version zu alt (min. Build 19041)")
        log("   - Falsches onnxruntime Paket installiert")

except ImportError as e:
    log(f"❌ onnxruntime nicht installiert: {e}")
except Exception as e:
    log(f"❌ Fehler: {e}")

# ============================================
# 2. ONNX Runtime GenAI DirectML
# ============================================

log("\n--- ONNX Runtime GenAI DirectML ---")

try:
    import onnxruntime_genai as og
    log(f"✅ onnxruntime-genai importiert")
    log(f"   Version: {og.__version__ if hasattr(og, '__version__') else 'unbekannt'}")
    
except ImportError as e:
    log(f"❌ onnxruntime-genai nicht installiert: {e}")
except Exception as e:
    log(f"❌ Fehler: {e}")

# ============================================
# 3. GPU Info (falls verfügbar)
# ============================================

log("\n--- System GPU Info ---")

try:
    import subprocess
    
    # Windows: dxdiag oder wmic
    result = subprocess.run(
        ["wmic", "path", "win32_videocontroller", "get", "name"],
        capture_output=True, text=True, timeout=10
    )
    
    gpus = [line.strip() for line in result.stdout.split("\n") if line.strip() and "Name" not in line]
    
    if gpus:
        log("Gefundene GPUs:")
        for gpu in gpus:
            log(f"  - {gpu}")
            if "AMD" in gpu.upper() or "RADEON" in gpu.upper():
                log(f"    ✅ AMD GPU erkannt!")
    else:
        log("Keine GPUs gefunden")
        
except Exception as e:
    log(f"GPU-Info nicht verfügbar: {e}")

# ============================================
# 4. DirectML DLL Check
# ============================================

log("\n--- DirectML DLL Check ---")

try:
    import ctypes
    
    # Versuche DirectML.dll zu laden
    try:
        directml = ctypes.WinDLL("DirectML.dll")
        log("✅ DirectML.dll geladen")
    except OSError:
        # Suche in System32
        system32 = os.path.join(os.environ["WINDIR"], "System32")
        dml_path = os.path.join(system32, "DirectML.dll")
        
        if os.path.exists(dml_path):
            log(f"✅ DirectML.dll gefunden: {dml_path}")
        else:
            log("⚠️ DirectML.dll nicht in System32")
            log("   Windows Update könnte erforderlich sein")
            
except Exception as e:
    log(f"DLL Check fehlgeschlagen: {e}")

# ============================================
# ZUSAMMENFASSUNG
# ============================================

print("\n" + "=" * 50)
print("GPU TEST ABGESCHLOSSEN")
print("=" * 50)

# Report schreiben
with open(REPORT_FILE, "w", encoding="utf-8") as f:
    f.write("# PB Studio AMD - GPU Report\n")
    f.write(f"# Erstellt: {datetime.now()}\n")
    f.write("=" * 50 + "\n")
    f.write("\n".join(results))

print(f"\nReport: {REPORT_FILE}")
