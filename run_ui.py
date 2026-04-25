"""
PB Studio AMD - Main Launcher (Production Version)
Starts the C# WPF Production UI.
"""
import os
import subprocess
import sys
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Launcher")

def main():
    root = Path(__file__).parent.resolve()
    # Pfad zur Release-EXE (von uns gerade erfolgreich gebaut)
    ui_exe = root / "PBStudio.UI" / "bin" / "Release" / "net9.0-windows" / "PBStudio.UI.exe"
    
    if not ui_exe.exists():
        logger.error(f"UI Executable nicht gefunden unter: {ui_exe}")
        logger.info("Versuche Debug-Fallback...")
        ui_exe = root / "PBStudio.UI" / "bin" / "Debug" / "net9.0-windows" / "PBStudio.UI.exe"

    if not ui_exe.exists():
        logger.error("Keine PBStudio.UI.exe gefunden. Bitte zuerst build.ps1 ausfuehren.")
        sys.exit(1)

    logger.info(f"Starte PB Studio UI: {ui_exe}")
    try:
        # Startet das Frontend (das Frontend startet das Python-Backend selbst via PythonBridgeService)
        subprocess.Popen([str(ui_exe)], cwd=str(root))
        logger.info("PB Studio Prozess gestartet.")
    except Exception as e:
        logger.error(f"Fehler beim Starten der UI: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
