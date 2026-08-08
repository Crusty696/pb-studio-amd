from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
from pywinauto import Application, findwindows
from pywinauto.keyboard import send_keys


EVIDENCE_DIR = Path(__file__).resolve().parent
SCREENSHOT_DIR = EVIDENCE_DIR / "screenshots-cycle-12-project-switch"
REPO_DIR = EVIDENCE_DIR.parents[3]
WPF_LOG = REPO_DIR / "logs" / "wpf_app.log"
GLOBAL_DB = REPO_DIR / "data" / "pb_studio.db"
SOURCE_PROJECT = Path(
    r"C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245"
)
TARGET_PROJECT = Path(
    r"C:\Users\david\Documents\PBStudio\ReleaseSmoke_20260727_083320"
)
OUTPUT_PATH = (
    SOURCE_PROJECT
    / "output"
    / "t337_project_switch_cancelled_cycle12.mp4"
)
BACKEND_LOG = Path(os.environ["T337_BACKEND_LOG"])
USER32 = ctypes.windll.user32
ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HWND,
    wintypes.LPARAM,
)


def _http_json(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 30,
) -> dict[str, Any]:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"http://127.0.0.1:8765{path}",
        data=body,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _visible_text(window) -> list[str]:
    values: set[str] = set()
    for control_type in ("Text", "Edit", "Button"):
        for control in window.descendants(control_type=control_type):
            try:
                value = control.window_text().strip()
                if control.is_visible() and value:
                    values.add(value)
            except Exception:
                continue
    return sorted(values)


def _capture(window, name: str) -> dict[str, Any]:
    screenshot = SCREENSHOT_DIR / f"{name}.png"
    image = window.capture_as_image()
    image.save(screenshot)
    extrema = image.convert("RGB").getextrema()
    channel_range_sum = sum(high - low for low, high in extrema)
    if channel_range_sum <= 30:
        raise RuntimeError(
            f"Blank screenshot gate failed for {name}: {channel_range_sum}"
        )
    return {
        "path": str(screenshot),
        "size": list(image.size),
        "channel_range_sum": channel_range_sum,
    }


def _invoke_button_from_text(window, text: str) -> None:
    control = window.child_window(
        title=text,
        control_type="Text",
    ).wrapper_object()
    for _ in range(8):
        control = control.parent()
        if control.element_info.control_type == "Button":
            if not control.is_enabled():
                raise RuntimeError(f"Button is disabled: {text}")
            control.invoke()
            return
    raise RuntimeError(f"No button ancestor found for text: {text}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _project_hashes(root: Path) -> dict[str, str]:
    return {
        name: _sha256(root / name)
        for name in ("project.json", "timeline.json", "state.db")
    }


def _matching_ffmpeg_processes() -> list[dict[str, Any]]:
    needle = str(OUTPUT_PATH).casefold()
    matches = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (process.info["name"] or "").casefold()
            command_line = " ".join(process.info["cmdline"] or [])
            if "ffmpeg" in name and needle in command_line.casefold():
                matches.append(
                    {
                        "pid": process.info["pid"],
                        "name": process.info["name"],
                        "command_line": command_line,
                    }
                )
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return matches


def _queue_row(queue_job_id: str) -> dict[str, Any] | None:
    connection = sqlite3.connect(
        f"file:{GLOBAL_DB}?mode=ro",
        uri=True,
        timeout=5,
    )
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT job_id, status, progress_percent, error, output_path, "
            "created_at, updated_at, started_at, finished_at "
            "FROM render_queue WHERE job_id = ?",
            (queue_job_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def _native_window_text(handle: int) -> str:
    length = USER32.GetWindowTextLengthW(handle)
    buffer = ctypes.create_unicode_buffer(length + 1)
    USER32.GetWindowTextW(handle, buffer, len(buffer))
    return buffer.value


def _native_class_name(handle: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    USER32.GetClassNameW(handle, buffer, len(buffer))
    return buffer.value


def _native_top_windows() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    @ENUM_WINDOWS_PROC
    def callback(handle: int, _: int) -> bool:
        if USER32.IsWindowVisible(handle):
            result.append(
                {
                    "handle": int(handle),
                    "title": _native_window_text(handle),
                    "class_name": _native_class_name(handle),
                    "owner": int(USER32.GetWindow(handle, 4)),
                }
            )
        return True

    USER32.EnumWindows(callback, 0)
    return result


def _native_child_windows(parent: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    @ENUM_WINDOWS_PROC
    def callback(handle: int, _: int) -> bool:
        result.append(
            {
                "handle": int(handle),
                "title": _native_window_text(handle),
                "class_name": _native_class_name(handle),
                "visible": bool(USER32.IsWindowVisible(handle)),
                "enabled": bool(USER32.IsWindowEnabled(handle)),
            }
        )
        return True

    USER32.EnumChildWindows(parent, callback, 0)
    return result


def _open_project_with_dialog(window, target: Path) -> dict[str, Any]:
    project_tab = window.child_window(title="PROJEKT", control_type="TabItem")
    project_tab.select()
    time.sleep(1)
    baseline = {
        candidate["handle"]
        for candidate in _native_top_windows()
    }
    open_button = window.child_window(
        title_re=r"Projekt .*ffnen",
        control_type="Button",
    )
    if not open_button.is_enabled():
        raise RuntimeError("Project open button is disabled")
    open_button.invoke()

    dialog_handle = 0
    observed: list[dict[str, Any]] = []
    for _ in range(40):
        time.sleep(0.25)
        observed = [
            candidate
            for candidate in _native_top_windows()
            if candidate["handle"] not in baseline
        ]
        preferred = [
            candidate
            for candidate in observed
            if candidate["class_name"] == "#32770"
        ]
        owned = [
            candidate
            for candidate in observed
            if candidate["owner"] == window.handle
        ]
        if preferred or owned:
            dialog_handle = int((preferred or owned)[0]["handle"])
            break
    if not dialog_handle:
        raise RuntimeError(f"Project dialog did not open: {observed}")

    USER32.ShowWindow(dialog_handle, 9)
    USER32.SetForegroundWindow(dialog_handle)
    send_keys("%d")
    time.sleep(0.25)
    send_keys(str(target), with_spaces=True, pause=0.001)
    send_keys("{ENTER}")
    time.sleep(1)

    children = _native_child_windows(dialog_handle)
    select_buttons = [
        child
        for child in children
        if child["class_name"] == "Button"
        and child["visible"]
        and child["enabled"]
        and (
            "ordner" in child["title"].casefold()
            or "select" in child["title"].casefold()
        )
    ]
    if select_buttons:
        USER32.PostMessageW(select_buttons[0]["handle"], 0x00F5, 0, 0)
    else:
        USER32.SetForegroundWindow(dialog_handle)
        send_keys("{ENTER}")

    for _ in range(80):
        time.sleep(0.25)
        if not USER32.IsWindow(dialog_handle) or not USER32.IsWindowVisible(
            dialog_handle
        ):
            break
    else:
        raise RuntimeError(
            f"Project dialog did not close after selection: {observed}"
        )

    return {
        "dialog_handle": dialog_handle,
        "observed_windows": observed,
        "select_buttons": select_buttons,
    }


def _close_project_during_job(window) -> dict[str, Any]:
    project_tab = window.child_window(title="PROJEKT", control_type="TabItem")
    project_tab.select()
    time.sleep(1)
    close_button = window.child_window(
        title_re=r"Projekt schlie.en",
        control_type="Button",
    )
    if not close_button.is_enabled():
        raise RuntimeError("Project close button is disabled during render")
    close_button.invoke()

    closed_text: list[str] = []
    for _ in range(80):
        time.sleep(0.25)
        closed_text = _visible_text(window)
        if any(value == "Kein Projekt" for value in closed_text):
            break
    else:
        raise RuntimeError(
            f"Project did not close during running job: {closed_text}"
        )
    return {
        "visible_project_closed": True,
        "screenshot": _capture(
            window,
            "project-closed-during-running-job",
        ),
    }


def main() -> None:
    if OUTPUT_PATH.exists():
        raise RuntimeError(
            f"Refusing to overwrite existing T337 target: {OUTPUT_PATH}"
        )
    existing_related = list(
        OUTPUT_PATH.parent.glob(f"{OUTPUT_PATH.stem}*")
    )
    if existing_related:
        raise RuntimeError(
            f"Refusing to reuse existing T337 artifacts: {existing_related}"
        )

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    before_hashes = {
        "source": _project_hashes(SOURCE_PROJECT),
        "target": _project_hashes(TARGET_PROJECT),
    }
    models_list = _http_json("/models/list")
    model_recommendation = _http_json(
        "/models/recommendations?task=video_captioning&mode=balance"
    )
    provider_available = bool(
        models_list.get("lmstudio_available")
        or models_list.get("ollama_available")
    )
    if (
        provider_available
        and "Kein LLM-Provider erreichbar"
        in str(model_recommendation.get("reason") or "")
    ):
        raise RuntimeError(
            "Live model provider was misreported as unreachable: "
            f"{model_recommendation}"
        )

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
    user32.ShowWindow(handles[0], 3)
    user32.SetForegroundWindow(handles[0])
    user32.SetWindowPos(
        handles[0],
        -1,
        0,
        0,
        0,
        0,
        0x0001 | 0x0002 | 0x0040,
    )
    window.wait("visible enabled ready", timeout=20)
    window.maximize()
    time.sleep(1)

    export_tab = window.child_window(title="EXPORT", control_type="TabItem")
    export_tab.select()
    time.sleep(2)
    _invoke_button_from_text(window, "Render starten")
    time.sleep(1)
    failure_text = _visible_text(window)
    if not any("Kein Ausgabepfad" in value for value in failure_text):
        raise RuntimeError(
            f"Visible render failure state missing: {failure_text}"
        )
    failure_capture = _capture(window, "export-visible-failure")

    timeline = _http_json("/pacing/timeline")
    audio_path = timeline.get("audio_path")
    entries = timeline.get("entries") or []
    if not audio_path or not entries:
        raise RuntimeError("ReleaseQC timeline/audio contract is incomplete")
    total_seconds = sum(
        max(
            float(entry.get("end_time", 0))
            - float(entry.get("start_time", 0)),
            0,
        )
        for entry in entries
    )
    render = _http_json(
        "/render/start",
        method="POST",
        payload={
            "output_path": str(OUTPUT_PATH),
            "audio_path": audio_path,
            "quality": "preview",
            "encoder": "h264_amf",
            "resolution_width": 1280,
            "resolution_height": 720,
            "fps": 30.0,
            "bitrate_mbps": 4.0,
            "include_audio": True,
        },
        timeout=60,
    )
    task_id = render["task_id"]
    queue_job_id = render["queue_job_id"]
    backend_log_start = BACKEND_LOG.stat().st_size

    status = render
    ffmpeg_processes = []
    for _ in range(120):
        time.sleep(1)
        try:
            status = _http_json(f"/render/status/{task_id}", timeout=5)
        except urllib.error.HTTPError:
            break
        ffmpeg_processes = _matching_ffmpeg_processes()
        if (
            status.get("status") == "running"
            and (
                int(status.get("current_frame") or 0) > 0
                or ffmpeg_processes
            )
        ):
            break
        if status.get("status") in {"completed", "failed", "cancelled"}:
            break
    if status.get("status") != "running":
        raise RuntimeError(
            f"Render did not reach running state before switch: {status}"
        )

    partial_text = _visible_text(window)
    if not any(value == "Abbrechen" for value in partial_text):
        raise RuntimeError(
            f"Visible running state missing cancel control: {partial_text}"
        )
    partial_capture = _capture(window, "export-running-partial-progress")
    current_frame = int(status.get("current_frame") or 0)
    out_time_seconds = current_frame / 30.0
    monitor_sample = {
        "sampled_at": datetime.now().astimezone().isoformat(),
        "task_id": task_id,
        "queue_job_id": queue_job_id,
        "status": status,
        "ffmpeg_processes": ffmpeg_processes,
        "backend_log_bytes_before": backend_log_start,
        "backend_log_bytes_now": BACKEND_LOG.stat().st_size,
        "backend_log_growth_bytes": (
            BACKEND_LOG.stat().st_size - backend_log_start
        ),
        "output_exists": OUTPUT_PATH.exists(),
        "output_bytes": OUTPUT_PATH.stat().st_size if OUTPUT_PATH.exists() else 0,
        "out_time_seconds": out_time_seconds,
    }

    close_evidence = _close_project_during_job(window)
    dialog_evidence = _open_project_with_dialog(window, TARGET_PROJECT)
    project_info = {}
    for _ in range(80):
        time.sleep(0.25)
        try:
            project_info = _http_json("/project/info", timeout=5)
        except urllib.error.HTTPError:
            continue
        if Path(project_info.get("path", "")).resolve() == TARGET_PROJECT.resolve():
            break
    else:
        raise RuntimeError(
            f"Backend did not switch to target project: {project_info}"
        )

    target_text = _visible_text(window)
    if not any(TARGET_PROJECT.name in value for value in target_text):
        raise RuntimeError(
            f"Target project name is not visible after switch: {target_text}"
        )
    project_capture = _capture(window, "project-after-running-job-switch")

    queue = None
    for _ in range(120):
        time.sleep(0.5)
        queue = _queue_row(queue_job_id)
        if (
            queue
            and queue.get("status") == "failed"
            and queue.get("error") == "cancelled"
            and not _matching_ffmpeg_processes()
        ):
            break
    else:
        raise RuntimeError(
            "Cancelled render did not terminate cleanly: "
            f"queue={queue}, ffmpeg={_matching_ffmpeg_processes()}"
        )

    export_tab.select()
    time.sleep(2)
    post_switch_text = _visible_text(window)
    if not any("Bereit für Rendering" in value for value in post_switch_text):
        raise RuntimeError(
            f"Export did not recover after project switch: {post_switch_text}"
        )
    if any(value == "Abbrechen" for value in post_switch_text):
        raise RuntimeError("Stale cancel control remained after project switch")
    post_switch_capture = _capture(window, "export-after-project-switch")

    related_after = [
        {
            "path": str(path),
            "bytes": path.stat().st_size if path.is_file() else None,
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
        }
        for path in OUTPUT_PATH.parent.glob(f"{OUTPUT_PATH.stem}*")
    ]
    if OUTPUT_PATH.exists() or any(
        item["is_file"] for item in related_after
    ):
        raise RuntimeError(
            f"Cancelled render left output artifacts: {related_after}"
        )

    after_hashes = {
        "source": _project_hashes(SOURCE_PROJECT),
        "target": _project_hashes(TARGET_PROJECT),
    }
    for side in ("source", "target"):
        for name in ("project.json", "timeline.json", "state.db"):
            if before_hashes[side][name] != after_hashes[side][name]:
                raise RuntimeError(
                    f"Project file changed during switch: {side}/{name}"
                )

    log_text = WPF_LOG.read_text(encoding="utf-8", errors="replace")
    error_counts = {
        "xaml_parse_exception": log_text.count("XamlParseException"),
        "path_xpath_failure": log_text.count(
            'Die bidirektionale Bindung erfordert "Path" oder "XPath".'
        ),
        "unhandled_ui_exception": log_text.count(
            "Unbehandelte UI-Exception"
        ),
        "unobserved_task_exception": log_text.count(
            "Unbeobachtete Task-Exception"
        ),
    }
    if any(error_counts.values()):
        raise RuntimeError(f"WPF log gate failed: {error_counts}")

    report = {
        "status": "pass",
        "completed_at": datetime.now().astimezone().isoformat(),
        "source_project": str(SOURCE_PROJECT),
        "target_project": str(TARGET_PROJECT),
        "timeline_total_seconds": total_seconds,
        "models_live": {
            "list": models_list,
            "recommendation": model_recommendation,
        },
        "failure_state": {
            "status_text": next(
                value
                for value in failure_text
                if "Kein Ausgabepfad" in value
            ),
            "screenshot": failure_capture,
        },
        "partial_progress_state": {
            "status": status,
            "screenshot": partial_capture,
        },
        "ffmpeg_monitor": monitor_sample,
        "project_switch": {
            "close_during_job": close_evidence,
            "dialog": dialog_evidence,
            "backend_project_info": project_info,
            "screenshot": project_capture,
        },
        "cancel_contract": {
            "queue": queue,
            "matching_ffmpeg_after": _matching_ffmpeg_processes(),
            "output_exists": OUTPUT_PATH.exists(),
            "related_output_artifacts": related_after,
        },
        "post_switch_export": {
            "status_visible": "Bereit für Rendering",
            "cancel_control_visible": False,
            "screenshot": post_switch_capture,
        },
        "project_hashes": {
            "before": before_hashes,
            "after": after_hashes,
        },
        "wpf_log": {
            "path": str(WPF_LOG),
            "bytes": WPF_LOG.stat().st_size,
            "error_counts": error_counts,
        },
    }
    (EVIDENCE_DIR / "project-switch-cycle-12.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
