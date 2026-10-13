"""Wave A config contracts; run without global GPU/backend fixtures."""
import json
import pytest
from pb_studio.config_manager import ConfigManager

@pytest.fixture
def manager(tmp_path):
    ConfigManager.reset_instance_for_tests()
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"app_name": "test", "ai": {"provider": "native"}}))
    obj = ConfigManager(config_file=config)
    yield obj
    obj.stop_watcher()
    ConfigManager.reset_instance_for_tests()

def test_disabled_by_default_and_no_config_write(manager):
    before = manager.config_file.read_bytes()
    settings = manager.comfyui_settings
    assert settings.enabled is False
    assert settings.endpoint_url == "http://127.0.0.1:8188"
    assert manager.config_file.read_bytes() == before

@pytest.mark.parametrize("section", [[], None, {"enabled": "yes"}, {"endpoint_url": "https://example.com"}, {"endpoint_url": "http://user:secret@localhost:8188"}, {"control_timeout_seconds": 0}, {"control_timeout_seconds": float("nan")}, {"max_response_bytes": True}, {"unknown": 1}])
def test_invalid_connection_config_rejected(section):
    valid, reason = ConfigManager.validate_config_dict({"comfyui": section})
    assert not valid
    assert "comfyui" in reason
    assert "secret" not in reason

def test_reload_invalid_keeps_last_valid(manager):
    before = manager.comfyui_settings
    valid, _ = manager.reload_if_changed(raw_content=json.dumps({"comfyui": {"endpoint_url": "http://example.com"}}).encode())
    assert valid is False
    assert manager.comfyui_settings == before

def test_temporary_save_reload_and_other_sections_preserved(manager):
    manager.set("comfyui", {"enabled": True, "endpoint_url": "http://127.0.0.1:8189", "endpoint_id": "second-local"})
    ConfigManager.reset_instance_for_tests()
    reloaded = ConfigManager(config_file=manager.config_file)
    assert reloaded.comfyui_settings.endpoint_url == "http://127.0.0.1:8189"
    assert reloaded.comfyui_settings.endpoint_id == "second-local"
    assert reloaded.get("ai")["provider"] == "native"
    assert reloaded.get("app_name") == "test"

def test_accessor_validates_in_memory_settings(manager):
    manager._config["comfyui"] = {"endpoint_url": "http://example.com"}
    with pytest.raises(ValueError):
        _ = manager.comfyui_settings


def test_invalid_set_does_not_poison_memory_or_disk(manager):
    before_disk = manager.config_file.read_bytes()
    before_memory = manager.get("comfyui")
    with pytest.raises(ValueError):
        manager.set("comfyui", {"endpoint_url": "http://example.com"})
    assert manager.config_file.read_bytes() == before_disk
    assert manager.get("comfyui") == before_memory


def test_save_failure_rolls_back_memory(manager, monkeypatch):
    before = manager.get("comfyui")
    before_disk = manager.config_file.read_bytes()
    def fail_save(*args, **kwargs):
        raise OSError("test disk failure")
    monkeypatch.setattr(manager, "save_config", fail_save)
    with pytest.raises(OSError):
        manager.set("comfyui", {"enabled": True})
    assert manager.get("comfyui") == before
    assert manager.config_file.read_bytes() == before_disk

def test_defaults_match_typed_settings():
    from pb_studio.comfyui.schemas import ComfyConnectionSettings
    assert ComfyConnectionSettings.model_validate(ConfigManager.DEFAULTS["comfyui"]) == ComfyConnectionSettings()
