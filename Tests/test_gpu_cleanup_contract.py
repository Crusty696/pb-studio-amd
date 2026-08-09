from __future__ import annotations

import asyncio
from types import SimpleNamespace

from backend import main
from pb_studio.core import vram_budget_manager


def test_gpu_cleanup_uses_public_model_budget_lookup(monkeypatch) -> None:
    class Manager:
        def __init__(self) -> None:
            self.loaded = True

        def get_stats(self):
            return {
                "models": {
                    "idle-model": {
                        "is_loaded": True,
                        "priority": "LOW",
                    }
                }
            }

        def get_model(self, model_id: str):
            assert model_id == "idle-model"
            return SimpleNamespace(unload_callback=lambda: None)

        def evict_all(self, _priority):
            self.loaded = False
            return 256

        def is_model_loaded(self, model_id: str):
            assert model_id == "idle-model"
            return self.loaded

    manager = Manager()
    monkeypatch.setattr(vram_budget_manager, "get_vram_manager", lambda: manager)

    result = asyncio.run(main.gpu_cleanup())

    assert result.success is True
    assert result.freed_mb == 256
    assert result.error is None
