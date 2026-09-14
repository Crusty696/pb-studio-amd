import copy
import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from pb_studio.storage.recovery_barrier import recovery_write_operation
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from pb_studio.runtime_contract import ffmpeg_path

logger = logging.getLogger(__name__)

# Projekt-Root berechnen (2 Ebenen hoch von diesem Modul)
_PROJECT_ROOT = Path(__file__).parent.parent.parent

# FR-005: Klassifikation der Schlüssel-Wirkungsbereiche
KEY_CLASSIFICATION: Dict[str, str] = {
    "ai.task_overrides": "next_job",
    "ai.task_provider_overrides": "next_job",
    "ai.default_mode": "next_job",
    "ai.provider": "next_job",
    "ai.task_preferences": "next_job",
    "ui": "live",
    "app_name": "restart_required",
    "version": "restart_required",
    "paths.db_path": "restart_required",
    "paths.lhm_lib": "restart_required",
    "paths.ffmpeg_bin": "restart_required",
    "paths.ffprobe_bin": "restart_required",
    "paths.temp_dir": "next_job",
    "hardware.gpu_backend": "restart_required",
    "hardware.directml_adapter_policy": "restart_required",
    "hardware.vram_limit_mb": "next_job",
}

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

    _file_digest: str = ""
    _revision: int = 1
    _subscribers: List[Callable[[Dict[str, Any], Dict[str, Tuple[Any, Any]], int], None]] = []
    _watcher_thread: Optional[threading.Thread] = None
    _stop_event: threading.Event = threading.Event()
    _poll_interval: float = 1.0
    _last_reload_time: Optional[float] = None
    _last_error: Optional[str] = None
    _last_error_digest: Optional[str] = None
    _last_error_time: Optional[float] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config(*args, **kwargs)
        elif args or kwargs:
            cls._instance._load_config(*args, **kwargs)
        return cls._instance

    @classmethod
    def reset_instance_for_tests(cls) -> None:
        """Setzt das Singleton für Tests sauber zurück und stoppt laufende Watcher."""
        with cls._config_lock:
            if cls._instance is not None:
                try:
                    cls._instance.stop_watcher()
                except Exception:
                    pass
            cls._instance = None

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

    @staticmethod
    def _compute_diff(old_dict: dict, new_dict: dict, prefix: str = "") -> Dict[str, Tuple[Any, Any]]:
        """Ermittelt geänderte Keys zwischen zwei Konfigurationen."""
        diff: Dict[str, Tuple[Any, Any]] = {}
        all_keys = set(old_dict.keys()) | set(new_dict.keys())
        for k in all_keys:
            full_key = f"{prefix}.{k}" if prefix else k
            old_val = old_dict.get(k)
            new_val = new_dict.get(k)
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                diff.update(ConfigManager._compute_diff(old_val, new_val, prefix=full_key))
            elif old_val != new_val:
                diff[full_key] = (old_val, new_val)
        return diff

    @staticmethod
    def validate_config_dict(data: Any) -> Tuple[bool, str]:
        """FR-002: Validiert vollständiges JSON-Objekt und unterstützte Key-Typen vor Publish."""
        if not isinstance(data, dict):
            return False, "Konfiguration muss ein JSON-Objekt sein"

        known_sections = {
            "app_name": str,
            "version": str,
            "paths": dict,
            "hardware": dict,
            "ai": dict,
            "ui": dict,
        }
        for section, expected_type in known_sections.items():
            if section in data and not isinstance(data[section], expected_type):
                return False, f"Sektion '{section}' muss Typ {expected_type.__name__} sein"

        ai_data = data.get("ai")
        if isinstance(ai_data, dict):
            if "task_overrides" in ai_data and not isinstance(ai_data["task_overrides"], dict):
                return False, "ai.task_overrides muss ein Dictionary sein"
            if "task_provider_overrides" in ai_data and not isinstance(ai_data["task_provider_overrides"], dict):
                return False, "ai.task_provider_overrides muss ein Dictionary sein"
            if "task_preferences" in ai_data and not isinstance(ai_data["task_preferences"], dict):
                return False, "ai.task_preferences muss ein Dictionary sein"
            if "default_mode" in ai_data and not isinstance(ai_data["default_mode"], str):
                return False, "ai.default_mode muss ein String sein"
            if "provider" in ai_data and not isinstance(ai_data["provider"], str):
                return False, "ai.provider muss ein String sein"

        return True, ""

    def _load_config(self, *args, **kwargs):
        with self._config_lock:
            config_file = kwargs.get("config_file") or (args[0] if args else None)
            if config_file is not None:
                self.config_file = Path(config_file)
            elif not hasattr(self, "config_file") or self.config_file is None:
                self.config_file = _PROJECT_ROOT / "config.json"

            self._subscribers = []
            self._watcher_thread = None
            self._stop_event = threading.Event()
            self._file_digest = ""
            self._revision = 1
            self._last_reload_time = None
            self._last_error = None
            self._last_error_digest = None
            self._last_error_time = None

            if self.config_file.exists():
                try:
                    content = self.config_file.read_bytes()
                    self._file_digest = hashlib.sha256(content).hexdigest()
                    user_config = json.loads(content.decode("utf-8"))
                    valid, err = self.validate_config_dict(user_config)
                    if valid:
                        self._config = self._deep_merge(self.DEFAULTS, user_config)
                    else:
                        logger.error("Config initial load rejected (%s). Using defaults.", err)
                        self._config = copy.deepcopy(self.DEFAULTS)
                except Exception as e:
                    logger.error(f"Config load failed: {e}. Using defaults.")
                    self._config = copy.deepcopy(self.DEFAULTS)
            else:
                self._config = copy.deepcopy(self.DEFAULTS)
                self.save_config()

    def reload_if_changed(
        self,
        raw_content: Optional[bytes] = None,
    ) -> Tuple[bool, Dict[str, Tuple[Any, Any]]]:
        """FR-001/FR-002: Erkennt externe Änderungen und validiert vor atomarem Publish."""
        try:
            if raw_content is None:
                if not self.config_file.exists():
                    return False, {}
                raw_content = self.config_file.read_bytes()
        except OSError as exc:
            logger.debug("Config-Datei konnte nicht gelesen werden: %s", exc)
            return False, {}

        new_digest = hashlib.sha256(raw_content).hexdigest()
        with self._config_lock:
            if new_digest == self._file_digest:
                return False, {}

        # 1. JSON Parse
        try:
            parsed = json.loads(raw_content.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            with self._config_lock:
                if new_digest != self._last_error_digest:
                    logger.warning(
                        "Config Hot-Reload: Ungültiges JSON in %s abgelehnt (%s). Behalte letzten gültigen Stand.",
                        self.config_file.name,
                        exc,
                    )
                    self._last_error = f"JSON-Syntaxfehler: {exc}"
                    self._last_error_digest = new_digest
                    self._last_error_time = time.time()
            return False, {}

        # 2. Schema- / Typvalidierung
        valid, err_msg = self.validate_config_dict(parsed)
        if not valid:
            with self._config_lock:
                if new_digest != self._last_error_digest:
                    logger.warning(
                        "Config Hot-Reload: Ungültige Struktur in %s abgelehnt (%s). Behalte letzten gültigen Stand.",
                        self.config_file.name,
                        err_msg,
                    )
                    self._last_error = err_msg
                    self._last_error_digest = new_digest
                    self._last_error_time = time.time()
            return False, {}

        # 3. Gültiger Snapshot: Mergen & atomar austauschen
        new_config = self._deep_merge(self.DEFAULTS, parsed)
        callbacks = []
        with self._config_lock:
            diff = self._compute_diff(self._config, new_config)
            self._config = new_config
            self._file_digest = new_digest
            self._revision += 1
            self._last_reload_time = time.time()
            self._last_error = None
            self._last_error_digest = None
            self._last_error_time = None
            callbacks = list(self._subscribers)

        logger.info(
            "Config Hot-Reload: Revision %d aktiv, %d Keys geändert: %s",
            self._revision,
            len(diff),
            list(diff.keys()),
        )

        for cb in callbacks:
            try:
                cb(new_config, diff, self._revision)
            except Exception as cb_exc:
                logger.warning("Config Subscriber-Fehler: %s", cb_exc)

        return True, diff

    def subscribe(
        self,
        callback: Callable[[Dict[str, Any], Dict[str, Tuple[Any, Any]], int], None],
    ) -> None:
        """Registriert einen Callback(new_config, diff, revision)."""
        with self._config_lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(
        self,
        callback: Callable[[Dict[str, Any], Dict[str, Tuple[Any, Any]], int], None],
    ) -> None:
        with self._config_lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def start_watcher(self, poll_interval: float = 1.0) -> None:
        """TR-001: Startet den Hintergrund-Poller für externe Änderungen an config.json."""
        with self._config_lock:
            if self._watcher_thread is not None and self._watcher_thread.is_alive():
                return
            self._poll_interval = max(float(poll_interval), 0.1)
            self._stop_event.clear()
            self._watcher_thread = threading.Thread(
                target=self._watcher_loop,
                name="pb-config-watcher",
                daemon=True,
            )
            self._watcher_thread.start()
            logger.info("ConfigManager: Watcher gestartet (Intervall=%.1fs)", self._poll_interval)

    def stop_watcher(self, timeout: float = 2.0) -> None:
        """TR-001: Stoppt den Hintergrund-Poller sauber."""
        thread = None
        with self._config_lock:
            self._stop_event.set()
            thread = self._watcher_thread
            self._watcher_thread = None

        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
            logger.info("ConfigManager: Watcher gestoppt")

    def _watcher_loop(self) -> None:
        candidate_digest: Optional[str] = None
        candidate_count = 0
        while not self._stop_event.wait(self._poll_interval):
            try:
                if not self.config_file.exists():
                    candidate_digest = None
                    candidate_count = 0
                    continue

                content = self.config_file.read_bytes()
                digest = hashlib.sha256(content).hexdigest()

                with self._config_lock:
                    current_digest = self._file_digest

                if digest == current_digest:
                    candidate_digest = None
                    candidate_count = 0
                    continue

                # Stabilisierung über 2 aufeinanderfolgende Abtastungen
                if digest == candidate_digest:
                    candidate_count += 1
                else:
                    candidate_digest = digest
                    candidate_count = 1

                if candidate_count >= 2:
                    self.reload_if_changed(raw_content=content)
                    candidate_digest = None
                    candidate_count = 0
            except Exception as e:
                logger.debug("ConfigManager: Watcher-Abtastung fehlgeschlagen: %s", e)

    def get_status(self) -> Dict[str, Any]:
        """FR-005: Liefert Status, Revision und Key-Klassifikation."""
        with self._config_lock:
            return {
                "revision": self._revision,
                "file_digest": self._file_digest,
                "watcher_running": bool(
                    self._watcher_thread is not None and self._watcher_thread.is_alive()
                ),
                "last_reload_time": self._last_reload_time,
                "last_error": self._last_error,
                "last_error_time": self._last_error_time,
                "key_classification": KEY_CLASSIFICATION,
            }

    @recovery_write_operation("config")
    def save_config(self, force: bool = True):
        temp_path: Path | None = None
        try:
            with self._config_lock:
                if not force and self.config_file.exists():
                    current_disk = self.config_file.read_bytes()
                    current_digest = hashlib.sha256(current_disk).hexdigest()
                    if self._file_digest and current_digest != self._file_digest:
                        raise RuntimeError(
                            "Konflikt: config.json wurde extern geändert seit dem letzten Stand."
                        )

                descriptor, raw_temp_path = tempfile.mkstemp(
                    prefix=f".{self.config_file.name}.",
                    suffix=".tmp",
                    dir=str(self.config_file.parent),
                )
                temp_path = Path(raw_temp_path)
                serialized = json.dumps(
                    self._config,
                    indent=4,
                    ensure_ascii=False,
                ) + "\n"
                encoded = serialized.encode("utf-8")
                with os.fdopen(
                    descriptor,
                    "wb",
                ) as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, self.config_file)
                temp_path = None
                self._file_digest = hashlib.sha256(encoded).hexdigest()
                self._revision += 1
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
