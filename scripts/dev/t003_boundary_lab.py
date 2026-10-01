"""T003 lab: cache 1-s mix features once, then evaluate boundary detection fast.

    python scripts/dev/t003_boundary_lab.py extract MIX.flac CACHE.npz
    python scripts/dev/t003_boundary_lab.py eval CACHE.npz GT.boundaries.txt [...pairs] [VARIANTS.json]

`extract` runs the same per-chunk feature code as the long-mix path of
`SubtrackDetector` (120-s chunks, ~1-s bins) and stores every 20-s tempo
window (10-s hop), so `eval` can rerun the production boundary logic and
parameter variants of it in seconds instead of minutes. Read-only against the
mix files.

VARIANTS.json maps a name to overrides; upper-case keys replace module
constants of `subtrack_detector` for that run, ``hop_every`` thins the cached
tempo windows, ``debug`` prints reference and found times:

    {"production": {}, "penalty14": {"PARTITION_PENALTY": 14.0, "debug": true}}
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_subtrack_detection import _load_gt, evaluate_boundaries  # noqa: E402

from pb_studio.audio import subtrack_detector as sd  # noqa: E402

CACHE_TEMPO_HOP_SEC = 10.0


def extract(mix: Path, out: Path) -> None:
    import librosa
    from pb_studio.audio.beat_grid import estimate_beat_grid

    det = sd.SubtrackDetector()
    duration = float(librosa.get_duration(path=str(mix)))
    chroma, onset, tempo_c, tempo_b, tempo_k = [], [], [], [], []
    chunk_bins: list[int] = []
    timing = {"load": 0.0, "chroma": 0.0, "onset": 0.0, "tempo": 0.0}
    offset = 0.0
    while offset < duration:
        chunk = min(det.LONG_MIX_CHUNK_SEC, duration - offset)
        t = time.perf_counter()
        y, sr = librosa.load(str(mix), sr=det.sr, mono=True, offset=offset, duration=chunk)
        timing["load"] += time.perf_counter() - t
        if y.size == 0:
            offset += chunk
            continue
        fpb = max(1, int(round(sr / det.hop_length)))
        t = time.perf_counter()
        c = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=det.hop_length)
        timing["chroma"] += time.perf_counter() - t
        t = time.perf_counter()
        o = librosa.onset.onset_strength(y=y, sr=sr, hop_length=det.hop_length)
        timing["onset"] += time.perf_counter() - t
        cb = det._mean_bin_2d(c, fpb)
        chroma.append(cb)
        chunk_bins.append(cb.shape[1])
        onset.append(det._mean_bin_1d(o, fpb, cb.shape[1]))
        t = time.perf_counter()
        win, hop = int(sd.TEMPO_WINDOW_SEC * sr), int(CACHE_TEMPO_HOP_SEC * sr)
        starts = range(0, y.size - win + 1, hop) if y.size >= win else [0]
        for s in starts:
            seg = y[s:s + win]
            g = estimate_beat_grid(seg, sr)
            tempo_c.append(offset + (s + seg.size / 2.0) / sr)
            tempo_b.append(g.bpm)
            tempo_k.append(g.contrast)
        timing["tempo"] += time.perf_counter() - t
        offset += chunk
    np.savez(out, chroma=np.concatenate(chroma, 1), onset=np.concatenate(onset),
             tempo_c=np.asarray(tempo_c), tempo_b=np.asarray(tempo_b),
             tempo_k=np.asarray(tempo_k), chunk_bins=np.asarray(chunk_bins),
             duration=duration, timing=json.dumps(timing))
    print(json.dumps({k: round(v, 1) for k, v in timing.items()}))


def tempo_bins(z, n: int, chunk_sec: float = 120.0, hop_every: int = 1) -> np.ndarray:
    """Production `_window_tempo_bins`: nearest window *within the same chunk*."""
    from pb_studio.audio.beat_grid import GRID_CONTRAST_MIN

    out = np.zeros(n, dtype=np.float32)
    c, b, k = z["tempo_c"], z["tempo_b"], z["tempo_k"]
    bin_sec = 43 * 512 / 22050.0
    chunk_of = np.floor(c / chunk_sec).astype(int)
    lo = 0
    for ch, n_bins in enumerate(z["chunk_bins"]):
        hi = lo + int(n_bins)
        idx = np.where(chunk_of == ch)[0][::hop_every]
        ok = idx[(b[idx] > 0) & (k[idx] >= GRID_CONTRAST_MIN)]
        if ok.size:
            centers = (np.arange(n_bins) + 0.5) * bin_sec
            near = np.abs(centers[:, None] - (c[ok] - ch * chunk_sec)[None, :]).argmin(axis=1)
            out[lo:hi] = b[ok][near]
        lo = hi
    return out


def run(z, variant: dict) -> list[float]:
    """Production `_long_mix_boundaries` on cached features."""
    det = sd.SubtrackDetector()
    duration = float(z["duration"])
    chroma = z[variant.get("chroma_key", "chroma")]
    n = chroma.shape[1]
    saved = {}
    for key, value in variant.items():
        if key.isupper():
            saved[key] = getattr(sd, key)
            setattr(sd, key, value)
    try:
        default_every = max(1, int(round(sd.TEMPO_HOP_SEC / CACHE_TEMPO_HOP_SEC)))
        tempo = tempo_bins(z, n, hop_every=variant.get("hop_every", default_every))
        act = np.zeros(n, np.float32)
        flux = z["onset"][:n].astype(np.float32)
        found = det._long_mix_boundaries(chroma, act, flux, tempo, duration)
    finally:
        for key, value in saved.items():
            setattr(sd, key, value)
    return [b.time for b in found]


def evaluate(pairs: list[tuple[str, str]], variants: dict[str, dict]) -> None:
    data = [(Path(c).stem, np.load(c), _load_gt(Path(g))) for c, g in pairs]
    for name, var in variants.items():
        f1s = []
        line = []
        for stem, z, gt in data:
            b = run(z, var)
            m = evaluate_boundaries(b, gt, 15.0)
            f1s.append(m["f1"])
            err = [round(min(abs(x - g) for x in b)) if b else None for g in gt]
            line.append(f"{stem}: F1 {m['f1']:.3f} n={len(b)} err={err}")
            if var.get("debug"):
                line.append("      gt    " + " ".join(f"{g:6.0f}" for g in gt))
                line.append("      found " + " ".join(f"{g:6.0f}" for g in b))
        print(f"== {name}  mean F1 {np.mean(f1s):.3f}  min {np.min(f1s):.3f}")
        for s in line:
            print("   " + s)


if __name__ == "__main__":
    if sys.argv[1] == "extract":
        extract(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        args = sys.argv[2:]
        variants = {"production": {}}
        if args and args[-1].endswith(".json"):
            variants = json.loads(Path(args.pop()).read_text(encoding="utf-8"))
        pairs = list(zip(args[0::2], args[1::2]))
        evaluate(pairs, variants)
