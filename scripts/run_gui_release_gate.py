"""Automated runtime GUI, layout and keyboard gate for PB Studio WPF."""

from __future__ import annotations

import argparse
import ctypes
import json
import time
from pathlib import Path

import win32con
import win32gui
import win32ui
from PIL import Image
from pywinauto import Application, keyboard
from pywinauto.uia_defines import IUIA


TABS = (
    "PROJEKT",
    "AUDIO",
    "VIDEO",
    "KI-REGIE",
    "TIMELINE",
    "EXPORT",
    "HIRN",
    "SETTINGS",
    "PERFORMANCE",
    "MODELLE",
    "CHAT",
    "TERMINAL",
    "INGEST",
    "ANCHOR",
)
WM_DPICHANGED = 0x02E0
INTERACTIVE_TYPES = {
    "Button",
    "CheckBox",
    "ComboBox",
    "Edit",
    "Hyperlink",
    "List",
    "RadioButton",
    "Slider",
    "TabItem",
    "Tree",
}


def capture_window(hwnd: int, target: Path) -> Image.Image:
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top
    if width < 100 or height < 100:
        raise RuntimeError(f"invalid window size {width}x{height}")
    window_dc = win32gui.GetWindowDC(hwnd)
    source_dc = win32ui.CreateDCFromHandle(window_dc)
    memory_dc = source_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(source_dc, width, height)
    memory_dc.SelectObject(bitmap)
    try:
        rendered = ctypes.windll.user32.PrintWindow(
            hwnd, memory_dc.GetSafeHdc(), 0x2
        )
        if not rendered:
            raise RuntimeError("PrintWindow returned false")
        info = bitmap.GetInfo()
        bits = bitmap.GetBitmapBits(True)
        image = Image.frombuffer(
            "RGB",
            (info["bmWidth"], info["bmHeight"]),
            bits,
            "raw",
            "BGRX",
            0,
            1,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, format="PNG", optimize=True)
        return image
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        memory_dc.DeleteDC()
        source_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, window_dc)


def apply_test_dpi(hwnd: int, dpi: int) -> None:
    class Rect(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    rect = Rect()
    if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("GetWindowRect failed before WM_DPICHANGED")
    wparam = (dpi << 16) | dpi
    ctypes.windll.user32.SendMessageW(
        hwnd, WM_DPICHANGED, wparam, ctypes.byref(rect)
    )
    time.sleep(0.4)


def content_metrics(image: Image.Image) -> dict[str, int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    crop = rgb.crop((40, max(80, height // 5), width - 40, height - 30))
    step_x = max(1, crop.width // 80)
    step_y = max(1, crop.height // 60)
    pixels = [
        crop.getpixel((x, y))
        for x in range(0, crop.width, step_x)
        for y in range(0, crop.height, step_y)
    ]
    ranges = [max(channel) - min(channel) for channel in zip(*pixels)]
    return {
        "variance": sum(ranges),
        "unique_sampled_colors": len(set(pixels)),
    }


def is_offscreen(wrapper) -> bool:
    try:
        return bool(wrapper.element_info.element.CurrentIsOffscreen)
    except Exception:
        return not wrapper.is_visible()


def audit_visible_controls(window) -> tuple[list[dict], list[dict]]:
    bounds = window.rectangle()
    missing_names: list[dict] = []
    clipped: list[dict] = []
    for control in window.descendants():
        control_type = control.element_info.control_type
        if control_type not in INTERACTIVE_TYPES or is_offscreen(control):
            continue
        if control.element_info.class_name in {"ItemsControl", "RepeatButton"}:
            continue
        parent = control.parent()
        nested_interactive = False
        while parent is not None and parent.handle != window.handle:
            if parent.element_info.control_type in INTERACTIVE_TYPES:
                nested_interactive = True
                break
            try:
                parent = parent.parent()
            except Exception:
                break
        if nested_interactive:
            continue
        rect = control.rectangle()
        if rect.width() <= 1 or rect.height() <= 1:
            continue
        name = str(control.element_info.name or "").strip()
        if not name:
            missing_names.append(
                {"type": control_type, "rect": str(rect)}
            )
        center_x = (rect.left + rect.right) // 2
        center_y = (rect.top + rect.bottom) // 2
        center_is_visible = (
            bounds.left <= center_x <= bounds.right
            and bounds.top <= center_y <= bounds.bottom
        )
        try:
            is_scroll_container = bool(
                control.iface_scroll.CurrentHorizontallyScrollable
                or control.iface_scroll.CurrentVerticallyScrollable
            )
        except Exception:
            is_scroll_container = False
        frame_tolerance = 16
        if center_is_visible and not is_scroll_container and (
            rect.left < bounds.left - frame_tolerance
            or rect.top < bounds.top - frame_tolerance
            or rect.right > bounds.right + frame_tolerance
            or rect.bottom > bounds.bottom + frame_tolerance
        ):
            clipped.append(
                {"type": control_type, "name": name, "rect": str(rect)}
            )
    return missing_names, clipped


def selected_tab(tabs) -> str | None:
    for name, tab in tabs.items():
        try:
            if tab.is_selected():
                return name
        except Exception:
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--sizes",
        default="1280x720,1400x900",
        help="comma-separated effective WPF sizes in device-independent pixels",
    )
    parser.add_argument(
        "--dpis",
        default="96",
        help="comma-separated DPI values; 96,144,192 correspond to 100,150,200%",
    )
    args = parser.parse_args()
    sizes = [tuple(map(int, item.split("x"))) for item in args.sizes.split(",")]
    dpis = [int(item) for item in args.dpis.split(",")]
    output = args.out.resolve()
    screenshots = output / "screenshots"
    output.mkdir(parents=True, exist_ok=True)

    hwnd = win32gui.FindWindow(None, "PB Studio AMD")
    if not hwnd:
        raise RuntimeError("PB Studio AMD window not found")
    app = Application(backend="uia").connect(handle=hwnd, timeout=20)
    window_spec = app.window(handle=hwnd)
    window_spec.wait("visible enabled ready", timeout=20)
    window = window_spec.wrapper_object()
    window.set_focus()
    tabs = {
        name: window_spec.child_window(
            title=name, control_type="TabItem"
        ).wrapper_object()
        for name in TABS
    }
    results: dict[str, object] = {
        "schema_version": 1,
        "tabs": list(TABS),
        "sizes": [f"{width}x{height}" for width, height in sizes],
        "dpis": dpis,
        "runs": [],
        "keyboard": {},
        "failures": [],
    }
    failures: list[str] = results["failures"]  # type: ignore[assignment]

    try:
        for dpi in dpis:
            apply_test_dpi(window.handle, dpi)
            for width, height in sizes:
                physical_width = round(width * dpi / 96)
                physical_height = round(height * dpi / 96)
                win32gui.MoveWindow(
                    window.handle,
                    0,
                    0,
                    physical_width,
                    physical_height,
                    True,
                )
                time.sleep(0.8)
                actual = window.rectangle()
                if (
                    abs(actual.width() - physical_width) > 2
                    or abs(actual.height() - physical_height) > 2
                ):
                    failures.append(
                        f"dpi {dpi}: physical size requested "
                        f"{physical_width}x{physical_height}, got "
                        f"{actual.width()}x{actual.height()}"
                    )
                for name, tab in tabs.items():
                    tab.select()
                    time.sleep(0.35)
                    if not tab.is_selected():
                        failures.append(
                            f"dpi {dpi} {width}x{height} {name}: tab not selected"
                        )
                    target = screenshots / (
                        f"dpi{dpi}-{width}x{height}-{name.lower()}.png"
                    )
                    image = capture_window(window.handle, target)
                    metrics = content_metrics(image)
                    missing_names, clipped = audit_visible_controls(window)
                    visible_count = sum(
                        1 for item in window.descendants() if not is_offscreen(item)
                    )
                    record = {
                        "dpi": dpi,
                        "effective_size": f"{width}x{height}",
                        "physical_size": f"{physical_width}x{physical_height}",
                        "tab": name,
                        "screenshot": target.relative_to(output).as_posix(),
                        "visible_uia_elements": visible_count,
                        "missing_interactive_names": missing_names,
                        "clipped_interactive_controls": clipped,
                        **metrics,
                    }
                    results["runs"].append(record)  # type: ignore[union-attr]
                    if (
                        metrics["variance"] <= 30
                        or metrics["unique_sampled_colors"] < 8
                    ):
                        failures.append(
                            f"dpi {dpi} {width}x{height} {name}: blank/flat rendering"
                        )
                    if visible_count < 10:
                        failures.append(
                            f"dpi {dpi} {width}x{height} {name}: sparse UIA tree"
                        )
                    if missing_names:
                        failures.append(
                            f"dpi {dpi} {width}x{height} {name}: "
                            f"{len(missing_names)} unnamed controls"
                        )
                    if clipped:
                        failures.append(
                            f"dpi {dpi} {width}x{height} {name}: "
                            f"{len(clipped)} clipped controls"
                        )
    finally:
        apply_test_dpi(window.handle, 96)

    win32gui.MoveWindow(window.handle, 40, 40, 1600, 900, True)
    tabs = {
        name: window_spec.child_window(
            title=name, control_type="TabItem"
        ).wrapper_object()
        for name in TABS
    }
    tabs[TABS[0]].select()
    tabs[TABS[0]].set_focus()
    keyboard_forward = []
    for _ in range(len(TABS) - 1):
        keyboard.send_keys("{RIGHT}", pause=0.08)
        time.sleep(0.08)
        keyboard_forward.append(selected_tab(tabs))
    expected_forward = list(TABS[1:])
    results["keyboard"] = {
        "right_arrow": keyboard_forward,
        "expected_right_arrow": expected_forward,
    }
    if keyboard_forward != expected_forward:
        failures.append("Right Arrow does not traverse all tab headers")

    tabs[TABS[3]].select()
    tabs[TABS[3]].set_focus()
    focus_sequence = []
    for _ in range(8):
        keyboard.send_keys("{TAB}")
        time.sleep(0.08)
        focused = IUIA().iuia.GetFocusedElement()
        focus_sequence.append(
            {
                "name": str(focused.CurrentName or ""),
                "control_type_id": int(focused.CurrentControlType),
            }
        )
    results["keyboard"]["ki_regie_tab_focus"] = focus_sequence
    unnamed_focus = [
        item
        for item in focus_sequence
        if item["control_type_id"] != 50032 and not item["name"]
    ]
    if unnamed_focus:
        failures.append("KI-Regie Tab focus reached unnamed controls")

    results["passed"] = not failures
    result_path = output / "gui-release-gate.json"
    result_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "passed": not failures,
                "screenshots": len(results["runs"]),
                "failures": failures,
                "result": str(result_path),
            },
            ensure_ascii=False,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
