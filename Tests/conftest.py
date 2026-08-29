"""
Pytest Configuration and Fixtures for PB Studio Tests

Provides shared fixtures for:
- Mock configurations
- Temporary directories
- Test asset paths
- Mock hardware monitors
"""

import logging
import os
import warnings

import httpx
import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import MagicMock, patch


TEST_OWNER_CAPABILITY = "pb-studio-pytest-owner-capability"
os.environ["PBSTUDIO_OWNER_CAPABILITY"] = TEST_OWNER_CAPABILITY

# Bewusst NACH dem Setzen der Owner-Capability: die Reihenfolge wird
# festgeschrieben, statt sich darauf zu verlassen, dass heute zufaellig nichts
# in der Importkette diese Variable liest.
try:
    from backend._brain_singleton import clear_project_state
except ImportError:
    clear_project_state = None


class BrainResetFailure(RuntimeWarning):
    """Der Brain-State konnte zwischen zwei Tests nicht geloest werden."""


def _reset_brain_project_state(phase: str) -> None:
    """Brain-State zwischen Tests loesen, ohne dass die Suite am Verhalten des
    Produktionscodes haengt.

    Audit 2026-08-29: isolated_test_database ist autouse und rief
    clear_project_state() ohne try/except in Setup UND Teardown. Solange das so
    war, konnte clear_project_state niemals zu einem Re-Raise weiterentwickelt
    werden - gemessen: ein Wurf im Setup erzeugt 1552 Fixture-Errors bei
    0 ausgefuehrten Tests. Die Testinfrastruktur diktierte das
    Produktionsverhalten.

    Der Fehlschlag wird gemeldet, nicht geschluckt. Die Logzeile allein
    genuegt dafuer NICHT: pytest.ini setzt weder log_cli noch log_file, und
    pytest zeigt den Captured-log-Abschnitt nur bei fehlschlagenden Tests - in
    einem gruenen Lauf waere sie unsichtbar. Erst warnings.warn taucht im
    warnings summary jedes Laufs auf. Ohne diese zweite Meldung waere die
    Kapselung eine Verschlechterung: sie wuerde eine laute Fehlerwand gegen
    stilles Schlucken tauschen und eine kaputte Testisolation unbemerkt
    gruen durchlaufen lassen.
    """
    if clear_project_state is None:
        return
    try:
        clear_project_state()
    except Exception as exc:
        logging.getLogger("conftest").warning(
            "clear_project_state() hat im %s geworfen - die Testisolation ist "
            "moeglicherweise unvollstaendig",
            phase,
            exc_info=True,
        )
        warnings.warn(
            f"clear_project_state() hat im {phase} geworfen ({exc!r}) - "
            "die Testisolation ist moeglicherweise unvollstaendig",
            BrainResetFailure,
            stacklevel=2,
        )


@pytest.fixture(scope="session", autouse=True)
def directml_adapter_contract_for_hardwareless_tests():
    """Use a deterministic AMD descriptor when a test runner has no AMD GPU."""
    from pb_studio.core import directml_adapter

    original = directml_adapter._selected_adapter
    try:
        selected = directml_adapter.select_directml_adapter(
            directml_adapter.enumerate_dxgi_adapters(),
            {"hardware": {}, "ai": {}},
        )
    except directml_adapter.DirectMLAdapterError:
        selected = directml_adapter.DirectMLAdapter(
            device_id=0,
            luid="0x00000000_0x00000001",
            name="AMD DirectML Test Adapter",
            vendor_id=0x1002,
            device_id_pci=0,
            dedicated_vram_bytes=8 * 1024 * 1024 * 1024,
            shared_system_memory_bytes=0,
            is_software=False,
            is_discrete=True,
            high_performance_preferred=True,
            selection_policy="highest_vram_amd",
            selection_reason="hardwareless test contract",
        )
    directml_adapter._selected_adapter = selected
    yield selected
    directml_adapter._selected_adapter = original


@pytest.fixture(autouse=True)
def authorize_main_app_test_client(request, monkeypatch):
    """Authenticate legacy tests that exercise the real default-deny ASGI app."""
    if request.node.get_closest_marker("unauthorized_backend") is not None:
        yield
        return

    from fastapi.testclient import TestClient
    from backend import owner_capability
    from backend.main import app as backend_app

    original_request = TestClient.request

    def authorized_request(client, method, url, **kwargs):
        if client.app is backend_app:
            headers = httpx.Headers(kwargs.get("headers"))
            capability = owner_capability.get_owner_capability()
            if capability and owner_capability.OWNER_CAPABILITY_HEADER not in headers:
                headers[owner_capability.OWNER_CAPABILITY_HEADER] = capability
            kwargs["headers"] = headers
        return original_request(client, method, url, **kwargs)

    monkeypatch.setattr(TestClient, "request", authorized_request)
    yield


@pytest.fixture(autouse=True)
def isolated_test_database(tmp_path, monkeypatch):
    """Jeder Test nutzt eine isolierte SQLite-Datei statt der produktiven DB."""
    from pb_studio.config_manager import ConfigManager
    from pb_studio.data.database_core import DatabaseCore
    from pb_studio.brain.brain_service import BrainService

    test_db_path = tmp_path / "test_pb_studio.db"

    def _load_test_config(self):
        self.config_file = tmp_path / "config.test.json"
        self._config = ConfigManager._deep_merge(
            ConfigManager.DEFAULTS,
            {"paths": {"db_path": str(test_db_path)}},
        )

    # Singletons vor jedem Test hart zurücksetzen
    if DatabaseCore._instance is not None:
        DatabaseCore._instance.shutdown()
    ConfigManager._instance = None
    DatabaseCore._instance = None
    
    BrainService.reset_singleton()
    _reset_brain_project_state("Setup")

    monkeypatch.setattr(ConfigManager, "_load_config", _load_test_config)

    yield test_db_path

    if DatabaseCore._instance is not None:
        DatabaseCore._instance.shutdown()
    ConfigManager._instance = None
    DatabaseCore._instance = None
    
    BrainService.reset_singleton()
    _reset_brain_project_state("Teardown")


@pytest.fixture
def test_assets_dir():
    """Returns path to test assets directory."""
    return Path(__file__).parent / "test_assets"


@pytest.fixture
def sample_audio_path(test_assets_dir):
    """Returns path to sample audio file."""
    return test_assets_dir / "sample.wav"


@pytest.fixture
def sample_video_path(test_assets_dir):
    """Returns path to sample video file."""
    return test_assets_dir / "sample.mp4"


@pytest.fixture
def temp_dir():
    """Creates a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config():
    """Returns a mock configuration dictionary."""
    return {
        "app_name": "PB Studio Test",
        "version": "1.0.0-test",
        "paths": {
            "ffmpeg_bin": "./tools/ffmpeg/bin/ffmpeg.exe",
            "lhm_lib": "./tools/LibreHardwareMonitor/LibreHardwareMonitorLib.dll",
            "temp_dir": "./temp",
            "db_path": "./data/test_pb_studio.db",
            "models_dir": "./models"
        },
        # Audit 2026-08-06 (T4.6): fuenf wirkungslose Schluessel entfernt,
        # synchron zu ConfigManager.DEFAULTS.
        # Audit 2026-08-07: `ai.vision_model` ebenfalls — geschrieben, nie gelesen.
        "hardware": {
            "gpu_backend": "directml",
            "vram_limit_mb": 4096
        },
        "ai": {},
        "ui": {}
    }


@pytest.fixture
def temp_config_file(temp_dir, mock_config):
    """Creates a temporary config.json file."""
    config_path = temp_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(mock_config, f, indent=4)
    return config_path


@pytest.fixture
def mock_gpu_stats():
    """Returns mock GPU statistics."""
    return {
        "gpu_load": 35.5,
        "gpu_temp": 62.0,
        "gpu_memory_used": 2048.0,
        "gpu_memory_total": 8192.0
    }


@pytest.fixture
def mock_system_monitor(mock_gpu_stats):
    """Creates a mock SystemMonitor."""
    monitor = MagicMock()
    monitor.get_stats.return_value = mock_gpu_stats
    monitor.computer = MagicMock()
    monitor.gpu_sensor = MagicMock()
    return monitor


@pytest.fixture
def mock_hardware_sensor():
    """Creates a mock hardware sensor for LHM tests."""
    sensor = MagicMock()
    sensor.Name = "GPU Core"
    sensor.SensorType = "Load"
    sensor.Value = 45.0
    return sensor


@pytest.fixture
def reset_config_singleton():
    """
    Resets ConfigManager singleton between tests.
    Use as a fixture in tests that modify config.
    """
    from pb_studio.config_manager import ConfigManager
    ConfigManager._instance = None
    yield
    ConfigManager._instance = None


@pytest.fixture
def mock_faiss_index():
    """Creates a mock FAISS index."""
    index = MagicMock()
    index.ntotal = 0
    index.add = MagicMock()
    index.search = MagicMock(return_value=([[-1]], [[-1]]))
    return index
