"""FeedbackLogger — atomic 5-level update + raw event log (Plan Decision #11).

Mapping: perfect=(α+2,β+0) | fits=(α+1,β+0) | not_quite=(α+0,β+1) | no_match=(α+0,β+2)
Pro Klick: 17 Achsen × 5 Levels = 85 Bucket-Updates in einer Transaktion.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .bridge_dimensions import BRIDGE_AXES
from .weight_store import WeightStore

logger = logging.getLogger(__name__)

RATING_MAP: dict[str, tuple[float, float]] = {
    "perfect":   (2.0, 0.0),
    "fits":      (1.0, 0.0),
    "not_quite": (0.0, 1.0),
    "no_match":  (0.0, 2.0),
}


class FeedbackLogger:
    """Persistiert Klick-Roh-Events (state.db) + bumped buckets (weights.db)."""

    def __init__(
        self,
        *,
        weight_store: WeightStore,
        state_conn: sqlite3.Connection,
    ):
        self.weights = weight_store
        self.state_conn = state_conn

    def log_feedback(
        self,
        *,
        cut_id: int,
        rating: str,
        context_keys: list[str],
        timestamp: Optional[str] = None,
    ) -> int:
        """Returns number of bucket updates performed (17 * len(context_keys))."""
        if rating not in RATING_MAP:
            raise ValueError(f"unknown rating: {rating}")
        alpha_delta, beta_delta = RATING_MAP[rating]
        ts = timestamp or datetime.now(timezone.utc).isoformat()

        self.state_conn.execute(
            "INSERT INTO feedback_events (cut_id, rating, alpha_delta, "
            "beta_delta, context_keys_json, timestamp) VALUES (?,?,?,?,?,?)",
            (
                int(cut_id), rating,
                float(alpha_delta), float(beta_delta),
                json.dumps(context_keys), ts,
            ),
        )

        bumps = 0
        try:
            self.weights.conn.execute("BEGIN IMMEDIATE")
            for axis in BRIDGE_AXES:
                for level, key in enumerate(context_keys):
                    self.weights.update(
                        axis, level, key,
                        alpha_delta=alpha_delta,
                        beta_delta=beta_delta,
                        now_iso=ts,
                        invalidate=False,
                    )
                    bumps += 1
            self.weights.conn.execute("COMMIT")
            self.weights._invalidate()  # Einmalige Invalidierung nach erfolgreichem COMMIT
        except Exception:
            self.weights.conn.execute("ROLLBACK")
            raise
        return bumps
