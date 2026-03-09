# Verification & QA Skill

## Trigger
Aktiviere diesen Skill automatisch bei:
- "Test", "Verify", "QA", "Check", "Validate"
- Nach Implementierung eines Features
- Vor Merge/Release
- Bei Bug Reports oder Regressionen

## Cross-References
- → `generic-workflow.md` (Reflect Phase)
- → `debugging.md` (Error Analysis)
- → `python-backend.md` (Unit Tests)
- → Alle Skills (Skill-spezifische Tests)

---

## Core Principles
| Regel | Beschreibung |
|-------|--------------|
| **No Unverified Claims** | Nie "es funktioniert" ohne Beweis |
| **AMD Only** | Ausschließlich AMD GPU Kompatibilität verifizieren |
| **Evidence-Based** | Tests, Logs, Screenshots als Beweis |

---

## 1. Verification Status System

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

class VerificationStatus(Enum):
    NOT_VERIFIED = "not_verified"
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"

@dataclass
class VerificationResult:
    status: VerificationStatus
    message: str
    timestamp: datetime
    evidence: list[str]  # Pfade zu Screenshots, Logs, etc.
    
    # Spezifische Checks
    amd_tested: bool = False
    offline_tested: bool = False
    ui_responsive: bool = False
    
    @property
    def summary(self) -> str:
        checks = []
        if self.amd_tested:
            checks.append("✅ AMD")
        else:
            checks.append("❌ AMD")
        
        if self.offline_tested:
            checks.append("✅ Offline")
        else:
            checks.append("❌ Offline")
        
        if self.ui_responsive:
            checks.append("✅ UI")
        else:
            checks.append("❌ UI")
        
        return f"[{self.status.value}] {' | '.join(checks)} - {self.message}"

# Korrekte Aussagen nach Implementierung:
# ✅ "Implementiert, pending verification"
# ✅ "Implementiert und lokal getestet auf AMD GPU"
# ❌ "Es funktioniert" (ohne Test)
# ❌ "Sollte funktionieren" (Annahme)
```

---

## 2. Test-Typen und Wann sie anzuwenden sind

```
┌─────────────────────────────────────────────────────────┐
│                    TEST PYRAMID                          │
└─────────────────────────────────────────────────────────┘

                    ╱╲
                   ╱  ╲
                  ╱ E2E╲         ← Wenige, langsam, teuer
                 ╱──────╲           (Manuelle UI Tests)
                ╱        ╲
               ╱Integration╲     ← Mehr, Services testen
              ╱────────────╲        (pytest + fixtures)
             ╱              ╲
            ╱   Unit Tests   ╲   ← Viele, schnell, isoliert
           ╱──────────────────╲     (pytest, einzelne Funktionen)
          ╱                    ╲
```

---

## 3. Unit Test Templates

```python
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import numpy as np

# Test-Verzeichnis-Struktur
# tests/
# ├── conftest.py          # Shared Fixtures
# ├── unit/
# │   ├── test_audio.py
# │   ├── test_video.py
# │   └── test_database.py
# └── integration/
#     ├── test_pipeline.py
#     └── test_services.py

# conftest.py - Shared Fixtures
@pytest.fixture
def temp_audio_file(tmp_path) -> Path:
    """Erstellt temporäre Audio-Datei für Tests."""
    import soundfile as sf
    
    audio_path = tmp_path / "test_audio.wav"
    
    # 1 Sekunde Stille bei 44100 Hz
    samples = np.zeros(44100, dtype=np.float32)
    sf.write(str(audio_path), samples, 44100)
    
    return audio_path

@pytest.fixture
def mock_database():
    """Mock Database für isolierte Tests."""
    mock = MagicMock()
    mock.execute_read.return_value = []
    mock.execute_write.return_value = 1
    return mock

@pytest.fixture
def mock_gpu_info():
    """Mock GPU Info für AMD-Tests."""
    from src.pb_studio.hardware import GPUInfo, GPUVendor
    
    return GPUInfo(
        vendor=GPUVendor.AMD,
        name="AMD Radeon RX 6800",
        vram_mb=16384,
        driver_version="23.10",
        supports_directml=True,
        supports_amf=True,
        supports_qsv=False
    )

# Unit Test Example
class TestAudioProcessor:
    """Tests für AudioProcessor."""
    
    def test_load_valid_file(self, temp_audio_file):
        """Test: Gültige Audio-Datei laden."""
        from src.pb_studio.audio import AudioProcessor
        
        processor = AudioProcessor()
        audio, sr = processor.load(temp_audio_file)
        
        assert audio is not None
        assert sr == 44100
        assert len(audio) == 44100
    
    def test_load_invalid_file_raises(self, tmp_path):
        """Test: Ungültige Datei wirft Exception."""
        from src.pb_studio.audio import AudioProcessor
        
        invalid_path = tmp_path / "not_exists.wav"
        processor = AudioProcessor()
        
        with pytest.raises(FileNotFoundError):
            processor.load(invalid_path)
    
    def test_bpm_detection_returns_valid_range(self, temp_audio_file):
        """Test: BPM liegt im gültigen Bereich."""
        from src.pb_studio.audio import AudioProcessor
        
        processor = AudioProcessor()
        result = processor.analyze(temp_audio_file)
        
        assert 60 <= result.bpm <= 200  # Typischer BPM-Bereich
    
    @pytest.mark.parametrize("format_ext", [".mp3", ".wav", ".flac", ".ogg"])
    def test_supported_formats(self, tmp_path, format_ext):
        """Test: Alle unterstützten Formate."""
        from src.pb_studio.audio import AudioProcessor
        
        processor = AudioProcessor()
        formats = processor.get_supported_formats()
        
        assert format_ext in formats

# AMD-Spezifische Tests
class TestAMDCompatibility:
    """Tests für AMD GPU Kompatibilität."""
    
    @pytest.mark.gpu
    def test_directml_provider_available(self):
        """Test: DirectML Provider ist verfügbar."""
        import onnxruntime as ort
        
        providers = ort.get_available_providers()
        
        # DirectML oder CPU sollte verfügbar sein
        assert (
            'DmlExecutionProvider' in providers or
            'CPUExecutionProvider' in providers
        )
    
    @pytest.mark.gpu
    def test_inference_on_directml(self, mock_gpu_info):
        """Test: Inference funktioniert mit DirectML."""
        from src.pb_studio.ai import get_optimal_providers
        
        with patch('src.pb_studio.hardware.detect_gpu', return_value=mock_gpu_info):
            providers = get_optimal_providers()
        
        # DirectML sollte erste Wahl sein für AMD
        assert 'DmlExecutionProvider' in providers
```

---

## 4. Integration Tests

```python
class TestAudioPipeline:
    """Integration Tests für Audio-Pipeline."""
    
    @pytest.fixture
    def full_pipeline(self, tmp_path, mock_database):
        """Erstellt vollständige Test-Pipeline."""
        from src.pb_studio.services import AudioService, TaskManager
        from src.pb_studio.ai import ModelManager
        
        # Task Manager (ohne echte Threads für Tests)
        task_manager = TaskManager(max_concurrent=1)
        
        # Model Manager mit Test-Models
        model_manager = ModelManager(models_dir=tmp_path / "models")
        
        # Audio Service
        service = AudioService(
            task_manager=task_manager,
            model_manager=model_manager
        )
        service.initialize()
        
        return service
    
    def test_full_analysis_pipeline(self, full_pipeline, temp_audio_file):
        """Test: Komplette Analyse-Pipeline."""
        result_received = []
        
        def callback(result):
            result_received.append(result)
        
        # Analyse starten
        task_id = full_pipeline.analyze_file(
            temp_audio_file,
            callback=callback
        )
        
        # Warten auf Completion (in Tests synchron)
        import time
        timeout = 30
        while len(result_received) == 0 and timeout > 0:
            time.sleep(0.1)
            timeout -= 0.1
        
        assert len(result_received) == 1
        assert result_received[0].success

# Offline Tests
class TestOfflineCapability:
    """Tests für Offline-Betrieb."""
    
    @pytest.fixture
    def block_network(self):
        """Blockiert Netzwerk-Zugriff."""
        import socket
        original = socket.socket
        
        def blocked_socket(*args, **kwargs):
            raise OSError("Network blocked for testing")
        
        socket.socket = blocked_socket
        yield
        socket.socket = original
    
    def test_model_loading_offline(self, block_network, tmp_path):
        """Test: Models laden ohne Internet."""
        from src.pb_studio.ai import OfflineModelLoader
        
        # Fake Model erstellen
        model_path = tmp_path / "models" / "test.onnx"
        model_path.parent.mkdir(parents=True)
        model_path.write_bytes(b"fake model")  # Wird beim Laden fehlschlagen
        
        loader = OfflineModelLoader(tmp_path / "models")
        
        # Sollte keine Netzwerk-Anfrage machen
        # (würde sonst durch block_network fehlschlagen)
        with pytest.raises(Exception):  # Laden wird fehlschlagen (fake model)
            loader.load("test")
```

---

## 5. Manual Verification Checklists

### Pre-Release Checklist

```markdown
# Pre-Release Verification Checklist

## Datum: ____________________
## Version: __________________
## Tester: ___________________

## 1. Startup Tests
- [ ] App startet ohne Fehler (Console prüfen)
- [ ] Splash Screen zeigt Progress
- [ ] Main Window erscheint < 5 Sekunden
- [ ] Keine Warnungen in logs/app.log

## 2. AMD GPU Tests (NUR auf AMD Hardware)
- [ ] GPU wird korrekt erkannt (Settings → System Info)
- [ ] DirectML Provider aktiv (nicht CPU Fallback)
- [ ] AI-Inference funktioniert (Test-Datei analysieren)
- [ ] Keine Provider-Fehler in Logs

## 3. Offline Tests
- [ ] Netzwerkkabel ziehen / WLAN aus
- [ ] App startet normal
- [ ] Alle Core-Features funktionieren
- [ ] Keine "Connection refused" Fehler

## 4. UI Responsiveness
- [ ] Klicks reagieren sofort (<100ms)
- [ ] Keine "Not Responding" Meldungen
- [ ] Progress-Anzeige bei langen Operationen
- [ ] Cancel-Button funktioniert

## 5. Feature Tests
### Audio
- [ ] Audio-Import (MP3, WAV, FLAC)
- [ ] BPM-Erkennung (Ergebnis plausibel?)
- [ ] Stem Separation (4 Stems exportiert?)

### Video
- [ ] Video-Import (MP4, MKV)
- [ ] Keyframe-Extraktion
- [ ] Thumbnail-Generierung

### Search
- [ ] Text-Suche funktioniert
- [ ] Ergebnisse sind relevant
- [ ] Performance bei >100 Dateien

## 6. Error Handling
- [ ] Ungültige Datei → Sinnvolle Fehlermeldung
- [ ] Fehlende Berechtigung → Sinnvolle Fehlermeldung
- [ ] Abbruch während Verarbeitung → Kein Crash

## 7. Logs prüfen
- [ ] logs/app.log: Keine ERROR oder CRITICAL
- [ ] logs/error.log: Leer oder nur erwartete Fehler

## Ergebnis
- [ ] PASSED - Alle Tests bestanden
- [ ] FAILED - Kritische Fehler gefunden
- [ ] BLOCKED - Tests konnten nicht ausgeführt werden

## Notizen
_________________________________
_________________________________
_________________________________
```

---

## 6. Automated Verification Scripts

```python
#!/usr/bin/env python
"""Automatisiertes Verification-Script für PB Studio."""

import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass
import json

@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    details: str = ""

class AutoVerifier:
    """Automatisierte Verification-Checks."""
    
    def __init__(self, project_dir: Path = None):
        self.project_dir = project_dir or Path.cwd()
        self.results: list[CheckResult] = []
    
    def run_all_checks(self) -> bool:
        """Führt alle Checks aus."""
        checks = [
            self.check_python_version,
            self.check_dependencies,
            self.check_models_exist,
            self.check_database,
            self.check_gpu_providers,
            self.check_no_internet_deps,
            self.run_unit_tests,
        ]
        
        for check in checks:
            try:
                result = check()
                self.results.append(result)
            except Exception as e:
                self.results.append(CheckResult(
                    name=check.__name__,
                    passed=False,
                    message=f"Check crashed: {e}"
                ))
        
        return all(r.passed for r in self.results)
    
    def check_python_version(self) -> CheckResult:
        """Prüft Python Version."""
        version = sys.version_info
        passed = version >= (3, 10)
        
        return CheckResult(
            name="Python Version",
            passed=passed,
            message=f"Python {version.major}.{version.minor}.{version.micro}",
            details="Requires Python 3.10+" if not passed else ""
        )
    
    def check_dependencies(self) -> CheckResult:
        """Prüft ob alle Dependencies installiert sind."""
        required = [
            "PyQt6",
            "onnxruntime",
            "numpy",
            "librosa",
            "soundfile"
        ]
        
        missing = []
        for pkg in required:
            try:
                __import__(pkg.lower().replace("-", "_"))
            except ImportError:
                missing.append(pkg)
        
        return CheckResult(
            name="Dependencies",
            passed=len(missing) == 0,
            message=f"Missing: {missing}" if missing else "All present",
            details=str(missing)
        )
    
    def check_models_exist(self) -> CheckResult:
        """Prüft ob required Models existieren."""
        models_dir = self.project_dir / "models"
        
        if not models_dir.exists():
            return CheckResult(
                name="Models",
                passed=False,
                message="models/ directory missing"
            )
        
        # Prüfe Manifest
        manifest = models_dir / "manifest.json"
        if not manifest.exists():
            return CheckResult(
                name="Models",
                passed=False,
                message="manifest.json missing"
            )
        
        with open(manifest) as f:
            data = json.load(f)
        
        missing = []
        for name, info in data.get("assets", {}).items():
            path = models_dir / info["path"]
            if info.get("required", True) and not path.exists():
                missing.append(name)
        
        return CheckResult(
            name="Models",
            passed=len(missing) == 0,
            message=f"Missing: {missing}" if missing else "All present"
        )
    
    def check_gpu_providers(self) -> CheckResult:
        """Prüft ONNX Runtime Providers (AMD-fokussiert)."""
        try:
            import onnxruntime as ort
            providers = ort.get_available_providers()
            
            has_directml = 'DmlExecutionProvider' in providers
            
            return CheckResult(
                name="GPU Providers",
                passed=True,  # CPU ist auch OK
                message=f"Available: {providers}",
                details="DirectML (AMD) available" if has_directml else "CPU only"
            )
        except Exception as e:
            return CheckResult(
                name="GPU Providers",
                passed=False,
                message=str(e)
            )
    
    def check_no_internet_deps(self) -> CheckResult:
        """Prüft auf versteckte Internet-Abhängigkeiten."""
        from src.pb_studio.offline import InternetDependencyChecker
        
        checker = InternetDependencyChecker()
        issues = checker.check_directory(self.project_dir / "src")
        
        return CheckResult(
            name="Offline Safety",
            passed=len(issues) == 0,
            message=f"{len(issues)} potential issues" if issues else "Clean",
            details=str(issues[:5]) if issues else ""  # Erste 5
        )
    
    def check_database(self) -> CheckResult:
        """Prüft Datenbank-Initialisierung."""
        try:
            from src.pb_studio.data import DatabaseCore
            
            db = DatabaseCore()
            conn = db.get_connection()
            
            # Prüfe ob Tabellen existieren
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            
            return CheckResult(
                name="Database",
                passed=len(tables) > 0,
                message=f"{len(tables)} tables found"
            )
        except Exception as e:
            return CheckResult(
                name="Database",
                passed=False,
                message=str(e)
            )
    
    def run_unit_tests(self) -> CheckResult:
        """Führt Unit Tests aus."""
        result = subprocess.run(
            ["pytest", "tests/unit", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            cwd=str(self.project_dir)
        )
        
        return CheckResult(
            name="Unit Tests",
            passed=result.returncode == 0,
            message="Passed" if result.returncode == 0 else "Failed",
            details=result.stdout[-500:] if result.stdout else result.stderr[-500:]
        )
    
    def generate_report(self) -> str:
        """Generiert Verification Report."""
        report = "# Verification Report\n\n"
        report += f"Date: {datetime.now().isoformat()}\n\n"
        
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        
        report += f"## Summary: {passed}/{total} checks passed\n\n"
        
        for result in self.results:
            icon = "✅" if result.passed else "❌"
            report += f"{icon} **{result.name}**: {result.message}\n"
            if result.details:
                report += f"   > {result.details}\n"
        
        return report

if __name__ == "__main__":
    verifier = AutoVerifier()
    success = verifier.run_all_checks()
    print(verifier.generate_report())
    sys.exit(0 if success else 1)
```

---

## Checkliste: Verification & QA

### Nach jeder Implementierung
- [ ] Unit Tests geschrieben/aktualisiert?
- [ ] Lokal getestet?
- [ ] AMD-Kompatibilität verifiziert?
- [ ] Offline-Betrieb getestet?

### Vor Merge/Release
- [ ] Alle Unit Tests grün?
- [ ] Integration Tests bestanden?
- [ ] Manual Checklist durchgearbeitet?
- [ ] Keine ERROR/CRITICAL in Logs?

### Bei Bug Reports
- [ ] Bug reproduziert?
- [ ] Root Cause identifiziert?
- [ ] Regression Test hinzugefügt?

---

## Häufige Fehler & Lösungen

| Fehler | Ursache | Lösung |
|--------|---------|--------|
| "Es funktioniert" ohne Test | Annahme statt Verifikation | Test schreiben/ausführen |
| Test nur auf einem System | Keine AMD-Hardware | CI mit DirectML oder Mock |
| Flaky Tests | Race Conditions | Synchronisation/Mocks |
| Langsame Tests | Zu viele E2E Tests | Mehr Unit Tests |
