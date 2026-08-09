"""Non-destructive live smoke for video selection isolation across project switches."""

from __future__ import annotations

import ctypes
import faulthandler
import json
import os
import sqlite3
import time
import urllib.request
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pywinauto import Application, findwindows
from pywinauto.keyboard import send_keys


REPO_ROOT = Path(__file__).resolve().parents[1]
GLOBAL_DB = REPO_ROOT / "data" / "pb_studio.db"
USER32 = ctypes.windll.user32
ENUM_WINDOWS_PROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HWND,
    wintypes.LPARAM,
)
VIDEO_SUFFIXES = {".avi", ".mkv", ".mov", ".mp4", ".webm", ".wmv"}


@dataclass(frozen=True)
class ProjectCandidate:
    root: Path
    clip_ids: frozenset[int]


def _read_only_connection(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro",
        uri=True,
        timeout=5,
    )


def _discover_candidates() -> tuple[ProjectCandidate, ProjectCandidate, int]:
    projects: dict[int, Path] = {}
    media: dict[int, set[int]] = {}
    connection = _read_only_connection(GLOBAL_DB)
    try:
        for project_id, raw_json in connection.execute(
            "SELECT id, json_data FROM projects ORDER BY id"
        ):
            try:
                payload = json.loads(raw_json or "{}")
            except json.JSONDecodeError:
                continue
            root = Path(str(payload.get("path") or ""))
            if root.is_dir() and (root / "project.json").is_file():
                projects[int(project_id)] = root.resolve()

        for project_id, file_path, raw_metadata in connection.execute(
            "SELECT project_id, file_path, metadata_json FROM media "
            "WHERE project_id IS NOT NULL ORDER BY project_id, id"
        ):
            project_id = int(project_id)
            if project_id not in projects:
                continue
            try:
                metadata = json.loads(raw_metadata or "{}")
                clip_id = int(metadata["clip_id"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            path = Path(str(file_path))
            if (
                metadata.get("clip_type") == "video"
                and path.suffix.casefold() in VIDEO_SUFFIXES
                and path.is_file()
            ):
                media.setdefault(project_id, set()).add(clip_id)
    finally:
        connection.close()

    pairs: list[tuple[int, int, int, int, int]] = []
    for source_id, source_clips in media.items():
        if len(source_clips) < 2:
            continue
        for target_id, target_clips in media.items():
            if source_id == target_id:
                continue
            overlap = source_clips & target_clips
            if overlap:
                pairs.append(
                    (
                        len(source_clips),
                        len(target_clips),
                        source_id,
                        target_id,
                        min(overlap),
                    )
                )
    if not pairs:
        raise RuntimeError(
            "No local A/B projects with two source videos and a reused clip ID"
        )

    _, _, source_id, target_id, reused_id = min(pairs)
    return (
        ProjectCandidate(projects[source_id], frozenset(media[source_id])),
        ProjectCandidate(projects[target_id], frozenset(media[target_id])),
        reused_id,
    )


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


def _open_project(window, target: Path) -> None:
    window.child_window(title="PROJEKT", control_type="TabItem").select()
    time.sleep(0.5)
    baseline = {candidate["handle"] for candidate in _native_top_windows()}
    button = window.child_window(title="Projekt öffnen", control_type="Button")
    if not button.is_enabled():
        raise RuntimeError("Project-open action is disabled")
    # UIA Invoke blocks while WPF owns the modal folder dialog. A physical
    # click lets this process drive that dialog and keeps the smoke bounded.
    button.click_input()

    dialog_handle = 0
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
        raise RuntimeError("Project folder dialog did not open")

    USER32.ShowWindow(dialog_handle, 9)
    USER32.SetForegroundWindow(dialog_handle)
    send_keys("%d")
    time.sleep(0.25)
    send_keys(str(target), with_spaces=True, pause=0.001)
    send_keys("{ENTER}")
    time.sleep(0.75)

    select_buttons = [
        child
        for child in _native_child_windows(dialog_handle)
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
        if not USER32.IsWindowVisible(dialog_handle):
            return
    raise RuntimeError("Project folder dialog did not close")


def _project_info() -> dict[str, Any]:
    request = urllib.request.Request("http://127.0.0.1:8765/project/info")
    owner_capability = os.environ.get("PBSTUDIO_OWNER_CAPABILITY", "").strip()
    if owner_capability:
        request.add_header("X-PBStudio-Owner-Capability", owner_capability)
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_for_project(target: Path) -> None:
    for _ in range(80):
        time.sleep(0.25)
        try:
            active = Path(str(_project_info().get("path") or "")).resolve()
        except Exception:
            continue
        if active == target.resolve():
            return
    raise RuntimeError("Backend did not activate the expected anonymous project")


def _current_project_path() -> Path | None:
    try:
        raw_path = str(_project_info().get("path") or "").strip()
    except Exception:
        return None
    return Path(raw_path).resolve() if raw_path else None


def _video_items(window, minimum: int):
    window.child_window(title="VIDEO", control_type="TabItem").select()
    video_list = window.child_window(
        title="Video-Clip-Liste",
        control_type="List",
    )
    for _ in range(80):
        time.sleep(0.25)
        items = video_list.children(control_type="ListItem")
        if len(items) >= minimum:
            return video_list, items
    raise RuntimeError("Video list did not expose the expected item count")


def _selected_items(items) -> list[Any]:
    selected = []
    for item in items:
        try:
            if item.is_selected():
                selected.append(item)
        except Exception:
            continue
    return selected


def _batch_buttons(window):
    return (
        window.child_window(
            title="Ausgewählte Video-Clips löschen",
            control_type="Button",
        ),
        window.child_window(
            title="Ausgewählte Video-Clips analysieren",
            control_type="Button",
        ),
    )


def main() -> None:
    if os.name != "nt":
        raise RuntimeError("This live smoke requires Windows UI Automation")

    faulthandler.dump_traceback_later(120, exit=True)
    source, target, reused_id = _discover_candidates()
    print("phase=candidates_ready", flush=True)
    handles = findwindows.find_windows(title="PB Studio AMD", top_level_only=True)
    if len(handles) != 1:
        raise RuntimeError("Expected exactly one running PB Studio main window")
    app = Application(backend="uia").connect(handle=handles[0], timeout=20)
    window = app.window(handle=handles[0])
    window.wait("visible enabled ready", timeout=20)
    print("phase=window_ready", flush=True)
    original_project = _current_project_path()
    try:
        _open_project(window, source.root)
        _wait_for_project(source.root)
        print("phase=source_open", flush=True)
        _, source_items = _video_items(window, 2)
        source_items[0].iface_selection_item.Select()
        source_items[1].iface_selection_item.AddToSelection()
        time.sleep(0.5)
        if len(_selected_items(source_items)) != 2:
            raise RuntimeError("Source project did not retain a two-item selection")

        delete_button, analyze_button = _batch_buttons(window)
        if not delete_button.is_enabled() or not analyze_button.is_enabled():
            raise RuntimeError("Batch actions were not enabled for the source selection")

        _open_project(window, target.root)
        _wait_for_project(target.root)
        print("phase=target_open", flush=True)
        _, target_items = _video_items(window, 1)
        time.sleep(0.5)
        delete_button, analyze_button = _batch_buttons(window)
        if _selected_items(target_items):
            raise RuntimeError("Selection leaked into the target project")
        if delete_button.is_enabled() or analyze_button.is_enabled():
            raise RuntimeError("Batch actions remained enabled without target selection")

        print(
            json.dumps(
                {
                    "status": "pass",
                    "source_video_count": len(source.clip_ids),
                    "target_video_count": len(target.clip_ids),
                    "reused_clip_id": reused_id,
                    "source_selected": 2,
                    "target_selected": 0,
                    "delete_enabled_after_switch": False,
                    "analyze_enabled_after_switch": False,
                    "destructive_actions_invoked": False,
                },
                sort_keys=True,
            )
        )
    finally:
        if original_project is not None and original_project.is_dir():
            _open_project(window, original_project)
            _wait_for_project(original_project)
        faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    main()
