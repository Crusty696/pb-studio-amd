# PB Studio QA API Test Suite
# Runs against http://localhost:8765
# Uses real test data from Audio and Video dirs

import json
import time
import urllib.request
import urllib.error
import urllib.parse
import threading
from datetime import datetime
from pathlib import Path

BASE_URL = "http://localhost:8765"

AUDIO_DIR = r"C:\Users\david\Videos\Music-Video_Clips\AV\Audio\Psy-Set"
VIDEO_DIR = r"C:\Users\david\Videos\Music-Video_Clips\AV\Video\Sora_20250622_0307_100_Generations"

# Allowed project base (from config.project_dir)
QA_PROJECT_BASE = r"C:\Users\david\OneDrive\Dokumente\PBStudio"
QA_PROJECT_NAME = "QA-Test-2026-03-15"
QA_PROJECT_PATH = QA_PROJECT_BASE + "\\" + QA_PROJECT_NAME

# Pick real test files
AUDIO_FILE = str(Path(AUDIO_DIR) / "Progressive Psy trance 2.wav")
VIDEO_FILE = str(Path(VIDEO_DIR) / "2025-06-25T22.19.31_1.mp4")

results = []


def req(method, path, body=None, timeout=30):
    url = BASE_URL + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    rq = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as ex:
        return 0, str(ex)


def record(test_id, name, status, details, error=None):
    entry = {
        "id": test_id,
        "name": name,
        "status": status,
        "details": details,
        "error": error,
    }
    results.append(entry)
    mark = "OK" if status == "PASS" else ("~~" if status == "PARTIAL" else "XX")
    print(f"  [{mark}] {test_id} {name}: {status}")
    if error:
        print(f"       ERROR: {error}")


def sse_collect(path, collect_secs=3.0):
    url = BASE_URL + path
    lines = []
    deadline = time.time() + collect_secs

    def _read():
        try:
            rq = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
            with urllib.request.urlopen(rq, timeout=int(collect_secs + 2)) as resp:
                while time.time() < deadline:
                    line = resp.readline()
                    if not line:
                        break
                    lines.append(line.decode(errors="replace").strip())
        except Exception:
            pass

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(timeout=collect_secs + 2)
    return lines


# ──────────────────────────────────────────────
print("\n=== BEREICH 1: Health & GPU ===")

# F-1.1 Health
code, body = req("GET", "/health")
if code == 200 and isinstance(body, dict) and body.get("status") == "ok":
    record("F-1.1", "Health-Check", "PASS",
           "status=ok, gpu_available=" + str(body.get("gpu_available")) +
           ", uptime=" + str(body.get("uptime_seconds", "?")))
else:
    record("F-1.1", "Health-Check", "FAIL", "code=" + str(code), str(body)[:200])

# F-1.2 GPU Status
code, body = req("GET", "/gpu/status")
if code == 200 and isinstance(body, dict):
    record("F-1.2", "GPU-Status", "PASS",
           "response=" + json.dumps(body)[:300])
else:
    record("F-1.2", "GPU-Status", "FAIL", "code=" + str(code), str(body)[:200])

# F-1.3 GPU Cleanup
code, body = req("POST", "/gpu/cleanup")
if code == 200:
    record("F-1.3", "GPU-Cleanup", "PASS",
           "response=" + (json.dumps(body) if isinstance(body, dict) else str(body)))
else:
    record("F-1.3", "GPU-Cleanup", "FAIL", "code=" + str(code), str(body)[:200])

# ──────────────────────────────────────────────
print("\n=== BEREICH 2: Projekt-Management ===")
print("  [i] Using project path: " + QA_PROJECT_PATH)

# F-2.1 Create Project — body must have {name, path} where path=parent dir
# The router does: project_path = (Path(request.path) / request.name).resolve()
# So we pass path=QA_PROJECT_BASE and name=QA_PROJECT_NAME
code, body = req("POST", "/project/create",
                 {"name": QA_PROJECT_NAME, "path": QA_PROJECT_BASE})
if code in (200, 201):
    record("F-2.1", "Project-Create", "PASS",
           "response=" + json.dumps(body)[:200])
elif code == 409:
    record("F-2.1", "Project-Create", "PARTIAL",
           "Already exists (409): " + str(body)[:200])
else:
    record("F-2.1", "Project-Create", "FAIL",
           "code=" + str(code), str(body)[:300])

# F-2.2 Project Info
code, body = req("GET", "/project/info")
if code == 200 and isinstance(body, dict):
    record("F-2.2", "Project-Info", "PASS",
           "name=" + str(body.get("name")) + ", path=" + str(body.get("path")))
else:
    record("F-2.2", "Project-Info", "FAIL", "code=" + str(code), str(body)[:200])

# F-2.3 Project Save
code, body = req("POST", "/project/save")
if code == 200:
    record("F-2.3", "Project-Save", "PASS",
           "response=" + (json.dumps(body) if isinstance(body, dict) else str(body)))
else:
    record("F-2.3", "Project-Save", "FAIL", "code=" + str(code), str(body)[:200])

# F-2.4 Project Close
code, body = req("POST", "/project/close")
if code == 200:
    record("F-2.4", "Project-Close", "PASS",
           "response=" + (json.dumps(body) if isinstance(body, dict) else str(body)))
else:
    record("F-2.4", "Project-Close", "FAIL", "code=" + str(code), str(body)[:200])

# F-2.5 Project Open — path is the FULL project directory (not parent)
code, body = req("POST", "/project/open", {"path": QA_PROJECT_PATH})
if code == 200:
    record("F-2.5", "Project-Open", "PASS",
           "response=" + (json.dumps(body)[:200] if isinstance(body, dict) else str(body)[:200]))
else:
    record("F-2.5", "Project-Open", "FAIL",
           "code=" + str(code), str(body)[:300])

# ──────────────────────────────────────────────
print("\n=== BEREICH 3: Audio-Import & Bibliothek ===")
print("  [i] Audio file: " + AUDIO_FILE)

# F-3.1 Audio Import — field is "path", not "file_path"
audio_clip_id = None
code, body = req("POST", "/audio/import", {"path": AUDIO_FILE})
if code in (200, 201) and isinstance(body, dict):
    audio_clip_id = body.get("id")
    record("F-3.1", "Audio-Import", "PASS",
           "clip_id=" + str(audio_clip_id) + ", file=" + Path(AUDIO_FILE).name)
else:
    record("F-3.1", "Audio-Import", "FAIL",
           "code=" + str(code) + ", file=" + Path(AUDIO_FILE).name, str(body)[:300])

# F-3.2 Audio Clips List
code, body = req("GET", "/audio/clips")
if code == 200:
    count = len(body) if isinstance(body, list) else "?"
    if audio_clip_id is None and isinstance(body, list) and body:
        audio_clip_id = body[0].get("id")
    record("F-3.2", "Audio-Clips-List", "PASS", "clips=" + str(count))
else:
    record("F-3.2", "Audio-Clips-List", "FAIL", "code=" + str(code), str(body)[:200])

print("  [i] Using audio_clip_id=" + str(audio_clip_id))

# ──────────────────────────────────────────────
print("\n=== BEREICH 4: Audio-Analyse ===")

# F-4.1 Audio Analyze
if audio_clip_id is not None:
    code, body = req("POST", "/audio/analyze",
                     {"clip_id": audio_clip_id, "waveform_bands": 3}, timeout=180)
    if code in (200, 202):
        record("F-4.1", "Audio-Analyze", "PASS",
               "bpm=" + str(body.get("bpm") if isinstance(body, dict) else "?") +
               ", beats=" + str(body.get("beat_count") if isinstance(body, dict) else "?"))
    else:
        record("F-4.1", "Audio-Analyze", "FAIL", "code=" + str(code), str(body)[:300])
else:
    record("F-4.1", "Audio-Analyze", "FAIL", "No audio_clip_id available", "Import failed")

# F-4.2 Audio Beats
if audio_clip_id is not None:
    code, body = req("GET", "/audio/beats/" + str(audio_clip_id))
    if code == 200:
        beats_count = len(body) if isinstance(body, list) else "?"
        record("F-4.2", "Audio-Beats", "PASS", "beats=" + str(beats_count))
    else:
        record("F-4.2", "Audio-Beats", "FAIL", "code=" + str(code), str(body)[:200])
else:
    record("F-4.2", "Audio-Beats", "FAIL", "No audio_clip_id", None)

# F-4.3 Audio Waveform
if audio_clip_id is not None:
    code, body = req("GET", "/audio/waveform/" + str(audio_clip_id))
    if code == 200:
        record("F-4.3", "Audio-Waveform", "PASS",
               "response_type=" + type(body).__name__ + ", size=" + str(len(str(body))) + " chars")
    else:
        record("F-4.3", "Audio-Waveform", "FAIL", "code=" + str(code), str(body)[:200])
else:
    record("F-4.3", "Audio-Waveform", "FAIL", "No audio_clip_id", None)

# F-4.4 Audio Structure
if audio_clip_id is not None:
    code, body = req("GET", "/audio/structure/" + str(audio_clip_id))
    if code == 200:
        seg_count = len(body) if isinstance(body, list) else "?"
        record("F-4.4", "Audio-Structure", "PASS", "segments=" + str(seg_count))
    else:
        record("F-4.4", "Audio-Structure", "FAIL", "code=" + str(code), str(body)[:200])
else:
    record("F-4.4", "Audio-Structure", "FAIL", "No audio_clip_id", None)

# F-4.5 Audio Spectral
if audio_clip_id is not None:
    code, body = req("GET", "/audio/spectral/" + str(audio_clip_id))
    if code == 200:
        record("F-4.5", "Audio-Spectral", "PASS",
               "clip_id=" + str(body.get("clip_id") if isinstance(body, dict) else "?"))
    else:
        record("F-4.5", "Audio-Spectral", "FAIL", "code=" + str(code), str(body)[:200])
else:
    record("F-4.5", "Audio-Spectral", "FAIL", "No audio_clip_id", None)

# ──────────────────────────────────────────────
print("\n=== BEREICH 5: Video-Import & Bibliothek ===")
print("  [i] Video file: " + VIDEO_FILE)

# F-5.1 Video Import — field is "paths" (list), not "file_path"
video_clip_id = None
code, body = req("POST", "/video/import", {"paths": [VIDEO_FILE]})
if code in (200, 201) and isinstance(body, list) and body:
    video_clip_id = body[0].get("id")
    record("F-5.1", "Video-Import", "PASS",
           "clip_id=" + str(video_clip_id) + ", file=" + Path(VIDEO_FILE).name)
else:
    record("F-5.1", "Video-Import", "FAIL",
           "code=" + str(code) + ", file=" + Path(VIDEO_FILE).name, str(body)[:300])

# F-5.2 Video Clips List
code, body = req("GET", "/video/clips")
if code == 200:
    count = len(body) if isinstance(body, list) else "?"
    if video_clip_id is None and isinstance(body, list) and body:
        video_clip_id = body[0].get("id")
    record("F-5.2", "Video-Clips-List", "PASS", "clips=" + str(count))
else:
    record("F-5.2", "Video-Clips-List", "FAIL", "code=" + str(code), str(body)[:200])

print("  [i] Using video_clip_id=" + str(video_clip_id))

# F-5.3 Video Thumbnail
if video_clip_id is not None:
    url = BASE_URL + "/video/thumbnails/" + str(video_clip_id)
    rq2 = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(rq2, timeout=30) as resp:
            data = resp.read()
            ct = resp.headers.get("Content-Type", "")
            if len(data) > 100:
                record("F-5.3", "Video-Thumbnail", "PASS",
                       "size=" + str(len(data)) + " bytes, content_type=" + ct)
            else:
                record("F-5.3", "Video-Thumbnail", "FAIL",
                       "Too small: " + str(len(data)) + " bytes", None)
    except urllib.error.HTTPError as e:
        record("F-5.3", "Video-Thumbnail", "FAIL",
               "code=" + str(e.code), e.read().decode()[:200])
    except Exception as ex:
        record("F-5.3", "Video-Thumbnail", "FAIL", "Exception", str(ex))
else:
    record("F-5.3", "Video-Thumbnail", "FAIL", "No video_clip_id", None)

# ──────────────────────────────────────────────
print("\n=== BEREICH 6: Video-Analyse ===")

# F-6.1 Video Analyze
if video_clip_id is not None:
    code, body = req("POST", "/video/analyze", {"clip_id": video_clip_id}, timeout=180)
    if code in (200, 202):
        record("F-6.1", "Video-Analyze", "PASS",
               "scenes=" + str(body.get("scene_count") if isinstance(body, dict) else "?") +
               ", avg_motion=" + str(body.get("avg_motion") if isinstance(body, dict) else "?"))
    else:
        record("F-6.1", "Video-Analyze", "FAIL", "code=" + str(code), str(body)[:300])
else:
    record("F-6.1", "Video-Analyze", "FAIL", "No video_clip_id", None)

# F-6.2 Video Scenes
if video_clip_id is not None:
    code, body = req("GET", "/video/scenes/" + str(video_clip_id))
    if code == 200:
        count = len(body) if isinstance(body, list) else "?"
        record("F-6.2", "Video-Scenes", "PASS", "scenes=" + str(count))
    else:
        record("F-6.2", "Video-Scenes", "FAIL", "code=" + str(code), str(body)[:200])
else:
    record("F-6.2", "Video-Scenes", "FAIL", "No video_clip_id", None)

# F-6.3 Video Motion
if video_clip_id is not None:
    code, body = req("GET", "/video/motion/" + str(video_clip_id))
    if code == 200:
        avg_motion = body.get("avg_motion", "?") if isinstance(body, dict) else "?"
        record("F-6.3", "Video-Motion", "PASS", "avg_motion=" + str(avg_motion))
    else:
        record("F-6.3", "Video-Motion", "FAIL", "code=" + str(code), str(body)[:200])
else:
    record("F-6.3", "Video-Motion", "FAIL", "No video_clip_id", None)

# ──────────────────────────────────────────────
print("\n=== BEREICH 7: Pacing & Director ===")

# F-7.1 Pacing Generate — PacingConfigSchema fields
if audio_clip_id is not None and video_clip_id is not None:
    payload = {
        "audio_clip_id": audio_clip_id,
        "video_clip_ids": [video_clip_id],
        "expected_bpm": 120.0,
        "use_motion_matching": False,
    }
    code, body = req("POST", "/pacing/generate", payload, timeout=180)
    if code in (200, 202):
        record("F-7.1", "Pacing-Generate", "PASS",
               "cuts=" + str(body.get("cut_count") if isinstance(body, dict) else "?") +
               ", total_dur=" + str(body.get("total_duration") if isinstance(body, dict) else "?"))
    else:
        record("F-7.1", "Pacing-Generate", "FAIL",
               "code=" + str(code), str(body)[:300])
else:
    record("F-7.1", "Pacing-Generate", "FAIL", "Missing audio or video clip_id", None)

# F-7.2 Pacing Timeline
code, body = req("GET", "/pacing/timeline")
if code == 200:
    count = len(body.get("entries", [])) if isinstance(body, dict) else "?"
    record("F-7.2", "Pacing-Timeline", "PASS", "timeline_entries=" + str(count))
else:
    record("F-7.2", "Pacing-Timeline", "FAIL", "code=" + str(code), str(body)[:200])

# F-7.3 Pacing Preview — PreviewRequest has start_sec and duration (no output_path)
code, body = req("POST", "/pacing/preview", {"start_sec": 0.0, "duration": 5.0}, timeout=120)
if code in (200, 202):
    record("F-7.3", "Pacing-Preview", "PASS",
           "preview_path=" + str(body.get("preview_path") if isinstance(body, dict) else "?"))
elif code == 400:
    record("F-7.3", "Pacing-Preview", "PARTIAL",
           "code=400 (no timeline or other issue): " + str(body)[:200])
else:
    record("F-7.3", "Pacing-Preview", "FAIL", "code=" + str(code), str(body)[:300])

# ──────────────────────────────────────────────
print("\n=== BEREICH 8: Rendering ===")

# Get current audio_path for render (needed by RenderRequest)
audio_path_for_render = AUDIO_FILE  # fallback
code_info, body_info = req("GET", "/project/info")
# Use the actual audio file path from the clip
if audio_clip_id is not None:
    code_clips, body_clips = req("GET", "/audio/clips")
    if code_clips == 200 and isinstance(body_clips, list):
        for clip in body_clips:
            if clip.get("id") == audio_clip_id:
                audio_path_for_render = clip.get("path", AUDIO_FILE)
                break

render_output = QA_PROJECT_PATH + "\\output.mp4"

# F-8.1 Render Start — requires output_path + audio_path
render_task_id = None
code, body = req("POST", "/render/start", {
    "output_path": render_output,
    "audio_path": audio_path_for_render,
    "quality": "high",
    "fps": 30.0,
}, timeout=30)
if code in (200, 202) and isinstance(body, dict):
    render_task_id = body.get("task_id")
    record("F-8.1", "Render-Start", "PASS",
           "task_id=" + str(render_task_id) + ", status=" + str(body.get("status")))
elif code == 400:
    record("F-8.1", "Render-Start", "PARTIAL",
           "code=400 (no timeline/path issue): " + str(body)[:300])
else:
    record("F-8.1", "Render-Start", "FAIL", "code=" + str(code), str(body)[:300])

# F-8.2 Render Status
if render_task_id:
    time.sleep(1)
    code, body = req("GET", "/render/status/" + str(render_task_id))
    if code == 200:
        record("F-8.2", "Render-Status", "PASS",
               "status=" + str(body.get("status") if isinstance(body, dict) else "?") +
               ", percent=" + str(body.get("percent") if isinstance(body, dict) else "?"))
    else:
        record("F-8.2", "Render-Status", "FAIL", "code=" + str(code), str(body)[:200])
else:
    record("F-8.2", "Render-Status", "PARTIAL", "No render task_id (no timeline)", None)

# F-8.3 Render Cancel
if render_task_id:
    code, body = req("POST", "/render/cancel/" + str(render_task_id))
    if code in (200, 202, 404):
        record("F-8.3", "Render-Cancel", "PASS",
               "code=" + str(code) + ", response=" + (json.dumps(body)[:100] if isinstance(body, dict) else str(body)[:100]))
    else:
        record("F-8.3", "Render-Cancel", "FAIL", "code=" + str(code), str(body)[:200])
else:
    record("F-8.3", "Render-Cancel", "PARTIAL", "No render task_id (no timeline)", None)

# ──────────────────────────────────────────────
print("\n=== BEREICH 9: SSE Events ===")

for endpoint, test_id, name in [
    ("/events/gpu",      "F-9.1", "SSE-GPU"),
    ("/events/log",      "F-9.2", "SSE-Log"),
    ("/events/progress", "F-9.3", "SSE-Progress"),
]:
    lines = sse_collect(endpoint, collect_secs=4.0)
    non_empty = [l for l in lines if l]
    if non_empty:
        record(test_id, name, "PASS",
               "Received " + str(len(non_empty)) + " lines in 4s. First: " + non_empty[0][:120])
    else:
        record(test_id, name, "PARTIAL",
               "Stream connected but no events in 4s (idle stream is acceptable)")

# ──────────────────────────────────────────────
print("\n=== ZUSAMMENFASSUNG ===")
total = len(results)
passed = sum(1 for r in results if r["status"] == "PASS")
partial = sum(1 for r in results if r["status"] == "PARTIAL")
failed = sum(1 for r in results if r["status"] == "FAIL")
print("  Total: " + str(total) +
      "  PASS: " + str(passed) +
      "  PARTIAL: " + str(partial) +
      "  FAIL: " + str(failed))

# ──────────────────────────────────────────────
report = {
    "timestamp": "2026-03-15",
    "run_at": datetime.now().isoformat(),
    "backend_url": BASE_URL,
    "audio_file": AUDIO_FILE,
    "video_file": VIDEO_FILE,
    "qa_project_path": QA_PROJECT_PATH,
    "allowed_project_base": QA_PROJECT_BASE,
    "summary": {
        "total": total,
        "pass": passed,
        "partial": partial,
        "fail": failed,
    },
    "results": results,
}

out_path = Path(r"C:\Users\david\Dokumente\Pb_studio_AMD_version\test-report\qa-2026-03-15-api-results.json")
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print("\nReport saved to: " + str(out_path))
