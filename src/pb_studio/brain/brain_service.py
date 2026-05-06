"""BrainService — Singleton der Brain-Pipeline (Plan Phase 3+4).

Hält BrainStore + WeightStore + Reranker + SmartSampler + FeedbackLogger
in einer langlebigen Instanz. Wird vom backend (FastAPI) als Dependency
injiziert.

Recovery: Bei Korruption von weights.db wird Backup-Restore versucht
(falls vorhanden), sonst Cold-Start mit leerem Schema.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from ..storage.brain_store import BrainStore, default_brain_dir
from ..storage.migration_runner import migrate
from ..storage.sqlite_init import init_connection
from .feedback_logger import FeedbackLogger
from .reranker import BrainReranker
from .smart_sampler import SmartSampler
from .weight_store import WeightStore

logger = logging.getLogger(__name__)


class BrainService:
    """Singleton: BrainStore + projektspezifischer state.db + 4 Helfer."""

    _instance: Optional["BrainService"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        *,
        brain_dir: Optional[str | Path] = None,
        state_db_path: Optional[str | Path] = None,
    ):
        self.brain = BrainStore(brain_dir or default_brain_dir())
        self.weights = WeightStore(self.brain.weights_conn)
        self.reranker = BrainReranker(weight_store=self.weights)
        self.sampler = SmartSampler(self.weights)

        self.state_conn: Optional[sqlite3.Connection] = None
        if state_db_path:
            self.bind_project_state(state_db_path)

    def bind_project_state(self, state_db_path: str | Path) -> None:
        """Attach project-store state.db (timeline + feedback events)."""
        path = Path(state_db_path)
        mig = (
            Path(__file__).parent.parent
            / "storage" / "migrations" / "state"
        )
        migrate(path, mig)
        if self.state_conn is not None:
            try:
                self.state_conn.close()
            except Exception:
                pass
        conn = sqlite3.connect(
            str(path), isolation_level=None, check_same_thread=False
        )
        init_connection(conn)
        self.state_conn = conn

    @property
    def feedback_logger(self) -> FeedbackLogger:
        if self.state_conn is None:
            raise RuntimeError(
                "BrainService.bind_project_state() must be called first"
            )
        return FeedbackLogger(
            weight_store=self.weights, state_conn=self.state_conn
        )

    def close(self) -> None:
        if self.state_conn is not None:
            try:
                self.state_conn.close()
            except Exception:
                pass
        self.brain.close()

    @classmethod
    def get(cls, **kwargs) -> "BrainService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset_singleton(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
            cls._instance = None
