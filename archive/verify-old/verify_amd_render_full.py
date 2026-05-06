
import asyncio
import time
import json
from pathlib import Path
from backend.app_state import AppState
from backend.routers.render_router import _execute_render
from backend.schemas.render_schemas import RenderRequest, RenderQuality, RenderEncoder

async def mock_publish_event(event_type, payload):
    if event_type == "render_progress":
        meta = payload.get("metadata", {})
        print(f"PROGRESS: {payload.get('percent')}% | FPS: {meta.get('fps')} | ETA: {meta.get('eta_seconds')}s")

async def mock_publish_log(msg, **kwargs):
    pass

import importlib
render_mod = importlib.import_module('backend.routers.render_router')
render_mod.publish_event = mock_publish_event
render_mod.publish_log = mock_publish_log

async def test_full_render():
    state = AppState()
    base_dir = Path.cwd()
    
    # Fixtures
    test_clip = base_dir / "data" / "test_clip_full.mp4"
    if not test_clip.exists():
        import subprocess
        test_clip.parent.mkdir(exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=10:size=1280x720:rate=30", "-c:v", "libx264", str(test_clip)], check=True, capture_output=True)
    
    dummy_audio = base_dir / "data" / "dummy_audio_full.wav"
    if not dummy_audio.exists():
        import subprocess
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=duration=10", str(dummy_audio)], check=True, capture_output=True)

    timeline = [{
        "file_path": str(test_clip),
        "start_time": 0.0,
        "end_time": 10.0,
        "metadata": { "clip_start": 0.0 }
    }]

    output_path = base_dir / "data" / "final_export_test.mp4"
    request = RenderRequest(
        output_path=str(output_path),
        audio_path=str(dummy_audio),
        quality=RenderQuality.STANDARD,
        encoder=RenderEncoder.H264_AMF, # Test real AMF
        resolution_width=1280,
        resolution_height=720,
        fps=30.0,
        bitrate_mbps=10.0
    )

    task_id = "full-render-test"
    state.set_render_task(task_id, {"status": "pending"})
    state.set_cancel_flag(task_id, False)

    print(f"Starting FULL AMD Render for {task_id}...")
    start_time = time.time()
    
    try:
        await asyncio.to_thread(_execute_render, task_id, request, state, timeline, asyncio.get_running_loop())
    except Exception as e:
        print(f"Render FAILED: {e}")
        return

    duration = time.time() - start_time
    final_state = state.get_render_task(task_id)
    
    print("\nRender Finished.")
    print(f"Total Time: {duration:.2f}s")
    print(f"Final State: {json.dumps(final_state, indent=2)}")
    
    if output_path.exists() and output_path.stat().st_size > 0:
        print(f"SUCCESS: Output file created ({output_path.stat().st_size / 1024 / 1024:.2f} MB)")
    else:
        print("FAILURE: Output file missing or empty")

if __name__ == "__main__":
    import os
    os.environ["PYTHONPATH"] = "src"
    asyncio.run(test_full_render())
