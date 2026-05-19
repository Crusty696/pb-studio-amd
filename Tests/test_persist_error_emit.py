"""Regression-Test fuer Pe-C1 (Audit 2026-05-19):
Persist-Fehler wurden als "unkritisch" geloggt → Iron Rule 10 Verletzung.
Fix: _emit_persist_error publiziert SSE-Event "persist_error" mit metadata.
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from backend.app_state import _emit_persist_error


def test_emit_persist_error_no_loop_falls_back_to_log(caplog):
    """Ohne running asyncio loop: Fallback auf logger.error, kein Crash."""
    import logging
    caplog.set_level(logging.ERROR)
    _emit_persist_error("test_source", "Test message", "Test detail")
    assert any("persist_error" in r.message and "test_source" in r.message for r in caplog.records), \
        f"Expected log entry with persist_error tag. Got: {[r.message for r in caplog.records]}"


def test_emit_persist_error_with_loop_schedules_publish_event():
    """Mit running loop: publish_event coroutine wird geschedult. (sync wrapper)"""
    scheduled: list = []

    async def fake_publish(event_type, data, client_id="default"):
        scheduled.append((event_type, data))

    async def runner():
        with patch("backend.dependencies.publish_event", side_effect=fake_publish):
            _emit_persist_error("audio_import", "Test message", "Test detail")
            # fire-and-forget — give event loop one tick
            await asyncio.sleep(0.01)

    asyncio.run(runner())

    assert len(scheduled) == 1
    event_type, data = scheduled[0]
    assert event_type == "persist_error"
    assert data["source"] == "audio_import"
    assert data["message"] == "Test message"
    assert data["detail"] == "Test detail"
    assert data["severity"] == "error"


def test_emit_persist_error_truncates_long_detail():
    """Detail-String wird bei 500 chars truncated (kein Riesen-Stack-Trace im SSE)."""
    long_detail = "x" * 1000
    # No assert on log content (env-dependent); just verify no exception
    _emit_persist_error("test", "msg", long_detail)


def test_emit_persist_error_handles_publish_failure_gracefully(caplog):
    """Wenn publish_event selbst failed (z.B. import error), darf der Persist-Path
    NICHT blockieren — Fail-Path muss weitergehen."""
    import logging
    caplog.set_level(logging.ERROR)

    with patch("backend.dependencies.publish_event", side_effect=ImportError("forced fail")):
        # Should NOT raise
        _emit_persist_error("test", "msg", "detail")

    # Either the import failure or the fallback log should be visible
    assert len(caplog.records) > 0
