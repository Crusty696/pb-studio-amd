"""Drive the running PB Studio window via UIA for T013 GUI evidence.

Usage:
  t013_gui_drive.py tab <TabName> <shot.png>
  t013_gui_drive.py click <ButtonName> <shot.png>
  t013_gui_drive.py dump <depth> [filter]          # whole desktop windows of the process
  t013_gui_drive.py shot <shot.png>
Screenshots are taken from the foreground window rectangle (PIL.ImageGrab).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PIL import ImageGrab
from pywinauto import Application, Desktop

TITLE = "PB Studio AMD"


def main_window():
    app = Application(backend="uia").connect(title=TITLE, timeout=10)
    return app, app.window(title=TITLE)


def shot(win, path: str) -> None:
    w = win.wrapper_object()
    try:
        w.set_focus()
    except Exception as exc:  # noqa: BLE001
        print("set_focus failed:", exc)
    time.sleep(1.5)
    r = w.rectangle()
    ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom), all_screens=True).save(path)
    print("screenshot", path)


def walk(ctrl, depth, level=0, filt=""):
    if level > depth:
        return
    info = ctrl.element_info
    name = (info.name or "").replace("\n", " ")[:120]
    line = f"{'  ' * level}{info.control_type} | {info.automation_id} | {name}"
    if not filt or filt.lower() in line.lower():
        print(line)
    try:
        children = ctrl.children()
    except Exception as exc:  # noqa: BLE001 - element vanished during re-render
        print(f"{'  ' * (level + 1)}<children unavailable: {type(exc).__name__}>")
        return
    for child in children:
        try:
            walk(child, depth, level + 1, filt)
        except Exception as exc:  # noqa: BLE001
            print(f"{'  ' * (level + 1)}<element unavailable: {type(exc).__name__}>")


cmd = sys.argv[1]
app, win = main_window()
if cmd == "tab":
    win.wrapper_object().set_focus()
    win.child_window(title=sys.argv[2], control_type="TabItem").select()
    time.sleep(2.5)
    walk(win.child_window(control_type="Tab").wrapper_object(), 9)
    shot(win, sys.argv[3])
elif cmd == "click":
    win.wrapper_object().set_focus()
    btn = win.child_window(title=sys.argv[2], control_type="Button")
    btn.invoke()
    time.sleep(3.0)
    for w in Desktop(backend="uia").windows(process=app.process):
        print("WINDOW:", w.window_text())
        walk(w, 7)
    if len(sys.argv) > 3:
        shot(win, sys.argv[3])
elif cmd == "dump":
    for w in Desktop(backend="uia").windows(process=app.process):
        print("WINDOW:", w.window_text())
        walk(w, int(sys.argv[2]), filt=sys.argv[3] if len(sys.argv) > 3 else "")
elif cmd == "selectfirst":
    # selectfirst <TabName> <ListAutomationIdOrName> <wait_s>
    win.wrapper_object().set_focus()
    win.child_window(title=sys.argv[2], control_type="TabItem").select()
    time.sleep(2.0)
    lst = win.child_window(auto_id=sys.argv[3], control_type="List")
    if not lst.exists(timeout=2):
        lst = win.child_window(title=sys.argv[3], control_type="List")
    items = lst.wrapper_object().children(control_type="ListItem")
    print("items:", len(items))
    items[0].select()
    time.sleep(float(sys.argv[4]) if len(sys.argv) > 4 else 3.0)
    walk(win.child_window(control_type="Tab").wrapper_object(), 9)
elif cmd == "checkvideos":
    # checkvideos <name-prefix>: tick the checkbox of every Video list item whose title starts with prefix
    win.wrapper_object().set_focus()
    win.child_window(title="VIDEO", control_type="TabItem").select()
    time.sleep(3.0)
    lst = win.child_window(auto_id="VideoClipList", control_type="List").wrapper_object()
    ticked = []
    for item in lst.children(control_type="ListItem"):
        texts = [t.window_text() for t in item.children(control_type="Text")]
        if any(t.startswith(sys.argv[2]) for t in texts):
            box = item.children(control_type="CheckBox")[0]
            if box.get_toggle_state() == 0:
                box.toggle()
            ticked.append([t for t in texts if t.startswith(sys.argv[2])][0])
    print("ticked:", ticked)
elif cmd == "pickfolder":
    dlg = win.child_window(control_type="Window", found_index=0)
    print("dialog:", dlg.window_text())
    edit = dlg.child_window(auto_id="1152", control_type="Edit")
    edit.set_edit_text(sys.argv[2])
    time.sleep(0.5)
    buttons = [b for b in dlg.descendants(control_type="Button") if "auswählen" in (b.window_text() or "")]
    print("confirm buttons:", [b.window_text() for b in buttons])
    buttons[0].invoke()
    time.sleep(float(sys.argv[3]) if len(sys.argv) > 3 else 8.0)
    print("dialog still open:", dlg.exists(timeout=1))
elif cmd == "shot":
    shot(win, sys.argv[2])
