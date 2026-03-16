"""Schnelltest: Backend starten + Import testen (kein BeatNet)."""
import os
import sys
import threading
import time

import httpx
import uvicorn

PROJECT = r"C:\Users\david\Dokumente\Pb_studio_AMD_version"
PORT = 18766
BASE_URL = f"http://127.0.0.1:{PORT}"
PROJECT_AUDIO = r"C:\Users\david\Videos\Music-Video_Clips\AV\Audio\recording-2021-04-24-235308.wav"
PROJECT_VIDEO = r"C:\Users\david\Videos\Music-Video_Clips\20250719_0402_Cyberpunk Jungle Dance_storyboard_01k0g6na4efrab05brd4hzzk2n.mp4"

sys.path.insert(0, os.path.join(PROJECT, "src"))
os.chdir(PROJECT)

from backend.main import app


def wait_for_health(client: httpx.Client, timeout_seconds: float = 15.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error = None

    while time.time() < deadline:
        try:
            response = client.get("/health")
            if response.status_code == 200:
                return
            last_error = RuntimeError(f"Unexpected health status: {response.status_code}")
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)

    raise RuntimeError(f"Backend failed to become healthy on {BASE_URL}: {last_error}")


server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()

client = httpx.Client(base_url=BASE_URL, timeout=120.0)

try:
    wait_for_health(client)
    print(f"Backend OK auf Port {PORT}")

    # Audio Import
    r = client.post("/audio/import", json={"path": PROJECT_AUDIO})
    print(f"Audio Import: {r.status_code} - {r.json() if r.status_code == 200 else r.text[:100]}")
    clip_id = r.json().get("id", 0) if r.status_code == 200 else 0

    # Audio Analyse (nur Beats + Structure, kein Spectral)
    if clip_id:
        print("Starte Audio-Analyse (kann 30-60s dauern)...")
        r2 = client.post(
            "/audio/analyze",
            json={
                "clip_id": clip_id,
                "detect_beats": True,
                "detect_structure": True,
                "spectral_analysis": False,
            },
        )
        if r2.status_code == 200:
            d = r2.json()
            print(
                f"  BPM={d.get('bpm', 0):.1f} Beats={d.get('beat_count', 0)} "
                f"Key={d.get('key', '?')} Energy={len(d.get('energy_curve', []))} "
                f"Struct={len(d.get('structure_segments', []))}"
            )
            print("  AUDIO: OK" if d.get("bpm", 0) > 0 else "  AUDIO: FEHLER (BPM=0)")
        else:
            print(f"  AUDIO ANALYSE FEHLER: {r2.status_code} - {r2.text[:200]}")

    # Video Import
    r = client.post("/video/import", json={"paths": [PROJECT_VIDEO]})
    print(f"Video Import: {r.status_code}")
    vclips = r.json() if r.status_code == 200 else []
    vid = vclips[0]["id"] if vclips else 0

    # Video Analyse
    if vid:
        print("Starte Video-Analyse...")
        r2 = client.post(
            "/video/analyze",
            json={"clip_id": vid, "detect_scenes": True, "analyze_motion": True, "generate_embeddings": False},
        )
        if r2.status_code == 200:
            d = r2.json()
            print(f"  Scenes={d.get('scene_count', 0)} Motion={d.get('avg_motion', 0):.2f}")
            print("  VIDEO: OK")
        else:
            print(f"  VIDEO ANALYSE FEHLER: {r2.status_code} - {r2.text[:200]}")

        # Motion Endpoint (ehemaliger Crash-Punkt)
        r3 = client.get(f"/video/motion/{vid}")
        if r3.status_code == 200:
            m = r3.json()
            print(f"  Motion-Endpoint: OK (avg={m.get('avg_motion', 0):.2f}, peaks={len(m.get('peak_frames', []))})")
        else:
            print(f"  MOTION CRASH: {r3.status_code} - {r3.text[:200]}")

    print("\nFERTIG")
finally:
    client.close()
    server.should_exit = True
    thread.join(timeout=10)
