"""Record non-destructive UIA evidence for PB Studio destructive controls."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import win32gui
from pywinauto import Application


EXPECTED_CONTROLS = {
    "AUDIO": {
        "Markierte Audio-Clips löschen": None,
        "Alle Audio-Clips löschen": None,
    },
    "VIDEO": {
        "Markierte Video-Clips löschen": None,
        "Alle Video-Clips löschen": None,
    },
    "HIRN": {
        "Hirn-Reset anfordern": True,
        "Hirn-Reset bestätigen": False,
    },
    "SETTINGS": {"Inaktive GPU-Modelle entladen": None},
    "CHAT": {"Chat-Verlauf leeren": None},
    "ANCHOR": {"Ausgewählten Anchor-Punkt entfernen": False},
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    hwnd = win32gui.FindWindow(None, "PB Studio AMD")
    if not hwnd:
        raise RuntimeError("PB Studio AMD window not found")
    app = Application(backend="uia").connect(handle=hwnd, timeout=20)
    window_spec = app.window(handle=hwnd)
    window_spec.wait("visible enabled ready", timeout=20)

    controls: list[dict[str, object]] = []
    failures: list[str] = []
    for tab_name, expected in EXPECTED_CONTROLS.items():
        tab = window_spec.child_window(
            title=tab_name, control_type="TabItem"
        ).wrapper_object()
        tab.select()
        time.sleep(0.25)
        for name, expected_enabled in expected.items():
            matches = [
                control
                for control in window_spec.wrapper_object().descendants()
                if control.element_info.control_type == "Button"
                and str(control.element_info.name or "").strip() == name
            ]
            if len(matches) != 1:
                failures.append(
                    f"{tab_name}: expected one '{name}' button, found {len(matches)}"
                )
                continue
            enabled = bool(matches[0].is_enabled())
            controls.append(
                {
                    "tab": tab_name,
                    "name": name,
                    "enabled": enabled,
                    "expected_enabled": expected_enabled,
                }
            )
            if expected_enabled is not None and enabled != expected_enabled:
                failures.append(
                    f"{tab_name}: '{name}' enabled={enabled}, "
                    f"expected {expected_enabled}"
                )

    result = {
        "schema_version": 1,
        "note": "Controls were inspected through UIA and were not invoked.",
        "controls": controls,
        "failures": failures,
        "passed": not failures,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
