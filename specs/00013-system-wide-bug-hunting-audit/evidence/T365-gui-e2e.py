"""Release-WPF UIA and screenshot proof for T365."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pywinauto import Application


ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path(__file__).with_name("T365-gui")
RECEIPT = Path(__file__).with_name("T365-gui-runtime.json")


def _get_json(path: str) -> dict:
    with urllib.request.urlopen(
        f"http://127.0.0.1:8765{path}",
        timeout=30,
    ) as response:
        return json.load(response)


def _visible_texts(window) -> list[str]:
    texts: list[str] = []
    for child in window.descendants(control_type="Text"):
        try:
            if not child.is_visible():
                continue
            rect = child.rectangle()
            if rect.width() <= 0 or rect.height() <= 0:
                continue
            text = (child.window_text() or "").strip()
            if text and text not in texts:
                texts.append(text)
        except Exception:
            continue
    return texts


def _activate_tab(window, name: str, marker: str, *, prefer_select: bool = False):
    tab = window.child_window(title=name, control_type="TabItem")
    methods = ("select", "click_input") if prefer_select else ("click_input", "select")
    for method in methods:
        getattr(tab, method)()
        time.sleep(2.0)
        texts = _visible_texts(window)
        if marker in texts:
            return texts
    raise AssertionError(f"Tab {name} did not render marker {marker!r}")


def _capture(window, name: str) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    window.set_focus()
    time.sleep(0.4)
    image = window.capture_as_image().convert("RGB")
    path = OUTPUT_DIR / f"{name.lower()}.png"
    image.save(path)

    width, height = image.size
    if width < 500 or height < 400:
        raise AssertionError(f"{name} screenshot too small: {width}x{height}")
    crop = image.crop((40, 80, width - 40, height - 30))
    pixels = list(crop.resize((80, 50)).getdata())
    variance = sum(
        max(channel) - min(channel)
        for channel in zip(*pixels, strict=True)
    )
    if variance <= 30:
        raise AssertionError(f"{name} screenshot is visually blank: {variance}")
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
        "width": width,
        "height": height,
        "color_range_sum": variance,
    }


def _contains(texts: list[str], fragment: str) -> bool:
    return any(fragment in text for text in texts)


def main() -> dict:
    gpu = _get_json("/gpu/status")
    models = _get_json("/models/list?refresh=true")
    expected_model_count = len(models["models"])

    app = Application(backend="uia").connect(
        title="PB Studio AMD",
        timeout=20,
    )
    window = app.window(title="PB Studio AMD")
    window.wait("visible", timeout=10)
    process = app.process
    results: dict[str, dict] = {}

    settings = _activate_tab(window, "SETTINGS", "GPU STATUS")
    for expected in (
        "AMD Radeon RX 7800 XT",
        "0x00000000_0x0001185b",
        "highest_vram_amd",
        "Aktiv auf ausgewähltem Adapter",
        "Bereit",
    ):
        if expected not in settings:
            raise AssertionError(f"SETTINGS is missing {expected!r}")
    if not _contains(settings, "16177 MB"):
        raise AssertionError("SETTINGS does not show dedicated RX 7800 XT VRAM")
    results["settings"] = {
        "checks": {
            "adapter_name": gpu["adapter_name"],
            "adapter_index": gpu["adapter_index"],
            "adapter_luid": gpu["adapter_luid"],
            "selection_policy": gpu["selection_policy"],
            "directml_active": gpu["directml_active"],
            "monitoring_status": gpu["monitoring_status"],
            "monitoring_error": gpu["monitoring_error"],
        },
        "screenshot": _capture(window, "settings"),
    }

    performance = _activate_tab(
        window,
        "PERFORMANCE",
        "VRAM TELEMETRIE",
        prefer_select=True,
    )
    for expected in ("VRAM TELEMETRIE", "VRAM BUDGET", "MAX (MB)", "USABLE"):
        if expected not in performance:
            raise AssertionError(f"PERFORMANCE is missing {expected!r}")
    results["performance"] = {
        "visible_markers": [
            marker
            for marker in ("VRAM TELEMETRIE", "VRAM BUDGET", "MAX (MB)", "USABLE")
            if marker in performance
        ],
        "screenshot": _capture(window, "performance"),
    }

    model_texts = _activate_tab(window, "MODELLE", "INSTALLIERT")
    summary = next(
        (
            text
            for text in model_texts
            if " installiert " in text and " verfuegbar " in text
        ),
        "",
    )
    for expected in (
        f"{expected_model_count} installiert",
        "Hybrid: beide live",
        "LM Studio: READY",
        "Ollama: READY",
        "LM STUDIO",
        "OLLAMA",
        "GELADEN",
        "ON-DEMAND",
    ):
        if not _contains(model_texts, expected):
            raise AssertionError(f"MODELLE is missing {expected!r}")
    results["models"] = {
        "api_model_count": expected_model_count,
        "summary": summary,
        "providers": models["providers"],
        "screenshot": _capture(window, "models"),
    }

    video = _activate_tab(window, "VIDEO", "SCENE ANALYSIS")
    for expected in (
        "Analysieren",
        "Alle analysieren",
        "Markierte analysieren",
        "SCENE ANALYSIS",
    ):
        if expected not in video:
            raise AssertionError(f"VIDEO is missing {expected!r}")
    if _contains(video, "JSON") or _contains(video, "Exception"):
        raise AssertionError("VIDEO exposes a JSON/exception failure")
    results["video"] = {
        "visible_markers": [
            marker
            for marker in (
                "Analysieren",
                "Alle analysieren",
                "Markierte analysieren",
                "SCENE ANALYSIS",
            )
            if marker in video
        ],
        "screenshot": _capture(window, "video"),
    }

    if not app.is_process_running():
        raise AssertionError("Release WPF process exited during UIA sweep")

    wpf_log = (ROOT / "logs" / "wpf_app.log").read_text(
        encoding="utf-8",
        errors="replace",
    )
    forbidden = [
        token
        for token in ("JsonException", "Unhandled exception", "Fatal")
        if token.casefold() in wpf_log.casefold()
    ]
    if forbidden:
        raise AssertionError(f"WPF log contains failures: {forbidden}")

    receipt = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "release_process_id": process,
        "window_title": window.window_text(),
        "window_size": {
            "width": window.rectangle().width(),
            "height": window.rectangle().height(),
        },
        "results": results,
        "wpf_log_forbidden_matches": forbidden,
    }
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return receipt


if __name__ == "__main__":
    main()
