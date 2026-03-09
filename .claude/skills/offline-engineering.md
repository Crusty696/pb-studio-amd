# Offline Engineering Skill

## Trigger
Aktiviere diesen Skill automatisch bei:
- "Offline", "Lokal", "Ohne Internet", "Download", "Bundle", "Asset"
- Arbeit an Model-Loading, Asset-Management, Setup/Installer
- Fragen zu Internet-Abhängigkeiten, lokalen Ressourcen

## Cross-References
- → `ai-inference.md` (Lokale ONNX Models)
- → `audio-engineering.md` (Lokale Audio-Verarbeitung)
- → `video-engineering.md` (Lokale Video-Verarbeitung)
- → `data-persistence.md` (Lokale Datenbank)

---

## Core Principles
| Regel | Beschreibung |
|-------|--------------|
| **No Phoning Home** | 100% Offline nach Installation |
| **Local Assets** | Alle Ressourcen lokal gebündelt |
| **Explicit Downloads** | Downloads nur während Setup, nie Runtime |

---

## 1. Asset Management Architecture

```
project/
├── models/                    # AI Models (ONNX)
│   ├── moondream/
│   │   ├── vision.onnx
│   │   ├── text.onnx
│   │   └── config.json
│   ├── demucs/
│   │   └── htdemucs.onnx
│   └── clip/
│       ├── vision.onnx
│       └── text.onnx
├── assets/                    # Statische Assets
│   ├── icons/
│   ├── fonts/
│   └── templates/
├── data/                      # Runtime Data
│   ├── pb_studio.db
│   └── vectors.faiss
└── config/                    # Konfiguration
    └── settings.json
```

---

## 2. Model Asset Manager

```python
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import json
import hashlib
import logging

logger = logging.getLogger(__name__)

@dataclass
class ModelAsset:
    name: str
    path: Path
    version: str
    size_mb: float
    checksum: str
    required: bool = True

class AssetManager:
    """Verwaltet lokale Assets mit Integritätsprüfung."""
    
    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path("models")
        self.manifest_path = self.base_dir / "manifest.json"
        self._manifest: dict[str, ModelAsset] = {}
        
        self._load_manifest()
    
    def _load_manifest(self):
        """Lädt Asset-Manifest."""
        if self.manifest_path.exists():
            with open(self.manifest_path) as f:
                data = json.load(f)
                for name, info in data.get("assets", {}).items():
                    self._manifest[name] = ModelAsset(
                        name=name,
                        path=self.base_dir / info["path"],
                        version=info.get("version", "1.0"),
                        size_mb=info.get("size_mb", 0),
                        checksum=info.get("checksum", ""),
                        required=info.get("required", True)
                    )
    
    def get_asset(self, name: str) -> Optional[Path]:
        """Holt Asset-Pfad wenn verfügbar."""
        asset = self._manifest.get(name)
        
        if asset is None:
            logger.warning(f"Asset nicht im Manifest: {name}")
            return None
        
        if not asset.path.exists():
            logger.error(f"Asset fehlt: {asset.path}")
            return None
        
        return asset.path
    
    def verify_asset(self, name: str) -> tuple[bool, str]:
        """Verifiziert Asset-Integrität."""
        asset = self._manifest.get(name)
        
        if asset is None:
            return False, "Asset nicht im Manifest"
        
        if not asset.path.exists():
            return False, f"Datei fehlt: {asset.path}"
        
        # Größencheck
        actual_size = asset.path.stat().st_size / (1024 * 1024)
        if asset.size_mb > 0 and abs(actual_size - asset.size_mb) > 1:
            return False, f"Größe falsch: {actual_size:.1f}MB statt {asset.size_mb:.1f}MB"
        
        # Checksum (optional, kann langsam sein)
        if asset.checksum:
            actual_checksum = self._calculate_checksum(asset.path)
            if actual_checksum != asset.checksum:
                return False, "Checksum stimmt nicht"
        
        return True, "OK"
    
    def verify_all(self) -> dict[str, tuple[bool, str]]:
        """Verifiziert alle Assets."""
        results = {}
        for name in self._manifest:
            results[name] = self.verify_asset(name)
        return results
    
    def get_missing_assets(self) -> list[ModelAsset]:
        """Gibt Liste fehlender Assets zurück."""
        missing = []
        for name, asset in self._manifest.items():
            if asset.required and not asset.path.exists():
                missing.append(asset)
        return missing
    
    def _calculate_checksum(self, path: Path, algorithm: str = "sha256") -> str:
        """Berechnet Datei-Checksum."""
        hasher = hashlib.new(algorithm)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def create_manifest(self, assets: list[dict]) -> None:
        """Erstellt neues Manifest."""
        manifest = {"assets": {}}
        
        for asset_info in assets:
            name = asset_info["name"]
            path = self.base_dir / asset_info["path"]
            
            if path.exists():
                manifest["assets"][name] = {
                    "path": asset_info["path"],
                    "version": asset_info.get("version", "1.0"),
                    "size_mb": round(path.stat().st_size / (1024 * 1024), 2),
                    "checksum": self._calculate_checksum(path),
                    "required": asset_info.get("required", True)
                }
        
        with open(self.manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"Manifest erstellt: {self.manifest_path}")
```

---

## 3. Offline-Safe Model Loading

```python
import onnxruntime as ort
from pathlib import Path
from typing import Optional

class OfflineModelLoader:
    """Lädt Models strikt offline."""
    
    def __init__(self, models_dir: Path = None):
        self.models_dir = models_dir or Path("models")
        self.asset_manager = AssetManager(self.models_dir)
        self._sessions: dict[str, ort.InferenceSession] = {}
    
    def load(self, model_name: str) -> ort.InferenceSession:
        """Lädt Model aus lokalem Pfad."""
        
        # Aus Cache
        if model_name in self._sessions:
            return self._sessions[model_name]
        
        # Pfad holen
        model_path = self.asset_manager.get_asset(model_name)
        
        if model_path is None:
            raise FileNotFoundError(
                f"Model '{model_name}' nicht gefunden. "
                f"Bitte führen Sie das Setup aus."
            )
        
        # Integrität prüfen
        valid, message = self.asset_manager.verify_asset(model_name)
        if not valid:
            raise ValueError(f"Model '{model_name}' beschädigt: {message}")
        
        # Laden
        from .ai_inference import get_optimal_providers
        
        session = ort.InferenceSession(
            str(model_path),
            providers=get_optimal_providers()
        )
        
        self._sessions[model_name] = session
        logger.info(f"Model geladen: {model_name} auf {session.get_providers()}")
        
        return session
    
    def is_available(self, model_name: str) -> bool:
        """Prüft ob Model offline verfügbar ist."""
        path = self.asset_manager.get_asset(model_name)
        return path is not None and path.exists()
    
    def get_missing_models(self) -> list[str]:
        """Gibt fehlende Models zurück."""
        return [a.name for a in self.asset_manager.get_missing_assets()]
    
    def unload(self, model_name: str):
        """Entlädt Model aus Cache."""
        if model_name in self._sessions:
            del self._sessions[model_name]
            logger.info(f"Model entladen: {model_name}")
    
    def unload_all(self):
        """Entlädt alle Models."""
        self._sessions.clear()
        logger.info("Alle Models entladen")


# ❌ FALSCH - Downloads zur Runtime
def bad_load_model():
    from transformers import AutoModel
    model = AutoModel.from_pretrained("openai/clip")  # INTERNET!

# ✅ RICHTIG - Strikt offline
def good_load_model():
    loader = OfflineModelLoader()
    session = loader.load("clip-vision")  # Nur lokal
```

---

## 4. Setup/Download Phase

```python
import requests
from pathlib import Path
from tqdm import tqdm
from typing import Callable, Optional
import hashlib

@dataclass
class DownloadTask:
    name: str
    url: str
    target_path: Path
    expected_size_mb: float
    expected_checksum: str

class SetupDownloader:
    """Downloads nur während Setup-Phase."""
    
    def __init__(self, models_dir: Path = None):
        self.models_dir = models_dir or Path("models")
        self.models_dir.mkdir(parents=True, exist_ok=True)
    
    def download_model(
        self,
        task: DownloadTask,
        progress_callback: Callable[[int, str], None] = None
    ) -> bool:
        """Downloaded ein Model mit Progress."""
        
        # Bereits vorhanden?
        if task.target_path.exists():
            if self._verify_checksum(task.target_path, task.expected_checksum):
                logger.info(f"Model bereits vorhanden: {task.name}")
                return True
            else:
                logger.warning(f"Checksum falsch, lade neu: {task.name}")
                task.target_path.unlink()
        
        # Download
        try:
            response = requests.get(task.url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            task.target_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(task.target_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if progress_callback and total_size:
                        percent = int((downloaded / total_size) * 100)
                        progress_callback(percent, f"Downloading {task.name}")
            
            # Verify
            if not self._verify_checksum(task.target_path, task.expected_checksum):
                task.target_path.unlink()
                raise ValueError("Download corrupted - checksum mismatch")
            
            logger.info(f"Model heruntergeladen: {task.name}")
            return True
            
        except Exception as e:
            logger.error(f"Download fehlgeschlagen: {task.name} - {e}")
            return False
    
    def _verify_checksum(self, path: Path, expected: str) -> bool:
        """Verifiziert SHA256 Checksum."""
        if not expected:
            return True  # Kein Checksum erforderlich
        
        hasher = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        
        return hasher.hexdigest() == expected
    
    def check_internet(self) -> bool:
        """Prüft Internet-Verfügbarkeit."""
        try:
            response = requests.get("https://www.google.com", timeout=5)
            return response.status_code == 200
        except:
            return False
```

---

## 5. Internet Dependency Checker

```python
import ast
import importlib.util
from pathlib import Path

class InternetDependencyChecker:
    """Findet versteckte Internet-Abhängigkeiten im Code."""
    
    # Bekannte problematische Patterns
    DANGEROUS_PATTERNS = [
        # Hugging Face
        "from_pretrained",
        "snapshot_download",
        "hf_hub_download",
        
        # Torch Hub
        "torch.hub.load",
        
        # Requests ohne Offline-Check
        "requests.get",
        "requests.post",
        "urllib.request",
        
        # Auto-Download Patterns
        "download=True",
        "force_download",
    ]
    
    # Safe Patterns (False Positives vermeiden)
    SAFE_PATTERNS = [
        "requests.get(\"http://localhost",
        "requests.get('http://localhost",
        "requests.get(\"http://127.0.0.1",
    ]
    
    def check_file(self, file_path: Path) -> list[dict]:
        """Prüft eine Python-Datei auf Internet-Abhängigkeiten."""
        issues = []
        
        with open(file_path, encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Skip Kommentare
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            
            # Check dangerous patterns
            for pattern in self.DANGEROUS_PATTERNS:
                if pattern in line:
                    # Prüfe ob es ein safe pattern ist
                    is_safe = any(safe in line for safe in self.SAFE_PATTERNS)
                    
                    if not is_safe:
                        issues.append({
                            "file": str(file_path),
                            "line": i,
                            "pattern": pattern,
                            "code": line.strip()[:100]
                        })
        
        return issues
    
    def check_directory(self, directory: Path, pattern: str = "**/*.py") -> list[dict]:
        """Prüft alle Python-Dateien in einem Verzeichnis."""
        all_issues = []
        
        for py_file in directory.glob(pattern):
            issues = self.check_file(py_file)
            all_issues.extend(issues)
        
        return all_issues
    
    def generate_report(self, directory: Path) -> str:
        """Generiert Bericht über Internet-Abhängigkeiten."""
        issues = self.check_directory(directory)
        
        if not issues:
            return "✅ Keine Internet-Abhängigkeiten gefunden."
        
        report = f"⚠️ {len(issues)} potenzielle Internet-Abhängigkeiten gefunden:\n\n"
        
        for issue in issues:
            report += f"📍 {issue['file']}:{issue['line']}\n"
            report += f"   Pattern: {issue['pattern']}\n"
            report += f"   Code: {issue['code']}\n\n"
        
        return report
```

---

## 6. Airplane Mode Test

```python
def airplane_mode_test(func):
    """Decorator zum Testen ob Funktion offline funktioniert."""
    import functools
    import socket
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Original DNS resolver
        original_getaddrinfo = socket.getaddrinfo
        
        def blocked_getaddrinfo(*args, **kwargs):
            raise OSError("Network access blocked (Airplane Mode Test)")
        
        try:
            # Block network
            socket.getaddrinfo = blocked_getaddrinfo
            
            # Run function
            result = func(*args, **kwargs)
            
            logger.info(f"✅ {func.__name__} passed airplane mode test")
            return result
            
        except OSError as e:
            if "Network access blocked" in str(e):
                logger.error(f"❌ {func.__name__} requires internet!")
                raise RuntimeError(f"{func.__name__} is not offline-safe!")
            raise
        finally:
            # Restore network
            socket.getaddrinfo = original_getaddrinfo
    
    return wrapper

# Verwendung:
@airplane_mode_test
def test_model_loading():
    loader = OfflineModelLoader()
    session = loader.load("moondream-vision")
    return session is not None
```

---

## 7. Offline-Safe Configuration

```python
from pathlib import Path
import json
from typing import Any, Optional

class OfflineConfig:
    """Konfiguration ohne Cloud-Sync."""
    
    DEFAULT_CONFIG = {
        "app": {
            "theme": "dark",
            "language": "de"
        },
        "processing": {
            "max_threads": 4,
            "gpu_enabled": True
        },
        "paths": {
            "models": "models",
            "data": "data",
            "output": "output"
        }
    }
    
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or Path("config/settings.json")
        self._config: dict = {}
        
        self._load()
    
    def _load(self):
        """Lädt Konfiguration lokal."""
        if self.config_path.exists():
            with open(self.config_path) as f:
                self._config = json.load(f)
        else:
            self._config = self.DEFAULT_CONFIG.copy()
            self._save()
    
    def _save(self):
        """Speichert Konfiguration lokal."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self._config, f, indent=2)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Holt Konfigurationswert (dot notation)."""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Setzt Konfigurationswert (dot notation)."""
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        self._save()
```

---

## Checkliste: Offline Engineering

### Vor Release
- [ ] Alle Models lokal in `models/` vorhanden?
- [ ] Manifest erstellt und verifiziert?
- [ ] `InternetDependencyChecker` über Codebase laufen lassen?
- [ ] `airplane_mode_test` für kritische Funktionen?

### Bei der Entwicklung
- [ ] Kein `from_pretrained()` ohne lokalen Pfad?
- [ ] Keine API-Calls zur Runtime?
- [ ] Downloads nur in Setup-Phase?
- [ ] Fehlerbehandlung für fehlende Assets?

### Im Setup
- [ ] Internet-Check vor Downloads?
- [ ] Checksum-Verifikation nach Downloads?
- [ ] Resume bei abgebrochenen Downloads?

---

## Häufige Fehler & Lösungen

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| `Model not found` | Asset fehlt | Setup erneut ausführen |
| `Checksum mismatch` | Download korrupt | Neu downloaden |
| `requests.exceptions` | Code macht API-Call | `InternetDependencyChecker` verwenden |
| `from_pretrained failed` | Kein Internet | Lokalen Pfad verwenden |
| `Missing DLL` | DirectML nicht installiert | Offline-Installer mit DLLs bündeln |
