"""
Backend-Konfiguration für PB Studio AMD FastAPI Server.

Alle Pfade und Einstellungen für den lokalen HTTP-Server.
"""

import sys
from pathlib import Path
from pydantic_settings import BaseSettings


# src/ Ordner zum Python-Path hinzufügen
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


class ServerConfig(BaseSettings):
    """Server-Konfiguration via Environment oder .env Datei."""

    host: str = "127.0.0.1"
    port: int = 8765
    debug: bool = False
    log_level: str = "info"

    # Pfade
    project_dir: Path = Path.home() / "Documents" / "PBStudio"
    ffmpeg_path: Path = Path(__file__).resolve().parent.parent / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
    ffprobe_path: Path = Path(__file__).resolve().parent.parent / "tools" / "ffmpeg" / "bin" / "ffprobe.exe"

    # GPU
    gpu_timeout_seconds: int = 300

    # Timeouts
    analysis_timeout: int = 120
    render_timeout: int = 600
    stem_timeout: int = 300

    model_config = {"env_prefix": "PBSTUDIO_", "env_file": ".env"}


config = ServerConfig()
