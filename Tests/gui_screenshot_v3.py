"""
PB Studio GUI Screenshot Test v3 (Modernized for current German UI tabs)
"""
import time
import sys
import os
import ctypes
from ctypes import wintypes
from pywinauto import Application
from PIL import ImageGrab

# DPI awareness for correct screenshots
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gui_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

PASSED = []
ERRORS = []


def check(name, ok, detail=""):
    tag = "PASS" if ok else "FAIL"
    (PASSED if ok else ERRORS).append(f"{tag}: {name} - {detail}")
    print(f"  [{tag}] {name}" + (f" - {detail}" if detail else ""))


def grab_window(rect):
    """Grab screenshot using PIL ImageGrab with window coordinates."""
    return ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))


def check_content(img, tab_name):
    """Check if image has meaningful content (not solid color)."""
    w, h = img.size
    if w < 100 or h < 100:
        return False, f"too small: {w}x{h}"
    content = img.crop((50, h // 3, w - 50, h - 30))
    
    r_vals, g_vals, b_vals = [], [], []
    for x in range(0, content.width, max(1, content.width // 50)):
        for y in range(0, content.height, max(1, content.height // 50)):
            r, g, b = content.getpixel((x, y))[:3]
            r_vals.append(r)
            g_vals.append(g)
            b_vals.append(b)

    var = (max(r_vals) - min(r_vals)) + (max(g_vals) - min(g_vals)) + (max(b_vals) - min(b_vals))
    return var > 30, f"variance={var}"


def main():
    print("=" * 60)
    print("PB STUDIO GUI SCREENSHOT TEST (German UI Edition)")
    print("=" * 60)

    # Restore window via Win32
    print("\n[0] Fenster wiederherstellen...")
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, "PB Studio AMD")
    if hwnd:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        time.sleep(0.5)
        user32.SetForegroundWindow(hwnd)
        time.sleep(1)
        print(f"  HWND: {hwnd}")
    else:
        print("  Window 'PB Studio AMD' not found!")
        sys.exit(1)

    # Connect
    print("\n[1] App verbinden...")
    app = Application(backend="uia").connect(title_re=".*PB Studio.*", timeout=10)
    win = app.window(title_re=".*PB Studio.*")
    win.wait("visible", timeout=5)
    rect = win.rectangle()
    print(f"  Rect: {rect.left},{rect.top} -> {rect.right},{rect.bottom}")
    print(f"  Size: {rect.width()}x{rect.height()}")
    check("App verbunden", rect.width() > 500, f"{rect.width()}x{rect.height()}")

    # Take screenshots per tab using the actual WPF tab titles
    print("\n[2] Tab-Screenshots...")
    tabs = [
        "PROJEKT", "AUDIO", "VIDEO", "KI-REGIE", 
        "TIMELINE", "EXPORT", "CHAT", "HIRN", 
        "MODELLE", "PERFORMANCE", "SETTINGS"
    ]

    for i, tab_name in enumerate(tabs):
        try:
            tab = win.child_window(title=tab_name, control_type="TabItem")
            tab.select()
            time.sleep(1.0) # Wait for page load and animation

            rect = win.rectangle()
            img = grab_window(rect)
            fname = os.path.join(SCREENSHOT_DIR, f"tab_{tab_name.lower()}.png")
            img.save(fname)

            ok, detail = check_content(img, tab_name)
            check(f"Tab {tab_name!r}", ok, f"{img.size[0]}x{img.size[1]}, {detail}")
        except Exception as e:
            check(f"Tab {tab_name!r}", False, str(e)[:100])

    # Summary
    print(f"\n{'=' * 60}")
    print(f"ERGEBNIS: {len(PASSED)} PASSED, {len(ERRORS)} FAILED")
    print(f"Screenshots: {SCREENSHOT_DIR}")
    print(f"{'=' * 60}")
    if ERRORS:
        for e in ERRORS:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("ALLE SCREENSHOT-TESTS BESTANDEN!")


if __name__ == "__main__":
    main()
