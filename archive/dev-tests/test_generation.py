import logging
import time
from pathlib import Path
from src.pb_studio.video.engine import VideoGenerator

# Setup logging
logging.basicConfig(level=logging.INFO)

def _progress_callback(step, progress):
    print(f"[{progress}%] {step}")

def main():
    print("Testing Video Generator...")
    
    # Needs a real audio and video to work.
    # Check for test files in current dir
    root = Path(".")
    audio_files = list(root.glob("*.mp3")) + list(root.glob("*.wav"))
    video_files = list(root.glob("*.mp4"))
    
    if not audio_files:
        print("SKIP: No audio files found for testing.")
        return
    if not video_files:
        print("SKIP: No video files found for testing.")
        return
        
    master_audio = str(audio_files[0])
    source_video = str(video_files[0])
    
    print(f"Using Audio: {master_audio}")
    print(f"Using Video: {source_video}")
    
    engine = VideoGenerator()
    
    config = {
        "master_audio": master_audio,
        "source_videos": [source_video],
        "output_path": "test_output.mp4",
        "pacing": 4, # Fast
        "min_dur": 1.0,
        "max_dur": 3.0,
        "precision": 8,
        "energy_react": 8,
        "chaos": 5,
        "keep_temp": True
    }
    
    try:
        engine.generate(config, callback=_progress_callback)
        print("Success! Check test_output.mp4")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    main()
