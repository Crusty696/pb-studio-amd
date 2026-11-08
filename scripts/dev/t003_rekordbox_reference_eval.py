"""T003: compare PB Studio key/tempo/beat phase against rekordbox reference data.

rekordbox (Pioneer) analysed the user's library independently of PB Studio and
exported per-track key (Camelot ``Tonality``), tempo and beat-grid anchor
(``TEMPO Inizio/Bpm``) to ``rekordbox.xml``. This script reads that export
read-only, runs the production ``KeyDetector`` and ``estimate_beat_grid`` on
the same audio files and writes per-track results plus MIREX-style scores.

Also writes an M3U of one rekordbox playlist so a reference mix can be built
with ``t003_build_reference_mix.py``.

Usage (PYTHONPATH=src):
    python scripts/dev/t003_rekordbox_reference_eval.py --xml F:/pioneer_xml/rekordbox.xml \
        --remap D:/=F:/ --tracks 40 --playlist 18.12.2025 --out DIR
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import librosa
import numpy as np

from pb_studio.audio.beat_grid import estimate_beat_grid
from pb_studio.audio.key_detector import KeyDetector

NOTES = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6,
         "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
# Camelot number -> (minor tonic, major tonic)
CAMELOT = {1: (8, 11), 2: (3, 6), 3: (10, 1), 4: (5, 8), 5: (0, 3), 6: (7, 10),
           7: (2, 5), 8: (9, 0), 9: (4, 7), 10: (11, 2), 11: (6, 9), 12: (1, 4)}


def camelot_to_key(code: str) -> tuple[int, str] | None:
    code = code.strip().upper()
    if len(code) < 2 or code[-1] not in "AB" or not code[:-1].isdigit():
        return None
    minor, major = CAMELOT[int(code[:-1])]
    return (minor, "minor") if code[-1] == "A" else (major, "major")


def parse_key(text: str) -> tuple[int, str] | None:
    parts = text.replace("_", " ").split()
    if len(parts) != 2 or parts[0] not in NOTES:
        return None
    mode = parts[1].lower()
    return (NOTES[parts[0]], mode) if mode in ("major", "minor") else None


def mirex(est: tuple[int, str] | None, ref: tuple[int, str]) -> tuple[str, float]:
    if est is None:
        return "none", 0.0
    (e, em), (r, rm) = est, ref
    if (e, em) == (r, rm):
        return "exact", 1.0
    if em == rm and (e - r) % 12 in (5, 7):
        return "fifth", 0.5
    if em != rm and ((em == "minor" and (e + 3) % 12 == r) or (em == "major" and (e - 3) % 12 == r)):
        return "relative", 0.3
    if em != rm and e == r:
        return "parallel", 0.2
    return "other", 0.0


def to_path(location: str, remap: tuple[str, str] | None) -> Path:
    p = urllib.parse.unquote(location.replace("file://localhost/", ""))
    if remap and p.startswith(remap[0]):
        p = remap[1] + p[len(remap[0]):]
    return Path(p)


def beat_phase_hit(grid, ref_anchor: float, ref_bpm: float, start: float, end: float,
                   tol: float = 0.07) -> float | None:
    est = grid.beat_times(start, end)
    if len(est) == 0 or ref_bpm <= 0:
        return None
    period = 60.0 / ref_bpm
    ref = ref_anchor + np.arange(np.ceil((start - ref_anchor) / period),
                                 np.floor((end - ref_anchor) / period) + 1) * period
    d = np.min(np.abs(est[:, None] - ref[None, :]), axis=1)
    return float(np.mean(d <= tol))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml", type=Path, required=True)
    ap.add_argument("--remap", default="")
    ap.add_argument("--tracks", type=int, default=40)
    ap.add_argument("--playlist", default="")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    remap = tuple(a.remap.split("=", 1)) if a.remap else None

    root = ET.parse(a.xml).getroot()
    tracks = root.find("COLLECTION").findall("TRACK")
    by_id = {t.get("TrackID"): t for t in tracks}

    if a.playlist:
        for node in root.iter("NODE"):
            if node.get("Name") == a.playlist and node.get("Type") == "1":
                lines = ["#EXTM3U"]
                for k in node.findall("TRACK"):
                    t = by_id.get(k.get("Key"))
                    if t is not None:
                        p = to_path(t.get("Location"), remap)
                        if p.is_file():
                            lines.append(str(p))
                (a.out / "playlist.m3u").write_text("\n".join(lines) + "\n", encoding="utf-8")
                break

    candidates = [t for t in tracks if to_path(t.get("Location"), remap).is_file()
                  and camelot_to_key(t.get("Tonality") or "") and t.find("TEMPO") is not None]
    step = max(1, len(candidates) // a.tracks)
    sample = candidates[::step][: a.tracks]

    kd = KeyDetector()
    rows = []
    for t in sample:
        path = to_path(t.get("Location"), remap)
        tempo = t.findall("TEMPO")
        ref_bpm, ref_anchor = float(tempo[0].get("Bpm")), float(tempo[0].get("Inizio"))
        ref_key = camelot_to_key(t.get("Tonality"))
        t0 = time.perf_counter()
        y, sr = librosa.load(str(path), sr=22050, mono=True)
        est_key_txt = kd.detect_key(y, sr)
        start, end = 60.0, min(180.0, len(y) / sr)
        seg = y[int(start * sr): int(end * sr)]
        grid = estimate_beat_grid(seg, sr)
        # grid anchor is relative to the excerpt start
        grid.anchor_s += start
        ratio = grid.bpm / ref_bpm if ref_bpm else 0.0
        octave_ok = any(abs(ratio - m) <= 0.02 * m for m in (0.5, 1.0, 2.0, 2 / 3, 1.5))
        verdict, score = mirex(parse_key(est_key_txt), ref_key)
        rows.append({
            "file": path.name, "rb_tonality": t.get("Tonality"), "rb_bpm": ref_bpm,
            "rb_anchor": ref_anchor, "rb_tempo_changes": len(tempo),
            "est_key": est_key_txt, "key_verdict": verdict, "key_score": score,
            "est_bpm": round(grid.bpm, 2), "grid_status": grid.status,
            "bpm_within_2pct": abs(ratio - 1.0) <= 0.02, "bpm_octave_related": octave_ok,
            "beat_hit_70ms": beat_phase_hit(grid, ref_anchor, ref_bpm, start, end),
            "seconds": round(time.perf_counter() - t0, 1)})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)

    n = len(rows)
    summary = {
        "tracks": n,
        "key_exact": sum(r["key_verdict"] == "exact" for r in rows),
        "key_mirex_mean": round(sum(r["key_score"] for r in rows) / max(n, 1), 3),
        "key_verdicts": {v: sum(r["key_verdict"] == v for r in rows)
                         for v in ("exact", "fifth", "relative", "parallel", "other", "none")},
        "bpm_within_2pct": sum(r["bpm_within_2pct"] for r in rows),
        "bpm_octave_related": sum(r["bpm_octave_related"] for r in rows),
        "beat_hit_70ms_median": float(np.median([r["beat_hit_70ms"] for r in rows
                                                  if r["beat_hit_70ms"] is not None] or [0])),
    }
    (a.out / "results.json").write_text(json.dumps({"summary": summary, "rows": rows},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY", json.dumps(summary))


if __name__ == "__main__":
    main()
