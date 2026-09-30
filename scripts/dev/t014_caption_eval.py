"""T014: live caption sample via the production LM Studio vision path.

Read-only against the project DB. Writes frames, a contact sheet per clip and
results.json into a run folder so a human can judge every tag list.

Usage (PYTHONPATH=src):
    python scripts/dev/t014_caption_eval.py --project-id 10 --clips 12 --out <dir>
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from pb_studio.video.lmstudio_vision_wrapper import extract_tags_and_model_via_lmstudio


def loaded_models() -> list[dict]:
    with urllib.request.urlopen("http://127.0.0.1:1234/api/v0/models", timeout=10) as r:
        data = json.load(r)["data"]
    return [{"id": m["id"], "state": m.get("state"), "type": m.get("type")}
            for m in data if m.get("state") == "loaded"]


def grab(path: str, fractions=(0.2, 0.5, 0.8)) -> list[np.ndarray]:
    cap = cv2.VideoCapture(path)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    out = []
    for f in fractions:
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(n * f)))
        ok, bgr = cap.read()
        if ok:
            out.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    cap.release()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/pb_studio.db")
    ap.add_argument("--project-id", type=int, required=True)
    ap.add_argument("--clips", type=int, default=12)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)

    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    rows = con.execute(
        "select id, file_path, ai_data_json from media where project_id=? "
        "and file_path like '%.mp4' order by id", (a.project_id,)).fetchall()
    step = max(1, len(rows) // a.clips)
    sample = rows[::step][: a.clips]

    before = loaded_models()
    results = []
    for mid, path, ai in sample:
        frames = grab(path)
        stored = json.loads(ai or "{}")
        frame_results = []
        for i, fr in enumerate(frames):
            t0 = time.perf_counter()
            tags, model = extract_tags_and_model_via_lmstudio(fr)
            frame_results.append({"frame": i, "tags": tags, "model": model,
                                  "seconds": round(time.perf_counter() - t0, 2)})
        h = 240
        thumbs = [cv2.resize(f, (int(f.shape[1] * h / f.shape[0]), h)) for f in frames]
        if thumbs:
            sheet = np.hstack(thumbs)
            cv2.imwrite(str(out / f"clip_{mid}.jpg"), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
        results.append({"media_id": mid, "file": Path(path).name,
                        "stored_tags": stored.get("tags"),
                        "stored_tag_source": stored.get("tag_source"),
                        "live": frame_results})
        print(mid, Path(path).name, [fr["tags"] for fr in frame_results], flush=True)

    receipt = {"loaded_before": before, "loaded_after": loaded_models(),
               "project_id": a.project_id, "results": results}
    (out / "results.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2),
                                      encoding="utf-8")


if __name__ == "__main__":
    main()
