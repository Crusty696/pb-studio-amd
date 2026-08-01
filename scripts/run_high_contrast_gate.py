"""Temporarily enable Windows High Contrast and audit all PB Studio views."""

from __future__ import annotations

import argparse
import ctypes
import json
import time
import winreg
from pathlib import Path

import win32gui
from pywinauto import Application

from run_gui_release_gate import (
    TABS,
    audit_visible_controls,
    capture_window,
    content_metrics,
    is_offscreen,
)


SPI_GETHIGHCONTRAST = 0x0042
SPI_SETHIGHCONTRAST = 0x0043
SPIF_UPDATEINIFILE = 0x0001
SPIF_SENDCHANGE = 0x0002
HCF_HIGHCONTRASTON = 0x0001
HCF_OPTION_NOTHEMECHANGE = 0x1000
HIGH_CONTRAST_REGISTRY_PATH = r"Control Panel\Accessibility\HighContrast"
HIGH_CONTRAST_SCHEME_VALUE = "High Contrast Scheme"


class HighContrast(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwFlags", ctypes.c_uint),
        ("lpszDefaultScheme", ctypes.c_wchar_p),
    ]


def get_high_contrast() -> tuple[int, str | None]:
    state = HighContrast()
    state.cbSize = ctypes.sizeof(state)
    if not ctypes.windll.user32.SystemParametersInfoW(
        SPI_GETHIGHCONTRAST,
        state.cbSize,
        ctypes.byref(state),
        0,
    ):
        raise ctypes.WinError()
    scheme = str(state.lpszDefaultScheme) if state.lpszDefaultScheme else None
    return int(state.dwFlags), scheme


def set_high_contrast(flags: int, scheme: str | None) -> None:
    state = HighContrast()
    state.cbSize = ctypes.sizeof(state)
    state.dwFlags = flags & ~HCF_OPTION_NOTHEMECHANGE
    state.lpszDefaultScheme = scheme
    if not ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETHIGHCONTRAST,
        state.cbSize,
        ctypes.byref(state),
        SPIF_UPDATEINIFILE | SPIF_SENDCHANGE,
    ):
        raise ctypes.WinError()


def get_persisted_scheme() -> tuple[str, int]:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        HIGH_CONTRAST_REGISTRY_PATH,
        access=winreg.KEY_QUERY_VALUE,
    ) as key:
        value, value_type = winreg.QueryValueEx(key, HIGH_CONTRAST_SCHEME_VALUE)
    return str(value), int(value_type)


def set_persisted_scheme(value: str, value_type: int) -> None:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        HIGH_CONTRAST_REGISTRY_PATH,
        access=winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(
            key,
            HIGH_CONTRAST_SCHEME_VALUE,
            0,
            value_type,
            value,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    output = args.out.resolve()
    screenshots = output / "screenshots"
    output.mkdir(parents=True, exist_ok=True)

    original_flags, original_scheme = get_high_contrast()
    original_persisted_scheme, original_persisted_type = get_persisted_scheme()
    runs: list[dict] = []
    failures: list[str] = []
    restored_flags: int | None = None
    restored_scheme: str | None = None
    restored_persisted_scheme: str | None = None
    active_flags: int | None = None
    active_scheme: str | None = None
    try:
        set_high_contrast(
            original_flags | HCF_HIGHCONTRASTON,
            "High Contrast Black",
        )
        time.sleep(3.0)
        active_flags, active_scheme = get_high_contrast()
        if not active_flags & HCF_HIGHCONTRASTON:
            failures.append("Windows did not enable High Contrast")

        hwnd = win32gui.FindWindow(None, "PB Studio AMD")
        if not hwnd:
            raise RuntimeError("PB Studio AMD window not found")
        win32gui.MoveWindow(hwnd, 0, 0, 1280, 720, True)
        app = Application(backend="uia").connect(handle=hwnd, timeout=20)
        window_spec = app.window(handle=hwnd)
        window_spec.wait("visible enabled ready", timeout=20)
        window = window_spec.wrapper_object()
        tabs = {
            name: window_spec.child_window(
                title=name, control_type="TabItem"
            ).wrapper_object()
            for name in TABS
        }
        for name, tab in tabs.items():
            tab.select()
            time.sleep(0.4)
            target = screenshots / f"high-contrast-{name.lower()}.png"
            image = capture_window(hwnd, target)
            metrics = content_metrics(image)
            missing_names, clipped = audit_visible_controls(window)
            visible_count = sum(
                1 for item in window.descendants() if not is_offscreen(item)
            )
            runs.append(
                {
                    "tab": name,
                    "screenshot": target.relative_to(output).as_posix(),
                    "visible_uia_elements": visible_count,
                    "missing_interactive_names": missing_names,
                    "clipped_interactive_controls": clipped,
                    **metrics,
                }
            )
            if metrics["variance"] <= 30 or metrics["unique_sampled_colors"] < 8:
                failures.append(f"{name}: blank/flat High Contrast rendering")
            if visible_count < 10:
                failures.append(f"{name}: sparse High Contrast UIA tree")
            if missing_names:
                failures.append(f"{name}: unnamed High Contrast controls")
            if clipped:
                failures.append(f"{name}: clipped High Contrast controls")
    finally:
        set_high_contrast(original_flags, original_scheme)
        set_persisted_scheme(original_persisted_scheme, original_persisted_type)
        time.sleep(3.0)
        restored_flags, restored_scheme = get_high_contrast()
        restored_persisted_scheme, _ = get_persisted_scheme()

    active_state_restored = bool(restored_flags & HCF_HIGHCONTRASTON) == bool(
        original_flags & HCF_HIGHCONTRASTON
    )
    persisted_state_restored = (
        restored_persisted_scheme == original_persisted_scheme
    )
    restored = active_state_restored and persisted_state_restored
    if not restored:
        failures.append("High Contrast active or persisted state was not restored")
    result = {
        "schema_version": 1,
        "original": {
            "flags": original_flags,
            "scheme": original_scheme,
            "persisted_scheme": original_persisted_scheme,
        },
        "active": {"flags": active_flags, "scheme": active_scheme},
        "restored": {
            "flags": restored_flags,
            "scheme": restored_scheme,
            "persisted_scheme": restored_persisted_scheme,
            "active_state": active_state_restored,
            "persisted_state": persisted_state_restored,
            "complete": restored,
            "scheme_cache_changed": restored_scheme != original_scheme,
        },
        "runs": runs,
        "failures": failures,
        "passed": not failures,
    }
    result_path = output / "high-contrast-gate.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "passed": not failures,
                "screenshots": len(runs),
                "restored": restored,
                "failures": failures,
                "result": str(result_path),
            },
            ensure_ascii=False,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
