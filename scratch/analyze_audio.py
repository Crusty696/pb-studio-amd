import time
import requests

BASE_URL = "http://127.0.0.1:8765"
audio_clip_id = 1

print("=" * 60)
print("E2E AUDIO ANALYSIS - KLANGKRAFT")
print("=" * 60)

# Starte Audio-Analyse
print(f"Triggere Audio-Analyse für Clip-ID {audio_clip_id}...")
res = requests.post(f"{BASE_URL}/audio/analyze", json={"clip_id": audio_clip_id})
if res.status_code != 200:
    print(f"[ERROR] Audio-Analyse konnte nicht gestartet werden: {res.text}")
    import sys
    sys.exit(1)

print("Audio-Analyse gestartet. Polle Status...")
start_time = time.time()
while True:
    res = requests.get(f"{BASE_URL}/audio/clips?page=1&limit=50")
    if res.status_code == 200:
        clips = res.json()
        clip = next((c for c in clips if c.get("id") == audio_clip_id), None)
        if clip:
            bpm = clip.get("bpm")
            is_analyzed = clip.get("is_analyzed", False)
            duration = clip.get("duration_seconds", 0)
            
            elapsed = time.time() - start_time
            print(f"  [{elapsed:.1f}s] is_analyzed={is_analyzed}, BPM={bpm}, duration={duration:.2f}s")
            
            if is_analyzed and bpm and bpm > 0:
                print(f"\n[SUCCESS] Audio-Analyse erfolgreich beendet!")
                print(f"  Dauer: {duration/60:.2f} Minuten")
                print(f"  Erkanntes Tempo: {bpm} BPM")
                break
    time.sleep(5)
