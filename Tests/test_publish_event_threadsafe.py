"""Tests fuer publish_event_threadsafe (Review-Fix HIGH-1 2026-07-09)."""
import asyncio
import threading

from backend import dependencies as deps


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
