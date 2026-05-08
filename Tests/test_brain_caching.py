"""R-Brain-08: Tests fuer WeightStore in-memory caching.

Verifiziert:
- Hit nach Miss
- Cache-Invalidation bei update()
- Cache-Invalidation bei reset()
- LRU-Eviction wenn cache_max ueberschritten
- Cache-Stats korrekt
- Thread-Safety unter Concurrent-Reads
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from pb_studio.brain.weight_store import WeightStore


@pytest.fixture
def ws(tmp_path: Path) -> WeightStore:
    return WeightStore.from_path(str(tmp_path / "w.db"))


def test_first_call_is_miss_second_is_hit(ws):
    ws.get_posterior_mean("beat_weight", ["", "section=drop"])
    s1 = ws.cache_stats()
    assert s1["misses"] == 1
    assert s1["hits"] == 0

    ws.get_posterior_mean("beat_weight", ["", "section=drop"])
    s2 = ws.cache_stats()
    assert s2["hits"] == 1
    assert s2["misses"] == 1  # unchanged


def test_different_keys_are_separate_entries(ws):
    ws.get_posterior_mean("beat_weight", ["", "a"])
    ws.get_posterior_mean("beat_weight", ["", "b"])
    ws.get_posterior_mean("kick_weight", ["", "a"])
    s = ws.cache_stats()
    assert s["posterior_size"] == 3
    assert s["misses"] == 3


def test_variance_cache_separate_from_posterior(ws):
    ws.get_posterior_mean("beat_weight", [""])
    ws.get_variance("beat_weight", [""])
    s = ws.cache_stats()
    assert s["posterior_size"] == 1
    assert s["variance_size"] == 1


def test_update_invalidates_cache(ws):
    ws.get_posterior_mean("beat_weight", ["", "section=drop"])
    ws.get_variance("beat_weight", ["", "section=drop"])
    s_before = ws.cache_stats()
    assert s_before["posterior_size"] == 1
    assert s_before["variance_size"] == 1

    ws.update("beat_weight", 0, "", alpha_delta=1.0, beta_delta=0.0)
    s_after = ws.cache_stats()
    assert s_after["posterior_size"] == 0
    assert s_after["variance_size"] == 0
    assert s_after["version"] > s_before["version"]


def test_reset_invalidates_cache(ws):
    ws.get_posterior_mean("beat_weight", [""])
    assert ws.cache_stats()["posterior_size"] == 1
    ws.reset()
    assert ws.cache_stats()["posterior_size"] == 0


def test_cache_returns_consistent_value_with_underlying_data(ws):
    """Nach 20 perfect-clicks (alpha=40 am bucket) sollte posterior > 0.95."""
    from pb_studio.brain.bridge_dimensions import BRIDGE_AXES
    ck = ["", "section=drop"]
    # simuliere viele clicks
    for _ in range(20):
        for axis in BRIDGE_AXES:
            for level, key in enumerate(ck):
                ws.update(axis, level, key, alpha_delta=2.0, beta_delta=0.0)

    p1 = ws.get_posterior_mean("beat_weight", ck)
    p2 = ws.get_posterior_mean("beat_weight", ck)  # cached
    assert p1 == p2
    assert p1 > 0.9  # alpha=40 -> (40+1)/(40+2) = 0.976...


def test_lru_eviction_when_over_limit(tmp_path):
    ws = WeightStore.from_path(str(tmp_path / "w.db"), cache_max=64)
    # fuelle bis zur Eviction
    for i in range(80):
        ws.get_posterior_mean(f"axis_{i}", [""])
    s = ws.cache_stats()
    assert s["posterior_size"] <= 64
    assert s["posterior_size"] >= 32  # nur ~25% evicted, Rest bleibt


def test_cache_stats_structure(ws):
    s = ws.cache_stats()
    assert set(s.keys()) >= {
        "version", "posterior_size", "variance_size",
        "hits", "misses", "max_size",
    }


def test_concurrent_reads_thread_safe(ws):
    """16 threads × 100 calls -> kein crash, results konsistent."""
    from pb_studio.brain.bridge_dimensions import BRIDGE_AXES
    ws.update("beat_weight", 0, "", alpha_delta=10.0, beta_delta=0.0)
    expected = ws.get_posterior_mean("beat_weight", [""])

    results: list[float] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def worker():
        try:
            for _ in range(100):
                v = ws.get_posterior_mean("beat_weight", [""])
                with lock:
                    results.append(v)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(results) == 1600
    assert all(r == expected for r in results)


def test_cache_speedup_on_repeated_calls(ws):
    """Sanity-Check: Cache-Hits sollten in Stats steigen, Misses gleich bleiben."""
    from pb_studio.brain.bridge_dimensions import BRIDGE_AXES
    # 17 axes × 6 backoff-levels durchpfluegen, dann nochmal -> alle hits
    ck = ["", "s=a", "s=a|m=b", "s=a|m=b|mo=c",
          "s=a|m=b|mo=c|e=d", "s=a|m=b|mo=c|e=d|p=f|sp=g"]
    for axis in BRIDGE_AXES:
        ws.get_posterior_mean(axis, ck)
        ws.get_variance(axis, ck)
    misses_after_first = ws.cache_stats()["misses"]
    assert misses_after_first == 34  # 17 axes × 2 fns

    # zweite Runde -> alle hits
    for axis in BRIDGE_AXES:
        ws.get_posterior_mean(axis, ck)
        ws.get_variance(axis, ck)
    s = ws.cache_stats()
    assert s["misses"] == 34  # unchanged
    assert s["hits"] == 34


def test_update_clears_both_caches_not_just_one(ws):
    """update() muss BEIDE caches (posterior + variance) leeren."""
    ws.get_posterior_mean("beat_weight", [""])
    ws.get_variance("beat_weight", [""])
    assert ws.cache_stats()["posterior_size"] == 1
    assert ws.cache_stats()["variance_size"] == 1

    ws.update("beat_weight", 0, "", alpha_delta=1.0, beta_delta=1.0)
    s = ws.cache_stats()
    assert s["posterior_size"] == 0
    assert s["variance_size"] == 0
