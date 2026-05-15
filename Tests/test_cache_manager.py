"""Test coverage for utils/cache_manager.py (P3.1 Test-Coverage-Gap-Filler).

Spec: PLAN_OPEN_TASKS_2026-05-15.md P3.1 — cache_manager.py hat 8 defs ohne Tests.
Hier: vollstaendiger CacheManager-Lifecycle inkl. TTL-Expiry und clear_all.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pb_studio.utils.cache_manager import CacheManager


@pytest.fixture
def cache(tmp_path):
    return CacheManager(cache_dir=tmp_path / "cache", prefix="test")


def test_init_creates_directory(tmp_path):
    cache_dir = tmp_path / "newcache"
    assert not cache_dir.exists()
    CacheManager(cache_dir=cache_dir, prefix="x")
    assert cache_dir.exists()
    assert cache_dir.is_dir()


def test_save_and_load_roundtrip(cache):
    data = {"foo": 42, "bar": [1, 2, 3], "nested": {"k": "v"}}
    cache.save("key1", data)
    loaded = cache.load("key1")
    assert loaded == data


def test_load_returns_none_for_missing_key(cache):
    assert cache.load("nonexistent") is None


def test_exists_reports_correctly(cache):
    cache.save("present", {"x": 1})
    assert cache.exists("present") is True
    assert cache.exists("absent") is False


def test_invalidate_removes_existing(cache):
    cache.save("key", {"value": "data"})
    assert cache.invalidate("key") is True
    assert cache.exists("key") is False


def test_invalidate_returns_false_for_missing(cache):
    assert cache.invalidate("never-saved") is False


def test_clear_all_removes_only_matching_prefix(tmp_path):
    cache_dir = tmp_path / "c"
    cache_a = CacheManager(cache_dir=cache_dir, prefix="a")
    cache_b = CacheManager(cache_dir=cache_dir, prefix="b")
    cache_a.save("k1", {"v": 1})
    cache_a.save("k2", {"v": 2})
    cache_b.save("k3", {"v": 3})
    removed = cache_a.clear_all()
    assert removed == 2
    assert cache_a.exists("k1") is False
    assert cache_b.exists("k3") is True  # prefix b unangetastet


def test_cache_size_increases_after_save(cache):
    initial = cache.get_cache_size()
    assert initial == 0
    cache.save("k", {"data": "x" * 1000})
    after = cache.get_cache_size()
    assert after > initial


def test_get_cache_info_has_required_keys(cache):
    cache.save("k1", {"v": 1})
    cache.save("k2", {"v": 2})
    info = cache.get_cache_info()
    assert info["file_count"] == 2
    assert info["total_size_bytes"] > 0
    assert info["total_size_mb"] >= 0
    assert info["prefix"] == "test"
    assert "cache_dir" in info


def test_ttl_expiry_removes_old_entries(tmp_path):
    cache = CacheManager(cache_dir=tmp_path / "ttl", prefix="t", ttl_seconds=1)
    cache.save("expiring", {"data": "fresh"})
    assert cache.load("expiring") is not None
    # Simulate age by patching the timestamp inside the file
    path = cache._get_cache_path("expiring")
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    old_ts = (datetime.now() - timedelta(seconds=5)).isoformat()
    data["_timestamp"] = old_ts
    path.write_text(json.dumps(data), encoding="utf-8")
    # Now load should return None and delete the file
    assert cache.load("expiring") is None
    assert not path.exists()


def test_load_handles_corrupt_json(tmp_path):
    cache = CacheManager(cache_dir=tmp_path / "c", prefix="x")
    cache_file = cache._get_cache_path("key")
    cache_file.write_text("{not json", encoding="utf-8")
    assert cache.load("key") is None
    assert not cache_file.exists()  # corrupt file removed


def test_different_keys_yield_different_paths(cache):
    p1 = cache._get_cache_path("key_a")
    p2 = cache._get_cache_path("key_b")
    assert p1 != p2
