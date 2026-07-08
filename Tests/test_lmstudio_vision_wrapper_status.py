"""Tests fuer den Status-Publisher-Hook im Vision-Wrapper (Review-Fix 2026-07-09)."""
import pb_studio.video.lmstudio_vision_wrapper as w


def test_set_status_publisher_roundtrip():
    events = []
    w.set_status_publisher(lambda et, data: events.append((et, data)))
    try:
        w._publish_status("m1", "LM Studio", "loading", 25.0)
        assert events == [("llm_status", {
            "model": "m1", "provider": "LM Studio",
            "status": "loading", "percent": 25.0,
        })]
    finally:
        w.set_status_publisher(None)


def test_publish_status_without_publisher_is_noop():
    w.set_status_publisher(None)
    w._publish_status("m1", "LM Studio", "active", 100.0)  # darf nicht werfen


def test_publish_status_swallows_publisher_errors():
    def boom(et, data):
        raise RuntimeError("kaputt")
    w.set_status_publisher(boom)
    try:
        w._publish_status("m1", "Ollama", "failed", 0.0)  # darf nicht werfen
    finally:
        w.set_status_publisher(None)
