import logging
from scenedetect import open_video, SceneManager, ContentDetector
import sys
import os

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def test_scene_detection():
    # File from previous logs
    video_path = r"C:\Users\david\Videos\Music-Video_Clips\AV\Video\Sora_20250622_0307_100_Generations\20250621_1011_Goddess_in_Mystical_Jungle_gen_01jy8zhhgwepcakhyzbzak3kwt.mp4"
    
    if not os.path.exists(video_path):
        print("ERROR: Video not found!")
        return

    print(f"Testing Scene Detect on: {video_path}")
    
    # Test multiple thresholds
    for threshold in [20.0, 15.0, 10.0, 5.0]:
        try:
            print(f"\n--- Testing Threshold: {threshold} ---")
            video = open_video(video_path)
            scene_manager = SceneManager()
            scene_manager.add_detector(ContentDetector(threshold=threshold))
            
            scene_manager.detect_scenes(video, show_progress=False)
            
            scenes = scene_manager.get_scene_list()
            print(f"Found {len(scenes)} scenes.")
            for i, scene in enumerate(scenes):
                print(f"   Scene {i}: {scene[0].get_seconds()} - {scene[1].get_seconds()}")
                
        except Exception as e:
            print(f"CRASH at {threshold}: {e}")

if __name__ == "__main__":
    test_scene_detection()
