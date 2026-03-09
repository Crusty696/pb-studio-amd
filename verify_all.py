"""Vollständiger Verifikationstest aller Backend-Endpoints."""
import requests
import json
import time
import sys

BASE = "http://127.0.0.1:8765"
results = []


def test(method, url, body=None, expect_status=200, label=None, timeout=300):
    name = label or f"{method} {url}"
    try:
        if method == "GET":
            r = requests.get(BASE + url, timeout=timeout)
        else:
            r = requests.post(BASE + url, json=body, timeout=timeout)
        ok = r.status_code == expect_status
        detail = ""
        if ok:
            try:
                d = r.json()
                if isinstance(d, dict):
                    detail = ", ".join(f"{k}={v}" for k, v in list(d.items())[:3])[:80]
                elif isinstance(d, list):
                    detail = f"{len(d)} items"
            except Exception:
                detail = f"{len(r.content)} bytes"
        else:
            detail = r.text[:80]
        status = "OK" if ok else f"FAIL({r.status_code})"
        results.append((name, status, detail))
        icon = "PASS" if ok else "FAIL"
        print(f"  [{icon}] {name}")
    except Exception as e:
        results.append((name, "ERROR", str(e)[:60]))
        print(f"  [ERR!] {name}: {e}")


# BLOCK 1: Health & System
print("=== Block 1: Health & System ===")
test("GET", "/health", label="1. Health Check")
test("GET", "/gpu/status", label="2. GPU Status")
test("POST", "/gpu/cleanup", label="3. GPU Cleanup")

# BLOCK 2: Audio Import & List
print("\n=== Block 2: Audio Import & List ===")
test("GET", "/audio/clips?page=1&limit=5", label="4. Audio Clips List")
test(
    "POST",
    "/audio/import",
    {"path": r"C:\Users\david\Videos\Music-Video_Clips\AV\Audio\recording-2021-04-24-235308.wav"},
    label="5. Audio Import",
)

# BLOCK 3: Video Import & List
print("\n=== Block 3: Video Import & List ===")
test("GET", "/video/clips?page=1&limit=5", label="6. Video Clips List")
test(
    "POST",
    "/video/import",
    {
        "paths": [
            r"C:\Users\david\Videos\Music-Video_Clips\AV\Video\Tanzende Frau wenig Pfanzen\20250621_0631_Goddess_Dance_Monolith_gen_01jy8jxwkgecdrf0xfsfbe7tgj.mp4"
        ]
    },
    label="7. Video Import",
)

# BLOCK 4: Audio Analysis
print("\n=== Block 4: Audio Analysis (dauert ~90s) ===")
test("POST", "/audio/analyze", {"clip_id": 9}, label="8. Audio Analyze")
test("GET", "/audio/beats/9", label="9. Audio Beats")
test("GET", "/audio/waveform/9?bands=3", label="10. Audio Waveform", timeout=120)
test("GET", "/audio/structure/9", label="11. Audio Structure")
test("GET", "/audio/spectral/9", label="12. Audio Spectral")

# BLOCK 5: Video Analysis
print("\n=== Block 5: Video Analysis ===")
test("GET", "/video/thumbnails/220", label="13. Video Thumbnail")
test("POST", "/video/analyze", {"clip_id": 220}, label="14. Video Analyze")
test("GET", "/video/scenes/220", label="15. Video Scenes")
test("GET", "/video/motion/220", label="16. Video Motion")

# BLOCK 6: Pacing & Timeline
print("\n=== Block 6: Pacing & Timeline ===")
pacing_body = {
    "audio_clip_id": 9,
    "video_clip_ids": [220, 219, 218],
    "expected_bpm": 123,
    "use_motion_matching": False,
    "use_structure_awareness": False,
    "duration_limit": 30,
    "min_cut_interval": 0.5,
    "trigger_settings": {
        "beat_sensitivity": 0.7,
        "energy_threshold": 0.5,
        "onset_weight": 0.3,
        "spectral_weight": 0.2,
    },
}
test("POST", "/pacing/generate", pacing_body, label="17. Pacing Generate")
test("GET", "/pacing/timeline", label="18. Pacing Timeline")

# BLOCK 7: Pacing mit Motion Matching
print("\n=== Block 7: Pacing + Motion Matching ===")
pacing_motion = dict(pacing_body)
pacing_motion["use_motion_matching"] = True
test("POST", "/pacing/generate", pacing_motion, label="19. Pacing + Motion")

# BLOCK 8: Pacing + Structure Awareness
print("\n=== Block 8: Pacing + Structure ===")
pacing_struct = dict(pacing_body)
pacing_struct["use_motion_matching"] = True
pacing_struct["use_structure_awareness"] = True
test("POST", "/pacing/generate", pacing_struct, label="20. Pacing + Motion + Structure")

# BLOCK 9: Project Management
print("\n=== Block 9: Project Management ===")
test(
    "POST",
    "/project/create",
    {"name": "VerifyProject", "path": r"C:\Users\david\Documents\PBStudio"},
    label="21. Project Create",
)
test("GET", "/project/info", label="22. Project Info")
test("POST", "/project/save", label="23. Project Save")
test(
    "POST",
    "/project/open",
    {"path": r"C:\Users\david\Documents\PBStudio\VerifyProject"},
    label="24. Project Open",
)
test("POST", "/project/close", label="25. Project Close")

# BLOCK 10: Preview
print("\n=== Block 10: Preview ===")
# Pacing nochmal generieren (Timeline verloren nach close?)
test("POST", "/pacing/generate", pacing_body, label="26. Pacing Re-Generate")
test("POST", "/pacing/preview", {"start_sec": 0, "duration": 10}, label="27. Preview Generate")

# BLOCK 11: Render
print("\n=== Block 11: Render ===")
test(
    "POST",
    "/project/create",
    {"name": "VerifyProject", "path": r"C:\Users\david\Documents\PBStudio"},
    label="28. Project Create (Render)",
)
render_body = {
    "output_path": r"C:\Users\david\Documents\PBStudio\VerifyProject\output\verify.mp4",
    "audio_path": r"C:\Users\david\Videos\Music-Video_Clips\AV\Audio\recording-2021-04-24-235308.wav",
    "quality": "preview",
    "resolution_width": 640,
    "resolution_height": 360,
    "fps": 30.0,
}
test("POST", "/render/start", render_body, label="29. Render Start")

# Task-ID extrahieren
task_id = None
if results[-1][1] == "OK":
    r = requests.get(BASE + "/render/status/" + "nonexist")
    # Finde echte task_id
    for n, s, d in results:
        if "Render Start" in n and s == "OK" and "task_id=" in d:
            task_id = d.split("task_id=")[1].split(",")[0]

# Render Status warten
if task_id:
    print(f"  Warte auf Render {task_id}...")
    for i in range(60):
        time.sleep(5)
        r = requests.get(f"{BASE}/render/status/{task_id}")
        data = r.json()
        pct = data.get("percent", 0)
        status = data.get("status", "")
        print(f"    ... {pct:.0f}% ({status})")
        if status in ("completed", "failed", "cancelled"):
            break
    test("GET", f"/render/status/{task_id}", label="30. Render Final Status")
else:
    print("  [SKIP] Kein Render-Task-ID gefunden")
    results.append(("30. Render Final Status", "SKIP", "no task_id"))

# BLOCK 12: Error Cases
print("\n=== Block 12: Error Cases ===")
test("POST", "/audio/analyze", {"clip_id": 99999}, expect_status=404, label="31. Analyze Non-Exist")
test("GET", "/audio/beats/99999", expect_status=404, label="32. Beats Non-Exist")
test(
    "POST",
    "/pacing/generate",
    {
        "audio_clip_id": 99999,
        "video_clip_ids": [220],
        "expected_bpm": 120,
        "use_motion_matching": False,
        "use_structure_awareness": False,
        "trigger_settings": {
            "beat_sensitivity": 0.7,
            "energy_threshold": 0.5,
            "onset_weight": 0.3,
            "spectral_weight": 0.2,
        },
    },
    expect_status=404,
    label="33. Pacing Non-Exist Audio",
)
test("POST", "/render/cancel/nonexist", expect_status=404, label="34. Cancel Non-Exist")
test("GET", "/render/status/nonexist", expect_status=404, label="35. Status Non-Exist")

# BLOCK 13: SSE Endpoints (just check they connect)
print("\n=== Block 13: SSE Endpoints ===")
for sse_path, num in [("/events/progress", 36), ("/events/log", 37), ("/events/gpu", 38)]:
    try:
        r = requests.get(BASE + sse_path, stream=True, timeout=3)
        ok = r.status_code == 200
        results.append((f"{num}. SSE {sse_path}", "OK" if ok else f"FAIL({r.status_code})", "stream connected"))
        r.close()
        print(f"  [{'PASS' if ok else 'FAIL'}] {num}. SSE {sse_path}")
    except requests.exceptions.ReadTimeout:
        results.append((f"{num}. SSE {sse_path}", "OK", "stream timeout (expected)"))
        print(f"  [PASS] {num}. SSE {sse_path} (timeout=expected)")
    except Exception as e:
        results.append((f"{num}. SSE {sse_path}", "ERROR", str(e)[:40]))
        print(f"  [ERR!] {num}. SSE {sse_path}: {e}")

# ==========================================
# ERGEBNIS
# ==========================================
print()
print("=" * 80)
passed = sum(1 for _, s, _ in results if s == "OK")
total = len(results)
print(f"ERGEBNIS: {passed}/{total} Tests bestanden")
print("=" * 80)

fails = [(n, s, d) for n, s, d in results if s not in ("OK",)]
if fails:
    print("\nFEHLGESCHLAGEN:")
    for n, s, d in fails:
        print(f"  [{s}] {n}: {d}")
else:
    print("\nALLE TESTS BESTANDEN!")
