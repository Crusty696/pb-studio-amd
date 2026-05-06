"""Beta-Bernoulli WeightStore mit Hierarchical Backoff (Plan Phase 3 + Section 5).

Posterior Mean: (alpha + 1) / (alpha + beta + 2)
Variance:       (alpha*beta) / ((alpha+beta)^2 * (alpha+beta+1))

Backoff: lookup vom spezifischsten Level (5) zum allgemeinsten (0); erstes
Bucket mit n_samples >= MIN_CONFIDENT_SAMPLES gewinnt. Sonst Cold-Start-Default.

Verwendet `weights_conn` aus BrainStore. Atomic-Updates über Transaktionen.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .cold_start import COLD_START_DEFAULTS

logger = logging.getLogger(__name__)

MIN_CONFIDENT_SAMPLES = 10


class WeightStore:
    """Wraps the weights.db connection."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        cold_start_defaults: Optional[dict[str, float]] = None,
    ):
        self.conn = conn
        self.defaults = dict(cold_start_defaults or COLD_START_DEFAULTS)

    @classmethod
    def from_path(
        cls, db_path: str, *, cold_start_defaults: Optional[dict[str, float]] = None
    ) -> "WeightStore":
        from ..storage.migration_runner import migrate
        from ..storage.sqlite_init import init_connection
        from pathlib import Path

        mig_dir = Path(__file__).parent.parent / "storage" / "migrations" / "weights"
        migrate(db_path, mig_dir)
        conn = sqlite3.connect(db_path, isolation_level=None)
        init_connection(conn)
        return cls(conn, cold_start_defaults=cold_start_defaults)

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

    def get_posterior_mean(
        self, axis: str, context_keys: list[str]
    ) -> float:
        """Hierarchical backoff: most-specific confident bucket wins."""
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

    def get_variance(
        self, axis: str, context_keys: list[str]
    ) -> float:
        """Bayes variance for smart-sampling."""
        # Use the most-specific bucket that exists at all (even sub-confident).
        for level in range(len(context_keys) - 1, -1, -1):
            row = self.get_alpha_beta(axis, level, context_keys[level])
            if row is None:
                continue
            alpha, beta = row
            denom = (alpha + beta) ** 2 * (alpha + beta + 1) + 1e-9
            return (alpha * beta) / denom
        # Cold-start: maximum variance (1/4 = Beta(1,1) variance = 1/12; use 0.25 for prio)
        return 0.25

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

    def total_clicks(self) -> int:
        # Sum at level 0, key "" (incremented on every click for every axis)
        row = self.conn.execute(
            "SELECT COALESCE(SUM(positive_count + negative_count), 0) "
            "FROM axis_weights WHERE context_level = 0 AND context_key = ''"
        ).fetchone()
        if row is None:
            return 0
        # Each click updates 17 axes at level 0 -> divide
        return int(round(float(row[0]) / max(1, len(self.defaults))))

    def reset(self) -> None:
        self.conn.execute("DELETE FROM axis_weights")
