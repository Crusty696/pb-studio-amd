from __future__ import annotations

import asyncio
import threading

import pytest

from pb_studio.storage.recovery_barrier import (
    RecoveryBusyError,
    RecoveryWriteBarrier,
    get_recovery_write_barrier,
    recovery_write_operation,
)


def test_snapshot_times_out_with_named_active_owner() -> None:
    barrier = RecoveryWriteBarrier()
    entered = threading.Event()
    release = threading.Event()

    def writer() -> None:
        with barrier.write_lease("stem-output"):
            entered.set()
            release.wait(timeout=5.0)

    thread = threading.Thread(target=writer)
    thread.start()
    assert entered.wait(timeout=2.0)
    try:
        with pytest.raises(RecoveryBusyError, match="stem-output=1"):
            with barrier.snapshot_lease(timeout=0.01):
                pass
    finally:
        release.set()
        thread.join(timeout=2.0)


def test_snapshot_rejects_new_foreign_write_but_allows_owner_flush() -> None:
    barrier = RecoveryWriteBarrier()
    foreign_error: list[Exception] = []

    with barrier.snapshot_lease(timeout=1.0):
        with barrier.write_lease("vector-flush"):
            barrier.assert_snapshot_lease()

        def foreign_writer() -> None:
            try:
                with barrier.write_lease("chat-history"):
                    pass
            except Exception as exc:  # pragma: no branch - asserted below
                foreign_error.append(exc)

        thread = threading.Thread(target=foreign_writer)
        thread.start()
        thread.join(timeout=2.0)

    assert len(foreign_error) == 1
    assert isinstance(foreign_error[0], RecoveryBusyError)


def test_async_write_decorator_releases_owner() -> None:
    @recovery_write_operation("isolated-async-test")
    async def operation() -> int:
        return 7

    # The decorator uses the process barrier; this verifies its async lifetime
    # without mutating owner state.
    assert asyncio.run(operation()) == 7
    assert get_recovery_write_barrier().active_writes() == {}
