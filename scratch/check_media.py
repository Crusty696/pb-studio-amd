import os
from pathlib import Path

audio_path = Path(r"C:\Users\david\Music\Audio\Psy-Set\Crusty -Klangkraft-21nai2022.wav")
video_dir = Path(r"E:\Music-Video_Clips\Video\Clips")

print("=" * 60)
print("E2E MEDIA FILE AUDIT")
print("=" * 60)

if audio_path.exists():
    size_mb = audio_path.stat().st_size / (1024 * 1024)
    print(f"[OK] Audio gefunden: {audio_path.name} ({size_mb:.2f} MB)")
else:
    print(f"[FEHLT] Audio nicht gefunden: {audio_path}")

if video_dir.exists():
    video_extensions = {".mp4", ".mkv", ".mov", ".avi", ".MP4", ".MKV", ".MOV", ".AVI"}
    video_files = []
    for root, dirs, files in os.walk(video_dir):
        for file in files:
            if Path(file).suffix in video_extensions:
                video_files.append(os.path.join(root, file))
    
    print(f"[OK] Video-Ordner gefunden. Videos gesamt: {len(video_files)}")
    if video_files:
        print("\nErste 5 Videodateien:")
        for v in video_files[:5]:
            print(f"  - {v}")
else:
    print(f"[FEHLT] Video-Ordner nicht gefunden: {video_dir}")
