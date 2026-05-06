"""
PB Studio Auto-QA: Stem-Separation + Pacing Preview
Datum: 2026-03-29
"""
import httpx
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

BASE = "http://localhost:8765"
TIMEOUT = httpx.Timeout(600.0, connect=10.0)  # 10min fuer Stem-Separation

AUDIO_FILE = r"C:\Users\david\Videos\test_audio_music_60s.wav"
VIDEO_FILE_1 = r"C:\Users\david\Videos\Music-Video_Clips\AV\Video\1 (1).mp4"
VIDEO_FILE_2 = r"C:\Users\david\Videos\Music-Video_Clips\AV\Video\1 (10).mp4"

PROJECT_NAME = f"AutoQA-Stem-{datetime.now().strftime('%H%M%S')}"
PROJECT_BASE = r"C:\Users\david\OneDrive\Dokumente\PBStudio"

results = {}
bugs = []


def record(name, passed, details):
    results[name] = {"passed": passed, "details": details}
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}: {details}", flush=True)
    if not passed:
        bugs.append({"test": name, "details": details})


async def run_all():
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:

        # === SETUP: Projekt + Audio + Video + Analyse + Pacing ===
        print("=== SETUP ===", flush=True)

        r = await c.post("/project/create", json={"name": PROJECT_NAME, "path": PROJECT_BASE})
        project_path = r.json().get("path", "")
        print(f"  Projekt: {r.status_code} path={project_path}", flush=True)

        r = await c.post("/audio/import", json={"path": AUDIO_FILE})
        aid = r.json()["id"]
        print(f"  Audio: id={aid}", flush=True)

        r = await c.post("/video/import", json={"paths": [VIDEO_FILE_1, VIDEO_FILE_2]})
        vids = [v["id"] for v in r.json()]
        print(f"  Video: ids={vids}", flush=True)

        r = await c.post("/audio/analyze", json={"clip_id": aid})
        ad = r.json()
        print(f"  Analyse: bpm={ad.get('bpm')} key={ad.get('key')}", flush=True)

        r = await c.post("/pacing/generate", json={
            "audio_clip_id": aid, "video_clip_ids": vids, "min_cut_interval": 0.5
        })
        pd = r.json()
        print(f"  Pacing: cuts={pd.get('cut_count')} duration={pd.get('total_duration')}", flush=True)

        # ============================================================
        # TEST 1: STEM-SEPARATION (GPU, lange Laufzeit)
        # ============================================================
        print("\n=== TEST: Stem-Separation ===", flush=True)
        print("  (kann mehrere Minuten dauern - DirectML GPU)", flush=True)

        start_time = time.monotonic()
        r = await c.post("/audio/stems/separate", json={
            "clip_id": aid,
            "model": "UVR-MDX-NET-Inst_HQ_3.onnx"
        })
        elapsed = time.monotonic() - start_time

        if r.status_code == 200:
            sd = r.json()
            vocals = sd.get("vocals_path")
            instrumental = sd.get("instrumental_path")
            model_used = sd.get("model_used", "")

            # Pruefen ob Pfade existieren
            vocals_exists = vocals and Path(vocals).exists()
            inst_exists = instrumental and Path(instrumental).exists()

            vocals_size = Path(vocals).stat().st_size if vocals_exists else 0
            inst_size = Path(instrumental).stat().st_size if inst_exists else 0

            all_ok = vocals_exists and inst_exists and vocals_size > 1000 and inst_size > 1000

            record("stem/separate", all_ok,
                   f"elapsed={elapsed:.1f}s vocals={vocals_size}B inst={inst_size}B model={model_used}")

            if vocals_exists:
                record("stem/vocals_file", True, f"size={vocals_size}B path={vocals}")
            else:
                record("stem/vocals_file", False, f"vocals_path={vocals} exists={vocals_exists}")

            if inst_exists:
                record("stem/instrumental_file", True, f"size={inst_size}B path={instrumental}")
            else:
                record("stem/instrumental_file", False, f"inst_path={instrumental} exists={inst_exists}")

        else:
            record("stem/separate", False, f"status={r.status_code} elapsed={elapsed:.1f}s body={r.text[:300]}")
            record("stem/vocals_file", False, "skipped")
            record("stem/instrumental_file", False, "skipped")

        # ============================================================
        # TEST 2: PACING PREVIEW
        # ============================================================
        print("\n=== TEST: Pacing Preview ===", flush=True)

        # Test mit Standard-Parametern (erste 10 Sekunden)
        r = await c.post("/pacing/preview", json={
            "start_sec": 0.0,
            "duration": 10.0
        })

        if r.status_code == 200:
            pvd = r.json()
            preview_path = pvd.get("preview_path", "")
            preview_dur = pvd.get("duration", 0)
            preview_res = pvd.get("resolution", "")

            preview_exists = preview_path and Path(preview_path).exists()
            preview_size = Path(preview_path).stat().st_size if preview_exists else 0

            record("preview/generate", preview_exists and preview_size > 1000,
                   f"path={preview_path} size={preview_size}B duration={preview_dur} res={preview_res}")
        else:
            record("preview/generate", False,
                   f"status={r.status_code} body={r.text[:300]}")

        # Test Preview mit Offset (Mitte des Tracks)
        r = await c.post("/pacing/preview", json={
            "start_sec": 30.0,
            "duration": 5.0
        })
        if r.status_code == 200:
            pvd = r.json()
            pp = pvd.get("preview_path", "")
            pe = pp and Path(pp).exists()
            record("preview/offset", pe,
                   f"start=30s dur=5s exists={pe} size={Path(pp).stat().st_size if pe else 0}B")
        else:
            record("preview/offset", False, f"status={r.status_code} body={r.text[:300]}")

        # Test Preview ohne Timeline (nach Close)
        await c.post("/project/close")
        r2 = await c.post("/pacing/preview", json={"start_sec": 0.0, "duration": 5.0})
        record("preview/no_timeline", r2.status_code == 400,
               f"status={r2.status_code} (erwartet 400)")

    # === ZUSAMMENFASSUNG ===
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
    state = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "bugs": bugs,
        "summary": {"total": total, "passed": passed, "failed": failed},
    }
    report_path = Path(r"C:\Users\david\Dokumente\Pb_studio_AMD_version\test-report\stem_preview_state.json")
    report_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nState: {report_path}")


if __name__ == "__main__":
    asyncio.run(run_all())
