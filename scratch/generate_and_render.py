import requests

BASE_URL = "http://127.0.0.1:8765"
audio_clip_id = 1
expected_bpm = 143.55

print("=" * 60)
print("E2E PACING & RENDER START - KLANGKRAFT")
print("=" * 60)

# 1. Video-IDs paginiert abrufen (da max limit=200 ist)
print("Lese Video-IDs paginiert aus...")
video_clip_ids = []

# Seite 1 abrufen
res1 = requests.get(f"{BASE_URL}/video/clips?page=1&limit=200")
if res1.status_code == 200:
    clips1 = res1.json()
    video_clip_ids.extend([c.get("id") for c in clips1 if c.get("id")])
    print(f"  Seite 1 geladen: {len(clips1)} Clips")

# Seite 2 abrufen
res2 = requests.get(f"{BASE_URL}/video/clips?page=2&limit=200")
if res2.status_code == 200:
    clips2 = res2.json()
    video_clip_ids.extend([c.get("id") for c in clips2 if c.get("id")])
    print(f"  Seite 2 geladen: {len(clips2)} Clips")

print(f"Usable Videos gesamt geladen: {len(video_clip_ids)}")

# 2. Pacing generieren
print("\nGeneriere Timeline über die gesamte Länge (1.76 Stunden)...")
pacing_body = {
    "audio_clip_id": audio_clip_id,
    "video_clip_ids": video_clip_ids,
    "expected_bpm": float(expected_bpm),
    "use_motion_matching": False,
    "use_structure_awareness": False,
    "duration_limit": None,  # Füllt exakt die gesamte Audiolänge!
    "min_cut_interval": 1.5,
    "trigger_settings": {
        "beat_weight": 1.0,
        "onset_weight": 0.5,
        "kick_weight": 1.2,
        "snare_weight": 1.0,
        "hihat_weight": 0.3,
        "energy_weight": 0.8,
        "energy_threshold": 0.6,
        "min_clip_length": 2.0,
        "max_clip_length": 10.0,
        "onset_sensitivity": 0.5
    }
}

res = requests.post(f"{BASE_URL}/pacing/generate", json=pacing_body)
if res.status_code != 200:
    print(f"[ERROR] Pacing fehlgeschlagen: {res.text}")
    import sys
    sys.exit(1)

# Timeline Details abrufen
timeline_data = requests.get(f"{BASE_URL}/pacing/timeline").json()
total_duration = timeline_data.get('total_duration', 0)
print(f"[SUCCESS] Timeline erfolgreich generiert!")
print(f"  Cuts gesamt: {len(timeline_data.get('entries', []))}")
print(f"  Dauer Timeline: {total_duration/60:.2f} Minuten ({total_duration:.2f} Sekunden)")

# Projekt speichern
requests.post(f"{BASE_URL}/project/save")
print("Projekt dauerhaft in state.db gespeichert.")

# 3. Render starten
audio_path = r"C:\Users\david\Music\Audio\Psy-Set\Crusty -Klangkraft-21nai2022.wav"
render_output = r"C:\Users\david\Documents\PBStudio\Klangkraft_E2E_1780357792\output\Klangkraft_E2E_final.mp4"

print(f"\nStarte Hardware-beschleunigtes Rendering (AMD AMF / libx264)...")
print(f"  Ausgabe: {render_output}")

render_body = {
    "output_path": render_output,
    "audio_path": audio_path,
    "quality": "preview",  # Preview-Qualität für maximale Render-Geschwindigkeit
    "resolution_width": 640,
    "resolution_height": 360,
    "fps": 24,
    "bitrate_mbps": 6.0,
    "include_audio": True
}

res = requests.post(f"{BASE_URL}/render/start", json=render_body)
if res.status_code == 200:
    render_task = res.json()
    print(f"\n[SUCCESS] Render-Prozess gestartet!")
    print(f"  Render Task-ID: {render_task.get('task_id')}")
    print(f"  Das Video wird jetzt im Hintergrund gerendert.")
    print("  Du kannst den Fortschritt live auf deinem Desktop im Tab 'EXPORT' mitverfolgen!")
else:
    print(f"[ERROR] Render-Start fehlgeschlagen: {res.status_code} - {res.text}")
