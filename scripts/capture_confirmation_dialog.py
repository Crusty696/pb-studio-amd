"""Capture the real WPF destructive-confirmation dialog without mutating data."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from pywinauto import Desktop, keyboard
from pywinauto.uia_defines import IUIA

from run_gui_release_gate import capture_window


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    harness = args.harness.resolve()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    title = "Alle Audio-Clips löschen"
    message = "ALLE 3 Audio-Clips dauerhaft löschen?"
    process = subprocess.Popen(
        [str(harness)],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    failures: list[str] = []
    try:
        dialog = Desktop(backend="uia").window(title=title)
        dialog.wait("visible enabled ready", timeout=15)
        window = dialog.wrapper_object()
        window.set_focus()
        time.sleep(0.2)
        buttons = [
            str(control.element_info.name or "").strip()
            for control in window.descendants()
            if control.element_info.control_type == "Button"
        ]
        focused = IUIA().iuia.GetFocusedElement()
        focused_name = str(focused.CurrentName or "").strip()
        screenshot = output / "delete-confirmation-default-no.png"
        capture_window(window.handle, screenshot)
        no_buttons = [name for name in buttons if name.lower() in {"nein", "no"}]
        yes_buttons = [name for name in buttons if name.lower() in {"ja", "yes"}]
        if len(no_buttons) != 1 or len(yes_buttons) != 1:
            failures.append(f"expected Yes/No buttons, found {buttons}")
        if focused_name.lower() not in {"nein", "no"}:
            failures.append(f"default focus was '{focused_name}', expected No")
        if no_buttons:
            no_button = dialog.child_window(
                title=no_buttons[0], control_type="Button"
            ).wrapper_object()
            no_button.set_focus()
            keyboard.send_keys("{ENTER}")
        else:
            process.terminate()
        try:
            dialog.wait_not("visible", timeout=5)
            dialog_closed = True
        except Exception:
            dialog_closed = False
            failures.append("No did not close the confirmation dialog")
        return_code = process.poll()
        if return_code is None and dialog_closed:
            process.terminate()
            process.wait(timeout=5)
        elif return_code not in {None, 0}:
            failures.append(f"dialog returned unexpected code {return_code}")
        result = {
            "schema_version": 1,
            "harness": str(harness),
            "title": title,
            "message": message,
            "buttons": buttons,
            "default_focused_control": focused_name,
            "selected": "No",
            "dialog_closed": dialog_closed,
            "data_mutation_path_invoked": False,
            "screenshot": screenshot.name,
            "failures": failures,
            "passed": not failures,
        }
        (output / "delete-confirmation.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0 if not failures else 1
    finally:
        if process.poll() is None:
            process.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
