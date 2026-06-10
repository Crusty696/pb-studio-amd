import os
import requests
from pathlib import Path

BASE_URL = "http://127.0.0.1:8765"
video_dir = r"E:\Music-Video_Clips\Video\Clips"

print("Sammle Videos...")
video_extensions = {".mp4", ".mkv", ".mov", ".avi", ".MP4", ".MKV", ".MOV", ".AVI"}
video_files = []
for root, dirs, files in os.walk(video_dir):
    for file in files:
        if Path(file).suffix in video_extensions:
            video_files.append(os.path.join(root, file))

print(f"Videos gefunden: {len(video_files)}")

# Importiere alle Videos auf einmal
print("Sende Import-Request an das Backend...")
res = requests.post(f"{BASE_URL}/video/import", json={"paths": video_files})
if res.status_code == 200:
    imported = res.json()
    print(f"[SUCCESS] Erfolgreich {len(imported)} Videos in das aktuelle Projekt importiert!")
else:
    print(f"[ERROR] Video-Import fehlgeschlagen: {res.status_code} - {res.text}")
