"""
PB Studio Auto-QA Loop -- Vollstaendiger API-Test
Datum: 2026-03-29
Testdaten: Echte Audio/Video-Dateien
Korrekte API-Schemas basierend auf Pydantic-Modellen
"""
import httpx
import asyncio
import json
import time
import os
from datetime import datetime
from pathlib import Path

BASE = "http://localhost:8765"
TIMEOUT = httpx.Timeout(120.0, connect=10.0)

# Echte Testdaten
AUDIO_FILE = r"C:\Users\david\Videos\test_audio_music_60s.wav"
VIDEO_DIR = Path(r"C:\Users\david\Videos\Music-Video_Clips\AV\Video")
VIDEO_FILE_1 = str(VIDEO_DIR / "1 (1).mp4")
VIDEO_FILE_2 = str(VIDEO_DIR / "1 (10).mp4")

PROJECT_NAME = f"AutoQA-{datetime.now().strftime('%H%M%S')}"
PROJECT_BASE = r"C:\Users\david\OneDrive\Dokumente\PBStudio"

results = {}
bugs = []
state = {
    "timestamp": datetime.now().isoformat(),
    "backend_status": "running",
    "project_path": None,
    "audio_id": None,
    "video_ids": [],
}


def record(name, passed, details):
    results[name] = {"passed": passed, "details": details}
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}: {details}", flush=True)
    if not passed:
        bugs.append({"test": name, "details": details})


async def run_all():
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:

        # ============================================================
        # BEREICH 1: HEALTH & SYSTEM
        # ============================================================
        print("\n=== BEREICH 1: Health & System ===", flush=True)

        r = await c.get("/health")
        record("health/check", r.status_code == 200 and r.json().get("status") == "ok",
               f"status={r.status_code} gpu={r.json().get('gpu_available')}")

        r = await c.get("/gpu/status")
        d = r.json()
        record("health/gpu_status", r.status_code == 200,
               f"status={r.status_code} gpu={d.get('name','?')} vram={d.get('vram_used_mb','?')}/{d.get('vram_total_mb','?')}MB")

        r = await c.post("/gpu/cleanup")
        record("health/gpu_cleanup", r.status_code == 200,
               f"status={r.status_code}")

        # ============================================================
        # BEREICH 2: PROJEKT-MANAGEMENT
        # ============================================================
        print("\n=== BEREICH 2: Projekt-Management ===", flush=True)

        # Create project - needs name AND path
        r = await c.post("/project/create", json={
            "name": PROJECT_NAME,
            "path": PROJECT_BASE
        })
        create_ok = r.status_code == 200
        record("project/create", create_ok,
               f"status={r.status_code} body={r.text[:200]}")
        if create_ok:
            pdata = r.json()
            state["project_path"] = pdata.get("path", "")

        # Project info
        r = await c.get("/project/info")
        record("project/info", r.status_code == 200,
               f"status={r.status_code} body={r.text[:200]}")

        # Save
        r = await c.post("/project/save")
        record("project/save", r.status_code == 200,
               f"status={r.status_code}")

        # Close
        r = await c.post("/project/close")
        record("project/close", r.status_code == 200,
               f"status={r.status_code}")

        # Open - needs path field
        r = await c.post("/project/open", json={"path": state["project_path"]})
        record("project/open", r.status_code == 200,
               f"status={r.status_code} body={r.text[:200]}")

        # ============================================================
        # BEREICH 3: AUDIO-IMPORT & BIBLIOTHEK
        # ============================================================
        print("\n=== BEREICH 3: Audio-Import & Bibliothek ===", flush=True)

        # Audio import - field is "path" not "file_path"
        r = await c.post("/audio/import", json={"path": AUDIO_FILE})
        import_ok = r.status_code == 200
        record("audio/import", import_ok,
               f"status={r.status_code} body={r.text[:200]}")
        if import_ok:
            adata = r.json()
            state["audio_id"] = adata.get("id", 1)

        # List audio clips
        r = await c.get("/audio/clips")
        record("audio/list_clips", r.status_code == 200,
               f"status={r.status_code} body={r.text[:200]}")

        # ============================================================
        # BEREICH 4: AUDIO-ANALYSE
        # ============================================================
        print("\n=== BEREICH 4: Audio-Analyse ===", flush=True)

        clip_id = state["audio_id"] or 1
        r = await c.post("/audio/analyze", json={
            "clip_id": clip_id,
            "detect_beats": True,
            "detect_structure": True,
            "spectral_analysis": True
        })
        if r.status_code == 200:
            ad = r.json()
            record("audio/analyze", True,
                   f"bpm={ad.get('bpm')} key={ad.get('key')} beats={ad.get('beat_count')} struct_segs={len(ad.get('structure_segments',[]))}")
        else:
            record("audio/analyze", False,
                   f"status={r.status_code} body={r.text[:200]}")

        # Beats
        r = await c.get(f"/audio/beats/{clip_id}")
        if r.status_code == 200:
            bd = r.json()
            cnt = len(bd) if isinstance(bd, list) else bd.get("count", "?")
            record("audio/beats", True, f"count={cnt}")
        else:
            record("audio/beats", False, f"status={r.status_code} body={r.text[:150]}")

        # Waveform
        r = await c.get(f"/audio/waveform/{clip_id}", params={"bands": 3})
        record("audio/waveform", r.status_code == 200,
               f"status={r.status_code} len={len(r.text)}")

        # Structure
        r = await c.get(f"/audio/structure/{clip_id}")
        if r.status_code == 200:
            sd = r.json()
            cnt = len(sd) if isinstance(sd, list) else sd.get("total_segments", "?")
            record("audio/structure", True, f"segments={cnt}")
        else:
            record("audio/structure", False, f"status={r.status_code} body={r.text[:150]}")

        # Spectral
        r = await c.get(f"/audio/spectral/{clip_id}")
        record("audio/spectral", r.status_code == 200,
               f"status={r.status_code} len={len(r.text)}")

        # ============================================================
        # BEREICH 5: VIDEO-IMPORT & BIBLIOTHEK
        # ============================================================
        print("\n=== BEREICH 5: Video-Import & Bibliothek ===", flush=True)

        # Video import - field is "paths" (list)
        r = await c.post("/video/import", json={"paths": [VIDEO_FILE_1, VIDEO_FILE_2]})
        vimport_ok = r.status_code == 200
        record("video/import", vimport_ok,
               f"status={r.status_code} body={r.text[:200]}")
        if vimport_ok:
            vdata = r.json()
            if isinstance(vdata, list):
                state["video_ids"] = [v.get("id", i+1) for i, v in enumerate(vdata)]
            elif "clips" in vdata:
                state["video_ids"] = [v.get("id", i+1) for i, v in enumerate(vdata["clips"])]

        # List video clips
        r = await c.get("/video/clips")
        record("video/list_clips", r.status_code == 200,
               f"status={r.status_code} body={r.text[:200]}")

        # ============================================================
        # BEREICH 6: VIDEO-ANALYSE
        # ============================================================
        print("\n=== BEREICH 6: Video-Analyse ===", flush=True)

        vid_id = state["video_ids"][0] if state["video_ids"] else 1

        # Analyze video
        r = await c.post("/video/analyze", json={
            "clip_id": vid_id,
            "detect_scenes": True,
            "analyze_motion": True,
            "generate_embeddings": False,
            "generate_captions": False
        })
        if r.status_code == 200:
            vad = r.json()
            record("video/analyze", True,
                   f"scenes={vad.get('scene_count',0)} motion={vad.get('avg_motion','?')}")
        else:
            record("video/analyze", False, f"status={r.status_code} body={r.text[:200]}")

        # Thumbnail
        r = await c.get(f"/video/thumbnails/{vid_id}")
        record("video/thumbnail", r.status_code == 200,
               f"status={r.status_code} size={len(r.content)}bytes")

        # Scenes
        r = await c.get(f"/video/scenes/{vid_id}")
        record("video/scenes", r.status_code == 200,
               f"status={r.status_code} body={r.text[:150]}")

        # Motion
        r = await c.get(f"/video/motion/{vid_id}")
        record("video/motion", r.status_code == 200,
               f"status={r.status_code} body={r.text[:150]}")

        # ============================================================
        # BEREICH 7: PACING & DIRECTOR
        # ============================================================
        print("\n=== BEREICH 7: Pacing & Director ===", flush=True)

        # Generate cut list - needs audio_clip_id and video_clip_ids
        r = await c.post("/pacing/generate", json={
            "audio_clip_id": clip_id,
            "video_clip_ids": state["video_ids"],
            "min_cut_interval": 0.5
        })
        if r.status_code == 200:
            pd = r.json()
            record("pacing/generate", True,
                   f"cuts={pd.get('cut_count',len(pd.get('cuts',[])))} duration={pd.get('total_duration','?')}")
        else:
            record("pacing/generate", False, f"status={r.status_code} body={r.text[:200]}")

        # Timeline
        r = await c.get("/pacing/timeline")
        if r.status_code == 200:
            td = r.json()
            entries = td.get("entries", td.get("timeline", []))
            cnt = len(entries) if isinstance(entries, list) else entries
            record("pacing/timeline", True, f"entries={cnt}")
        else:
            record("pacing/timeline", False, f"status={r.status_code} body={r.text[:200]}")

        # ============================================================
        # BEREICH 8: RENDERING
        # ============================================================
        print("\n=== BEREICH 8: Rendering ===", flush=True)

        # Render needs output_path and audio_path
        output_dir = Path(state["project_path"]) / "output" if state["project_path"] else Path(PROJECT_BASE) / PROJECT_NAME / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = str(output_dir / "qa_render_test.mp4")

        r = await c.post("/render/start", json={
            "output_path": output_file,
            "audio_path": AUDIO_FILE,
            "quality": "preview",
            "encoder": "h264_amf",
            "resolution_width": 640,
            "resolution_height": 360,
            "fps": 30.0,
            "bitrate_mbps": 4.0,
            "include_audio": True
        })
        if r.status_code == 200:
            rd = r.json()
            task_id = rd.get("task_id", "unknown")
            record("render/start", True, f"task_id={task_id}")

            # Poll status
            final_status = "unknown"
            percent = 0
            for _ in range(180):  # max 3 min
                await asyncio.sleep(1)
                sr = await c.get(f"/render/status/{task_id}")
                if sr.status_code == 200:
                    sd = sr.json()
                    final_status = sd.get("status", "unknown")
                    percent = sd.get("percent", 0)
                    if final_status in ("completed", "failed", "cancelled"):
                        break

            record("render/status", final_status == "completed",
                   f"final_status={final_status} percent={percent}%")

            # Render cancel (test with already completed task)
            r = await c.post(f"/render/cancel/{task_id}")
            # Should be 200 or 400 (already completed) - both acceptable
            record("render/cancel", r.status_code in (200, 400),
                   f"status={r.status_code} body={r.text[:100]}")
        else:
            record("render/start", False, f"status={r.status_code} body={r.text[:200]}")
            record("render/status", False, "skipped")
            record("render/cancel", False, "skipped")

        # ============================================================
        # BEREICH 9: SSE EVENTS
        # ============================================================
        print("\n=== BEREICH 9: SSE Events ===", flush=True)

        # GPU SSE
        try:
            async with c.stream("GET", "/events/gpu") as resp:
                chunk = b""
                async for data in resp.aiter_bytes():
                    chunk += data
                    if len(chunk) > 50:
                        break
            record("sse/gpu_stream", len(chunk) > 0, f"received {len(chunk)} bytes")
        except Exception as e:
            record("sse/gpu_stream", False, f"error: {e}")

        # Progress SSE
        try:
            async with c.stream("GET", "/events/progress") as resp:
                record("sse/progress", resp.status_code == 200, f"status={resp.status_code}")
        except Exception as e:
            record("sse/progress", False, f"error: {e}")

        # Log SSE
        try:
            async with c.stream("GET", "/events/log") as resp:
                record("sse/log", resp.status_code == 200, f"status={resp.status_code}")
        except Exception as e:
            record("sse/log", False, f"error: {e}")

        # ============================================================
        # BEREICH 10: PERSISTENZ
        # ============================================================
        print("\n=== BEREICH 10: Persistenz ===", flush=True)

        r = await c.post("/project/close")
        record("persist/close", r.status_code == 200, f"status={r.status_code}")

        r = await c.post("/project/open", json={"path": state["project_path"]})
        record("persist/reopen", r.status_code == 200,
               f"status={r.status_code}")

        r = await c.get("/audio/clips")
        if r.status_code == 200:
            clips = r.json()
            cnt = len(clips) if isinstance(clips, list) else clips.get("total", 0)
            record("persist/audio_clips", cnt > 0, f"count={cnt}")
        else:
            record("persist/audio_clips", False, f"status={r.status_code}")

        r = await c.get("/video/clips")
        if r.status_code == 200:
            clips = r.json()
            cnt = len(clips) if isinstance(clips, list) else clips.get("total", 0)
            record("persist/video_clips", cnt > 0, f"count={cnt}")
        else:
            record("persist/video_clips", False, f"status={r.status_code}")

        # ============================================================
        # BEREICH 11: EDGE CASES
        # ============================================================
        print("\n=== BEREICH 11: Edge Cases ===", flush=True)

        r = await c.get("/audio/beats/99999")
        record("edge/invalid_clip_id", r.status_code in (404, 400, 422),
               f"status={r.status_code}")

        r = await c.post("/audio/import", json={"path": r"..\..\..\..\Windows\System32\config\sam"})
        record("edge/path_traversal", r.status_code in (400, 403, 422),
               f"status={r.status_code}")

        r = await c.post("/project/create", json={})
        record("edge/empty_body", r.status_code in (400, 422),
               f"status={r.status_code}")

        r = await c.post("/audio/import", json={"path": r"C:\nonexistent\fake.wav"})
        record("edge/nonexistent_file", r.status_code in (400, 404, 422),
               f"status={r.status_code}")

    # ============================================================
    # ZUSAMMENFASSUNG
    # ============================================================
    print("\n" + "=" * 60, flush=True)
    passed = sum(1 for v in results.values() if v["passed"])
    failed = sum(1 for v in results.values() if not v["passed"])
    total = len(results)
    print(f"ERGEBNIS: {passed}/{total} PASS | {failed} FAIL", flush=True)
    print("=" * 60, flush=True)

    if bugs:
        print(f"\nBUGS ({len(bugs)}):")
        for b in bugs:
            print(f"  - {b['test']}: {b['details']}")

    # State speichern
    state["results"] = results
    state["bugs"] = bugs
    state["summary"] = {"total": total, "passed": passed, "failed": failed}
    state["final_status"] = f"COMPLETE - {passed}/{total} PASS"

    report_path = Path(r"C:\Users\david\Dokumente\Pb_studio_AMD_version\test-report\state.json")
    report_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nState gespeichert: {report_path}")


if __name__ == "__main__":
    asyncio.run(run_all())
