import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Projekt-Root berechnen (2 Ebenen hoch von diesem Modul)
_PROJECT_ROOT = Path(__file__).parent.parent.parent

class ConfigManager:
    _instance = None
    _config: Dict[str, Any] = {}
    
    # Defaults tailored for AMD Setup
    DEFAULTS = {
        "app_name": "PB Studio (AMD Premium)",
        "version": "1.0.0-amd",
        "paths": {
            "ffmpeg_bin": "./tools/ffmpeg/bin/ffmpeg.exe",
            "lhm_lib": "./tools/LibreHardwareMonitor/LibreHardwareMonitorLib.dll",
            "temp_dir": "./temp",
            "db_path": "./data/pb_studio.db"
        },
        "hardware": {
            "gpu_backend": "directml",
            "vram_limit_mb": 4096,
            "enable_monitoring": True
        },
        "ai": {
            "vision_model": "moondream2_fp16",
            "audio_backend": "demucs_dml",
            "parallel_tasks": False
        },
        "ui": {
            "theme": "dark_red",
            "scale_factor": 1.0
        }
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Rekursiver Dict-Merge: override ueberschreibt base, behaelt fehlende Keys."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _load_config(self):
        # Config-Datei relativ zum Projekt-Root
        self.config_file = _PROJECT_ROOT / "config.json"
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    user_config = json.load(f)
                    # Deep merge: User-Config ueberschreibt Defaults, fehlende Keys bleiben
                    self._config = self._deep_merge(self.DEFAULTS, user_config)
            except Exception as e:
                logger.error(f"Config load failed: {e}. Using defaults.")
                self._config = self.DEFAULTS.copy()
        else:
            self._config = self.DEFAULTS.copy()
            self.save_config()

    def save_config(self):
        try:
            with open(self.config_file, "w") as f:
                json.dump(self._config, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def resolve_path(self, relative_path: str) -> Path:
        """Resolve relative path to absolute based on project root.
        Absolute Pfade werden unveraendert zurueckgegeben."""
        if not relative_path:
            return _PROJECT_ROOT
        p = Path(relative_path)
        if p.is_absolute():
            return p.resolve()
        # Entferne fuehrende ./ aber NICHT fuehrende /
        cleaned = relative_path
        while cleaned.startswith("./") or cleaned.startswith(".\\"):
            cleaned = cleaned[2:]
        return (_PROJECT_ROOT / cleaned).resolve()

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        self._config[key] = value
        self.save_config()

    # Typed helpers
    @property
    def ffmpeg_path(self) -> str:
        path = self._config["paths"]["ffmpeg_bin"]
        return str(self.resolve_path(path))

    @property
    def lhm_path(self) -> str:
        path = self._config["paths"]["lhm_lib"]
        return str(self.resolve_path(path))
