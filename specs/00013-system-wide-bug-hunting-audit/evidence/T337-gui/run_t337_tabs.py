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
SCREENSHOT_DIR = EVIDENCE_DIR / "screenshots-cycle-4"
CORE_TABS = [
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
]
EXTENDED_TABS = ["INGEST", "ANCHOR"]


def _get_json(path: str) -> dict[str, Any]:
    with urllib.request.urlopen(
        f"http://127.0.0.1:8765{path}",
        timeout=15,
    ) as response:
        return json.loads(response.read().decode("utf-8"))


def _content_metrics(image) -> dict[str, Any]:
    width, height = image.size
    left = min(40, max(width - 1, 0))
    top = min(180, max(height - 1, 0))
    right = max(width - 40, left + 1)
    bottom = max(height - 30, top + 1)
    content = image.crop((left, top, right, bottom)).convert("RGB")
    step_x = max(content.width // 80, 1)
    step_y = max(content.height // 60, 1)
    pixels = [
        content.getpixel((x, y))
        for x in range(0, content.width, step_x)
        for y in range(0, content.height, step_y)
    ]
    ranges = [
        max(pixel[channel] for pixel in pixels)
        - min(pixel[channel] for pixel in pixels)
        for channel in range(3)
    ]
    return {
        "width": width,
        "height": height,
        "sample_count": len(pixels),
        "channel_range_sum": sum(ranges),
        "unique_sample_colors": len(set(pixels)),
    }


def _visible_receipt(window, *, include_all: bool) -> dict[str, Any]:
    visible = []
    controls = (
        window.descendants()
        if include_all
        else [
            *window.descendants(control_type="Text"),
            *window.descendants(control_type="Edit"),
            *window.descendants(control_type="Button"),
        ]
    )
    for control in controls:
        try:
            if not control.is_visible():
                continue
            visible.append(
                {
                    "type": control.element_info.control_type,
                    "name": control.window_text(),
                    "automation_id": control.element_info.automation_id,
                    "enabled": control.is_enabled(),
                }
            )
        except Exception:
            continue
    text_values = sorted(
        {
            item["name"].strip()
            for item in visible
            if item["name"] and item["name"].strip()
        }
    )
    return {
        "visible_control_count": len(visible),
        "visible_type_counts": {
            control_type: sum(
                item["type"] == control_type for item in visible
            )
            for control_type in sorted({item["type"] for item in visible})
        },
        "visible_text": text_values,
        "copyable_textbox_count": sum(
            item["type"] == "Edit" for item in visible
        ),
    }


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
    time.sleep(0.5)
    user32.ShowWindow(handles[0], 3)
    user32.SetForegroundWindow(handles[0])
    time.sleep(1.0)
    window.wait("visible enabled ready", timeout=20)
    try:
        window.maximize()
        window.set_focus()
    except Exception:
        pass
    time.sleep(1.0)

    tab_receipts = []
    models_receipt = None
    for tab_name in [*CORE_TABS, *EXTENDED_TABS]:
        tab = window.child_window(
            title=tab_name,
            control_type="TabItem",
        )
        if not tab.exists(timeout=5):
            raise RuntimeError(f"Missing tab: {tab_name}")
        tab.select()
        time.sleep(4.0 if tab_name == "MODELLE" else 0.6)
        if not tab.is_selected():
            raise RuntimeError(f"Tab did not become selected: {tab_name}")
        image = window.capture_as_image()
        screenshot = SCREENSHOT_DIR / f"{tab_name.lower()}.png"
        image.save(screenshot)
        metrics = _content_metrics(image)
        visible = _visible_receipt(
            window,
            include_all=tab_name in {"MODELLE", "EXPORT"},
        )
        if metrics["width"] < 1000 or metrics["height"] < 600:
            raise RuntimeError(f"Window too small on {tab_name}: {metrics}")
        if metrics["channel_range_sum"] <= 30:
            raise RuntimeError(f"Blank render surface on {tab_name}: {metrics}")
        if visible["visible_control_count"] < 3:
            raise RuntimeError(
                f"UIA surface too small on {tab_name}: {visible}"
            )
        receipt = {
            "tab": tab_name,
            "core": tab_name in CORE_TABS,
            "screenshot": str(screenshot),
            "metrics": metrics,
            **visible,
        }
        tab_receipts.append(receipt)
        if tab_name == "MODELLE":
            models_receipt = receipt

    model_api = _get_json("/models/list")
    recommendation_api = _get_json("/models/recommendations")
    if models_receipt is None:
        raise RuntimeError("Models receipt missing")
    models_text = " | ".join(models_receipt["visible_text"])
    installed_count = len(model_api.get("models") or [])
    if installed_count == 0 and "0 installiert" not in models_text:
        raise RuntimeError(
            f"Models UI does not expose empty installed state: {models_text}"
        )
    if model_api.get("base_url") not in models_text:
        raise RuntimeError(
            f"Models UI missing live base URL: {model_api.get('base_url')}"
        )

    report = {
        "status": "pass",
        "completed_at": datetime.now().astimezone().isoformat(),
        "window": {
            "title": window.window_text(),
            "rectangle": {
                "left": window.rectangle().left,
                "top": window.rectangle().top,
                "right": window.rectangle().right,
                "bottom": window.rectangle().bottom,
            },
        },
        "core_tabs_expected": len(CORE_TABS),
        "core_tabs_passed": sum(item["core"] for item in tab_receipts),
        "extended_tabs_expected": len(EXTENDED_TABS),
        "extended_tabs_passed": sum(
            not item["core"] for item in tab_receipts
        ),
        "tabs": tab_receipts,
        "models": {
            "api": model_api,
            "recommendation": recommendation_api,
            "ui_visible_text": models_receipt["visible_text"],
            "ui_screenshot": models_receipt["screenshot"],
        },
    }
    (EVIDENCE_DIR / "tabs-ui-report-cycle-4.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
