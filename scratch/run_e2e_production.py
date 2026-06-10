import os
import sys
import time
import requests
from pathlib import Path

BASE_URL = "http://127.0.0.1:8765"
audio_path = r"C:\Users\david\Music\Audio\Psy-Set\Crusty -Klangkraft-21nai2022.wav"
video_dir = r"E:\Music-Video_Clips\Video\Clips"
project_dir = r"C:\Users\david\Documents\PBStudio"

print("=" * 60)
print("E2E PRODUCTION RUNNER - KLANGKRAFT")
print("=" * 60)

# 1. Sammle alle Videos
video_extensions = {".mp4", ".mkv", ".mov", ".avi", ".MP4", ".MKV", ".MOV", ".AVI"}
video_files = []
for root, dirs, files in os.walk(video_dir):
    for file in files:
        if Path(file).suffix in video_extensions:
            video_files.append(os.path.join(root, file))

print(f"[1/6] Gefundene Videos: {len(video_files)}")

# 2. Projekt erstellen
project_name = f"Klangkraft_E2E_{int(time.time())}"
print(f"[2/6] Erstelle Projekt '{project_name}'...")
res = requests.post(f"{BASE_URL}/project/create", json={"name": project_name, "path": project_dir})
if res.status_code != 200:
    print(f"FAILED to create project: {res.text}")
    sys.exit(1)
project_data = res.json()
print(f"  Projekt erstellt unter: {project_data.get('path')}")

# 3. Audio importieren
print(f"[3/6] Importiere Audio: {audio_path}...")
res = requests.post(f"{BASE_URL}/audio/import", json={"path": audio_path})
if res.status_code != 200:
    print(f"FAILED to import audio: {res.text}")
    sys.exit(1)
audio_data = res.json()
audio_clip_id = audio_data.get("id")
print(f"  Audio importiert. Clip-ID: {audio_clip_id}")

# 4. Videos importieren
print(f"[4/6] Importiere {len(video_files)} Videos in die Datenbank...")
# Wir importieren in Batches zu 50, um Timeouts zu vermeiden
batch_size = 50
imported_video_ids = []
for i in range(0, len(video_files), batch_size):
    batch = video_files[i:i+batch_size]
    print(f"  Batch {i//batch_size + 1}: Importiere {len(batch)} Clips...")
    res = requests.post(f"{BASE_URL}/video/import", json={"paths": batch})
    if res.status_code == 200:
        imported_clips = res.json()
        imported_video_ids.extend([c.get("id") for c in imported_clips if c.get("id")])
    else:
        print(f"  WARNING: Batch-Import fehlgeschlagen: {res.text}")

print(f"  Erfolgreich importierte Video-IDs in DB: {len(imported_video_ids)}")

# 5. Audio-Analyse triggern
print(f"[5/6] Starte Audio-Analyse für den Mix...")
res = requests.post(f"{BASE_URL}/audio/analyze", json={"clip_id": audio_clip_id})
if res.status_code != 200:
    print(f"FAILED to start audio analysis: {res.text}")
    sys.exit(1)

# Warten auf Abschluss der Audio-Analyse
print("  Audio-Analyse läuft im Backend (berechnet Beats, BPM und Key)...")
analysis_data = {}
start_time = time.time()
while True:
    # Lese den Clip-Status aus
    res = requests.get(f"{BASE_URL}/audio/clips?page=1&limit=50")
    if res.status_code == 200:
        clips = res.json()
        clip = next((c for c in clips if c.get("id") == audio_clip_id), None)
        if clip:
            # Falls analyzed und bpm > 0, ist es fertig
            bpm = clip.get("bpm")
            is_analyzed = clip.get("is_analyzed", False)
            duration = clip.get("duration_seconds", 0)
            
            elapsed = time.time() - start_time
            print(f"  Status nach {elapsed:.1f}s: is_analyzed={is_analyzed}, BPM={bpm}, Duration={duration:.1f}s")
            
            if is_analyzed and bpm and bpm > 0:
                analysis_data = clip
                print(f"\n[SUCCESS] Audio-Analyse fertig! BPM: {bpm}, Dauer: {duration/60:.1f} Minuten.")
                break
    time.sleep(10)

# 6. Pacing & Timeline generieren
expected_bpm = analysis_data.get("bpm", 140.0)
print(f"\n[6/6] Generiere beat-synchrone Timeline über die gesamte Länge ({analysis_data.get('duration_seconds')/60:.1f} Min)...")
pacing_body = {
    "audio_clip_id": audio_clip_id,
    "video_clip_ids": imported_video_ids,
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
    print(f"FAILED to generate pacing: {res.text}")
    sys.exit(1)

timeline_data = requests.get(f"{BASE_URL}/pacing/timeline").json()
print(f"  Timeline erfolgreich generiert!")
print(f"  Cuts gesamt: {len(timeline_data.get('entries', []))}")
print(f"  Gesamtdauer Timeline: {timeline_data.get('total_duration', 0)/60:.1f} Minuten.")

# Projekt speichern
requests.post(f"{BASE_URL}/project/save")
print("  Projektstatus dauerhaft gespeichert.")

# 7. Render-Prozess anstoßen
render_output = os.path.join(project_dir, project_name, "output", f"{project_name}_final.mp4")
os.makedirs(os.path.dirname(render_output), exist_ok=True)

print(f"\n[RENDER] Starte Rendering des stundenlangen Videos...")
print(f"  Ausgabepfad: {render_output}")

render_body = {
    "output_path": render_output,
    "audio_path": audio_path,
    "quality": "preview",  # preview für stabilen Hochgeschwindigkeits-Render-Lauf
    "resolution_width": 640,
    "resolution_height": 360,
    "fps": 24,
    "bitrate_mbps": 6.0,
    "include_audio": True
}

res = requests.post(f"{BASE_URL}/render/start", json=render_body)
if res.status_code != 200:
    print(f"FAILED to start rendering: {res.text}")
    sys.exit(1)

render_task = res.json()
print(f"\n[FERTIG] Render-Prozess erfolgreich im Hintergrund gestartet!")
print(f"  Render Task-ID: {render_task.get('task_id')}")
print(f"  Die App läuft live weiter. Du kannst den Render-Fortschritt im Tab 'EXPORT' mitverfolgen!")
