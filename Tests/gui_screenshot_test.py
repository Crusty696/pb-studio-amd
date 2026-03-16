"""
PB Studio WPF GUI Screenshot Test
Macht Screenshots jedes Tabs und prüft visuell ob Content gerendert wird.
Nutzt pywinauto für Tab-Navigation + capture_as_image() für Verifikation.
"""
import time
import sys
import os
from pywinauto import Application
from PIL import Image

PASSED = []
ERRORS = []
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "gui_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def check(name, success, detail=""):
    if success:
        PASSED.append(f"PASS: {name}")
        print(f"  [PASS] {name}" + (f" - {detail}" if detail else ""))
    else:
        ERRORS.append(f"FAIL: {name} - {detail}")
        print(f"  [FAIL] {name} - {detail}")


def screenshot_has_content(img, tab_name):
    """Check if screenshot has non-trivial content (not just solid color)."""
    # Crop to content area (below tabs ~370px, above status bar)
    w, h = img.size
    content_area = img.crop((0, 370, w, h - 30))

    # Check pixel variance - solid color = no content
    pixels = list(content_area.getdata())
    if not pixels:
        return False, "No pixels"

    # Sample pixels and check variance
    r_vals = [p[0] for p in pixels[::100]]
    g_vals = [p[1] for p in pixels[::100]]
    b_vals = [p[2] for p in pixels[::100]]

    r_range = max(r_vals) - min(r_vals)
    g_range = max(g_vals) - min(g_vals)
    b_range = max(b_vals) - min(b_vals)

    total_range = r_range + g_range + b_range
    has_content = total_range > 30  # More than 30 total variance = real content

    return has_content, f"pixel variance: {total_range}"


def main():
    print("=" * 60)
    print("PB STUDIO GUI SCREENSHOT TEST")
    print("=" * 60)

    # Connect
    print("\n[1] App verbinden...")
    try:
        app = Application(backend="uia").connect(title_re=".*PB Studio.*", timeout=10)
        win = app.window(title_re=".*PB Studio.*")
        win.wait("visible", timeout=10)
        check("App verbunden", True, win.window_text())
    except Exception as e:
        check("App verbunden", False, str(e))
        sys.exit(1)

    # Screenshot each tab
    tab_names = [
        "IMPORT", "AUDIO", "VIDEO", "ANCHORS",
        "DIRECTOR", "TIMELINE", "PRODUKTION", "SETTINGS",
    ]

    print("\n[2] Screenshots aller 8 Tabs...")
    for tab_name in tab_names:
        try:
            tab = win.child_window(title=tab_name, control_type="TabItem")
            tab.click_input()
            time.sleep(1.5)

            # Take screenshot
            img = win.capture_as_image()
            filepath = os.path.join(SCREENSHOT_DIR, f"tab_{tab_name.lower()}.png")
            img.save(filepath)

            has_content, detail = screenshot_has_content(img, tab_name)
            check(
                f"Tab {tab_name!r} hat Content",
                has_content,
                f"{detail}, saved: {filepath}",
            )
        except Exception as e:
            check(f"Tab {tab_name!r} Screenshot", False, str(e)[:100])

    # Take a full window screenshot
    print("\n[3] Header pruefen...")
    try:
        img = win.capture_as_image()
        # Header area (top 80px)
        header = img.crop((0, 0, img.width, 80))
        header.save(os.path.join(SCREENSHOT_DIR, "header.png"))
        check("Header Screenshot", True)
    except Exception as e:
        check("Header Screenshot", False, str(e)[:100])

    # === RESULT ===
    print("\n" + "=" * 60)
    print(f"ERGEBNIS: {len(PASSED)} PASSED, {len(ERRORS)} FAILED")
    print(f"Screenshots in: {os.path.abspath(SCREENSHOT_DIR)}")
    print("=" * 60)
    for p in PASSED:
        print(f"  {p}")
    if ERRORS:
        print(f"\nFEHLER:")
        for e in ERRORS:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("\nALLE SCREENSHOT-TESTS BESTANDEN!")


if __name__ == "__main__":
    main()
