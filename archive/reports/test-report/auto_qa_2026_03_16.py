"""
Auto-QA Script für PB Studio — 2026-03-16
Systematisches Testen aller 8 Bereiche via direkter API-Aufrufe.
"""
import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import os
from pathlib import Path
from datetime import datetime

BASE_URL = "http://127.0.0.1:8765"
AUDIO_FILE = r"C:\Users\david\Videos\test_audio_music_60s.wav"
VIDEO_FILE1 = r"C:\Users\david\Videos\Music-Video_Clips\AV\Video\1 (1).mp4"
VIDEO_FILE2 = r"C:\Users\david\Videos\Music-Video_Clips\AV\Video\1 (2).mp4"
PROJECT_BASE = r"C:\Users\david\OneDrive\Dokumente\PBStudio"

RESULTS = {}
BUGS = []


def api(method, path, body=None, raw=False):
    url = BASE_URL + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            content = resp.read()
            if raw:
                return resp.status, content
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read()
        try:
            return e.code, json.loads(content)
        except Exception:
            return e.code, {"detail": content.decode("utf-8", errors="replace")}
    except Exception as ex:
        return 0, {"detail": str(ex)}


def log(msg):
    print(msg)
    sys.stdout.flush()


def record(area, name, passed, details="", bug=None):
    key = f"{area}/{name}"
    RESULTS[key] = {"passed": passed, "details": details}
    status = "PASS" if passed else "FAIL"
    log(f"  [{status}] {name}: {details}")
    if bug and not passed:
        BUGS.append({"area": area, "test": name, "details": details, "bug": bug})


# ============================================================
# AREA 1: Project Management
# ============================================================
def test_project_management():
    log("\n=== AREA 1: Project Management ===")
    area = "project"

    # 1a: Create project
    project_name = f"AutoQA-{datetime.now().strftime('%H%M%S')}"
    status, body = api("POST", "/project/create", {
        "name": project_name,
        "path": PROJECT_BASE
    })
    passed = status == 200 and body.get("name") == project_name
    record(area, "create_project", passed, f"status={status} name={body.get('name')}")
    created_path = body.get("path", "")

    # 1b: Get info
    status, body = api("GET", "/project/info")
    passed = status == 200 and body.get("name") == project_name
    record(area, "project_info", passed, f"status={status} name={body.get('name')}")

    # 1c: Save
    status, body = api("POST", "/project/save")
    passed = status == 200 and body.get("success") is True
    record(area, "save_project", passed, f"status={status} success={body.get('success')}")

    # 1d: Close
    status, body = api("POST", "/project/close")
    passed = status == 200 and body.get("success") is True
    record(area, "close_project", passed, f"status={status}")

    # 1e: Re-open
    if created_path:
        status, body = api("POST", "/project/open", {"path": created_path})
        passed = status == 200 and body.get("name") == project_name
        record(area, "open_project", passed, f"status={status} name={body.get('name')}")
    else:
        record(area, "open_project", False, "No created_path available")

    return created_path, project_name


# ============================================================
# AREA 2: Media Import
# ============================================================
def test_media_import():
    log("\n=== AREA 2: Media Import ===")
    area = "media"
    audio_id = None
    video_ids = []

    # 2a: Import audio
    if not Path(AUDIO_FILE).exists():
        log(f"  [SKIP] Audio file not found: {AUDIO_FILE}")
        record(area, "import_audio", False, "Audio file not found", bug="missing_test_data")
    else:
        status, body = api("POST", "/audio/import", {"path": AUDIO_FILE})
        passed = status == 200 and "id" in body
        audio_id = body.get("id")
        record(area, "import_audio", passed, f"status={status} id={audio_id} duration={body.get('duration_seconds', 'N/A')}s")

    # 2b: Import video 1
    if not Path(VIDEO_FILE1).exists():
        log(f"  [SKIP] Video file not found: {VIDEO_FILE1}")
        record(area, "import_video1", False, "Video file not found", bug="missing_test_data")
    else:
        status, body = api("POST", "/video/import", {"paths": [VIDEO_FILE1]})
        passed = status == 200 and len(body) > 0
        if passed:
            video_ids.append(body[0].get("id"))
        record(area, "import_video1", passed, f"status={status} id={video_ids[0] if video_ids else 'N/A'}")

    # 2c: Import video 2
    if not Path(VIDEO_FILE2).exists():
        log(f"  [SKIP] Video file 2 not found")
        record(area, "import_video2", False, "Video file 2 not found", bug="missing_test_data")
    else:
        status, body = api("POST", "/video/import", {"paths": [VIDEO_FILE2]})
        passed = status == 200 and len(body) > 0
        if passed:
            video_ids.append(body[0].get("id"))
        record(area, "import_video2", passed, f"status={status} id={video_ids[-1] if video_ids else 'N/A'}")

    # 2d: List audio clips
    status, body = api("GET", "/audio/clips")
    passed = status == 200 and isinstance(body, list)
    record(area, "list_audio_clips", passed, f"status={status} count={len(body) if isinstance(body, list) else 'N/A'}")

    # 2e: List video clips
    status, body = api("GET", "/video/clips")
    passed = status == 200 and isinstance(body, list)
    record(area, "list_video_clips", passed, f"status={status} count={len(body) if isinstance(body, list) else 'N/A'}")

    return audio_id, video_ids


# ============================================================
# AREA 3: Audio Analysis
# ============================================================
def test_audio_analysis(audio_id):
    log("\n=== AREA 3: Audio Analysis ===")
    area = "audio"

    if audio_id is None:
        log("  [SKIP] No audio_id available")
        return

    # 3a: Analyze audio
    log(f"  Analyzing audio clip {audio_id} (may take 30-60s)...")
    status, body = api("POST", "/audio/analyze", {
        "clip_id": audio_id,
        "detect_beats": True,
        "detect_structure": True,
        "spectral_analysis": True
    })
    passed = status == 200
    bpm = body.get("bpm", 0)
    key = body.get("key")
    beat_count = body.get("beat_count", 0)
    record(area, "analyze_audio", passed, f"status={status} bpm={bpm:.1f} key={key} beats={beat_count}")

    # 3b: Get beats
    status, body = api("GET", f"/audio/beats/{audio_id}")
    passed = status == 200 and isinstance(body, list) and len(body) > 0
    record(area, "get_beats", passed, f"status={status} count={len(body) if isinstance(body, list) else 'N/A'}")

    # 3c: Get waveform
    status, body = api("GET", f"/audio/waveform/{audio_id}?bands=3")
    passed = status == 200 and "bands" in body
    bands = body.get("bands", [])
    record(area, "get_waveform", passed, f"status={status} bands={len(bands)} samples={len(bands[0]) if bands else 0}")

    # 3d: Get structure
    status, body = api("GET", f"/audio/structure/{audio_id}")
    passed = status == 200 and isinstance(body, list)
    record(area, "get_structure", passed, f"status={status} segments={len(body) if isinstance(body, list) else 'N/A'}")

    # 3e: Get spectral
    status, body = api("GET", f"/audio/spectral/{audio_id}")
    passed = status == 200
    record(area, "get_spectral", passed, f"status={status} bands_available={bool(body.get('bands'))}")


# ============================================================
# AREA 4: Video Analysis
# ============================================================
def test_video_analysis(video_ids):
    log("\n=== AREA 4: Video Analysis ===")
    area = "video"

    if not video_ids:
        log("  [SKIP] No video_ids available")
        return

    vid = video_ids[0]

    # 4a: Analyze video
    log(f"  Analyzing video clip {vid} (may take 30-120s)...")
    status, body = api("POST", "/video/analyze", {
        "clip_id": vid,
        "detect_scenes": True,
        "analyze_motion": True,
        "generate_embeddings": False
    })
    passed = status == 200
    scene_count = body.get("scene_count", 0)
    avg_motion = body.get("avg_motion", 0.0)
    record(area, "analyze_video", passed, f"status={status} scenes={scene_count} avg_motion={avg_motion:.2f}")

    # 4b: Thumbnail
    status, raw_content = api("GET", f"/video/thumbnails/{vid}", raw=True)
    passed = status == 200 and len(raw_content) > 1000
    record(area, "get_thumbnail", passed, f"status={status} size={len(raw_content)} bytes")

    # 4c: Scenes
    status, body = api("GET", f"/video/scenes/{vid}")
    passed = status == 200 and isinstance(body, list)
    record(area, "get_scenes", passed, f"status={status} count={len(body) if isinstance(body, list) else 'N/A'}")

    # 4d: Motion
    status, body = api("GET", f"/video/motion/{vid}")
    passed = status == 200
    record(area, "get_motion", passed, f"status={status} avg_motion={body.get('avg_motion', 'N/A')}")


# ============================================================
# AREA 5: Pacing/Director
# ============================================================
def test_pacing(audio_id, video_ids):
    log("\n=== AREA 5: Pacing/Director ===")
    area = "pacing"

    if audio_id is None or not video_ids:
        log("  [SKIP] Missing audio_id or video_ids")
        record(area, "generate_cutlist", False, "Missing prerequisites")
        return

    # 5a: Generate cut list
    log(f"  Generating cut list (audio={audio_id}, videos={video_ids})...")
    status, body = api("POST", "/pacing/generate", {
        "audio_clip_id": audio_id,
        "video_clip_ids": video_ids,
        "expected_bpm": 0.0,
        "use_motion_matching": False,
        "use_structure_awareness": True,
        "duration_limit": 60.0
    })
    passed = status == 200 and body.get("cut_count", 0) > 0
    cut_count = body.get("cut_count", 0)
    total_dur = body.get("total_duration", 0.0)
    record(area, "generate_cutlist", passed, f"status={status} cuts={cut_count} total_duration={total_dur:.1f}s")

    # 5b: Get timeline
    status, body = api("GET", "/pacing/timeline")
    passed = status == 200 and body.get("total_duration", 0) > 0
    entries = body.get("entries", [])
    record(area, "get_timeline", passed, f"status={status} entries={len(entries)} total_duration={body.get('total_duration', 0):.1f}s")


# ============================================================
# AREA 6: Rendering
# ============================================================
def test_rendering(project_path):
    log("\n=== AREA 6: Rendering ===")
    area = "render"

    # Check if timeline exists
    status, timeline = api("GET", "/pacing/timeline")
    if status != 200 or not timeline.get("entries"):
        log("  [SKIP] No timeline available for rendering")
        record(area, "start_render", False, "No timeline available")
        return

    if not project_path:
        log("  [SKIP] No project_path available")
        record(area, "start_render", False, "No project_path")
        return

    output_path = str(Path(project_path) / "output" / "auto_qa_test_render.mp4")

    # 6a: Start render
    audio_path = timeline.get("audio_path", "")
    status, body = api("POST", "/render/start", {
        "output_path": output_path,
        "audio_path": audio_path,
        "resolution_width": 640,
        "resolution_height": 360,
        "fps": 25.0,
        "bitrate_mbps": 4.0,
        "encoder": "h264_amf"
    })
    passed = status == 200 and "task_id" in body
    task_id = body.get("task_id", "")
    record(area, "start_render", passed, f"status={status} task_id={task_id}")

    if not task_id:
        record(area, "render_status", False, "No task_id")
        return

    # 6b: Poll render status (up to 5 minutes for large renders)
    log(f"  Polling render status for task {task_id} (up to 300s)...")
    final_status = None
    for i in range(60):  # max 300s (5 min)
        time.sleep(5)
        status, body = api("GET", f"/render/status/{task_id}")
        if status == 200:
            final_status = body.get("status")
            pct = body.get("percent", 0)
            log(f"    [{i+1}/60] status={final_status} percent={pct:.1f}%")
            if final_status in ("completed", "failed", "cancelled"):
                break
        elif status == 404:
            log(f"    Task {task_id} not found (maybe cleared)")
            final_status = "not_found"
            break

    passed = final_status == "completed"
    record(area, "render_status", passed, f"final_status={final_status} percent={body.get('percent', 0):.1f}%",
           bug=None if passed else "render_did_not_complete")
    if not passed and final_status == "failed":
        error_msg = body.get("error", "unknown")
        log(f"    Render error: {error_msg}")
        BUGS.append({"area": area, "test": "render_error", "details": error_msg, "bug": "render_failed"})


# ============================================================
# AREA 7: SSE Events
# ============================================================
def test_sse_events():
    log("\n=== AREA 7: SSE Events ===")
    area = "sse"

    # 7a: GPU stream (get 1 event with timeout)
    import socket
    try:
        s = socket.create_connection(("127.0.0.1", 8765), timeout=5)
        s.sendall(b"GET /events/gpu HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nAccept: text/event-stream\r\nConnection: close\r\n\r\n")
        data = b""
        s.settimeout(12)
        try:
            while len(data) < 2048:
                chunk = s.recv(512)
                if not chunk:
                    break
                data += chunk
                if b"gpu_status" in data:
                    break
        except socket.timeout:
            pass
        s.close()
        passed = b"gpu_status" in data
        record(area, "gpu_sse_stream", passed, f"received {len(data)} bytes, has gpu_status={passed}")
    except Exception as ex:
        record(area, "gpu_sse_stream", False, f"exception: {ex}")

    # 7b: Progress stream connect
    try:
        s = socket.create_connection(("127.0.0.1", 8765), timeout=5)
        s.sendall(b"GET /events/progress HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nAccept: text/event-stream\r\nConnection: close\r\n\r\n")
        data = b""
        s.settimeout(5)
        try:
            chunk = s.recv(1024)
            data += chunk
        except socket.timeout:
            pass
        s.close()
        passed = b"200 OK" in data or b"text/event-stream" in data
        record(area, "progress_sse_connect", passed, f"status_line present={passed}")
    except Exception as ex:
        record(area, "progress_sse_connect", False, f"exception: {ex}")


# ============================================================
# AREA 8: Persistence after restart
# ============================================================
def test_persistence_checks(audio_id, video_ids, project_path):
    """
    We cannot restart the backend here, but we can verify that
    DB persistence is working by checking that re-opening the
    project restores clips.
    """
    log("\n=== AREA 8: Persistence (DB state verification) ===")
    area = "persistence"

    if not project_path:
        record(area, "reopen_restores_clips", False, "No project_path")
        return

    # Save project first
    api("POST", "/project/save")

    # Close project
    status, body = api("POST", "/project/close")
    passed_close = status == 200
    record(area, "close_before_reopen", passed_close, f"status={status}")

    # Re-open project
    status, body = api("POST", "/project/open", {"path": project_path})
    passed_open = status == 200
    record(area, "reopen_project", passed_open, f"status={status} name={body.get('name')}")

    if passed_open:
        # Verify audio clips persist
        status_a, audio_clips = api("GET", "/audio/clips")
        audio_count_after = len(audio_clips) if isinstance(audio_clips, list) else 0
        passed_audio = status_a == 200 and audio_count_after > 0
        record(area, "audio_clips_persist", passed_audio, f"count_after_reopen={audio_count_after}")

        # Verify video clips persist
        status_v, video_clips = api("GET", "/video/clips")
        video_count_after = len(video_clips) if isinstance(video_clips, list) else 0
        passed_video = status_v == 200 and video_count_after > 0
        record(area, "video_clips_persist", passed_video, f"count_after_reopen={video_count_after}")
    else:
        record(area, "audio_clips_persist", False, "Could not reopen project")
        record(area, "video_clips_persist", False, "Could not reopen project")


# ============================================================
# MAIN
# ============================================================
def main():
    log("=" * 60)
    log("PB Studio Auto-QA 2026-03-16")
    log("=" * 60)

    # Initial health check
    status, body = api("GET", "/health")
    log(f"\nBackend health: status={status} {body}")
    if status != 200:
        log("FATAL: Backend not running!")
        sys.exit(1)

    # Run all areas
    project_path, project_name = test_project_management()
    audio_id, video_ids = test_media_import()
    test_audio_analysis(audio_id)
    test_video_analysis(video_ids)
    test_pacing(audio_id, video_ids)
    test_rendering(project_path)
    test_sse_events()
    test_persistence_checks(audio_id, video_ids, project_path)

    # Summary
    log("\n" + "=" * 60)
    log("SUMMARY")
    log("=" * 60)
    total = len(RESULTS)
    passed_count = sum(1 for v in RESULTS.values() if v["passed"])
    failed_count = total - passed_count
    log(f"Total: {total} tests, PASSED: {passed_count}, FAILED: {failed_count}")
    log(f"\nFailed tests:")
    for k, v in RESULTS.items():
        if not v["passed"]:
            log(f"  FAIL: {k} — {v['details']}")

    # Save state JSON
    state = {
        "timestamp": datetime.now().isoformat(),
        "backend_status": "running",
        "project_path": project_path,
        "audio_id": audio_id,
        "video_ids": video_ids,
        "results": RESULTS,
        "bugs": BUGS,
        "summary": {
            "total": total,
            "passed": passed_count,
            "failed": failed_count,
        }
    }
    state_path = r"C:\Users\david\Dokumente\Pb_studio_AMD_version\test-report\state.json"
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    log(f"\nState saved to: {state_path}")

    return state


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result["summary"]["failed"] == 0 else 1)
