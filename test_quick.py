"""Schnelltest: Backend starten + Import testen (kein BeatNet)."""
import sys, os, time, threading
PROJECT = r"C:\Users\david\Dokumente\Pb_studio_AMD_version"
sys.path.insert(0, os.path.join(PROJECT, "src"))
os.chdir(PROJECT)

import uvicorn
from backend.main import app

server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=18766, log_level="warning"))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
time.sleep(2)
print("Backend OK auf Port 18765")

import httpx
c = httpx.Client(base_url="http://127.0.0.1:18766", timeout=120.0)

# Audio Import
AUDIO = r"C:\Users\david\Videos\Music-Video_Clips\AV\Audio\recording-2021-04-24-235308.wav"
r = c.post("/audio/import", json={"path": AUDIO})
print(f"Audio Import: {r.status_code} - {r.json() if r.status_code==200 else r.text[:100]}")
clip_id = r.json().get("id", 0) if r.status_code == 200 else 0

# Audio Analyse (nur Beats + Structure, kein Spectral)
if clip_id:
    print("Starte Audio-Analyse (kann 30-60s dauern)...")
    r2 = c.post("/audio/analyze", json={"clip_id": clip_id, "detect_beats": True, "detect_structure": True, "spectral_analysis": False})
    if r2.status_code == 200:
        d = r2.json()
        print(f"  BPM={d.get('bpm',0):.1f} Beats={d.get('beat_count',0)} Key={d.get('key','?')} Energy={len(d.get('energy_curve',[]))} Struct={len(d.get('structure_segments',[]))}")
        print("  AUDIO: OK" if d.get("bpm", 0) > 0 else "  AUDIO: FEHLER (BPM=0)")
    else:
        print(f"  AUDIO ANALYSE FEHLER: {r2.status_code} - {r2.text[:200]}")

# Video Import
VIDEO = r"C:\Users\david\Videos\Music-Video_Clips\20250719_0402_Cyberpunk Jungle Dance_storyboard_01k0g6na4efrab05brd4hzzk2n.mp4"
r = c.post("/video/import", json={"paths": [VIDEO]})
print(f"Video Import: {r.status_code}")
vclips = r.json() if r.status_code == 200 else []
vid = vclips[0]["id"] if vclips else 0

# Video Analyse
if vid:
    print("Starte Video-Analyse...")
    r2 = c.post("/video/analyze", json={"clip_id": vid, "detect_scenes": True, "analyze_motion": True, "generate_embeddings": False})
    if r2.status_code == 200:
        d = r2.json()
        print(f"  Scenes={d.get('scene_count',0)} Motion={d.get('avg_motion',0):.2f}")
        print("  VIDEO: OK")
    else:
        print(f"  VIDEO ANALYSE FEHLER: {r2.status_code} - {r2.text[:200]}")

    # Motion Endpoint (ehemaliger Crash-Punkt)
    r3 = c.get(f"/video/motion/{vid}")
    if r3.status_code == 200:
        m = r3.json()
        print(f"  Motion-Endpoint: OK (avg={m.get('avg_motion',0):.2f}, peaks={len(m.get('peak_frames',[]))})")
    else:
        print(f"  MOTION CRASH: {r3.status_code} - {r3.text[:200]}")

print("\nFERTIG")
server.should_exit = True
