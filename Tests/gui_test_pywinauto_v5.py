# PB Studio WPF GUI-Test v5 - Visual Tab Sweep
import time
import sys
import os
from pathlib import Path
from pywinauto import Application

PASSED = []
ERRORS = []

def check(name, success, detail=""):
    if success:
        PASSED.append(f"PASS: {name}")
        print(f"  [PASS] {name}" + (f" - {detail}" if detail else ""))
    else:
        ERRORS.append(f"FAIL: {name} - {detail}")
        print(f"  [FAIL] {name} - {detail}")

def take_window_screenshot(win, proc_id, out_path):
    """PrintWindow screenshot using ctypes."""
    import ctypes
    from ctypes import wintypes
    
    hwnd = win.handle
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)
    
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    
    if w <= 0 or h <= 0:
        return False
        
    hdc_screen = user32.GetWindowDC(hwnd)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
    hobj = gdi32.SelectObject(hdc_mem, hbitmap)
    
    # PW_RENDERFULLCONTENT = 0x2
    ok = user32.PrintWindow(hwnd, hdc_mem, 0x2)
    
    gdi32.SelectObject(hdc_mem, hobj)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(hwnd, hdc_screen)
    
    if ok:
        # Save to file using PIL
        from PIL import Image
        import io
        
        # Get bitmap bits
        bmpinfo = ctypes.create_string_buffer(40) # BITMAPINFOHEADER is 40 bytes
        # Fill in header
        ctypes.memset(bmpinfo, 0, 40)
        ctypes.struct_copy = ctypes.memmove
        
        # struct BITMAPINFOHEADER
        # biSize=40, biWidth, biHeight, biPlanes=1, biBitCount=32, biCompression=0
        struct_header = struct_header = (ctypes.c_uint32 * 10)(
            40, w, -h, 1 | (32 << 16), 0, 0, 0, 0, 0, 0
        )
        ctypes.memmove(bmpinfo, ctypes.byref(struct_header), 40)
        
        buf_size = w * h * 4
        buf = ctypes.create_string_buffer(buf_size)
        gdi32.GetDIBits(hdc_screen, hbitmap, 0, h, buf, bmpinfo, 0) # DIB_RGB_COLORS = 0
        
        # Convert BGRA to RGBA
        raw_data = bytearray(buf.raw)
        for i in range(0, len(raw_data), 4):
            b, g, r, a = raw_data[i], raw_data[i+1], raw_data[i+2], raw_data[i+3]
            raw_data[i] = r
            raw_data[i+2] = b
            
        img = Image.frombytes("RGBA", (w, h), bytes(raw_data))
        img.save(out_path)
        img.close()
        
    gdi32.DeleteObject(hbitmap)
    return ok

def main():
    print("=" * 60)
    print("PB STUDIO WPF GUI-TEST v5 (Visual Tab Sweep)")
    print("=" * 60)

    # Make sure logs dir exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # === 1: App verbinden ===
    print("\n[1] App verbinden...")
    try:
        app = Application(backend="uia").connect(title_re=".*PB Studio.*", timeout=15)
        win = app.window(title_re=".*PB Studio.*")
        win.wait("visible", timeout=15)
        title = win.window_text()
        check("App verbunden", True, f"Titel: {title!r}")
    except Exception as e:
        check("App verbunden", False, str(e))
        sys.exit(1)

    # === 2: Fenster sichtbar ===
    print("\n[2] Fenster pruefen...")
    rect = win.rectangle()
    check("Fenster sichtbar", rect.width() > 100, f"{rect.width()}x{rect.height()}")

    # === 3: Alle 12 Tabs durchklicken & screenshoten ===
    print("\n[3] Alle 12 Tabs durchklicken und visualisieren...")
    tab_names = [
        "PROJEKT", "AUDIO", "VIDEO", "KI-REGIE", "TIMELINE", 
        "EXPORT", "HIRN", "SETTINGS", "PERFORMANCE", "MODELLE", "CHAT", "TERMINAL"
    ]
    for tab_name in tab_names:
        try:
            tab = win.child_window(title=tab_name, control_type="TabItem")
            if tab.exists(timeout=5):
                tab.click_input()
                time.sleep(1.5) # Wait for animation & render
                
                # Take screenshot of the active tab
                out_img = logs_dir / f"gui_tab_{tab_name.lower()}.png"
                ok = take_window_screenshot(win, app.process, str(out_img))
                
                check(f"Tab {tab_name!r} visualisiert", ok, f"Saved to {out_img}")
            else:
                check(f"Tab {tab_name!r} klickbar", False, "Nicht gefunden")
        except Exception as e:
            check(f"Tab {tab_name!r} Fehler", False, str(e)[:120])

    # === ERGEBNIS ===
    print("\n" + "=" * 60)
    print(f"GUI-TEST ERGEBNIS: {len(PASSED)} PASSED, {len(ERRORS)} FAILED")
    print("=" * 60)
    if ERRORS:
        sys.exit(1)
    else:
        print("\nALLE VISUELLEN GUI-TESTS BESTANDEN!")

if __name__ == "__main__":
    main()
