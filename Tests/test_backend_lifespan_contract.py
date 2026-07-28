"""Static contract for deterministic backend lifespan task shutdown."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_zombie_watcher_is_joined_before_resource_cleanup():
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")

    cancel_index = main.index("watcher_task.cancel()", main.index("yield"))
    await_index = main.index("await watcher_task", cancel_index)
    cleanup_index = main.index("set_status_publisher(None)", await_index)

    assert cancel_index < await_index < cleanup_index
    assert "except asyncio.CancelledError:" in main[cancel_index:cleanup_index]
