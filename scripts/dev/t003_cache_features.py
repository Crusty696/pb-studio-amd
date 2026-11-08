"""T003: cache per-track features for key/beat experiments (read-only on user data).

Sets: ``test`` = exactly the 40 tracks of ``t003_rekordbox_reference_eval.py``
(same selection rule), ``tune`` = 120 disjoint tracks used to choose parameters.
Per track: production chroma mean, pooled chroma/CQT (plain + harmonic), the
60-180 s excerpt as int16, and the production beat grid of that excerpt.

Usage (PYTHONPATH=src):
    python scripts/dev/t003_cache_features.py OUT_DIR [WORKERS] [XML] [REMAP_FROM=REMAP_TO]
Keep WORKERS <= 3 on a 48-GB machine (8 workers exhausted the commit limit).
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t003_rekordbox_reference_eval import camelot_to_key, to_path  # noqa: E402

XML = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(r"F:\pioneer_xml\rekordbox.xml")
REMAP = tuple(sys.argv[4].split("=", 1)) if len(sys.argv) > 4 else ("D:/", "F:/")
OUT = Path(sys.argv[1])
SR = 22050


def work(item: dict) -> dict:
    import librosa
    from pb_studio.audio.beat_grid import estimate_beat_grid

    dst = OUT / f"{item['set']}_{item['idx']:03d}.npz"
    if dst.exists():
        return {"ok": True, "cached": True, **item}
    t0 = time.perf_counter()
    y, sr = librosa.load(item["path"], sr=SR, mono=True)
    fps = int(round(SR / 512))

    def pool(m):
        n = m.shape[1] // fps
        return m[:, : n * fps].reshape(m.shape[0], n, fps).mean(axis=2).astype(np.float32)

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=512)
    prod_mean = chroma.mean(axis=1)
    cqt = np.abs(librosa.cqt(y, sr=sr, hop_length=512, n_bins=84, bins_per_octave=12))
    yh = librosa.effects.harmonic(y, margin=2.0)
    cqt_h = np.abs(librosa.cqt(yh, sr=sr, hop_length=512, n_bins=84, bins_per_octave=12))
    chroma_h = librosa.feature.chroma_cqt(C=cqt_h, sr=sr, hop_length=512)
    start, end = 60.0, min(180.0, len(y) / sr)
    seg = y[int(start * sr): int(end * sr)]
    grid = estimate_beat_grid(seg, sr)
    np.savez_compressed(
        dst,
        prod_mean=prod_mean.astype(np.float32),
        chroma_pool=pool(chroma), chroma_h_pool=pool(chroma_h),
        cqt_pool=pool(cqt ** 2), cqt_h_pool=pool(cqt_h ** 2),
        excerpt=(np.clip(seg, -1, 1) * 32767).astype(np.int16),
        grid=np.array([grid.bpm, grid.anchor_s + start, grid.contrast], dtype=np.float64),
        meta=json.dumps({**item, "grid_status": grid.status, "grid_method": grid.method,
                         "duration": len(y) / sr}),
    )
    return {"ok": True, "seconds": round(time.perf_counter() - t0, 1), **item}


def main() -> None:
    import xml.etree.ElementTree as ET

    OUT.mkdir(parents=True, exist_ok=True)
    root = ET.parse(XML).getroot()
    tracks = root.find("COLLECTION").findall("TRACK")
    cands = [t for t in tracks if to_path(t.get("Location"), REMAP).is_file()
             and camelot_to_key(t.get("Tonality") or "") and t.find("TEMPO") is not None]
    step = max(1, len(cands) // 40)
    test = cands[::step][:40]
    test_ids = {t.get("TrackID") for t in test}
    rest = [t for t in cands if t.get("TrackID") not in test_ids]
    tstep = max(1, len(rest) // 120)
    tune = rest[tstep // 2::tstep][:120]
    items = []
    for name, group in (("test", test), ("tune", tune)):
        for i, t in enumerate(group):
            tempo = t.findall("TEMPO")
            items.append({"set": name, "idx": i, "track_id": t.get("TrackID"),
                          "path": str(to_path(t.get("Location"), REMAP)),
                          "tonality": t.get("Tonality"), "rb_bpm": float(tempo[0].get("Bpm")),
                          "rb_anchor": float(tempo[0].get("Inizio")), "rb_tempo_changes": len(tempo),
                          "genre": t.get("Genre")})
    (OUT / "items.json").write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    # playlist inventory for extra reference mixes
    pls = []
    for node in root.iter("NODE"):
        if node.get("Type") == "1":
            n = sum(1 for k in node.findall("TRACK"))
            pls.append((node.get("Name"), n))
    (OUT / "playlists.json").write_text(json.dumps(pls, ensure_ascii=False), encoding="utf-8")
    print(f"{len(items)} items; {len(cands)} candidates", flush=True)
    done = 0
    with ProcessPoolExecutor(max_workers=int(sys.argv[2]) if len(sys.argv) > 2 else 6) as ex:
        futs = {ex.submit(work, it): it for it in items}
        for f in as_completed(futs):
            done += 1
            try:
                r = f.result()
                print(done, r["set"], r["idx"], r.get("seconds"), flush=True)
            except Exception:
                print(done, "FAIL", futs[f]["path"], traceback.format_exc()[-300:], flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
