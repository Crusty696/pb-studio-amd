"""Beta-Bernoulli WeightStore mit Hierarchical Backoff
(Plan Phase 3 + Section 5 + R-Brain-08 caching).

Posterior Mean: (alpha + 1) / (alpha + beta + 2)
Variance:       (alpha*beta) / ((alpha+beta)^2 * (alpha+beta+1))

Backoff: lookup vom spezifischsten Level (5) zum allgemeinsten (0); erstes
Bucket mit n_samples >= MIN_CONFIDENT_SAMPLES gewinnt fuer posterior. Sonst
Cold-Start-Default.

Verwendet `weights_conn` aus BrainStore. Atomic-Updates ueber Transaktionen.

R-Brain-08: In-Memory Cache fuer get_posterior_mean / get_variance.
- Key: (axis, tuple(context_keys), version)
- Version-Counter inkrementiert in update()/reset() -> automatische Invalidation
- Cache-Miss laeuft das alte SQL-basierte Lookup
- Cache-Hit spart 1-6 SQLite-Queries pro Aufruf

Thread-Safety: cache lock + write-lock um version-bump+SQL-update.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

from .cold_start import COLD_START_DEFAULTS

logger = logging.getLogger(__name__)

MIN_CONFIDENT_SAMPLES = 10
# Cache-Limits: 17 axes × ~50 typischer kontexte × 5 backoff-levels grob 4250.
# 8000 Slots geben gen. Headroom; LRU eviction sobald ueberschritten.
_DEFAULT_CACHE_MAX = 8000


class WeightStore:
    """Wraps the weights.db connection."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        cold_start_defaults: Optional[dict[str, float]] = None,
        cache_max: int = _DEFAULT_CACHE_MAX,
    ):
        self.conn = conn
        self.defaults = dict(cold_start_defaults or COLD_START_DEFAULTS)
        # R-Brain-08 caching
        self._version: int = 0
        self._lock = threading.Lock()
        self._posterior_cache: dict[tuple, float] = {}
        self._variance_cache: dict[tuple, float] = {}
        self._cache_max = max(64, int(cache_max))
        self._cache_hits = 0
        self._cache_misses = 0

    @classmethod
    def from_path(
        cls, db_path: str,
        *, cold_start_defaults: Optional[dict[str, float]] = None,
        cache_max: int = _DEFAULT_CACHE_MAX,
    ) -> "WeightStore":
        from ..storage.migration_runner import migrate
        from ..storage.sqlite_init import init_connection
        from pathlib import Path

        mig_dir = Path(__file__).parent.parent / "storage" / "migrations" / "weights"
        migrate(db_path, mig_dir)
        conn = sqlite3.connect(
            db_path, isolation_level=None, check_same_thread=False
        )
        init_connection(conn)
        return cls(conn, cold_start_defaults=cold_start_defaults,
                   cache_max=cache_max)

    # ---------- raw SQL ----------

    def get_alpha_beta(
        self, axis: str, level: int, key: str
    ) -> Optional[tuple[float, float]]:
        row = self.conn.execute(
            "SELECT positive_count, negative_count FROM axis_weights "
            "WHERE axis = ? AND context_level = ? AND context_key = ?",
            (axis, level, key),
        ).fetchone()
        if row is None:
            return None
        return float(row[0]), float(row[1])

    # ---------- cached read API ----------

    def get_posterior_mean(
        self, axis: str, context_keys: list[str]
    ) -> float:
        """Hierarchical backoff: most-specific confident bucket wins.

        Cached: O(1) hit, O(L) miss where L = len(context_keys).
        """
        cache_key = (axis, tuple(context_keys))
        with self._lock:
            cached = self._posterior_cache.get(cache_key)
            if cached is not None:
                self._cache_hits += 1
                return cached

        # B-6 FIX: Version vor Compute speichern, um Race Condition zu vermeiden
        current_version = self._version
        value = self._compute_posterior_mean(axis, context_keys)
        with self._lock:
            if self._version == current_version:
                self._cache_misses += 1
                self._evict_if_needed(self._posterior_cache)
                self._posterior_cache[cache_key] = value
        return value

    def get_variance(
        self, axis: str, context_keys: list[str]
    ) -> float:
        """Bayes variance for smart-sampling. Cached analog zu posterior."""
        cache_key = (axis, tuple(context_keys))
        with self._lock:
            cached = self._variance_cache.get(cache_key)
            if cached is not None:
                self._cache_hits += 1
                return cached

        current_version = self._version
        value = self._compute_variance(axis, context_keys)
        with self._lock:
            if self._version == current_version:
                self._cache_misses += 1
                self._evict_if_needed(self._variance_cache)
                self._variance_cache[cache_key] = value
        return value

    # ---------- write API (invalidates cache) ----------

    def update(
        self,
        axis: str,
        level: int,
        key: str,
        *,
        alpha_delta: float,
        beta_delta: float,
        now_iso: Optional[str] = None,
    ) -> None:
        ts = now_iso or datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO axis_weights (axis, context_level, context_key, "
            "positive_count, negative_count, last_updated) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(axis, context_level, context_key) DO UPDATE SET "
            "positive_count = positive_count + ?, "
            "negative_count = negative_count + ?, "
            "last_updated   = excluded.last_updated",
            (axis, level, key, alpha_delta, beta_delta, ts, alpha_delta, beta_delta),
        )
        self._invalidate()

    def reset(self) -> None:
        self.conn.execute("DELETE FROM axis_weights")
        self._invalidate()

    # ---------- diagnostics ----------

    def total_clicks(self) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(positive_count + negative_count), 0) "
            "FROM axis_weights WHERE context_level = 0 AND context_key = ''"
        ).fetchone()
        if row is None:
            return 0
        return int(round(float(row[0]) / max(1, len(self.defaults))))

    def cache_stats(self) -> dict:
        """R-Brain-08: liefert Hit/Miss-Stats fuer Diagnostik."""
        with self._lock:
            return {
                "version": self._version,
                "posterior_size": len(self._posterior_cache),
                "variance_size": len(self._variance_cache),
                "hits": self._cache_hits,
                "misses": self._cache_misses,
                "max_size": self._cache_max,
            }

    # ---------- internals ----------

    def _compute_posterior_mean(
        self, axis: str, context_keys: list[str]
    ) -> float:
        for level in range(len(context_keys) - 1, -1, -1):
            key = context_keys[level]
            row = self.get_alpha_beta(axis, level, key)
            if row is None:
                continue
            alpha, beta = row
            n = alpha + beta
            if n >= MIN_CONFIDENT_SAMPLES:
                return (alpha + 1.0) / (alpha + beta + 2.0)
        return float(self.defaults.get(axis, 0.5))

    def _compute_variance(
        self, axis: str, context_keys: list[str]
    ) -> float:
        for level in range(len(context_keys) - 1, -1, -1):
            row = self.get_alpha_beta(axis, level, context_keys[level])
            if row is None:
                continue
            alpha, beta = row
            if alpha + beta < 1e-6:
                return 0.25
            denom = (alpha + beta) ** 2 * (alpha + beta + 1) + 1e-9
            var = (alpha * beta) / denom
            if var != var:  # NaN-guard
                return 0.25
            return var
        return 0.25

    def _invalidate(self) -> None:
        """Drop cache + bump version. Called on update()/reset()."""
        with self._lock:
            self._version += 1
            self._posterior_cache.clear()
            self._variance_cache.clear()

    def _evict_if_needed(self, cache: dict) -> None:
        """Simple LRU-light: drop oldest 25% wenn ueber Limit (FIFO).
        Held with self._lock by caller.
        """
        if len(cache) >= self._cache_max:
            drop = max(1, self._cache_max // 4)
            for k in list(cache.keys())[:drop]:
                cache.pop(k, None)
