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
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional, TypeVar

from ..storage.brain_store import BrainStore, default_brain_dir
from ..storage.migration_runner import migrate, migrate_project_state
from ..storage.sqlite_init import init_connection
from .feedback_logger import FeedbackLogger
from .reranker import BrainReranker
from .smart_sampler import SmartSampler
from .weight_store import WeightStore

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


class BrainProjectNotBoundError(RuntimeError):
    """No project state connection is currently available."""


class StaleBrainProjectLeaseError(RuntimeError):
    """A project-state lease no longer belongs to the active project."""


@dataclass(frozen=True)
class BrainProjectIdentity:
    """Immutable identity bound to one project-state connection generation."""

    state_db_path: Path
    epoch: int
    project_id: Optional[int] = None
    project_uuid: Optional[str] = None


@dataclass(eq=False)
class _ProjectConnectionSlot:
    connection: sqlite3.Connection
    identity: Optional[BrainProjectIdentity]
    lease_count: int = 0
    retired: bool = False
    closed: bool = False


class BrainStateLease:
    """Keeps one project connection alive across async/threaded work."""

    def __init__(
        self,
        service: "BrainService",
        slot: _ProjectConnectionSlot,
    ):
        self._service = service
        self._slot = slot
        self._released = False

    def __enter__(self) -> "BrainStateLease":
        if self._released:
            raise RuntimeError("Brain project-state lease is already released")
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.release()

    @property
    def connection(self) -> sqlite3.Connection:
        if self._released:
            raise RuntimeError("Brain project-state lease is already released")
        return self._slot.connection

    @property
    def state_conn(self) -> sqlite3.Connection:
        """Compatibility alias for consumers that pass a state connection."""
        return self.connection

    @property
    def identity(self) -> BrainProjectIdentity:
        identity = self._slot.identity
        if identity is None:
            raise RuntimeError("Brain project-state lease has no project identity")
        return identity

    @property
    def state_db_path(self) -> Path:
        return self.identity.state_db_path

    @property
    def project_epoch(self) -> int:
        return self.identity.epoch

    @property
    def project_id(self) -> Optional[int]:
        return self.identity.project_id

    @property
    def project_uuid(self) -> Optional[str]:
        return self.identity.project_uuid

    @property
    def is_current(self) -> bool:
        return self._service._is_current_project_state_lease(self)

    def require_current_for_write(self) -> None:
        """Reject a mutation after the project connection has been swapped."""
        self._service._require_current_project_state_lease(self)

    @contextmanager
    def write_connection(self) -> Iterator[sqlite3.Connection]:
        """Linearize a complete mutation against project-state swaps."""
        with self._service._state_binding_lock:
            self._service._require_current_project_state_lease_locked(self)
            yield self._slot.connection

    def run_write(
        self,
        operation: Callable[[sqlite3.Connection], _T],
    ) -> _T:
        """Run a project mutation only while this lease is still current."""
        with self.write_connection() as connection:
            return operation(connection)

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._service._release_project_state_lease(self._slot)


class BrainService:
    """Singleton: BrainStore + projektspezifischer state.db + 4 Helfer."""

    _instance: Optional["BrainService"] = None
    _lock = threading.Lock()
    _state_runtime_init_lock = threading.Lock()

    def __init__(
        self,
        *,
        brain_dir: Optional[str | Path] = None,
        state_db_path: Optional[str | Path] = None,
    ):
        self.brain = BrainStore(brain_dir or default_brain_dir())
        # Review-Fix HIGH-3 (2026-07-09): Lock teilen, damit BrainStore.close()
        # nicht unter laufenden WeightStore-Queries zuschlaegt.
        self.weights = WeightStore(self.brain.weights_conn, lock=self.brain._weights_lock)
        self.reranker = BrainReranker(weight_store=self.weights)
        self.sampler = SmartSampler(self.weights)
        self.feedback_outbox_path = self.brain.brain_dir / "feedback_outbox.json"

        self._state_binding_lock = threading.RLock()
        self._state_slots: list[_ProjectConnectionSlot] = []
        self._current_state_slot: Optional[_ProjectConnectionSlot] = None
        self._state_binding_generation = 0
        self._state_close_requested = False
        self._brain_store_closed = False
        self.state_conn: Optional[sqlite3.Connection] = None
        if state_db_path:
            self.bind_project_state(state_db_path)

    @staticmethod
    def _canonical_state_path(state_db_path: str | Path) -> Path:
        return Path(state_db_path).resolve()

    def _ensure_state_lease_runtime(self) -> None:
        """Initialize lease state for legacy ``__new__`` test instances."""
        if hasattr(self, "_state_binding_lock"):
            return
        with type(self)._state_runtime_init_lock:
            if hasattr(self, "_state_binding_lock"):
                return
            self._state_binding_lock = threading.RLock()
            self._state_slots = []
            self._current_state_slot = None
            self._state_binding_generation = 0
            self._state_close_requested = False
            self._brain_store_closed = False
            old_connection = getattr(self, "state_conn", None)
            if old_connection is not None:
                slot = _ProjectConnectionSlot(old_connection, identity=None)
                self._state_slots.append(slot)
                self._current_state_slot = slot

    def bind_project_state(
        self,
        state_db_path: str | Path,
        *,
        project_epoch: Optional[int] = None,
        project_id: Optional[int] = None,
        project_uuid: Optional[str] = None,
    ) -> BrainProjectIdentity:
        """Open and atomically publish a project-store state connection.

        The replacement connection is fully initialized before publication.
        Existing leases retain the previous connection until their last
        release; mutations on such retired leases are rejected.
        """
        self._ensure_state_lease_runtime()
        path = self._canonical_state_path(state_db_path)
        mig = (
            Path(__file__).parent.parent
            / "storage" / "migrations" / "state"
        )
        normalized_project_uuid = (
            str(uuid.UUID(str(project_uuid)))
            if project_uuid is not None
            else str(uuid.uuid5(uuid.NAMESPACE_URL, path.as_uri()))
        )
        if project_uuid is None:
            logger.warning(
                "Brain state %s was bound without catalog project_uuid; "
                "using deterministic standalone identity",
                path,
            )
        if project_uuid is None:
            migrate(path, mig)
        else:
            migrate_project_state(
                path,
                mig,
                project_uuid=normalized_project_uuid,
            )

        new_connection: Optional[sqlite3.Connection] = None
        try:
            new_connection = sqlite3.connect(
                str(path), isolation_level=None, check_same_thread=False
            )
            init_connection(new_connection)
            if hasattr(self, "weights") and hasattr(self, "feedback_outbox_path"):
                FeedbackLogger(
                    weight_store=self.weights,
                    state_conn=new_connection,
                    outbox_path=self.feedback_outbox_path,
                ).recover_pending()
        except Exception:
            if new_connection is not None:
                try:
                    new_connection.close()
                except Exception:
                    pass
            raise

        connection_to_close: Optional[sqlite3.Connection] = None
        with self._state_binding_lock:
            if self._state_close_requested:
                connection_to_close = new_connection
                new_connection = None
            else:
                self._state_binding_generation += 1
                epoch = (
                    int(project_epoch)
                    if project_epoch is not None
                    else self._state_binding_generation
                )
                identity = BrainProjectIdentity(
                    state_db_path=path,
                    epoch=epoch,
                    project_id=(
                        int(project_id) if project_id is not None else None
                    ),
                    project_uuid=normalized_project_uuid,
                )
                new_slot = _ProjectConnectionSlot(new_connection, identity)
                self._state_slots.append(new_slot)

                old_slot = self._current_state_slot
                self._current_state_slot = new_slot
                self.state_conn = new_connection
                if old_slot is not None:
                    connection_to_close = self._retire_slot_locked(old_slot)

        if new_connection is None:
            self._close_state_connection(connection_to_close)
            raise RuntimeError("BrainService is closing")
        self._close_state_connection(connection_to_close)
        return identity

    def project_state_lease(
        self,
        *,
        state_db_path: Optional[str | Path] = None,
        project_epoch: Optional[int] = None,
        project_id: Optional[int] = None,
    ) -> BrainStateLease:
        """Acquire the current connection with optional identity checks."""
        self._ensure_state_lease_runtime()
        expected_path = (
            self._canonical_state_path(state_db_path)
            if state_db_path is not None
            else None
        )
        with self._state_binding_lock:
            slot = self._current_state_slot
            if (
                slot is None
                or slot.retired
                or slot.closed
                or self._state_close_requested
            ):
                raise BrainProjectNotBoundError("No project bound")
            identity = slot.identity
            if identity is None:
                raise BrainProjectNotBoundError(
                    "Current Brain project connection has no identity"
                )
            if (
                (expected_path is not None and identity.state_db_path != expected_path)
                or (project_epoch is not None and identity.epoch != int(project_epoch))
                or (project_id is not None and identity.project_id != int(project_id))
            ):
                raise StaleBrainProjectLeaseError(
                    "Brain project identity does not match the active project"
                )
            slot.lease_count += 1
            return BrainStateLease(self, slot)

    acquire_project_state_lease = project_state_lease

    @property
    def project_state_identity(self) -> Optional[BrainProjectIdentity]:
        self._ensure_state_lease_runtime()
        with self._state_binding_lock:
            slot = self._current_state_slot
            return None if slot is None else slot.identity

    @property
    def feedback_logger(self) -> FeedbackLogger:
        if self.state_conn is None:
            raise RuntimeError(
                "BrainService.bind_project_state() must be called first"
            )
        return FeedbackLogger(
            weight_store=self.weights,
            state_conn=self.state_conn,
            outbox_path=self.feedback_outbox_path,
        )

    def feedback_logger_for_lease(
        self,
        lease: BrainStateLease,
    ) -> FeedbackLogger:
        if lease._service is not self:
            raise ValueError("Brain project-state lease belongs to another service")
        return FeedbackLogger(
            weight_store=self.weights,
            state_conn=lease.connection,
            outbox_path=self.feedback_outbox_path,
        )

    def close(self) -> None:
        self._ensure_state_lease_runtime()
        connections_to_close: list[sqlite3.Connection] = []
        close_brain_store = False
        with self._state_binding_lock:
            self._state_close_requested = True
            current_slot = self._current_state_slot
            self._current_state_slot = None
            self.state_conn = None
            if current_slot is not None:
                connection = self._retire_slot_locked(current_slot)
                if connection is not None:
                    connections_to_close.append(connection)
            close_brain_store = self._claim_brain_store_close_locked()

        for connection in connections_to_close:
            self._close_state_connection(connection)
        if close_brain_store:
            self.brain.close()

    def unbind_project_state(self) -> None:
        """L-STATE-4: Loest state_conn vom aktuellen Projekt — wird beim
        /project/close gerufen damit /brain/feedback nicht weiter in die
        alte state.db schreibt. brain (cold-state) bleibt erhalten."""
        self._ensure_state_lease_runtime()
        connection_to_close: Optional[sqlite3.Connection] = None
        with self._state_binding_lock:
            current_slot = self._current_state_slot
            self._current_state_slot = None
            self.state_conn = None
            if current_slot is not None:
                connection_to_close = self._retire_slot_locked(current_slot)
        self._close_state_connection(connection_to_close)

    def _is_current_project_state_lease(self, lease: BrainStateLease) -> bool:
        self._ensure_state_lease_runtime()
        with self._state_binding_lock:
            return (
                not lease._released
                and not self._state_close_requested
                and self._current_state_slot is lease._slot
                and not lease._slot.retired
                and not lease._slot.closed
            )

    def _require_current_project_state_lease(
        self,
        lease: BrainStateLease,
    ) -> None:
        self._ensure_state_lease_runtime()
        with self._state_binding_lock:
            self._require_current_project_state_lease_locked(lease)

    def _require_current_project_state_lease_locked(
        self,
        lease: BrainStateLease,
    ) -> None:
        if (
            lease._service is not self
            or lease._released
            or self._state_close_requested
            or self._current_state_slot is not lease._slot
            or lease._slot.retired
            or lease._slot.closed
        ):
            raise StaleBrainProjectLeaseError(
                "Brain project changed before the mutation could commit"
            )

    def _release_project_state_lease(
        self,
        slot: _ProjectConnectionSlot,
    ) -> None:
        connection_to_close: Optional[sqlite3.Connection] = None
        close_brain_store = False
        with self._state_binding_lock:
            if slot.lease_count <= 0:
                raise RuntimeError("Brain project-state lease underflow")
            slot.lease_count -= 1
            if slot.retired and slot.lease_count == 0:
                connection_to_close = self._claim_slot_close_locked(slot)
            close_brain_store = self._claim_brain_store_close_locked()
        self._close_state_connection(connection_to_close)
        if close_brain_store:
            self.brain.close()

    def _retire_slot_locked(
        self,
        slot: _ProjectConnectionSlot,
    ) -> Optional[sqlite3.Connection]:
        slot.retired = True
        if slot.lease_count == 0:
            return self._claim_slot_close_locked(slot)
        return None

    def _claim_slot_close_locked(
        self,
        slot: _ProjectConnectionSlot,
    ) -> Optional[sqlite3.Connection]:
        if slot.closed:
            return None
        slot.closed = True
        if slot in self._state_slots:
            self._state_slots.remove(slot)
        return slot.connection

    def _claim_brain_store_close_locked(self) -> bool:
        if (
            self._state_close_requested
            and not self._brain_store_closed
            and all(slot.lease_count == 0 for slot in self._state_slots)
        ):
            self._brain_store_closed = True
            return True
        return False

    @staticmethod
    def _close_state_connection(
        connection: Optional[sqlite3.Connection],
    ) -> None:
        if connection is None:
            return
        try:
            connection.close()
        except Exception as close_error:
            logger.warning(
                "Retired project state connection could not be closed: %s",
                close_error,
            )

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
        import gc
        gc.collect()
