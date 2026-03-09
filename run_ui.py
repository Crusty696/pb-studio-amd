"""
PB Studio AMD - Main UI Launcher

Starts the PyQt6 GUI application with all workers registered.
"""

import os
import sys
import logging
from pathlib import Path

# src/ zum Python-Pfad hinzufuegen (konsistent mit PYTHONPATH=src)
_SRC_DIR = str(Path(__file__).parent / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from PyQt6.QtWidgets import QApplication
from pb_studio.ui.main_window import MainWindow
from pb_studio.utils.logging_setup import setup_logging

# FFmpeg zum PATH hinzufuegen (liegt unter tools/ffmpeg/bin/)
_PROJECT_ROOT = Path(__file__).parent
_FFMPEG_BIN = _PROJECT_ROOT / "tools" / "ffmpeg" / "bin"
if _FFMPEG_BIN.exists() and str(_FFMPEG_BIN) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(_FFMPEG_BIN) + os.pathsep + os.environ.get("PATH", "")


def main():
    setup_logging("gui_run")
    logger = logging.getLogger("Launcher")

    # Environment Check
    try:
        import verify_env_v2
        if not verify_env_v2.verify():
            logger.critical("Environment Check Failed. See console/logs.")
            # In Dev mode we might want to exit, but let's try to continue with warning for now
            # or strictly exit to force user to read it.
            # sys.exit(1)
    except ImportError:
        logger.warning("verify_env_v2 module not found. Skipping check.")

    # Initialize Worker Registry
    try:
        from pb_studio.workers import setup_worker_registry
        registry = setup_worker_registry()
        logger.info(f"Worker registry initialized: {len(registry.list_workers())} workers registered")
    except Exception as e:
        logger.error(f"Failed to initialize worker registry: {e}")
        # Continue anyway - workers will be loaded on-demand

    app = QApplication(sys.argv)
    
    # Apply qt-material Theme (Pro Tool Look)
    try:
        from qt_material import apply_stylesheet
        # Options: dark_teal.xml, dark_cyan.xml, dark_red.xml, dark_pink.xml, dark_purple.xml
        # We start with 'dark_teal.xml' for that "Hacker/Pro" vibe
        apply_stylesheet(app, theme='dark_teal.xml', css_file=str(_PROJECT_ROOT / 'src' / 'pb_studio' / 'ui' / 'custom_overrides.css'))
        logger.info("Applied qt-material theme: dark_teal.xml")
    except Exception as e:
        logger.warning(f"Failed to apply qt-material theme: {e}. Falling back to Fusion.")
        app.setStyle("Fusion")

    logger.info("Initializing Main Window...")
    try:
        window = MainWindow()
        window.show()

        logger.info("UI Started. Event loop running...")
        sys.exit(app.exec())
    except Exception as e:
        logger.critical(f"UI Crash: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
