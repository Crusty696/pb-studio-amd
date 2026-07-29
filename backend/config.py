"""
Backend-Konfiguration für PB Studio AMD FastAPI Server.

Alle Pfade und Einstellungen für den lokalen HTTP-Server.
"""

import os
import sys
import uuid
import ctypes
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings


# src/ Ordner zum Python-Path hinzufügen
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from pb_studio.runtime_contract import ffmpeg_path, ffprobe_path


def _default_documents_dir() -> Path:
    """Ermittelt den echten Benutzer-Dokumente-Ordner robust auf Windows.

    Vermeidet lokalisierungsbedingte Fehlannahmen wie ~/Documents vs ~/Dokumente.
    Fallback bleibt plattformneutral und env-overridebar via PBSTUDIO_PROJECT_DIR.
    """
    env_override = os.getenv("PBSTUDIO_PROJECT_DIR")
    if env_override:
        return Path(env_override).expanduser().resolve()

    if os.name == "nt":
        try:
            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", ctypes.c_uint32),
                    ("Data2", ctypes.c_uint16),
                    ("Data3", ctypes.c_uint16),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            guid_bytes = uuid.UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7").bytes_le
            documents_guid = GUID.from_buffer_copy(guid_bytes)
            documents_ptr = ctypes.c_wchar_p()
            result = ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(documents_guid),
                0,
                None,
                ctypes.byref(documents_ptr),
            )
            if result == 0 and documents_ptr.value:
                path = Path(documents_ptr.value)
                # BUG-082 FIX: COM-Speicher freigeben
                ctypes.windll.ole32.CoTaskMemFree(documents_ptr)
                return path
        except Exception:
            pass

        userprofile = Path(os.environ.get("USERPROFILE", str(Path.home())))
        for candidate in (userprofile / "Documents", userprofile / "Dokumente"):
            if candidate.exists():
                return candidate

    return Path.home() / "Documents"


class ServerConfig(BaseSettings):
    """Server-Konfiguration via Environment oder .env Datei."""

    host: str = "127.0.0.1"
    port: int = 8765
    debug: bool = False
    log_level: str = "info"

    # Pfade
    project_dir: Path = _default_documents_dir() / "PBStudio"
    ffmpeg_path: Path = ffmpeg_path()
    ffprobe_path: Path = ffprobe_path()

    # GPU
    gpu_timeout_seconds: int = 300

    # Timeouts
    analysis_timeout: int = 120
    render_timeout: int = 600
    # B3-Fix (2026-05-19): 300s war zu kurz fuer 90min DJ-Mixe — Demucs hat
    # 2x in einem Tag mit Timeout-Error abgebrochen (log 14:11 + 16:42).
    # 900s (15min) deckt typische 1-2h Sets ab. Override via PBSTUDIO_STEM_TIMEOUT.
    stem_timeout: int = 900

    model_config = {"env_prefix": "PBSTUDIO_", "env_file": ".env"}

    @field_validator("ffmpeg_path")
    @classmethod
    def require_canonical_ffmpeg(cls, value: Path) -> Path:
        canonical = ffmpeg_path()
        if value.resolve() != canonical:
            raise ValueError(
                f"PB Studio requires canonical FFmpeg runtime {canonical}"
            )
        return canonical

    @field_validator("ffprobe_path")
    @classmethod
    def require_canonical_ffprobe(cls, value: Path) -> Path:
        canonical = ffprobe_path()
        if value.resolve() != canonical:
            raise ValueError(
                f"PB Studio requires canonical FFprobe runtime {canonical}"
            )
        return canonical


config = ServerConfig()
