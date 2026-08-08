from __future__ import annotations

import json
import time
from pathlib import Path

from pywinauto import Application, Desktop, findwindows
from pywinauto.keyboard import send_keys


EVIDENCE_DIR = Path(__file__).resolve().parent


def main() -> None:
    handles = findwindows.find_windows(
        title="PB Studio AMD",
        top_level_only=True,
    )
    if len(handles) != 1:
        raise RuntimeError(f"Expected one PB Studio main window: {handles}")

    app = Application(backend="uia").connect(handle=handles[0], timeout=20)
    window = app.window(handle=handles[0])
    window.wait("visible enabled ready", timeout=20)
    window.maximize()

    project_tab = window.child_window(title="PROJEKT", control_type="TabItem")
    project_tab.select()
    time.sleep(1.5)
    desktop = Desktop(backend="uia")
    baseline_handles = {
        candidate.handle
        for candidate in desktop.windows()
        if candidate.handle
    }
    open_button = window.child_window(
        title_re=r"Projekt .*ffnen",
        control_type="Button",
    )
    if not open_button.is_enabled():
        raise RuntimeError("Project open button is disabled")
    open_button.invoke()

    dialog = None
    observed_windows = []
    for _ in range(30):
        time.sleep(0.5)
        observed_windows = []
        for candidate in desktop.windows():
            try:
                observed_windows.append(
                    {
                        "handle": candidate.handle,
                        "title": candidate.window_text(),
                        "class_name": candidate.element_info.class_name,
                        "visible": candidate.is_visible(),
                        "enabled": candidate.is_enabled(),
                    }
                )
                if (
                    candidate.handle not in baseline_handles
                    and candidate.is_visible()
                    and candidate.is_enabled()
                ):
                    dialog = candidate
            except Exception:
                continue
        if dialog is not None:
            break
    if dialog is None:
        raise RuntimeError(
            f"No process-owned dialog found: {observed_windows}"
        )
    controls = []
    for control in dialog.descendants():
        try:
            controls.append(
                {
                    "control_type": control.element_info.control_type,
                    "name": control.window_text(),
                    "automation_id": control.element_info.automation_id,
                    "class_name": control.element_info.class_name,
                    "visible": control.is_visible(),
                    "enabled": control.is_enabled(),
                }
            )
        except Exception:
            continue

    report = {
        "dialog_title": dialog.window_text(),
        "observed_windows": observed_windows,
        "control_count": len(controls),
        "controls": controls,
    }
    (EVIDENCE_DIR / "project-dialog-uia-inventory.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    send_keys("{ESC}")
    time.sleep(0.5)


if __name__ == "__main__":
    main()
