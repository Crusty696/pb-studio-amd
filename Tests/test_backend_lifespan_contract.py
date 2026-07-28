"""Static contract for deterministic backend lifespan task shutdown."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_zombie_watcher_is_joined_before_resource_cleanup():
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")

    cancel_index = main.index("watcher_task.cancel()", main.index("yield"))
    await_index = main.index("await watcher_task", cancel_index)
    render_shutdown_index = main.index(
        "await _shutdown_active_renders(get_app_state())",
        await_index,
    )
    cleanup_index = main.index("set_status_publisher(None)", render_shutdown_index)

    assert cancel_index < await_index < render_shutdown_index < cleanup_index
    assert "except asyncio.CancelledError:" in main[cancel_index:cleanup_index]


def test_hard_exit_terminates_render_processes_first():
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    hard_exit = main[main.index("def _hard_exit()"):main.index("fallback.daemon")]

    assert "RenderService.terminate_active_processes" in hard_exit
    assert hard_exit.index("terminate_active_processes") < hard_exit.index("os._exit(0)")
