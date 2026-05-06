"""E2E-Test: Audio + Video Analyse via FastAPI Backend."""
import sys
import os
import time
import threading

PROJECT = r"C:\Users\david\Dokumente\Pb_studio_AMD_version"
sys.path.insert(0, os.path.join(PROJECT, "src"))
os.chdir(PROJECT)

# --- 1. Backend starten ---
print("=" * 60)
print("E2E-TEST: Audio + Video Analyse")
print("=" * 60)

import uvicorn
from backend.main import app

# Server in Background-Thread starten
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=18765, log_level="warning"))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
time.sleep(2)
print("Backend laeuft auf Port 18765")

# --- 2. HTTP-Client ---
import httpx
BASE = "http://127.0.0.1:18765"
client = httpx.Client(base_url=BASE, timeout=120.0)

errors = []

# --- 3. Audio Import + Analyse ---
print("\n--- AUDIO TEST ---")
AUDIO = r"C:\Users\david\Videos\Music-Video_Clips\AV\Audio"
audio_files = []
for root, dirs, files in os.walk(AUDIO):
    for f in files:
        if f.lower().endswith((".mp3", ".wav", ".flac")):
            audio_files.append(os.path.join(root, f))
            break
    if audio_files:
        break

if audio_files:
    # Import
    r = client.post("/audio/import", json={"path": audio_files[0]})
    if r.status_code == 200:
        clip = r.json()
        clip_id = clip.get("id", 0)
        print(f"  Import OK: {clip.get('name')} (ID={clip_id}, {clip.get('duration_seconds', 0):.1f}s)")

        # Analyse
        r2 = client.post("/audio/analyze", json={
            "clip_id": clip_id,
            "detect_beats": True,
            "detect_structure": True,
            "spectral_analysis": True,
        })
        if r2.status_code == 200:
            result = r2.json()
            print(f"  BPM: {result.get('bpm', 0):.1f}")
            print(f"  Beats: {result.get('beat_count', 0)}")
            print(f"  Key: {result.get('key', 'N/A')}")
            print(f"  Energy-Curve: {len(result.get('energy_curve', []))} Werte")
            print(f"  Struktur: {len(result.get('structure_segments', []))} Segmente")
            if result.get("bpm", 0) > 0:
                print("  AUDIO ANALYSE: OK")
            else:
                errors.append("Audio: BPM = 0")
                print("  AUDIO ANALYSE: FEHLER (BPM=0)")
        else:
            errors.append(f"Audio Analyse: HTTP {r2.status_code} - {r2.text[:200]}")
            print(f"  AUDIO ANALYSE: HTTP {r2.status_code}")
    else:
        errors.append(f"Audio Import: HTTP {r.status_code}")
        print(f"  AUDIO IMPORT: HTTP {r.status_code}")
else:
    errors.append("Keine Audio-Testdateien gefunden")
    print("  KEINE AUDIO-TESTDATEIEN")

# --- 4. Video Import + Analyse ---
print("\n--- VIDEO TEST ---")
VIDEO = r"C:\Users\david\Videos\Music-Video_Clips"
video_files = []
for root, dirs, files in os.walk(VIDEO):
    for f in files:
        if f.lower().endswith((".mp4", ".mkv", ".avi", ".mov")):
            video_files.append(os.path.join(root, f))
            break
    if video_files:
        break

if video_files:
    # Import
    r = client.post("/video/import", json={"paths": [video_files[0]]})
    if r.status_code == 200:
        clips = r.json()
        if clips:
            clip = clips[0]
            clip_id = clip.get("id", 0)
            print(f"  Import OK: {clip.get('name')} (ID={clip_id}, {clip.get('duration_seconds', 0):.1f}s)")

            # Analyse
            r2 = client.post("/video/analyze", json={
                "clip_id": clip_id,
                "detect_scenes": True,
                "analyze_motion": True,
                "generate_embeddings": False,
            })
            if r2.status_code == 200:
                result = r2.json()
                print(f"  Scenes: {result.get('scene_count', 0)}")
                print(f"  Avg Motion: {result.get('avg_motion', 0):.2f}")
                print(f"  Has Embedding: {result.get('has_embedding', False)}")
                print("  VIDEO ANALYSE: OK")
            else:
                errors.append(f"Video Analyse: HTTP {r2.status_code} - {r2.text[:200]}")
                print(f"  VIDEO ANALYSE: HTTP {r2.status_code} - {r2.text[:200]}")
        else:
            errors.append("Video Import: Leere Antwort")
    else:
        errors.append(f"Video Import: HTTP {r.status_code}")
        print(f"  VIDEO IMPORT: HTTP {r.status_code}")
else:
    errors.append("Keine Video-Testdateien gefunden")
    print("  KEINE VIDEO-TESTDATEIEN")

# --- 5. Motion-Endpoint testen (hier war der Crash) ---
print("\n--- MOTION ENDPOINT TEST (ehemaliger Crash-Punkt) ---")
try:
    r = client.get(f"/video/motion/{clip_id}")
    if r.status_code == 200:
        motion = r.json()
        print(f"  Avg Motion: {motion.get('avg_motion', 0):.2f}")
        print(f"  Peak Frames: {len(motion.get('peak_frames', []))}")
        print(f"  Category: {motion.get('motion_category', 'N/A')}")
        print("  MOTION ENDPOINT: OK (kein Crash!)")
    elif r.status_code == 404:
        print("  MOTION ENDPOINT: 404 (keine Analyse vorhanden - normal wenn Video-Analyse fehlschlug)")
    else:
        errors.append(f"Motion Endpoint: HTTP {r.status_code} - {r.text[:200]}")
        print(f"  MOTION ENDPOINT: HTTP {r.status_code} - {r.text[:200]}")
except Exception as e:
    errors.append(f"Motion Endpoint Crash: {e}")
    print(f"  MOTION ENDPOINT CRASH: {e}")

# --- Ergebnis ---
print("\n" + "=" * 60)
if errors:
    print(f"FEHLER: {len(errors)}")
    for e in errors:
        print(f"  - {e}")
else:
    print("ALLE TESTS BESTANDEN")
print("=" * 60)

# Server stoppen
server.should_exit = True
