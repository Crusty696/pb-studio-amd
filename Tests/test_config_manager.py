"""
Unit Tests for ConfigManager

Tests:
- Singleton pattern works correctly
- Default values are loaded
- Config file loading/saving
- Get/Set operations
- Typed property accessors
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestConfigManagerDefaults:
    """Tests for default configuration loading."""

    def test_defaults_contain_required_keys(self, reset_config_singleton):
        """Verify DEFAULTS contains all required top-level keys."""
        from pb_studio.config_manager import ConfigManager

        required_keys = ["app_name", "version", "paths", "hardware", "ai", "ui"]

        for key in required_keys:
            assert key in ConfigManager.DEFAULTS, f"Missing default key: {key}"

    def test_defaults_paths_structure(self, reset_config_singleton):
        """Verify paths section has correct structure."""
        from pb_studio.config_manager import ConfigManager

        paths = ConfigManager.DEFAULTS["paths"]
        required_paths = ["ffmpeg_bin", "lhm_lib", "temp_dir", "db_path"]

        for path_key in required_paths:
            assert path_key in paths, f"Missing path: {path_key}"

    def test_defaults_hardware_has_directml(self, reset_config_singleton):
        """Verify hardware defaults to DirectML backend."""
        from pb_studio.config_manager import ConfigManager

        hardware = ConfigManager.DEFAULTS["hardware"]
        assert hardware["gpu_backend"] == "directml"

    def test_defaults_vram_limit_is_reasonable(self, reset_config_singleton):
        """Verify default VRAM limit is reasonable (2-16GB)."""
        from pb_studio.config_manager import ConfigManager

        vram = ConfigManager.DEFAULTS["hardware"]["vram_limit_mb"]
        assert 2048 <= vram <= 16384, f"Unreasonable VRAM default: {vram}"


class TestConfigManagerSingleton:
    """Tests for singleton pattern."""

    def test_singleton_returns_same_instance(self, reset_config_singleton):
        """Verify singleton pattern returns same instance."""
        from pb_studio.config_manager import ConfigManager

        config1 = ConfigManager()
        config2 = ConfigManager()

        assert config1 is config2, "Singleton should return same instance"

    def test_singleton_preserves_state(self, reset_config_singleton):
        """Verify singleton preserves modifications."""
        from pb_studio.config_manager import ConfigManager

        config1 = ConfigManager()
        config1._config["test_key"] = "test_value"

        config2 = ConfigManager()
        assert config2._config.get("test_key") == "test_value"


class TestConfigManagerGetSet:
    """Tests for get/set operations."""

    def test_get_returns_existing_value(self, reset_config_singleton):
        """Verify get() returns existing config values."""
        from pb_studio.config_manager import ConfigManager

        config = ConfigManager()
        app_name = config.get("app_name")

        assert app_name is not None
        assert "PB Studio" in app_name

    def test_get_returns_default_for_missing_key(self, reset_config_singleton):
        """Verify get() returns default for missing keys."""
        from pb_studio.config_manager import ConfigManager

        config = ConfigManager()
        result = config.get("nonexistent_key", "fallback")

        assert result == "fallback"

    def test_get_returns_none_for_missing_without_default(self, reset_config_singleton):
        """Verify get() returns None when no default provided."""
        from pb_studio.config_manager import ConfigManager

        config = ConfigManager()
        result = config.get("nonexistent_key")

        assert result is None


class TestConfigManagerProperties:
    """Tests for typed property accessors."""

    def test_ffmpeg_path_returns_absolute(self, reset_config_singleton):
        """Verify ffmpeg_path returns absolute path."""
        from pb_studio.config_manager import ConfigManager

        config = ConfigManager()
        ffmpeg_path = config.ffmpeg_path

        assert Path(ffmpeg_path).is_absolute()

    def test_lhm_path_returns_absolute(self, reset_config_singleton):
        """Verify lhm_path returns absolute path."""
        from pb_studio.config_manager import ConfigManager

        config = ConfigManager()
        lhm_path = config.lhm_path

        assert Path(lhm_path).is_absolute()
