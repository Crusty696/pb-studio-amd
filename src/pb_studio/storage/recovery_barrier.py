"""Process-wide write barrier used by crash-consistent recovery snapshots."""

from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
import inspect
import threading
import time
from typing import Callable, Iterator, TypeVar


class RecoveryBusyError(RuntimeError):
    """A product write or snapshot could not enter the recovery barrier."""


class RecoveryWriteBarrier:
    """Reject new writes while a snapshot drains already active owners."""

    def __init__(self) -> None:
        self._condition = threading.Condition(threading.RLock())
        self._snapshot_pending = False
        self._snapshot_owner: int | None = None
        self._active_writes = 0
        self._active_by_owner: dict[str, int] = {}

    @contextmanager
    def write_lease(self, owner: str) -> Iterator[None]:
        normalized = str(owner).strip()
        if not normalized:
            raise ValueError("Recovery write owner must not be empty")
        with self._condition:
            if (
                self._snapshot_pending
                and self._snapshot_owner != threading.get_ident()
            ):
                raise RecoveryBusyError("Recovery snapshot is draining product writes")
            self._active_writes += 1
            self._active_by_owner[normalized] = (
                self._active_by_owner.get(normalized, 0) + 1
            )
        try:
            yield
        finally:
            with self._condition:
                self._active_writes -= 1
                remaining = self._active_by_owner[normalized] - 1
                if remaining:
                    self._active_by_owner[normalized] = remaining
                else:
                    self._active_by_owner.pop(normalized, None)
                self._condition.notify_all()

    @contextmanager
    def snapshot_lease(self, *, timeout: float = 60.0) -> Iterator[None]:
        if timeout < 0:
            raise ValueError("Recovery snapshot timeout must be non-negative")
        thread_id = threading.get_ident()
        deadline = time.monotonic() + timeout
        with self._condition:
            if self._snapshot_pending:
                raise RecoveryBusyError("Another recovery snapshot is active")
            self._snapshot_pending = True
            self._snapshot_owner = thread_id
            while self._active_writes:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    active = ", ".join(
                        f"{owner}={count}"
                        for owner, count in sorted(self._active_by_owner.items())
                    )
                    self._snapshot_pending = False
                    self._snapshot_owner = None
                    self._condition.notify_all()
                    raise RecoveryBusyError(
                        f"Recovery snapshot timed out draining writes: {active}"
                    )
                self._condition.wait(timeout=remaining)
        try:
            yield
        finally:
            with self._condition:
                if self._snapshot_owner != thread_id:
                    raise RuntimeError("Recovery snapshot lease ownership changed")
                self._snapshot_pending = False
                self._snapshot_owner = None
                self._condition.notify_all()

    def assert_snapshot_lease(self) -> None:
        with self._condition:
            if not self._snapshot_pending or self._snapshot_owner != threading.get_ident():
                raise RecoveryBusyError("Recovery snapshot lease is required")

    def active_writes(self) -> dict[str, int]:
        with self._condition:
            return dict(self._active_by_owner)


_barrier = RecoveryWriteBarrier()


def get_recovery_write_barrier() -> RecoveryWriteBarrier:
    return _barrier


_F = TypeVar("_F", bound=Callable)


def recovery_write_operation(owner: str) -> Callable[[_F], _F]:
    """Decorate a synchronous or asynchronous product write operation."""

    def decorate(function: _F) -> _F:
        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def async_wrapper(*args, **kwargs):
                with _barrier.write_lease(owner):
                    return await function(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @wraps(function)
        def wrapper(*args, **kwargs):
            with _barrier.write_lease(owner):
                return function(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorate


__all__ = [
    "RecoveryBusyError",
    "RecoveryWriteBarrier",
    "get_recovery_write_barrier",
    "recovery_write_operation",
]
