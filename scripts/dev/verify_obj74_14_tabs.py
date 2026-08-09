"""Repeatable UIA evidence driver for OBJ-74/T023.

The script attaches to an already running PB Studio window. It never starts the
application. Each main tab is selected through UI Automation before the window
and its visible UIA controls are recorded.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable


EXPECTED_TABS = (
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
WINDOW_TITLE_RE = r".*PB Studio.*"
RESULT_FILENAME = "obj74-t023-result.json"


def _enable_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _element_name(wrapper: Any) -> str:
    try:
        return str(wrapper.element_info.name or "").strip()
    except Exception:
        try:
            return str(wrapper.window_text() or "").strip()
        except Exception:
            return ""


def _control_type(wrapper: Any) -> str:
    try:
        return str(wrapper.element_info.control_type or "")
    except Exception:
        return ""


def _visible(wrapper: Any) -> bool:
    try:
        if bool(wrapper.element_info.element.CurrentIsOffscreen):
            return False
    except Exception:
        pass
    try:
        return bool(wrapper.is_visible())
    except Exception:
        return True


def _rectangle(wrapper: Any) -> dict[str, int] | None:
    try:
        rect = wrapper.rectangle()
        return {
            "left": int(rect.left),
            "top": int(rect.top),
            "right": int(rect.right),
            "bottom": int(rect.bottom),
        }
    except Exception:
        return None


def _visible_uia_evidence(window: Any) -> dict[str, Any]:
    controls: list[dict[str, Any]] = []
    texts: list[str] = []
    seen_texts: set[str] = set()

    for wrapper in window.descendants():
        if not _visible(wrapper):
            continue
        name = _element_name(wrapper)
        control_type = _control_type(wrapper)
        if name and name not in seen_texts:
            seen_texts.add(name)
            texts.append(name)
        try:
            automation_id = str(wrapper.element_info.automation_id or "")
        except Exception:
            automation_id = ""
        try:
            enabled = bool(wrapper.is_enabled())
        except Exception:
            enabled = None
        controls.append(
            {
                "name": name,
                "control_type": control_type,
                "automation_id": automation_id,
                "enabled": enabled,
                "rectangle": _rectangle(wrapper),
            }
        )

    return {"visible_texts": texts, "visible_controls": controls}


def _capture_window(hwnd: int, target: Path) -> None:
    import win32gui
    import win32ui
    from PIL import Image

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    if width <= 0 or height <= 0:
        raise RuntimeError(f"invalid window bounds: {(left, top, right, bottom)}")

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
        if rendered != 1:
            raise RuntimeError("PrintWindow returned failure")
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
        image.save(target, "PNG")
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        memory_dc.DeleteDC()
        source_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, window_dc)


def _main_tab_items(window: Any) -> list[Any]:
    project_candidates = [
        wrapper
        for wrapper in window.descendants(control_type="TabItem")
        if _element_name(wrapper) == EXPECTED_TABS[0]
    ]
    if not project_candidates:
        raise RuntimeError("PROJEKT TabItem not found in UIA tree")

    best: list[Any] = []
    for candidate in project_candidates:
        parent = candidate.parent()
        siblings = [
            wrapper
            for wrapper in parent.children()
            if _control_type(wrapper) == "TabItem"
        ]
        if len(siblings) > len(best):
            best = siblings
    if not best:
        raise RuntimeError("main TabItem sibling group not found")
    return best


def _selected_tab_name(tab_items: Iterable[Any]) -> str | None:
    for tab in tab_items:
        try:
            if tab.is_selected():
                return _element_name(tab)
        except Exception:
            continue
    return None


def _base_result(output_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "ticket": "OBJ-74/T023",
        "output_dir": str(output_dir.resolve()),
        "expected_tabs": list(EXPECTED_TABS),
        "actual_tabs": [],
        "tab_tree_exact": False,
        "tabs": [],
        "keyboard": {
            "shortcut": "Ctrl+Tab",
            "expected": list(EXPECTED_TABS[1:]) + [EXPECTED_TABS[0]],
            "actual": [],
            "passed": False,
        },
        "failures": [],
        "passed": False,
    }


def _run(output_dir: Path) -> tuple[dict[str, Any], int]:
    from pywinauto import Application, keyboard

    result = _base_result(output_dir)
    app = Application(backend="uia").connect(title_re=WINDOW_TITLE_RE, timeout=20)
    window_spec = app.window(title_re=WINDOW_TITLE_RE)
    window_spec.wait("visible enabled ready", timeout=20)
    window = window_spec.wrapper_object()
    hwnd = int(window.handle)
    result["window"] = {"title": _element_name(window), "handle": hwnd}

    tab_items = _main_tab_items(window)
    actual_tabs = [_element_name(tab) for tab in tab_items]
    result["actual_tabs"] = actual_tabs
    result["tab_tree_exact"] = actual_tabs == list(EXPECTED_TABS)
    if not result["tab_tree_exact"]:
        result["failures"].append(
            f"main UIA TabItems differ: expected {list(EXPECTED_TABS)!r}, "
            f"got {actual_tabs!r}"
        )

    tab_by_name = {_element_name(tab): tab for tab in tab_items}
    for index, name in enumerate(EXPECTED_TABS, start=1):
        entry: dict[str, Any] = {"name": name, "selected": False, "errors": []}
        tab = tab_by_name.get(name)
        if tab is None:
            entry["errors"].append("TabItem missing")
            result["failures"].append(f"{name}: TabItem missing")
            result["tabs"].append(entry)
            continue

        slug = _slug(name)
        screenshot_path = output_dir / "screenshots" / f"{index:02d}-{slug}.png"
        uia_path = output_dir / "uia" / f"{index:02d}-{slug}.json"
        entry["screenshot"] = str(screenshot_path.relative_to(output_dir))
        entry["uia_evidence"] = str(uia_path.relative_to(output_dir))
        try:
            tab.select()
            time.sleep(0.5)
            entry["selected"] = bool(tab.is_selected())
            if not entry["selected"]:
                raise RuntimeError("UIA selection state did not change")

            evidence = _visible_uia_evidence(window)
            evidence.update({"tab": name, "selected": True})
            _write_json(uia_path, evidence)
            entry["visible_text_count"] = len(evidence["visible_texts"])
            entry["visible_control_count"] = len(evidence["visible_controls"])
            _capture_window(hwnd, screenshot_path)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            entry["errors"].append(message)
            result["failures"].append(f"{name}: {message}")
        result["tabs"].append(entry)

    if EXPECTED_TABS[0] in tab_by_name:
        try:
            window.set_focus()
            first_tab = tab_by_name[EXPECTED_TABS[0]]
            first_tab.select()
            first_tab.set_focus()
            time.sleep(0.2)
            for _ in EXPECTED_TABS:
                keyboard.send_keys("^{TAB}", pause=0.05)
                time.sleep(0.2)
                result["keyboard"]["actual"].append(
                    _selected_tab_name(tab_items)
                )
            result["keyboard"]["passed"] = (
                result["keyboard"]["actual"] == result["keyboard"]["expected"]
            )
            if not result["keyboard"]["passed"]:
                result["failures"].append(
                    "Ctrl+Tab cycle differs: "
                    f"expected {result['keyboard']['expected']!r}, "
                    f"got {result['keyboard']['actual']!r}"
                )
        except Exception as exc:
            message = f"Ctrl+Tab cycle failed: {type(exc).__name__}: {exc}"
            result["keyboard"]["error"] = message
            result["failures"].append(message)
    else:
        result["failures"].append("Ctrl+Tab cycle skipped: PROJEKT missing")

    result["passed"] = not result["failures"]
    return result, 0 if result["passed"] else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and capture all 14 PB Studio tabs from a running window."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for screenshots, UIA evidence, and the JSON result.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / RESULT_FILENAME
    _enable_dpi_awareness()

    try:
        result, exit_code = _run(output_dir)
    except Exception as exc:
        result = _base_result(output_dir)
        message = f"{type(exc).__name__}: {exc}"
        result["fatal_error"] = message
        result["failures"].append(message)
        exit_code = 2

    _write_json(result_path, result)
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "exit_code": exit_code,
                "result": str(result_path.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
