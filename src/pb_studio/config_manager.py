import copy
import json
import logging
import os
import tempfile
import threading
from pb_studio.storage.recovery_barrier import recovery_write_operation
from pathlib import Path
from typing import Any, Dict

from pb_studio.runtime_contract import ffmpeg_path

logger = logging.getLogger(__name__)

# Projekt-Root berechnen (2 Ebenen hoch von diesem Modul)
_PROJECT_ROOT = Path(__file__).parent.parent.parent

class ConfigManager:
    _instance = None
    _config: Dict[str, Any] = {}
    _config_lock = threading.RLock()
    
    # Defaults tailored for AMD Setup
    DEFAULTS = {
        "app_name": "PB Studio (AMD Premium)",
        "version": "1.0.0-amd",
        "paths": {
            "ffmpeg_bin": "./tools/ffmpeg/bin/ffmpeg.exe",
            "ffprobe_bin": "./tools/ffmpeg/bin/ffprobe.exe",
            "lhm_lib": "./tools/LibreHardwareMonitor/LibreHardwareMonitorLib.dll",
            "temp_dir": "./temp",
            "db_path": "./data/pb_studio.db"
        },
        # Audit 2026-08-06 (T4.6): Fuenf wirkungslose Schluessel entfernt —
        # `hardware.enable_monitoring`, `ai.audio_backend`, `ai.parallel_tasks`,
        # `ui.theme`, `ui.scale_factor`. Repo-weit verifiziert ohne einen
        # einzigen Leser ausserhalb dieser DEFAULTS: wer sie in config.json
        # setzte, aenderte nichts. Das Stem-Backend entscheidet der
        # StemSeparator selbst, Theme und Skalierung fuehrt das WPF-Frontend.
        # Ein Schalter, der nichts schaltet, ist schlimmer als kein Schalter.
        # Bestehende config.json-Dateien behalten die Keys — sie werden nur
        # nicht mehr angelegt und weiterhin ignoriert.
        "hardware": {
            "gpu_backend": "directml",
            "directml_adapter_policy": "highest_vram_amd",
            "vram_limit_mb": 0,   # 0 = auto-detect (VRAMBudgetManager reads actual capacity)
        },
        # Audit 2026-08-07: `ai.vision_model` ebenfalls entfernt. Er wurde von
        # models_router geschrieben, aber repo-weit nie gelesen — die
        # Vision-Auswahl laeuft komplett ueber task_overrides/task_preferences.
        # Gleiche Kategorie wie die fuenf Schluessel aus T4.6.
        "ai": {
            "task_overrides": {},
            "task_provider_overrides": {}
        },
        "ui": {}
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
        with self._config_lock:
            # Config-Datei relativ zum Projekt-Root
            self.config_file = _PROJECT_ROOT / "config.json"
            if self.config_file.exists():
                try:
                    with self.config_file.open("r", encoding="utf-8") as f:
                        user_config = json.load(f)
                        # Deep merge: User-Config ueberschreibt Defaults, fehlende Keys bleiben
                        self._config = self._deep_merge(self.DEFAULTS, user_config)
                except Exception as e:
                    logger.error(f"Config load failed: {e}. Using defaults.")
                    self._config = copy.deepcopy(self.DEFAULTS)
            else:
                self._config = copy.deepcopy(self.DEFAULTS)
                self.save_config()

    @recovery_write_operation("config")
    def save_config(self):
        temp_path: Path | None = None
        try:
            with self._config_lock:
                descriptor, raw_temp_path = tempfile.mkstemp(
                    prefix=f".{self.config_file.name}.",
                    suffix=".tmp",
                    dir=str(self.config_file.parent),
                )
                temp_path = Path(raw_temp_path)
                with os.fdopen(
                    descriptor,
                    "w",
                    encoding="utf-8",
                    newline="\n",
                ) as handle:
                    json.dump(
                        self._config,
                        handle,
                        indent=4,
                        ensure_ascii=False,
                    )
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, self.config_file)
                temp_path = None
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            raise
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning(
                        "Temporary config file could not be removed: %s",
                        temp_path.name,
                    )

    def resolve_path(self, relative_path: Any) -> Path:
        """Resolve relative path to absolute based on project root.
        Absolute Pfade werden unveraendert zurueckgegeben."""
        # BUG-081 FIX: Sicherer Umgang mit Path-Objekten oder leeren Pfaden
        if relative_path is None:
            return _PROJECT_ROOT
            
        p = Path(relative_path)
        if p.is_absolute():
            return p.resolve()
        # Entferne fuehrende ./ aber NICHT fuehrende /
        cleaned = str(relative_path)
        while cleaned.startswith("./") or cleaned.startswith(".\\"):
            cleaned = cleaned[2:]
        return (_PROJECT_ROOT / cleaned).resolve()

    def get(self, key: str, default=None):
        with self._config_lock:
            return copy.deepcopy(self._config.get(key, default))

    def set(self, key: str, value: Any):
        with self._config_lock:
            self._config[key] = copy.deepcopy(value)
            self.save_config()

    # Typed helpers
    @property
    def ffmpeg_path(self) -> str:
        configured = self.resolve_path(self._config["paths"]["ffmpeg_bin"])
        canonical = ffmpeg_path()
        if configured != canonical:
            logger.warning(
                "Ignoring non-canonical ffmpeg_bin %s; using %s",
                configured,
                canonical,
            )
        return str(canonical)

    @property
    def ffprobe_path(self) -> str:
        from pb_studio.runtime_contract import ffprobe_path

        configured = self.resolve_path(self._config["paths"]["ffprobe_bin"])
        canonical = ffprobe_path()
        if configured != canonical:
            logger.warning(
                "Ignoring non-canonical ffprobe_bin %s; using %s",
                configured,
                canonical,
            )
        return str(canonical)

    @property
    def lhm_path(self) -> str:
        path = self._config["paths"]["lhm_lib"]
        return str(self.resolve_path(path))
