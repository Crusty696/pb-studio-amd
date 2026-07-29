from __future__ import annotations

import ctypes
import json
import time
import urllib.request
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Any

from pywinauto import Application, findwindows
from pywinauto.keyboard import send_keys


EVIDENCE_DIR = Path(__file__).resolve().parent
TARGET_PROJECT = Path(
    r"C:\Users\david\Documents\PBStudio\ReleaseSmoke_20260727_083320"
)
REPORT_PATH = EVIDENCE_DIR / "project-dialog-win32-probe.json"
SCREENSHOT_PATH = (
    EVIDENCE_DIR
    / "screenshots-cycle-10-project-switch"
    / "project-after-dialog-probe.png"
)

user32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HWND,
    wintypes.LPARAM,
)


def _window_text(handle: int) -> str:
    length = user32.GetWindowTextLengthW(handle)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, buffer, len(buffer))
    return buffer.value


def _class_name(handle: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(handle, buffer, len(buffer))
    return buffer.value


def _top_windows() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    @EnumWindowsProc
    def callback(handle: int, _: int) -> bool:
        if user32.IsWindowVisible(handle):
            result.append(
                {
                    "handle": int(handle),
                    "title": _window_text(handle),
                    "class_name": _class_name(handle),
                    "owner": int(user32.GetWindow(handle, 4)),
                }
            )
        return True

    user32.EnumWindows(callback, 0)
    return result


def _child_windows(parent: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    @EnumWindowsProc
    def callback(handle: int, _: int) -> bool:
        result.append(
            {
                "handle": int(handle),
                "title": _window_text(handle),
                "class_name": _class_name(handle),
                "control_id": int(user32.GetDlgCtrlID(handle)),
                "visible": bool(user32.IsWindowVisible(handle)),
                "enabled": bool(user32.IsWindowEnabled(handle)),
            }
        )
        return True

    user32.EnumChildWindows(parent, callback, 0)
    return result


def _http_json(path: str) -> dict[str, Any]:
    with urllib.request.urlopen(
        f"http://127.0.0.1:8765{path}",
        timeout=5,
    ) as response:
        return json.loads(response.read().decode("utf-8"))


def _invoke_open_button(window) -> None:
    window.child_window(
        title_re=r"Projekt .*ffnen",
        control_type="Button",
    ).invoke()


def main() -> None:
    report: dict[str, Any] = {
        "status": "open",
        "started_at": datetime.now().astimezone().isoformat(),
        "target": str(TARGET_PROJECT),
    }
    dialog_handle = 0
    try:
        handles = findwindows.find_windows(
            title="PB Studio AMD",
            top_level_only=True,
        )
        if len(handles) != 1:
            raise RuntimeError(f"Expected one PB Studio window: {handles}")
        main_handle = handles[0]
        app = Application(backend="uia").connect(
            handle=main_handle,
            timeout=20,
        )
        window = app.window(handle=main_handle)
        window.wait("visible enabled ready", timeout=20)
        window.maximize()
        window.child_window(
            title="PROJEKT",
            control_type="TabItem",
        ).select()
        time.sleep(1)

        baseline = {item["handle"] for item in _top_windows()}
        _invoke_open_button(window)
        observed: list[dict[str, Any]] = []
        for _ in range(40):
            time.sleep(0.25)
            observed = [
                item
                for item in _top_windows()
                if item["handle"] not in baseline
            ]
            candidates = [
                item
                for item in observed
                if item["class_name"] == "#32770"
            ]
            if not candidates:
                candidates = [
                    item
                    for item in observed
                    if item["owner"] == main_handle
                ]
            if candidates:
                dialog_handle = int(candidates[0]["handle"])
                break
        if not dialog_handle:
            raise RuntimeError(f"Dialog not found: {observed}")

        report["dialog"] = {
            "handle": dialog_handle,
            "observed": observed,
            "children_before": _child_windows(dialog_handle),
        }
        user32.ShowWindow(dialog_handle, 9)
        user32.SetForegroundWindow(dialog_handle)
        time.sleep(0.25)
        send_keys("%d")
        time.sleep(0.25)
        send_keys(str(TARGET_PROJECT), with_spaces=True, pause=0.001)
        send_keys("{ENTER}")
        time.sleep(1)
        children_after = _child_windows(dialog_handle)
        report["dialog"]["children_after_navigation"] = children_after

        select_buttons = [
            item
            for item in children_after
            if item["class_name"] == "Button"
            and item["visible"]
            and item["enabled"]
            and (
                "ordner" in item["title"].casefold()
                or "select" in item["title"].casefold()
            )
        ]
        report["dialog"]["select_buttons"] = select_buttons
        if select_buttons:
            user32.PostMessageW(select_buttons[0]["handle"], 0x00F5, 0, 0)
        else:
            user32.SetForegroundWindow(dialog_handle)
            send_keys("{ENTER}")

        for _ in range(80):
            time.sleep(0.25)
            if not user32.IsWindow(dialog_handle) or not user32.IsWindowVisible(
                dialog_handle
            ):
                break
        else:
            raise RuntimeError("Dialog remained visible after selection")

        project_info: dict[str, Any] = {}
        for _ in range(80):
            time.sleep(0.25)
            project_info = _http_json("/project/info")
            if (
                Path(project_info.get("path", "")).resolve()
                == TARGET_PROJECT.resolve()
            ):
                break
        else:
            raise RuntimeError(f"Backend project did not switch: {project_info}")

        SCREENSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        image = window.capture_as_image()
        image.save(SCREENSHOT_PATH)
        report.update(
            {
                "status": "pass",
                "completed_at": datetime.now().astimezone().isoformat(),
                "project_info": project_info,
                "screenshot": str(SCREENSHOT_PATH),
            }
        )
    except Exception as exc:
        report.update(
            {
                "status": "failed",
                "failed_at": datetime.now().astimezone().isoformat(),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        raise
    finally:
        if dialog_handle and user32.IsWindow(dialog_handle):
            user32.PostMessageW(dialog_handle, 0x0010, 0, 0)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
