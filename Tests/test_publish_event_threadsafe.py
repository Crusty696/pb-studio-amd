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
