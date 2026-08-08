"""Wait for a WPF UIA text state and capture a runtime receipt."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import win32gui
from pywinauto import Application

from run_gui_release_gate import capture_window


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--state", choices=("present", "absent"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=75.0)
    args = parser.parse_args()

    hwnd = win32gui.FindWindow(None, "PB Studio AMD")
    if not hwnd:
        raise RuntimeError("PB Studio AMD window not found")
    app = Application(backend="uia").connect(handle=hwnd, timeout=20)
    window_spec = app.window(handle=hwnd)
    window_spec.wait("visible enabled ready", timeout=20)
    window = window_spec.wrapper_object()
    expected = args.state == "present"
    deadline = time.monotonic() + args.timeout
    matched = False
    matching_values: list[str] = []
    while time.monotonic() < deadline:
        matching_values = []
        for control in window.descendants():
            values = {
                str(control.element_info.name or ""),
                str(control.window_text() or ""),
            }
            matching_values.extend(
                value for value in values if args.text in value
            )
        matched = bool(matching_values) == expected
        if matched:
            break
        time.sleep(0.5)

    args.out.mkdir(parents=True, exist_ok=True)
    screenshot = args.out / f"{args.state}.png"
    capture_window(hwnd, screenshot)
    result = {
        "schema_version": 1,
        "text": args.text,
        "expected_state": args.state,
        "matched": matched,
        "matching_values": sorted(set(matching_values)),
        "screenshot": screenshot.name,
    }
    (args.out / f"{args.state}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if matched else 1


if __name__ == "__main__":
    raise SystemExit(main())
