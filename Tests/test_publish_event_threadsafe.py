"""Tests fuer publish_event_threadsafe (Review-Fix HIGH-1 2026-07-09)."""
import asyncio
import importlib
import threading

from backend import dependencies as deps

events_router = importlib.import_module("backend.routers.events_router")


def test_threadsafe_publish_from_worker_thread_wakes_main_loop():
    async def main():
        deps.set_main_loop(asyncio.get_running_loop())
        queue = deps.get_event_queue("test_ts")
        try:
            def worker():
                deps.publish_event_threadsafe("llm_status", {"status": "active"})

            t = threading.Thread(target=worker)
            t.start()
            t.join()
            # Muss OHNE Keepalive-Timeout ankommen (<1s statt 15s)
            event = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert event["event"] == "llm_status"
            assert event["data"]["status"] == "active"
        finally:
            deps._event_queues.pop("test_ts", None)
            deps.set_main_loop(None)

    asyncio.run(main())


def test_threadsafe_publish_without_loop_is_noop():
    deps.set_main_loop(None)
    # darf nicht werfen, auch ohne registrierte Queues/Loop
    deps.publish_event_threadsafe("llm_status", {"status": "failed"})


def test_threadsafe_publish_same_loop_direct():
    async def main():
        deps.set_main_loop(asyncio.get_running_loop())
        queue = deps.get_event_queue("test_direct")
        try:
            deps.publish_event_threadsafe("llm_status", {"status": "loading"})
            event = queue.get_nowait()
            assert event["data"]["status"] == "loading"
        finally:
            deps._event_queues.pop("test_direct", None)
            deps.set_main_loop(None)

    asyncio.run(main())


def test_queue_full_drops_oldest_and_keeps_latest_event():
    client_id = "test_queue_full"
    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=2)
    queue.put_nowait({"event": "first", "data": {"sequence": 1}})
    queue.put_nowait({"event": "second", "data": {"sequence": 2}})
    before = deps.get_event_queue_drop_metrics()["total"]

    deps._enqueue_event(
        client_id,
        queue,
        {"event": "third", "data": {"sequence": 3}},
    )

    assert queue.get_nowait()["data"]["sequence"] == 2
    assert queue.get_nowait()["data"]["sequence"] == 3
    metrics = deps.get_event_queue_drop_metrics()
    assert metrics["total"] == before + 1
    assert metrics["by_client"][client_id] == 1
    assert deps.unregister_event_queue(client_id) == 1


def test_filtered_event_never_consumes_queue_capacity_or_drop_budget():
    client_id = "test_filtered_queue"
    queue = deps.get_event_queue(client_id, {"progress"})
    before = deps.get_event_queue_drop_metrics()["total"]
    try:
        deps._fanout_event({"event": "log", "data": {"message": "ignored"}})

        assert queue.empty()
        assert deps.get_event_queue_drop_metrics()["total"] == before
    finally:
        assert deps.unregister_event_queue(client_id) == 0


def test_log_reconnect_emits_marker_when_journal_has_a_gap():
    class Request:
        headers = {"last-event-id": "1"}

        async def is_disconnected(self):
            return False

    async def scenario() -> None:
        deps.reset_event_journal()
        for index in range(deps.EVENT_JOURNAL_MAXLEN + 2):
            await deps.publish_event("log", {"message": f"log-{index}"})

        assert deps.get_event_journal_gap(1) == (2, 2)
        stream = events_router._event_stream(
            Request(),
            client_id="gap-test",
            event_filter={"log"},
        )
        try:
            marker = await anext(stream)
        finally:
            await stream.aclose()
            deps.reset_event_journal()

        assert "event: log" in marker
        assert "Events 2–2" in marker
        assert "nicht mehr verfügbar" in marker

    asyncio.run(scenario())


def test_log_reconnect_ignores_progress_only_evictions():
    class Request:
        headers = {"last-event-id": "1"}

        async def is_disconnected(self):
            return False

    async def scenario() -> None:
        deps.reset_event_journal()
        for index in range(deps.EVENT_JOURNAL_MAXLEN + 1):
            await deps.publish_event("analysis_progress", {"percent": index})
        await deps.publish_event("log", {"message": "retained"})

        assert deps.get_event_journal_gap(1, {"log"}) is None
        stream = events_router._event_stream(
            Request(),
            client_id="filtered-gap-test",
            event_filter={"log"},
        )
        try:
            replay = await anext(stream)
        finally:
            await stream.aclose()
            deps.reset_event_journal()

        assert "event: log" in replay
        assert "retained" in replay
        assert "nicht mehr" not in replay

    asyncio.run(scenario())
