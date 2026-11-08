"""Truth contract for AudioClipInfo.has_audio_embedding."""

from __future__ import annotations

import asyncio
import importlib
import sys
from types import SimpleNamespace

import numpy as np


class _State:
    def __init__(self, clips):
        self._clips = clips

    def get_audio_clips_snapshot(self):
        return self._clips

    def get_audio_analysis(self, _clip_id):
        return None

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def project_operation(self):
        yield self

    def require_project_context_current(self, _context):
        pass


def test_list_clips_derives_embedding_flag_from_current_cache(monkeypatch):
    audio_router = importlib.import_module("backend.routers.audio_router")

    seen = []

    def available(media_hash):
        seen.append(media_hash)
        return media_hash == "present"

    monkeypatch.setattr(audio_router, "_has_current_audio_embedding", available)
    state = _State({
        1: {"id": 1, "name": "one", "path": "one.wav", "duration_seconds": 1.0,
            "audio_hash": "present", "has_audio_embedding": False},
        2: {"id": 2, "name": "two", "path": "two.wav", "duration_seconds": 1.0,
            "audio_hash": "missing", "has_audio_embedding": True},
    })

    items = asyncio.run(audio_router.list_clips(page=1, limit=50, state=state))

    assert seen == ["present", "missing"]
    assert [item.has_audio_embedding for item in items] == [True, False]


def test_current_embedding_probe_requires_audio_entry(monkeypatch):
    audio_router = importlib.import_module("backend.routers.audio_router")
    from pb_studio.audio import audio_embedder
    from pb_studio.brain.brain_service import BrainService

    class Cache:
        def __init__(self, media_type):
            self.media_type = media_type
            self.calls = []

        def lookup(self, *args):
            self.calls.append(args)
            return SimpleNamespace(media_type=self.media_type)

    cache = Cache("video")
    monkeypatch.setattr(
        BrainService,
        "get",
        classmethod(lambda cls: SimpleNamespace(brain=SimpleNamespace(cache=cache))),
    )
    assert audio_router._has_current_audio_embedding("abc") is False
    cache.media_type = "audio"
    assert audio_router._has_current_audio_embedding("abc") is True
    assert cache.calls == [
        ("abc", audio_embedder.CURRENT_MODEL_NAME, audio_embedder.CURRENT_MODEL_VERSION),
        ("abc", audio_embedder.CURRENT_MODEL_NAME, audio_embedder.CURRENT_MODEL_VERSION),
    ]


def test_current_embedding_probe_fails_closed(monkeypatch):
    audio_router = importlib.import_module("backend.routers.audio_router")
    from pb_studio.brain.brain_service import BrainService

    monkeypatch.setattr(
        BrainService,
        "get",
        classmethod(lambda cls: (_ for _ in ()).throw(RuntimeError("cache unavailable"))),
    )
    assert audio_router._has_current_audio_embedding(None) is False
    assert audio_router._has_current_audio_embedding("abc") is False


def test_store_embedding_reports_success_only_after_audio_cache_write(monkeypatch):
    audio_router = importlib.import_module("backend.routers.audio_router")
    from pb_studio.audio import audio_embedder
    from pb_studio.brain.brain_service import BrainService

    class Cache:
        def __init__(self):
            self.stored = []

        def lookup(self, *_args):
            return None

        def store(self, **kwargs):
            self.stored.append(kwargs)
            return SimpleNamespace(media_type="audio")

    cache = Cache()
    monkeypatch.setattr(
        BrainService,
        "get",
        classmethod(lambda cls: SimpleNamespace(brain=SimpleNamespace(cache=cache))),
    )
    monkeypatch.setitem(
        sys.modules,
        "pb_studio.ai.clap_wrapper",
        SimpleNamespace(
            CLAPAnalyzer=lambda: SimpleNamespace(
                encode_audio=lambda _path: np.ones(audio_embedder.EMBED_DIM, dtype=np.float32)
            )
        ),
    )

    stored = asyncio.run(
        audio_router._store_audio_embedding_in_brain_cache(
            audio_path="track.wav",
            audio_hash="hash",
        )
    )

    assert stored is True
    assert len(cache.stored) == 1
    assert cache.stored[0]["media_hash"] == "hash"
    assert cache.stored[0]["media_type"] == "audio"
    assert cache.stored[0]["model_name"] == audio_embedder.CURRENT_MODEL_NAME
    assert cache.stored[0]["model_version"] == audio_embedder.CURRENT_MODEL_VERSION
