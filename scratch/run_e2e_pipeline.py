import os
import sys
import time
import requests
import glob
from pathlib import Path

# API Endpoint Configuration
BASE_URL = "http://127.0.0.1:8765"
AUDIO_PATH = r"C:\Users\david\Music\Audio\Psy-Set\Crusty -Klangkraft-21nai2022.wav"
VIDEO_DIR = r"E:\Music-Video_Clips\Video\Clips"
OUTPUT_DIR = r"C:\Users\david\Documents\PBStudio\Klangkraft_E2E_1780357792\output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "Klangkraft_E2E_final.mp4")

print("=" * 70)
print("             PB STUDIO E2E PRODUCTION PIPELINE RUNNER             ")
print("=" * 70)

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 1. Verify connection to Backend
try:
    resp = requests.get(f"{BASE_URL}/health")
    if resp.status_code == 200:
        print("[OK] Backend ist erreichbar und aktiv.")
    else:
        print(f"[ERR] Backend Fehler: {resp.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"[ERR] Backend nicht erreichbar: {e}")
    sys.exit(1)

# 2. Check active Project
try:
    resp = requests.get(f"{BASE_URL}/project/info")
    if resp.status_code == 200:
        proj = resp.json()
        print(f"[OK] Aktives Projekt: {proj['name']} (ID: {proj['db_project_id']})")
    else:
        print("[!] Kein aktives Projekt geladen. Versuche Projekt 6 zu öffnen...")
        # Try to open existing project
        proj_path = r"C:\Users\david\Documents\PBStudio\Klangkraft_E2E_1780357792"
        open_resp = requests.post(f"{BASE_URL}/project/open", json={"path": proj_path})
        if open_resp.status_code == 200:
            proj = open_resp.json()
            print(f"[OK] Projekt erfolgreich geöffnet: {proj['name']}")
        else:
            print(f"[ERR] Fehler beim Öffnen des Projekts: {open_resp.text}")
            sys.exit(1)
except Exception as e:
    print(f"[ERR] Fehler bei der Projekt-Abfrage: {e}")
    sys.exit(1)

# 3. Import Verification & Media Scan
print("\n" + "-" * 50)
print("SCHRITT 1: Medien importieren & verifizieren")
print("-" * 50)

# Check Audio clip in project
audio_id = None
try:
    resp = requests.get(f"{BASE_URL}/audio/clips")
    if resp.status_code == 200:
        clips = resp.json()
        for c in clips:
            if c["path"] == AUDIO_PATH:
                audio_id = c["id"]
                print(f"[OK] Audio-Mix ist bereits importiert (Clip-ID: {audio_id})")
                break
    if audio_id is None:
        print("[!] Audio-Mix noch nicht importiert. Starte Import...")
        import_resp = requests.post(f"{BASE_URL}/audio/import", json={"path": AUDIO_PATH})
        if import_resp.status_code == 200:
            audio_clip = import_resp.json()
            audio_id = audio_clip["id"]
            print(f"[OK] Audio-Mix erfolgreich importiert (Clip-ID: {audio_id})")
        else:
            print(f"[ERR] Fehler beim Importieren des Audios: {import_resp.text}")
            sys.exit(1)
except Exception as e:
    print(f"[ERR] Fehler beim Audio-Import-Check: {e}")
    sys.exit(1)

# Scan for video files recursively
print(f"Scanne Verzeichnis: {VIDEO_DIR} ...")
supported_exts = [".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv", ".flv"]
local_videos = []
for root, _, files in os.walk(VIDEO_DIR):
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in supported_exts:
            local_videos.append(os.path.abspath(os.path.join(root, f)))

print(f"Gefundene lokale Video-Dateien: {len(local_videos)}")

# Check currently imported videos in project
imported_videos = {}
page = 1
while True:
    try:
        resp = requests.get(f"{BASE_URL}/video/clips?page={page}&limit=200")
        if resp.status_code == 200:
            clips = resp.json()
            if not clips:
                break
            for c in clips:
                imported_videos[c["path"]] = c["id"]
            page += 1
        else:
            print(f"[ERR] Fehler beim Abrufen der Video-Liste: {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"[ERR] Fehler bei Video-Abfrage: {e}")
        sys.exit(1)

print(f"Bereits in der DB registrierte Videos: {len(imported_videos)}")

# Find missing videos to import
missing_videos = [v for v in local_videos if os.path.abspath(v) not in imported_videos and v not in imported_videos]
if missing_videos:
    print(f"[!] {len(missing_videos)} neue Videos gefunden. Starte Import...")
    # Import in batches to prevent API timeout
    batch_size = 20
    for i in range(0, len(missing_videos), batch_size):
        batch = missing_videos[i:i + batch_size]
        print(f"  Importiere Batch {i//batch_size + 1} ({len(batch)} Clips)...")
        try:
            import_resp = requests.post(f"{BASE_URL}/video/import", json={"paths": batch})
            if import_resp.status_code == 200:
                results = import_resp.json()
                for r in results:
                    imported_videos[r["path"]] = r["id"]
            else:
                print(f"  [!] Batch-Import fehlgeschlagen: {import_resp.text}")
        except Exception as e:
            print(f"  [ERR] Batch-Import Exception: {e}")
else:
    print("[OK] Alle lokalen Video-Dateien sind bereits importiert (stundenlanges Hashing übersprungen!).")

# Collect all video IDs
video_ids = list(imported_videos.values())
print(f"Gesamtanzahl einsatzbereiter Videos: {len(video_ids)}")

# 4. Trigger Stem Separation
print("\n" + "-" * 50)
print("SCHRITT 2: Stem-Separation starten")
print("-" * 50)
print(f"Separiere Audio-Mix (Clip-ID: {audio_id}) in 4 Stems (UVR-MDX-NET)...")
print("HINWEIS: Dies belegt die GPU und blockiert, bis die Separation abgeschlossen ist.")
t_start = time.time()
try:
    sep_resp = requests.post(
        f"{BASE_URL}/audio/stems/separate", 
        json={"clip_id": audio_id, "model": "UVR-MDX-NET-Inst_HQ_3.onnx"},
        timeout=1800 # 30 min timeout for 1.76h WAV
    )
    if sep_resp.status_code == 200:
        result = sep_resp.json()
        print(f"[OK] Stem-Separation erfolgreich abgeschlossen!")
        print(f"    Dauer: {time.time() - t_start:.2f}s")
        print(f"    Stems: {result.get('stems_paths', {})}")
    else:
        print(f"[ERR] Stem-Separation fehlgeschlagen: {sep_resp.text}")
        sys.exit(1)
except Exception as e:
    print(f"[ERR] Exception bei Stem-Separation: {e}")
    sys.exit(1)

# 5. Trigger Video Analysis (SigLIP & RAFT)
print("\n" + "-" * 50)
print("SCHRITT 3: KI-Video-Analyse (SigLIP & RAFT)")
print("-" * 50)
print("Analysiere alle 395 Clips. Überspringe bereits analysierte Clips...")

# Fetch all current clips to see analysis status
analyzed_count = 0
to_analyze = []
page = 1
while True:
    resp = requests.get(f"{BASE_URL}/video/clips?page={page}&limit=200")
    if resp.status_code == 200:
        clips = resp.json()
        if not clips:
            break
        for c in clips:
            if c["is_analyzed"]:
                analyzed_count += 1
            else:
                to_analyze.append(c["id"])
        page += 1
    else:
        break

print(f"Bereits analysiert: {analyzed_count}")
print(f"Noch zu analysieren: {len(to_analyze)}")

# Process analysis
if to_analyze:
    print(f"Starte Batch-Analyse für {len(to_analyze)} Videos...")
    for idx, vid_id in enumerate(to_analyze):
        print(f"  [{idx + 1}/{len(to_analyze)}] Analysiere Clip-ID {vid_id}...")
        try:
            analyze_resp = requests.post(
                f"{BASE_URL}/video/analyze",
                json={
                    "clip_id": vid_id,
                    "detect_scenes": True,
                    "generate_embeddings": True,
                    "analyze_motion": True,
                    "generate_captions": False
                },
                timeout=300 # 5 min timeout per clip
            )
            if analyze_resp.status_code == 200:
                print(f"    [OK] Clip-ID {vid_id} erfolgreich analysiert.")
            else:
                print(f"    [!] Clip-ID {vid_id} Analyse fehlgeschlagen: {analyze_resp.text}")
        except Exception as e:
            print(f"    [ERR] Clip-ID {vid_id} Exception: {e}")
else:
    print("[OK] Alle Video-Clips sind bereits KI-analysiert.")

# 6. Generate Timeline (Advanced Pacing Engine)
print("\n" + "-" * 50)
print("SCHRITT 4: Timeline generieren (KI-Regie & Pacing)")
print("-" * 50)
print(f"Generiere intelligente Timeline für 143.55 BPM...")
try:
    pacing_payload = {
        "audio_clip_id": audio_id,
        "video_clip_ids": video_ids,
        "expected_bpm": 143.55,
        "use_motion_matching": True,
        "use_semantic_matching": True,
        "use_structure_awareness": True,
        "use_key_matching": True,
        "use_stem_pacing": True,
        "duration_limit": None,
        "min_cut_interval": 1.5
    }
    pacing_resp = requests.post(
        f"{BASE_URL}/pacing/generate",
        json=pacing_payload,
        timeout=600 # 10 min timeout
    )
    if pacing_resp.status_code == 200:
        timeline = pacing_resp.json()
        print(f"[OK] Timeline erfolgreich generiert!")
        print(f"    Schnitte insgesamt: {len(timeline.get('cuts', []))}")
        
        # Save project to persist timeline
        save_resp = requests.post(f"{BASE_URL}/project/save")
        if save_resp.status_code == 200:
            print("[OK] Projekt erfolgreich gespeichert.")
        else:
            print(f"[!] Warnung beim Speichern des Projekts: {save_resp.text}")
    else:
        print(f"[ERR] Pacing-Generierung fehlgeschlagen: {pacing_resp.text}")
        sys.exit(1)
except Exception as e:
    print(f"[ERR] Exception bei Pacing-Generierung: {e}")
    sys.exit(1)

# 7. Start Rendering
print("\n" + "-" * 50)
print("SCHRITT 5: AMF-Hardware-Rendering starten")
print("-" * 50)
print(f"Rendere Video nach: {OUTPUT_FILE} ...")
try:
    render_payload = {
        "output_path": OUTPUT_FILE,
        "audio_path": AUDIO_PATH,
        "quality": "high",
        "encoder": "h264_amf",
        "resolution_width": 1920,
        "resolution_height": 1080,
        "fps": 30.0,
        "bitrate_mbps": 12.0,
        "include_audio": True
    }
    render_resp = requests.post(
        f"{BASE_URL}/render/start",
        json=render_payload
    )
    if render_resp.status_code == 200:
        render_task = render_resp.json()
        task_id = render_task["task_id"]
        print(f"[OK] Rendering erfolgreich im Hintergrund gestartet! (Render-Task-ID: {task_id})")
        print("Überwache Fortschritt...")
        
        # Monitor render task progress
        while True:
            status_resp = requests.get(f"{BASE_URL}/render/status/{task_id}")
            if status_resp.status_code == 200:
                prog = status_resp.json()
                status = prog["status"]
                pct = prog["percent"]
                print(f"  Rendering-Fortschritt: {pct:.2f}% | Status: {status}")
                if status == "completed":
                    print(f"\n[OK] RENDER-WORKFLOW ERFOLGREICH BESTANDEN!")
                    print(f"    Video liegt unter: {OUTPUT_FILE}")
                    break
                elif status in ["failed", "cancelled"]:
                    print(f"\n[ERR] Rendering abgebrochen oder fehlgeschlagen! Status: {status}")
                    sys.exit(1)
            else:
                print(f"  [!] Fehler beim Abrufen des Render-Status: {status_resp.text}")
            time.sleep(10)
    else:
        print(f"[ERR] Render-Start fehlgeschlagen: {render_resp.text}")
        sys.exit(1)
except Exception as e:
    print(f"[ERR] Exception beim Render-Start: {e}")
    sys.exit(1)
