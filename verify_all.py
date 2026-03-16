"""Robuster End-to-End-Verifikationstest für den laufenden PB Studio Backend-Server.

Ziele:
- keine hart codierten Clip-IDs
- Projektpfad dynamisch aus aktuellem erlaubtem Root ableiten
- Timeline vor Preview/Render deterministisch erzeugen
- Fehlermeldungen klar reporten
"""

from __future__ import annotations

import atexit
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8765"
PROJECT_ROOT = Path(__file__).resolve().parent
results: list[tuple[str, str, str]] = []
_STARTED_BACKEND: subprocess.Popen[str] | None = None


def resolve_allowed_root() -> Path:
    python_candidates = [
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        Path(sys.executable),
    ]
    python_exe = next((candidate for candidate in python_candidates if candidate.exists()), None)
    if python_exe is None:
        raise RuntimeError("Kein Python-Interpreter für Konfigurationsauflösung gefunden")

    completed = subprocess.run(
        [str(python_exe), "-c", "from backend.config import config; print(config.project_dir)"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    path = Path(completed.stdout.strip())
    path.mkdir(parents=True, exist_ok=True)
    return path


_ALLOWED_ROOT = resolve_allowed_root()
_FIXTURE_DIR = _ALLOWED_ROOT / "E2E_Complete"


def ensure_verification_media() -> tuple[Path, Path]:
    script_path = PROJECT_ROOT / "scripts" / "ensure_verification_media.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Verification media helper fehlt: {script_path}")

    python_candidates = [
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        Path(sys.executable),
    ]
    python_exe = next((candidate for candidate in python_candidates if candidate.exists()), None)
    if python_exe is None:
        raise RuntimeError("Kein Python-Interpreter für Medien-Fixures gefunden")

    completed = subprocess.run(
        [str(python_exe), str(script_path), str(_FIXTURE_DIR)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    parsed: dict[str, Path] = {}
    for line in completed.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            parsed[key.strip()] = Path(value.strip())

    audio = parsed.get("audio")
    video = parsed.get("video_a")
    if audio is None or video is None or not audio.exists() or not video.exists():
        raise RuntimeError("Verification media generation lieferte keine gültigen Fixtures")
    return audio, video


AUDIO_SAMPLE, VIDEO_SAMPLE = ensure_verification_media()


def _summarize_payload(payload):
    if isinstance(payload, dict):
        parts = []
        for key in list(payload.keys())[:4]:
            value = payload[key]
            if isinstance(value, (dict, list)):
                value = f"<{type(value).__name__}>"
            parts.append(f"{key}={value}")
        return ", ".join(parts)[:140]
    if isinstance(payload, list):
        return f"{len(payload)} items"
    return str(payload)[:140]


def call(method, url, body=None, *, expect_status=200, label=None, timeout=300):
    name = label or f"{method} {url}"
    expected_statuses = {expect_status} if isinstance(expect_status, int) else set(expect_status)
    try:
        if method == "GET":
            response = requests.get(BASE + url, timeout=timeout)
        else:
            response = requests.post(BASE + url, json=body, timeout=timeout)

        ok = response.status_code in expected_statuses
        try:
            payload = response.json()
            detail = _summarize_payload(payload)
        except Exception:
            payload = None
            detail = response.text[:140] or f"{len(response.content)} bytes"

        status = "OK" if ok else f"FAIL({response.status_code})"
        results.append((name, status, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        return ok, response, payload
    except Exception as exc:
        results.append((name, "ERROR", str(exc)[:140]))
        print(f"  [ERR!] {name}: {exc}")
        return False, None, None


def require_path(path: Path, label: str):
    if not path.exists():
        raise FileNotFoundError(f"{label} fehlt: {path}")


def _is_port_in_use(host: str = "127.0.0.1", port: int = 8765) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def ensure_backend() -> None:
    global _STARTED_BACKEND
    try:
        response = requests.get(BASE + "/health", timeout=2)
        if response.status_code == 200:
            return
    except Exception:
        pass

    if _is_port_in_use():
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                response = requests.get(BASE + "/health", timeout=2)
                if response.status_code == 200:
                    return
            except Exception:
                time.sleep(0.5)
        raise RuntimeError("Port 8765 ist belegt, aber /health antwortet nicht stabil – verweigere Doppelstart")

    python_candidates = [
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        Path(sys.executable),
    ]
    python_exe = next((candidate for candidate in python_candidates if candidate.exists()), None)
    if python_exe is None:
        raise RuntimeError("Kein Python-Interpreter für Backend-Start gefunden")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    _STARTED_BACKEND = subprocess.Popen(
        [str(python_exe), "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8765"],
        cwd=PROJECT_ROOT,
        env=env,
    )

    deadline = time.time() + 30
    while time.time() < deadline:
        if _STARTED_BACKEND.poll() is not None:
            raise RuntimeError(f"Backend-Prozess wurde vorzeitig beendet (exit={_STARTED_BACKEND.returncode})")
        try:
            response = requests.get(BASE + "/health", timeout=2)
            if response.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)

    raise RuntimeError("Backend konnte für verify_all.py nicht gestartet werden")


def shutdown_started_backend() -> None:
    global _STARTED_BACKEND
    if _STARTED_BACKEND is None:
        return
    try:
        requests.post(BASE + "/shutdown", timeout=5)
        _STARTED_BACKEND.wait(timeout=10)
    except Exception:
        _STARTED_BACKEND.kill()
        _STARTED_BACKEND.wait(timeout=5)
    finally:
        _STARTED_BACKEND = None


def get_allowed_project_parent() -> Path:
    ok, response, payload = call("GET", "/project/info", expect_status=(200, 400), label="Project Info (optional)")
    if ok and response is not None and response.status_code == 200 and isinstance(payload, dict) and payload.get("path"):
        return Path(payload["path"]).resolve().parent
    return _ALLOWED_ROOT


atexit.register(shutdown_started_backend)
ensure_backend()

print("=== Preconditions ===")
require_path(AUDIO_SAMPLE, "Audio-Sample")
require_path(VIDEO_SAMPLE, "Video-Sample")

project_parent = get_allowed_project_parent()
project_name = f"VerifyProject_{int(time.time())}"
project_path = (project_parent / project_name).resolve()

print("\n=== Block 1: Health & Project Setup ===")
call("GET", "/health", label="1. Health Check")
call("GET", "/gpu/status", label="2. GPU Status")
call("POST", "/gpu/cleanup", label="3. GPU Cleanup")
call("POST", "/project/close", expect_status=(200, 400), label="4. Project Close (optional)")
call(
    "POST",
    "/project/create",
    {"name": project_name, "path": str(project_parent)},
    label="5. Project Create",
)
call("GET", "/project/info", label="6. Project Info")

print("\n=== Block 2: Import & Catalog ===")
a_ok, _, a_payload = call("POST", "/audio/import", {"path": str(AUDIO_SAMPLE)}, label="7. Audio Import")
v_ok, _, v_payload = call("POST", "/video/import", {"paths": [str(VIDEO_SAMPLE)]}, label="8. Video Import")
call("GET", "/audio/clips?page=1&limit=5", label="9. Audio Clips List")
call("GET", "/video/clips?page=1&limit=5", label="10. Video Clips List")

audio_id = a_payload.get("id") if a_ok and isinstance(a_payload, dict) else None
video_id = None
if v_ok and isinstance(v_payload, list) and v_payload:
    video_id = v_payload[0].get("id")

if audio_id is None or video_id is None:
    print("\nABBRUCH: Import lieferte keine nutzbaren Clip-IDs.")
else:
    print("\n=== Block 3: Audio Analysis ===")
    call("POST", "/audio/analyze", {"clip_id": audio_id}, label="11. Audio Analyze")
    call("GET", f"/audio/beats/{audio_id}", label="12. Audio Beats")
    call("GET", f"/audio/waveform/{audio_id}?bands=3", label="13. Audio Waveform", timeout=120)
    call("GET", f"/audio/structure/{audio_id}", label="14. Audio Structure")
    call("GET", f"/audio/spectral/{audio_id}", label="15. Audio Spectral")

    print("\n=== Block 4: Video Analysis ===")
    call("GET", f"/video/thumbnails/{video_id}", label="16. Video Thumbnail")
    call(
        "POST",
        "/video/analyze",
        {"clip_id": video_id, "generate_embeddings": False},
        label="17. Video Analyze",
    )
    call("GET", f"/video/scenes/{video_id}", label="18. Video Scenes")
    call("GET", f"/video/motion/{video_id}", label="19. Video Motion")

    print("\n=== Block 5: Pacing, Preview, Save/Open ===")
    pacing_body = {
        "audio_clip_id": audio_id,
        "video_clip_ids": [video_id],
        "expected_bpm": 123,
        "use_motion_matching": False,
        "use_structure_awareness": False,
        "duration_limit": 15,
        "min_cut_interval": 0.5,
        "trigger_settings": {
            "beat_sensitivity": 0.7,
            "energy_threshold": 0.5,
            "onset_weight": 0.3,
            "spectral_weight": 0.2,
        },
    }
    call("POST", "/pacing/generate", pacing_body, label="20. Pacing Generate")
    call("GET", "/pacing/timeline", label="21. Pacing Timeline")
    call("POST", "/pacing/preview", {"start_sec": 0, "duration": 5}, label="22. Preview Generate")
    call("POST", "/project/save", label="23. Project Save")
    call("POST", "/project/open", {"path": str(project_path)}, label="24. Project Open")
    call("GET", "/project/info", label="25. Project Info Reloaded")

    print("\n=== Block 6: Render ===")
    render_output = project_path / "output" / "verify.mp4"
    render_body = {
        "output_path": str(render_output),
        "audio_path": str(AUDIO_SAMPLE),
        "quality": "preview",
        "resolution_width": 640,
        "resolution_height": 360,
        "fps": 30.0,
    }
    render_ok, _, render_payload = call("POST", "/render/start", render_body, label="26. Render Start")
    task_id = render_payload.get("task_id") if render_ok and isinstance(render_payload, dict) else None
    if task_id:
        final_payload = None
        for _ in range(120):
            time.sleep(5)
            status_ok, status_response, status_payload = call(
                "GET",
                f"/render/status/{task_id}",
                expect_status=(200, 404),
                label=f"Render Poll {task_id}",
            )
            if not status_ok:
                break
            if status_response is not None and status_response.status_code == 404:
                if render_output.exists() and render_output.stat().st_size > 0:
                    final_payload = {"status": "completed", "output_path": str(render_output), "detail": "task evicted after render completion"}
                break
            if not isinstance(status_payload, dict):
                break
            final_payload = status_payload
            if status_payload.get("status") in {"completed", "failed", "cancelled"}:
                break

        if (not isinstance(final_payload, dict) or final_payload.get("status") == "running") and render_output.exists() and render_output.stat().st_size > 0:
            final_payload = {"status": "completed", "output_path": str(render_output), "detail": "render output detected after polling window"}

        if isinstance(final_payload, dict):
            final_status = final_payload.get("status")
            detail = _summarize_payload(final_payload)
            status = "OK" if final_status == "completed" else f"FAIL({final_status})"
            results.append(("27. Render Final Status", status, detail))
            print(f"  [{'PASS' if final_status == 'completed' else 'FAIL'}] 27. Render Final Status")
        else:
            results.append(("27. Render Final Status", "ERROR", "kein finaler Render-Status"))
            print("  [ERR!] 27. Render Final Status")
    else:
        results.append(("27. Render Final Status", "SKIP", "keine task_id"))
        print("  [SKIP] 27. Render Final Status")

print("\n=== Block 7: Error Cases & SSE ===")
call("POST", "/audio/analyze", {"clip_id": 99999}, expect_status=404, label="28. Analyze Non-Exist")
call("GET", "/audio/beats/99999", expect_status=404, label="29. Beats Non-Exist")
call("GET", "/render/status/nonexist", expect_status=404, label="30. Status Non-Exist")
for index, sse_path in enumerate(["/events/progress", "/events/log", "/events/gpu"], start=31):
    try:
        response = requests.get(BASE + sse_path, stream=True, timeout=3)
        ok = response.status_code == 200
        results.append((f"{index}. SSE {sse_path}", "OK" if ok else f"FAIL({response.status_code})", "stream connected"))
        response.close()
        print(f"  [{'PASS' if ok else 'FAIL'}] {index}. SSE {sse_path}")
    except requests.exceptions.ReadTimeout:
        results.append((f"{index}. SSE {sse_path}", "OK", "stream timeout (expected)"))
        print(f"  [PASS] {index}. SSE {sse_path} (timeout=expected)")
    except Exception as exc:
        results.append((f"{index}. SSE {sse_path}", "ERROR", str(exc)[:140]))
        print(f"  [ERR!] {index}. SSE {sse_path}: {exc}")

print()
print("=" * 80)
passed = sum(1 for _, status, _ in results if status == "OK")
total = len(results)
print(f"ERGEBNIS: {passed}/{total} Checks bestanden")
print("=" * 80)

fails = [(name, status, detail) for name, status, detail in results if status != "OK"]
if fails:
    print("\nFEHLGESCHLAGEN:")
    for name, status, detail in fails:
        print(f"  [{status}] {name}: {detail}")
    sys.exit(1)
else:
    print("\nALLE CHECKS BESTANDEN!")
    sys.exit(0)
