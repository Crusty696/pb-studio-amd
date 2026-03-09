"""
Pytest Configuration and Fixtures for PB Studio Tests

Provides shared fixtures for:
- Mock configurations
- Temporary directories
- Test asset paths
- Mock hardware monitors
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def isolated_test_database(tmp_path, monkeypatch):
    """Jeder Test nutzt eine isolierte SQLite-Datei statt der produktiven DB."""
    from pb_studio.config_manager import ConfigManager
    from pb_studio.data.database_core import DatabaseCore

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

    monkeypatch.setattr(ConfigManager, "_load_config", _load_test_config)

    yield test_db_path

    if DatabaseCore._instance is not None:
        DatabaseCore._instance.shutdown()
    ConfigManager._instance = None
    DatabaseCore._instance = None


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
