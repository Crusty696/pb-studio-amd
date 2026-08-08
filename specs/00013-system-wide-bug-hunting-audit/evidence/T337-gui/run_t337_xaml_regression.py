from __future__ import annotations

import ctypes
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from pywinauto import Application, findwindows


EVIDENCE_DIR = Path(__file__).resolve().parent
SCREENSHOT_DIR = EVIDENCE_DIR / "screenshots-cycle-8-xaml"
REPO_DIR = EVIDENCE_DIR.parents[3]
WPF_LOG = REPO_DIR / "logs" / "wpf_app.log"


def _get_json(path: str) -> dict[str, Any]:
    with urllib.request.urlopen(
        f"http://127.0.0.1:8765{path}",
        timeout=15,
    ) as response:
        return json.loads(response.read().decode("utf-8"))


def _visible_text(window) -> list[str]:
    values: set[str] = set()
    for control_type in ("Text", "Edit", "Button"):
        for control in window.descendants(control_type=control_type):
            try:
                value = control.window_text().strip()
                if control.is_visible() and value:
                    values.add(value)
            except Exception:
                continue
    return sorted(values)


def _capture(window, name: str) -> str:
    screenshot = SCREENSHOT_DIR / f"{name}.png"
    window.capture_as_image().save(screenshot)
    return str(screenshot)


def main() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    handles = findwindows.find_windows(
        title="PB Studio AMD",
        top_level_only=True,
    )
    if len(handles) != 1:
        raise RuntimeError(f"Expected one PB Studio main window: {handles}")

    app = Application(backend="uia").connect(handle=handles[0], timeout=20)
    window = app.window(handle=handles[0])
    user32 = ctypes.windll.user32
    user32.ShowWindow(handles[0], 9)
    user32.ShowWindow(handles[0], 3)
    user32.SetForegroundWindow(handles[0])
    user32.SetWindowPos(
        handles[0],
        -1,
        0,
        0,
        0,
        0,
        0x0001 | 0x0002 | 0x0040,
    )
    window.wait("visible enabled ready", timeout=20)
    window.maximize()
    time.sleep(1.0)

    model_tab = window.child_window(title="MODELLE", control_type="TabItem")
    model_tab.select()
    model_api = _get_json("/models/list")
    installed_count = len(model_api.get("models") or [])
    installed_prefix = f"{installed_count} installiert"
    model_text: list[str] = []
    for _ in range(30):
        time.sleep(1.0)
        model_text = _visible_text(window)
        if any(value.startswith(installed_prefix) for value in model_text):
            break
    if not model_tab.is_selected():
        raise RuntimeError("MODELLE did not remain selected")
    installed_state = next(
        (
            value
            for value in model_text
            if value.startswith(installed_prefix)
        ),
        None,
    )
    if installed_state is None:
        raise RuntimeError(
            f"MODELLE refresh missing API state: {installed_prefix}"
        )
    model_screenshot = _capture(window, "modelle-after-refresh")

    export_tab = window.child_window(title="EXPORT", control_type="TabItem")
    export_tab.select()
    time.sleep(3.0)
    export_text = _visible_text(window)
    export_edits = [
        control
        for control in window.descendants(control_type="Edit")
        if control.is_visible()
    ]
    if not export_tab.is_selected():
        raise RuntimeError("EXPORT did not become selected")
    if not any("RENDER LOG" in value for value in export_text):
        raise RuntimeError("EXPORT render-log surface missing")
    if len(export_edits) < 5:
        raise RuntimeError(
            f"EXPORT copyable/read-only surfaces missing: {len(export_edits)}"
        )
    export_screenshot = _capture(window, "export-render-log")

    terminal_tab = window.child_window(title="TERMINAL", control_type="TabItem")
    terminal_tab.select()
    time.sleep(3.0)
    terminal_text = _visible_text(window)
    if not terminal_tab.is_selected():
        raise RuntimeError("TERMINAL did not become selected")
    if not any("LIVE BACKEND TERMINAL" in value for value in terminal_text):
        raise RuntimeError("TERMINAL surface missing")
    terminal_screenshot = _capture(window, "terminal-after-model-refresh")

    time.sleep(5.0)
    log_text = WPF_LOG.read_text(encoding="utf-8", errors="replace")
    error_counts = {
        "xaml_parse_exception": log_text.count("XamlParseException"),
        "path_xpath_failure": log_text.count(
            'Die bidirektionale Bindung erfordert "Path" oder "XPath".'
        ),
        "unhandled_ui_exception": log_text.count(
            "Unbehandelte UI-Exception"
        ),
        "unobserved_task_exception": log_text.count(
            "Unbeobachtete Task-Exception"
        ),
    }
    if any(error_counts.values()):
        raise RuntimeError(f"WPF regression log gate failed: {error_counts}")

    report: dict[str, Any] = {
        "status": "pass",
        "completed_at": datetime.now().astimezone().isoformat(),
        "window_handle": handles[0],
        "models": {
            "api_installed_count": installed_count,
            "base_url": model_api.get("base_url"),
            "installed_state": installed_state,
            "screenshot": model_screenshot,
        },
        "export": {
            "copyable_edit_count": len(export_edits),
            "render_log_visible": True,
            "screenshot": export_screenshot,
        },
        "terminal": {
            "visible": True,
            "screenshot": terminal_screenshot,
        },
        "wpf_log": {
            "path": str(WPF_LOG),
            "bytes": WPF_LOG.stat().st_size,
            "error_counts": error_counts,
        },
    }
    (EVIDENCE_DIR / "xaml-regression-cycle-8.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
