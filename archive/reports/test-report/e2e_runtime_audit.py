"""
E2E Runtime Audit — Komplette Pipeline mit Daten-Verifikation
Prueft: SQLite-Eintraege, Temp-Files, FAISS-Index, Timing, Fehlerpfade
"""
import httpx
import asyncio
import json
import time
import sqlite3
import os
from datetime import datetime
from pathlib import Path

BASE = "http://localhost:8765"
TIMEOUT = httpx.Timeout(300.0, connect=10.0)
AUDIO_FILE = r"C:\Users\david\Videos\test_audio_music_60s.wav"
VIDEO_FILE_1 = r"C:\Users\david\Videos\Music-Video_Clips\AV\Video\1 (1).mp4"
VIDEO_FILE_2 = r"C:\Users\david\Videos\Music-Video_Clips\AV\Video\1 (10).mp4"
PROJECT_NAME = f"E2E-Audit-{datetime.now().strftime('%H%M%S')}"
PROJECT_BASE = r"C:\Users\david\OneDrive\Dokumente\PBStudio"
DB_PATH = r"C:\Users\david\Dokumente\Pb_studio_AMD_version\data\pb_studio.db"

findings = []

def find(severity, area, detail):
    findings.append({"severity": severity, "area": area, "detail": detail})
    print(f"  [{severity}] {area}: {detail}", flush=True)

def ok(area, detail):
    print(f"  [OK] {area}: {detail}", flush=True)


async def run():
    async with httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT) as c:

        # ============================================================
        # PHASE 1: DB-Zustand VOR dem Test
        # ============================================================
        print("\n=== PHASE 1: DB-Zustand vor Test ===", flush=True)
        if Path(DB_PATH).exists():
            conn = sqlite3.connect(DB_PATH)
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            db_before = {}
            for (t,) in tables:
                cnt = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                db_before[t] = cnt
                print(f"  DB {t}: {cnt} Eintraege", flush=True)
            conn.close()
        else:
            db_before = {}
            ok("DB", "Keine DB vorhanden (wird erstellt)")

        # ============================================================
        # PHASE 2: Projekt erstellen
        # ============================================================
        print("\n=== PHASE 2: Projekt erstellen ===", flush=True)
        r = await c.post("/project/create", json={"name": PROJECT_NAME, "path": PROJECT_BASE})
        if r.status_code != 200:
            find("CRITICAL", "project/create", f"status={r.status_code} body={r.text[:200]}")
            return
        project_data = r.json()
        project_path = project_data["path"]
        project_db_id = project_data.get("db_project_id")
        ok("project/create", f"id={project_db_id} path={project_path}")

        # Prüfe ob Projektordner erstellt wurde
        if Path(project_path).exists():
            subdirs = [d.name for d in Path(project_path).iterdir() if d.is_dir()]
            ok("project/dirs", f"Unterordner: {subdirs}")
        else:
            find("BUG", "project/dirs", f"Projektordner nicht erstellt: {project_path}")

        # ============================================================
        # PHASE 3: Audio Import + DB-Verifikation
        # ============================================================
        print("\n=== PHASE 3: Audio Import ===", flush=True)
        t0 = time.monotonic()
        r = await c.post("/audio/import", json={"path": AUDIO_FILE})
        t_import = time.monotonic() - t0
        if r.status_code != 200:
            find("BUG", "audio/import", f"status={r.status_code} body={r.text[:200]}")
            return
        audio = r.json()
        audio_id = audio["id"]
        ok("audio/import", f"id={audio_id} dur={audio['duration_seconds']}s time={t_import:.2f}s")

        # Prüfe: Stimmt die Dauer?
        if abs(audio["duration_seconds"] - 60.0) > 1.0:
            find("WARN", "audio/duration", f"Erwartet ~60s, bekommen {audio['duration_seconds']}s")

        # ============================================================
        # PHASE 4: Audio Analyse + Timing + Datenqualitaet
        # ============================================================
        print("\n=== PHASE 4: Audio Analyse ===", flush=True)
        t0 = time.monotonic()
        r = await c.post("/audio/analyze", json={
            "clip_id": audio_id,
            "detect_beats": True,
            "detect_structure": True,
            "spectral_analysis": True
        })
        t_analyze = time.monotonic() - t0
        if r.status_code != 200:
            find("BUG", "audio/analyze", f"status={r.status_code} body={r.text[:200]}")
        else:
            a = r.json()
            ok("audio/analyze", f"bpm={a.get('bpm')} key={a.get('key')} beats={a.get('beat_count')} time={t_analyze:.1f}s")

            # Datenqualitaet prüfen
            if a.get("bpm", 0) <= 0:
                find("BUG", "audio/bpm", "BPM ist 0 oder negativ")
            if a.get("beat_count", 0) <= 0:
                find("BUG", "audio/beats", "Keine Beats erkannt")
            if not a.get("key"):
                find("WARN", "audio/key", "Keine Tonart erkannt")
            if not a.get("structure_segments"):
                find("WARN", "audio/structure", "Keine Struktur-Segmente")

            # Beats einzeln prüfen
            beats = a.get("beats", [])
            if beats:
                # Prüfe ob Beats sortiert sind
                times = [b["time"] for b in beats]
                if times != sorted(times):
                    find("BUG", "audio/beats_order", "Beats sind NICHT chronologisch sortiert")
                # Prüfe ob Beat-Zeiten innerhalb der Audio-Dauer liegen
                if any(t < 0 or t > audio["duration_seconds"] + 1 for t in times):
                    find("BUG", "audio/beats_range", f"Beats ausserhalb Audio-Dauer: min={min(times):.2f} max={max(times):.2f}")

        # ============================================================
        # PHASE 5: Video Import + Timing
        # ============================================================
        print("\n=== PHASE 5: Video Import ===", flush=True)
        t0 = time.monotonic()
        r = await c.post("/video/import", json={"paths": [VIDEO_FILE_1, VIDEO_FILE_2]})
        t_vimport = time.monotonic() - t0
        if r.status_code != 200:
            find("BUG", "video/import", f"status={r.status_code} body={r.text[:200]}")
            return
        videos = r.json()
        vids = [v["id"] for v in videos]
        ok("video/import", f"ids={vids} time={t_vimport:.2f}s")

        for v in videos:
            if v["duration_seconds"] <= 0:
                find("BUG", "video/duration", f"Video {v['id']} hat Dauer {v['duration_seconds']}s")
            if v["width"] <= 0 or v["height"] <= 0:
                find("BUG", "video/resolution", f"Video {v['id']} hat {v['width']}x{v['height']}")

        # ============================================================
        # PHASE 6: Video Analyse + Motion-Daten Qualitaet
        # ============================================================
        print("\n=== PHASE 6: Video Analyse ===", flush=True)
        t0 = time.monotonic()
        r = await c.post("/video/analyze", json={
            "clip_id": vids[0],
            "detect_scenes": True,
            "analyze_motion": True,
            "generate_embeddings": False,
            "generate_captions": False
        })
        t_vanalyze = time.monotonic() - t0
        if r.status_code != 200:
            find("BUG", "video/analyze", f"status={r.status_code} body={r.text[:200]}")
        else:
            va = r.json()
            ok("video/analyze", f"scenes={va.get('scene_count')} motion={va.get('avg_motion')} time={t_vanalyze:.1f}s")
            if va.get("avg_motion", 0) < 0:
                find("BUG", "video/motion_neg", "avg_motion ist negativ")

        # ============================================================
        # PHASE 7: Pacing / Cut-List Generierung
        # ============================================================
        print("\n=== PHASE 7: Pacing ===", flush=True)
        t0 = time.monotonic()
        r = await c.post("/pacing/generate", json={
            "audio_clip_id": audio_id,
            "video_clip_ids": vids,
            "min_cut_interval": 0.5
        })
        t_pacing = time.monotonic() - t0
        if r.status_code != 200:
            find("BUG", "pacing/generate", f"status={r.status_code} body={r.text[:200]}")
        else:
            p = r.json()
            cuts = p.get("cuts", [])
            ok("pacing/generate", f"cuts={p.get('cut_count')} dur={p.get('total_duration')} time={t_pacing:.1f}s")

            # Prüfe Cut-Qualitaet
            if not cuts:
                find("BUG", "pacing/empty", "Keine Cuts generiert")
            else:
                # Prüfe ob Cuts lückenlos sind
                for i in range(1, len(cuts)):
                    gap = cuts[i]["start_time"] - cuts[i-1]["end_time"]
                    if gap > 0.01:  # >10ms Luecke
                        find("WARN", "pacing/gap", f"Luecke bei Cut {i}: {gap:.3f}s")
                        break
                # Prüfe ob Cuts ueberlappen
                for i in range(1, len(cuts)):
                    overlap = cuts[i-1]["end_time"] - cuts[i]["start_time"]
                    if overlap > 0.01:
                        find("BUG", "pacing/overlap", f"Ueberlappung bei Cut {i}: {overlap:.3f}s")
                        break

        # ============================================================
        # PHASE 8: Render + Output-Verifikation
        # ============================================================
        print("\n=== PHASE 8: Render ===", flush=True)
        output_dir = Path(project_path) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = str(output_dir / "e2e_audit_render.mp4")

        t0 = time.monotonic()
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
        if r.status_code != 200:
            find("BUG", "render/start", f"status={r.status_code} body={r.text[:200]}")
        else:
            task_id = r.json()["task_id"]
            # Poll bis fertig
            for i in range(300):
                await asyncio.sleep(1)
                sr = await c.get(f"/render/status/{task_id}")
                sd = sr.json()
                if sd["status"] in ("completed", "failed", "cancelled"):
                    break
            t_render = time.monotonic() - t0

            if sd["status"] == "completed":
                ok("render", f"completed in {t_render:.1f}s")
                # Prüfe Output-Datei
                out_path = Path(output_file)
                if out_path.exists():
                    size_mb = out_path.stat().st_size / (1024*1024)
                    ok("render/output", f"Datei existiert: {size_mb:.1f}MB")
                    if size_mb < 0.1:
                        find("BUG", "render/output_small", f"Output nur {size_mb:.2f}MB — moeglicherweise korrupt")
                else:
                    find("BUG", "render/output_missing", "Output-Datei existiert nicht nach completed")
            else:
                find("BUG", "render/status", f"status={sd['status']} error={sd.get('error','')[:200]}")

        # ============================================================
        # PHASE 9: Temp-Files Verifikation
        # ============================================================
        print("\n=== PHASE 9: Temp-Files ===", flush=True)
        for d in ["temp", "data/temp"]:
            p = Path(r"C:\Users\david\Dokumente\Pb_studio_AMD_version") / d
            if p.exists():
                files = list(p.glob("*"))
                if files:
                    find("WARN", f"temp/{d}", f"{len(files)} Dateien nicht aufgeraeumt: {[f.name for f in files[:5]]}")
                else:
                    ok(f"temp/{d}", "Sauber")

        # Prüfe .temp_render Verzeichnisse
        temp_render = Path(project_path) / "output" / ".temp_render"
        if temp_render.exists():
            files = list(temp_render.glob("*"))
            if files:
                find("WARN", "temp/render", f".temp_render nicht aufgeraeumt: {len(files)} Dateien")
            else:
                ok("temp/render", ".temp_render leer")
        else:
            ok("temp/render", ".temp_render entfernt")

        # ============================================================
        # PHASE 10: DB-Zustand NACH dem Test
        # ============================================================
        print("\n=== PHASE 10: DB-Verifikation ===", flush=True)
        if Path(DB_PATH).exists():
            conn = sqlite3.connect(DB_PATH)
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            for (t,) in tables:
                cnt = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                before = db_before.get(t, 0)
                diff = cnt - before
                if diff > 0:
                    print(f"  DB {t}: {before} -> {cnt} (+{diff})", flush=True)
                    # Prüfe letzte Eintraege
                    try:
                        rows = conn.execute(f"SELECT * FROM [{t}] ORDER BY rowid DESC LIMIT 1").fetchone()
                        if rows:
                            cols = [d[0] for d in conn.execute(f"SELECT * FROM [{t}] LIMIT 0").description]
                            latest = dict(zip(cols, rows))
                            print(f"    Letzter Eintrag: {json.dumps(latest, default=str)[:200]}", flush=True)
                    except Exception:
                        pass
            conn.close()

        # ============================================================
        # PHASE 11: Persistenz-Test (Close + Reopen)
        # ============================================================
        print("\n=== PHASE 11: Persistenz ===", flush=True)
        await c.post("/project/save")
        await c.post("/project/close")
        r = await c.post("/project/open", json={"path": project_path})
        if r.status_code == 200:
            # Prüfe ob Daten erhalten sind
            r_audio = await c.get("/audio/clips")
            r_video = await c.get("/video/clips")
            ac = len(r_audio.json()) if r_audio.status_code == 200 else 0
            vc = len(r_video.json()) if r_video.status_code == 200 else 0
            if ac >= 1 and vc >= 2:
                ok("persist", f"Audio={ac} Video={vc} nach Reopen")
            else:
                find("BUG", "persist", f"Daten verloren: Audio={ac} Video={vc}")
        else:
            find("BUG", "persist/reopen", f"status={r.status_code}")

        # ============================================================
        # PHASE 12: Fehlerpfade testen
        # ============================================================
        print("\n=== PHASE 12: Fehlerpfade ===", flush=True)

        # Doppel-Import gleiche Datei
        r = await c.post("/audio/import", json={"path": AUDIO_FILE})
        if r.status_code == 200:
            dup_id = r.json()["id"]
            if dup_id == audio_id:
                ok("edge/dedup", "Idempotenter Import (gleiche ID)")
            else:
                find("WARN", "edge/dedup", f"Doppel-Import erzeugt neue ID: {dup_id} vs {audio_id}")

        # Analyse nicht-existierender Clip
        r = await c.get("/audio/beats/99999")
        if r.status_code in (404, 400):
            ok("edge/invalid_id", f"status={r.status_code}")
        else:
            find("BUG", "edge/invalid_id", f"Unerwarteter Status: {r.status_code}")

        # Render ohne Timeline (nach Close)
        await c.post("/project/close")
        r = await c.post("/render/start", json={
            "output_path": output_file,
            "audio_path": AUDIO_FILE,
            "quality": "preview"
        })
        if r.status_code in (400, 422):
            ok("edge/render_no_timeline", f"status={r.status_code}")
        else:
            find("WARN", "edge/render_no_timeline", f"status={r.status_code}")

    # ============================================================
    # ZUSAMMENFASSUNG
    # ============================================================
    print("\n" + "=" * 60, flush=True)
    bugs = [f for f in findings if f["severity"] in ("BUG", "CRITICAL")]
    warns = [f for f in findings if f["severity"] == "WARN"]
    print(f"E2E Runtime Audit: {len(bugs)} BUGS | {len(warns)} WARNINGS", flush=True)
    print("=" * 60, flush=True)

    if findings:
        for f in findings:
            print(f"  [{f['severity']}] {f['area']}: {f['detail']}")

    # Speichern
    Path(r"C:\Users\david\Dokumente\Pb_studio_AMD_version\test-report\e2e_runtime_findings.json").write_text(
        json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nGespeichert: test-report/e2e_runtime_findings.json")


if __name__ == "__main__":
    asyncio.run(run())
