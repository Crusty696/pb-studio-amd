
import asyncio
import time
import requests
import json
from pathlib import Path

BASE_URL = "http://127.0.0.1:8765"

def get_gpu_status():
    try:
        r = requests.get(f"{BASE_URL}/gpu/status")
        return r.json()
    except:
        return None

async def stress_test():
    print("=== PB STUDIO STRESS TEST START ===")
    print(f"Target: 50 Clips, Mass-Analysis, VRAM Pressure Check")
    
    # 1. Start Project if not open
    print("\n[Step 1] Opening/Creating Stress Project...")
    requests.post(f"{BASE_URL}/project/open", json={"name": "STRESS_TEST_PROJ", "path": "data/stress_project"})
    
    # 2. Mass Import
    print("\n[Step 2] Importing 50 Clips...")
    asset_dir = Path("data/stress_test_assets").absolute()
    clip_paths = [str(p) for p in asset_dir.glob("*.mp4")]
    
    start_time = time.time()
    r = requests.post(f"{BASE_URL}/video/import", json={"paths": clip_paths})
    imported_clips = r.json()
    print(f"Imported {len(imported_clips)} clips in {time.time() - start_time:.2f}s")
    
    # 3. Mass Analysis Loop (VRAM Pressure)
    print("\n[Step 3] Starting Mass Analysis (RAFT + SigLIP)...")
    analysis_results = []
    gpu_stats_log = []
    
    for i, clip in enumerate(imported_clips):
        clip_id = clip["id"]
        print(f"Analyzing Clip {i+1}/50 (ID: {clip_id})...", end="\r")
        
        # Monitor GPU before each task
        gpu = get_gpu_status()
        if gpu:
            gpu_stats_log.append(gpu)
            # print(f" VRAM: {gpu['vram_used_mb']:.0f} MB / {gpu['vram_total_mb']:.0f} MB", end="\r")
        
        # Trigger Analysis
        try:
            # BUG FIX: Send clip_id in JSON body, not query param
            r = requests.post(f"{BASE_URL}/video/analyze", json={"clip_id": clip_id})
            analysis_results.append(r.status_code)
        except Exception as e:
            print(f"\n[FAIL] Clip {clip_id} failed: {e}")
            
    total_time = time.time() - start_time
    print(f"\n\n=== STRESS TEST RESULTS ===")
    print(f"Total Time: {total_time:.2f}s")
    print(f"Successful Analyses: {analysis_results.count(200)} / 50")
    
    if gpu_stats_log:
        max_vram = max([g['vram_used_mb'] for g in gpu_stats_log])
        min_vram = min([g['vram_used_mb'] for g in gpu_stats_log])
        print(f"Max VRAM usage: {max_vram:.2f} MB")
        print(f"Min VRAM usage (Unloaded): {min_vram:.2f} MB")
        
        if max_vram > min_vram + 500:
            print("VRAM ARBITER CHECK: OK (Dynamic allocation detected)")
        else:
            print("VRAM ARBITER CHECK: WARNING (Low variance - is GPU active?)")
            
    print("\n=== SYSTEM HEALTH CHECK ===")
    health = requests.get(f"{BASE_URL}/health").json()
    print(f"Backend Status: {health['status']}")
    print(f"Uptime: {health['uptime_seconds']:.0f}s")

if __name__ == "__main__":
    asyncio.run(stress_test())
