"""
Tests für Config Hot-Reload (Spec 00025).

Verifiziert:
  - FR-001: Automatische Erkennung externer Dateiänderungen
  - FR-002: Validierung vor Publish, Beibehaltung des letzten gültigen Stands bei Fehlern
  - FR-003: Revisionszähler, Diff-Berechnung, Abonnenten und Konfliktschutz
  - FR-004: Wirkung auf ai.task_overrides, ai.task_provider_overrides, ai.default_mode
  - FR-005: Key-Klassifikation (live / next_job / restart_required)
  - TR-001: Lifecycle-gebundener Poller (Start/Stop/Join)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from pb_studio.config_manager import ConfigManager, KEY_CLASSIFICATION


@pytest.fixture
def isolated_config(tmp_path: Path):
    """Erstellt eine isolierte ConfigManager-Instanz auf einer temporären config.json."""
    ConfigManager.reset_instance_for_tests()
    temp_config_file = tmp_path / "config.json"
    
    # Initiale gültige Config
    initial_data = {
        "app_name": "PB Studio Test",
        "version": "1.0.0-test",
        "paths": {
            "temp_dir": str(tmp_path / "temp"),
        },
        "ai": {
            "default_mode": "balance",
            "task_overrides": {
                "vision": "moondream2",
            },
            "task_provider_overrides": {
                "vision": "directml",
            },
        },
    }
    temp_config_file.write_text(json.dumps(initial_data, indent=2), encoding="utf-8")

    mgr = ConfigManager(config_file=temp_config_file)

    yield mgr, temp_config_file

    mgr.stop_watcher()
    ConfigManager.reset_instance_for_tests()


def test_config_hot_reload_valid_update(isolated_config) -> None:
    """Gültige externe Änderungen werden erkannt, Snapshot aktualisiert, Diff ermittelt."""
    mgr, config_path = isolated_config
    assert mgr.get("ai")["default_mode"] == "balance"
    initial_rev = mgr.get_status()["revision"]

    events: list[tuple[dict, dict, int]] = []

    def on_reload(new_cfg, diff, rev):
        events.append((new_cfg, diff, rev))

    mgr.subscribe(on_reload)

    # Externe Datei ändern
    new_data = {
        "app_name": "PB Studio Test",
        "version": "1.0.0-test",
        "paths": {
            "temp_dir": str(config_path.parent / "temp"),
        },
        "ai": {
            "default_mode": "speed",
            "task_overrides": {
                "vision": "phi3-vision",
            },
            "task_provider_overrides": {
                "vision": "directml",
            },
        },
    }
    config_path.write_text(json.dumps(new_data, indent=2), encoding="utf-8")

    changed, diff = mgr.reload_if_changed()
    assert changed is True
    assert "ai.default_mode" in diff
    assert diff["ai.default_mode"] == ("balance", "speed")
    assert "ai.task_overrides.vision" in diff
    assert diff["ai.task_overrides.vision"] == ("moondream2", "phi3-vision")

    # Snapshot prüfen
    assert mgr.get("ai")["default_mode"] == "speed"
    assert mgr.get("ai")["task_overrides"]["vision"] == "phi3-vision"
    assert mgr.get_status()["revision"] == initial_rev + 1
    assert len(events) == 1
    assert events[0][2] == initial_rev + 1


def test_config_hot_reload_invalid_json_keeps_last_good(isolated_config) -> None:
    """Ungültiges JSON wird abgelehnt, letzter gültiger Snapshot bleibt aktiv."""
    mgr, config_path = isolated_config
    good_ai = mgr.get("ai")
    initial_rev = mgr.get_status()["revision"]

    # Syntaxfehler in die Datei schreiben (z.B. unvollständiger Write)
    config_path.write_text("{\"ai\": { unclosed json", encoding="utf-8")

    changed, diff = mgr.reload_if_changed()
    assert changed is False
    assert diff == {}

    # Snapshot bleibt unverändert
    assert mgr.get("ai") == good_ai
    assert mgr.get_status()["revision"] == initial_rev
    assert mgr.get_status()["last_error"] is not None
    assert "JSON-Syntaxfehler" in mgr.get_status()["last_error"]


def test_config_hot_reload_invalid_structure_keeps_last_good(isolated_config) -> None:
    """Ungültige Schlüsseltypen (z.B. ai ist int statt dict) werden abgelehnt."""
    mgr, config_path = isolated_config
    good_ai = mgr.get("ai")

    # Ungültige Struktur schreiben
    config_path.write_text(json.dumps({"ai": 12345}), encoding="utf-8")

    changed, diff = mgr.reload_if_changed()
    assert changed is False
    assert mgr.get("ai") == good_ai
    assert mgr.get_status()["last_error"] is not None
    assert "Sektion 'ai' muss Typ dict sein" in mgr.get_status()["last_error"]


def test_config_hot_reload_conflict_detection(isolated_config) -> None:
    """save_config(force=False) erkennt ungesehene externe Dateiänderungen als Konflikt."""
    mgr, config_path = isolated_config

    # Externe Änderung simulieren ohne reload
    config_path.write_text(json.dumps({"app_name": "External Modified"}), encoding="utf-8")

    # Speichern mit force=False muss scheitern
    with pytest.raises(RuntimeError, match="Konflikt"):
        mgr.save_config(force=False)

    # Speichern mit force=True überschreibt kontrolliert
    mgr.save_config(force=True)
    assert mgr.config_file.exists()


def test_config_watcher_background_polling(isolated_config) -> None:
    """TR-001: Poller erkennt Änderungen automatisch im Hintergrund."""
    mgr, config_path = isolated_config
    mgr.start_watcher(poll_interval=0.1)
    assert mgr.get_status()["watcher_running"] is True

    new_data = {
        "app_name": "PB Studio Test",
        "ai": {
            "default_mode": "quality",
            "task_overrides": {},
            "task_provider_overrides": {},
        },
    }
    config_path.write_text(json.dumps(new_data, indent=2), encoding="utf-8")

    # Auf automatischen Reload warten (max 3 Sekunden)
    deadline = time.time() + 3.0
    while time.time() < deadline:
        if mgr.get("ai", {}).get("default_mode") == "quality":
            break
        time.sleep(0.1)

    assert mgr.get("ai")["default_mode"] == "quality"
    mgr.stop_watcher()
    assert mgr.get_status()["watcher_running"] is False


def test_key_classification_coverage() -> None:
    """FR-005: Prüft Vollständigkeit und Sinnhaftigkeit der Key-Klassifikation."""
    status = ConfigManager().get_status()
    classification = status["key_classification"]
    assert classification["ai.task_overrides"] == "next_job"
    assert classification["ai.default_mode"] == "next_job"
    assert classification["paths.db_path"] == "restart_required"
    assert classification["hardware.gpu_backend"] == "restart_required"
    assert classification["ui"] == "live"
