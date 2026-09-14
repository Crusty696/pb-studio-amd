"""Beat This! (ONNX / DirectML) tempo + downbeat measurement harness.

Read-only research tool. Touches no production code, no database, no backend.

Model:  models/beat_this/beat_this.onnx  (musetric/beat-this-onnx, MIT)
        ONNX export of CPJKU/beat_this checkpoint `final0` (ISMIR 2024).

The feature front end and the `minimal` postprocessing are ported 1:1 from the
upstream reference (beat_this/preprocessing.py, beat_this/inference.py,
beat_this/model/postprocessor.py). torchaudio's MelSpectrogram is used directly,
so the log-mel is the reference transform, not a re-implementation.

Usage
-----
  python scripts/dev/measure_neural_beat_tracker.py --selftest
  python scripts/dev/measure_neural_beat_tracker.py --one <file.aiff>
  python scripts/dev/measure_neural_beat_tracker.py --all [--out docs/measurements/x.json]
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import scipy.ndimage as ndi
import soundfile as sf
import soxr
import torch
import torchaudio

REPO = Path(__file__).resolve().parents[2]
MODEL_DIR = REPO / "models" / "beat_this"
ONNX_PATH = MODEL_DIR / "beat_this.onnx"

TRACK_DIR = Path(r"D:\beatport_tracks_2025-08")

# --- contract, from models/beat_this/config.json -----------------------------
SR = 22050
N_FFT = 1024
HOP = 441
N_MELS = 128
F_MIN = 30
F_MAX = 11000
LOG_MULT = 1000
FPS = 50.0
CHUNK_SIZE = 1500
BORDER_SIZE = 6
PEAK_KERNEL = 7
PEAK_THRESHOLD = 0.0
DEDUP_WIDTH = 1

# --- measurement protocol ----------------------------------------------------
WINDOW_START_S = 60.0
WINDOW_LEN_S = 120.0
OCTAVE_LO = 90.0
OCTAVE_HI = 180.0
TOLERANCE = 0.02

BPM_RE = re.compile(r"_(\d{2,3})__")


# ============================ feature front end ==============================

_MEL = None


def log_mel(signal: np.ndarray) -> torch.Tensor:
    """Reference LogMelSpect: (T,) float32 @22050 -> (frames, 128) float32."""
    global _MEL
    if _MEL is None:
        _MEL = torchaudio.transforms.MelSpectrogram(
            sample_rate=SR,
            n_fft=N_FFT,
            hop_length=HOP,
            f_min=F_MIN,
            f_max=F_MAX,
            n_mels=N_MELS,
            mel_scale="slaney",
            normalized="frame_length",
            power=1,
        )
    x = torch.tensor(signal, dtype=torch.float32)
    return torch.log1p(LOG_MULT * _MEL(x).T)


def load_window(path: Path, start_s: float, length_s: float) -> np.ndarray:
    """Decode [start_s, start_s+length_s), mean-downmix, resample to 22050."""
    info = sf.info(str(path))
    start = int(round(start_s * info.samplerate))
    frames = int(round(length_s * info.samplerate))
    sig, sr = sf.read(str(path), start=start, frames=frames, dtype="float64")
    if sig.ndim == 2:
        sig = sig.mean(1)  # arithmetic mean, matches Audio2Frames
    if sr != SR:
        sig = soxr.resample(sig, in_rate=sr, out_rate=SR)
    return sig


# ============================ chunking (reference) ===========================


def split_piece(spect: torch.Tensor, chunk_size: int, border_size: int):
    n = len(spect)
    starts = np.arange(-border_size, n - border_size, chunk_size - 2 * border_size)
    if n > chunk_size - 2 * border_size:
        starts[-1] = n - (chunk_size - border_size)
    chunks = []
    for start in starts:
        piece = spect[max(start, 0) : min(start + chunk_size, n)]
        left = max(0, -start)
        right = max(0, min(border_size, start + chunk_size - n))
        if left or right:
            piece = torch.nn.functional.pad(piece, (0, 0, left, right), "constant", 0)
        chunks.append(piece)
    return chunks, starts


def aggregate(pred_chunks, starts, full_size, chunk_size, border_size):
    """keep_first aggregation, reference semantics."""
    beat = np.full((full_size,), -1000.0, dtype=np.float32)
    down = np.full((full_size,), -1000.0, dtype=np.float32)
    cut = [(b[border_size:-border_size], d[border_size:-border_size]) for b, d in pred_chunks]
    for start, (b, d) in zip(reversed(list(starts)), reversed(cut)):
        lo = start + border_size
        hi = start + chunk_size - border_size
        beat[lo:hi] = b
        down[lo:hi] = d
    return beat, down


# ============================ minimal postprocessing =========================


def deduplicate_peaks(peaks, width=1) -> np.ndarray:
    result = []
    it = iter(int(p) for p in peaks)
    try:
        p = next(it)
    except StopIteration:
        return np.array(result)
    c = 1
    for p2 in it:
        if p2 - p <= width:
            c += 1
            p += (p2 - p) / c
        else:
            result.append(p)
            p = p2
            c = 1
    result.append(p)
    return np.array(result)


def postp_minimal(beat_logits: np.ndarray, down_logits: np.ndarray):
    """Port of Postprocessor.postp_minimal / _postp_minimal_item (type='minimal')."""
    out = []
    for logits in (beat_logits, down_logits):
        # F.max_pool1d(x, 7, stride=1, padding=3) == centered max filter of size 7,
        # padded with -inf.
        mx = ndi.maximum_filter1d(logits, size=PEAK_KERNEL, mode="constant", cval=-np.inf)
        peaks = (logits == mx) & (logits > PEAK_THRESHOLD)
        out.append(np.nonzero(peaks)[0])
    beat_frame = deduplicate_peaks(out[0], width=DEDUP_WIDTH)
    down_frame = deduplicate_peaks(out[1], width=DEDUP_WIDTH)
    beat_time = beat_frame / FPS
    down_time = down_frame / FPS
    if len(beat_time) > 0:
        for i, d in enumerate(down_time):
            down_time[i] = beat_time[int(np.argmin(np.abs(beat_time - d)))]
    down_time = np.unique(down_time)
    return beat_time, down_time


# ============================ session ========================================


def make_session(provider: str = "dml"):
    if provider == "dml":
        providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
    else:
        providers = ["CPUExecutionProvider"]
    so = ort.SessionOptions()
    # IRON RULE 2 (DirectML): both must be off.
    so.enable_mem_pattern = False
    so.enable_cpu_mem_arena = False
    return ort.InferenceSession(str(ONNX_PATH), sess_options=so, providers=providers)


def track(sess, signal: np.ndarray):
    spect = log_mel(signal)
    chunks, starts = split_piece(spect, CHUNK_SIZE, BORDER_SIZE)
    preds = []
    for ch in chunks:
        # one window per call: batching materializes a windows*32*1500*1500 tensor
        arr = ch.numpy()[None, :, :].astype(np.float32)
        b, d = sess.run(["beat", "downbeat"], {"spect": arr})
        preds.append((b[0], d[0]))
    beat_l, down_l = aggregate(preds, starts, spect.shape[0], CHUNK_SIZE, BORDER_SIZE)
    beats, downbeats = postp_minimal(beat_l, down_l)
    return beats, downbeats, spect.shape[0], len(chunks)


# ============================ metrics ========================================


def octave_norm(bpm: float) -> float:
    if bpm <= 0:
        return 0.0
    while bpm < OCTAVE_LO:
        bpm *= 2.0
    while bpm >= OCTAVE_HI:
        bpm /= 2.0
    return bpm


def tempo_from_beats(beats: np.ndarray) -> float:
    """Median inter-beat interval. Quantized to the 20 ms model frame grid."""
    if len(beats) < 3:
        return 0.0
    d = np.diff(beats)
    d = d[d > 0]
    if len(d) == 0:
        return 0.0
    return float(60.0 / np.median(d))


def tempo_lsq(beats: np.ndarray) -> float:
    """Least-squares slope of beat time vs beat index.

    Beat times are quantized to the 20 ms model frame grid, so the median
    interval carries up to ~2 % quantization error at 126 BPM (0.42 vs 0.44 s
    are adjacent grid points; nothing in between is representable). Fitting a
    line through all beats averages that out.

    Beat indices are accumulated PER INTERVAL -- idx = cumsum(round(dt/period))
    -- not from round((t - t0) / period). The latter is circular: a median
    period biased by grid quantization makes the global index drift, the drifted
    beats collide, and the fit then merely reproduces the biased period. Per
    interval, round(dt/period) is 1 for every ordinary beat even when period is
    off by 2 %, so the index sequence is exact and the slope is free to differ
    from the median.
    """
    if len(beats) < 4:
        return 0.0
    d = np.diff(beats)
    if not np.any(d > 0):
        return 0.0
    period = float(np.median(d[d > 0]))
    if period <= 0:
        return 0.0
    steps = np.round(d / period)
    # Use only contiguous beat-to-beat intervals. Gaps (breakdowns, dropouts)
    # get a step count that a global fit cannot recover from: one 8.5-beat gap
    # rounded to 8 compresses the whole index and inflated one track here from
    # 143 to 166 BPM. Averaging single-step intervals is immune to that, and it
    # de-quantizes at the same time -- individual intervals snap to the 20 ms
    # grid (0.42 / 0.44 s), but their mean converges on the true period.
    single = d[steps == 1]
    if len(single) < 3:
        return float(60.0 / period)
    return float(60.0 / float(single.mean()))


def downbeat_stats(beats: np.ndarray, downbeats: np.ndarray) -> dict:
    """Are consecutive downbeats ~4 beat intervals apart?"""
    if len(downbeats) < 3 or len(beats) < 5:
        return {"n_downbeats": int(len(downbeats)), "verdict": "too_few"}
    # use the de-quantized period; the median is pinned to the 20 ms grid and
    # would bias every bar-length ratio by up to 2 %
    bpm = tempo_lsq(beats)
    beat_period = 60.0 / bpm if bpm > 0 else 0.0
    dd = np.diff(downbeats)
    if beat_period <= 0:
        return {"n_downbeats": int(len(downbeats)), "verdict": "no_beat_period"}
    ratios = dd / beat_period
    rounded = np.round(ratios)
    frac_4 = float(np.mean(rounded == 4))
    # A gap of 8 beats is one MISSED downbeat, not a misplaced one: the bar
    # grid is still intact. Multiples of 4 are the honest "grid holds" measure.
    frac_mult4 = float(np.mean((rounded >= 4) & (rounded % 4 == 0)))
    med_ratio = float(np.median(ratios))
    dev = float(np.mean(np.abs(ratios - rounded)))
    if frac_mult4 >= 0.9 and abs(med_ratio - 4) <= 0.1:
        verdict = "4/4_consistent"
    elif dev < 0.1:
        verdict = "mostly_integer"
    else:
        verdict = "irregular"
    return {
        "n_downbeats": int(len(downbeats)),
        "beat_period_s": round(beat_period, 6),
        "median_bar_in_beats": round(med_ratio, 4),
        "fraction_bars_of_4_beats": round(frac_4, 4),
        "fraction_bars_multiple_of_4": round(frac_mult4, 4),
        "mean_abs_dev_from_integer": round(dev, 4),
        "verdict": verdict,
    }


def fourier_tempo(sig: np.ndarray) -> tuple[float, float]:
    """Independent arbiter: peak of a phase-invariant Fourier tempogram.

    Shares nothing with Beat This and nothing with librosa.beat_track's
    tempogram grid -- it evaluates |sum_n env[n] exp(-2 pi i f t_n)| on a
    continuous 0.01 BPM grid, so it has no k-quantized candidate set and no
    start_bpm prior. Used to decide, per track, whether a disagreement between
    the tracker and the filename BPM is the tracker's fault or the label's.
    """
    import librosa

    env = librosa.onset.onset_strength(y=sig.astype(np.float32), sr=SR, hop_length=HOP)
    env = env - env.mean()
    t = np.arange(len(env)) / (SR / HOP)
    grid = np.arange(60.0, 200.0, 0.01)
    best_v, best_b = -1.0, 0.0
    for i in range(0, len(grid), 2000):
        g = grid[i : i + 2000] / 60.0
        mag = np.abs(np.exp(-2j * np.pi * np.outer(g, t)) @ env)
        j = int(np.argmax(mag))
        if mag[j] > best_v:
            best_v, best_b = float(mag[j]), float(grid[i + j])
    return best_b, best_v / (float(np.abs(env).sum()) + 1e-9)


def ref_bpm(path: Path):
    m = BPM_RE.search(path.name)
    return float(m.group(1)) if m else None


def collect_tracks():
    files = sorted(p for p in TRACK_DIR.rglob("*.aiff") if BPM_RE.search(p.name))
    return files


def measure_one(sess, path: Path) -> dict:
    t0 = time.perf_counter()
    sig = load_window(path, WINDOW_START_S, WINDOW_LEN_S)
    t_load = time.perf_counter() - t0
    t1 = time.perf_counter()
    beats, downbeats, n_frames, n_windows = track(sess, sig)
    t_infer = time.perf_counter() - t1
    est_med = tempo_from_beats(beats)
    est = tempo_lsq(beats) or est_med
    ref = ref_bpm(path)
    est_n = octave_norm(est)
    est_med_n = octave_norm(est_med)
    ref_n = octave_norm(ref) if ref else 0.0
    hit = bool(ref_n and est_n and abs(est_n - ref_n) / ref_n <= TOLERANCE)
    hit_med = bool(ref_n and est_med_n and abs(est_med_n - ref_n) / ref_n <= TOLERANCE)
    return {
        "file": path.name,
        "ref_bpm": ref,
        "ref_bpm_norm": round(ref_n, 4),
        "est_bpm": round(est, 4),
        "est_bpm_norm": round(est_n, 4),
        "est_bpm_median_norm": round(est_med_n, 4),
        "rel_error": round(abs(est_n - ref_n) / ref_n, 5) if ref_n else None,
        "hit": hit,
        "hit_median_estimator": hit_med,
        "n_beats": int(len(beats)),
        "n_frames": int(n_frames),
        "n_windows": int(n_windows),
        "seconds_load": round(t_load, 3),
        "seconds_infer": round(t_infer, 3),
        "downbeats": downbeat_stats(beats, downbeats),
        "first_beats": [round(float(b), 3) for b in beats[:8]],
        "first_downbeats": [round(float(b), 3) for b in downbeats[:6]],
    }


# ============================ entry points ===================================


def cmd_selftest(sess) -> int:
    files = collect_tracks()
    if not files:
        print("SELFTEST FAIL: no tracks found in", TRACK_DIR)
        return 1
    p = files[0]
    print(f"selftest on {p.name}")
    a = measure_one(sess, p)
    b = measure_one(sess, p)
    keys = ["est_bpm", "est_bpm_norm", "n_beats", "hit", "first_beats", "first_downbeats"]
    ok = all(a[k] == b[k] for k in keys)
    ok = ok and a["downbeats"] == b["downbeats"]
    for k in keys:
        print(f"  {k}: {a[k]!r} | {b[k]!r} {'OK' if a[k] == b[k] else 'MISMATCH'}")
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--one", type=str)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--arbiter", action="store_true", help="score tracker AND filename labels against an independent Fourier tempogram")
    ap.add_argument("--provider", default="dml", choices=["dml", "cpu"])
    ap.add_argument("--out", type=str)
    args = ap.parse_args()

    if not ONNX_PATH.exists():
        print("model missing:", ONNX_PATH)
        return 2

    t0 = time.perf_counter()
    sess = make_session(args.provider)
    load_s = time.perf_counter() - t0
    print(f"session providers: {sess.get_providers()}  (load {load_s:.2f}s)")
    print("inputs :", [(i.name, i.shape, i.type) for i in sess.get_inputs()])
    print("outputs:", [(o.name, o.shape, o.type) for o in sess.get_outputs()])

    if args.selftest:
        return cmd_selftest(sess)

    if args.one:
        r = measure_one(sess, Path(args.one))
        print(json.dumps(r, indent=2))
        return 0

    if args.arbiter:
        files = collect_tracks()
        rows, m_ok, l_ok = [], 0, 0
        for i, p in enumerate(files, 1):
            sig = load_window(p, WINDOW_START_S, WINDOW_LEN_S)
            beats, _, _, _ = track(sess, sig)
            model_n = octave_norm(tempo_lsq(beats))
            ft, sal = fourier_tempo(sig)
            four_n = octave_norm(ft)
            label_n = octave_norm(float(ref_bpm(p)))
            near = lambda a, b: bool(b and abs(a - b) / b <= TOLERANCE)
            mo, lo = near(model_n, four_n), near(label_n, four_n)
            m_ok += mo
            l_ok += lo
            rows.append({
                "file": p.name, "label_bpm_norm": round(label_n, 3),
                "beat_this_bpm_norm": round(model_n, 3),
                "fourier_bpm_norm": round(four_n, 3), "fourier_salience": round(sal, 4),
                "beat_this_agrees": mo, "label_agrees": lo,
            })
            print(f"[{i:2d}/{len(files)}] {'M+' if mo else 'M-'}{'L+' if lo else 'L-'} "
                  f"label={label_n:7.2f} beat_this={model_n:7.2f} fourier={four_n:7.2f}  {p.name[:44]}")
        summary = {
            "arbiter": "phase-invariant Fourier tempogram, 0.01 BPM grid, 60-200 BPM",
            "n_tracks": len(rows), "tolerance": TOLERANCE,
            "beat_this_agrees": m_ok, "beat_this_agreement": round(m_ok / len(rows), 4),
            "label_agrees": l_ok, "label_agreement": round(l_ok / len(rows), 4),
        }
        print(json.dumps(summary, indent=2))
        out = Path(args.out) if args.out else REPO / "docs" / "measurements" / "beat_this_onnx_arbiter.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"summary": summary, "results": rows}, indent=2), encoding="utf-8")
        print("wrote", out)
        return 0

    if args.all:
        files = collect_tracks()
        print(f"{len(files)} tracks")
        results = []
        for i, p in enumerate(files, 1):
            r = measure_one(sess, p)
            results.append(r)
            print(
                f"[{i:2d}/{len(files)}] {'HIT ' if r['hit'] else 'MISS'} "
                f"ref={r['ref_bpm']:>6.1f}->{r['ref_bpm_norm']:>7.2f} "
                f"est={r['est_bpm_norm']:>7.2f} "
                f"db={r['downbeats'].get('verdict','-'):<16} "
                f"{r['seconds_infer']:>5.1f}s  {p.name[:52]}"
            )
        hits = sum(1 for r in results if r["hit"])
        acc = hits / len(results) if results else 0.0
        db_ok = sum(1 for r in results if r["downbeats"].get("verdict") == "4/4_consistent")
        summary = {
            "tool": "Beat This! final0 ONNX via onnxruntime",
            "provider_requested": args.provider,
            "providers_active": sess.get_providers(),
            "onnxruntime": ort.__version__,
            "numpy": np.__version__,
            "torch": torch.__version__,
            "model_sha256_expected": "3472a3957f25f4c3a2d68b46ee4b784e065a8ebd46132796c1a6bdd817229253",
            "window": {"start_s": WINDOW_START_S, "length_s": WINDOW_LEN_S},
            "octave_range": [OCTAVE_LO, OCTAVE_HI],
            "tolerance": TOLERANCE,
            "n_tracks": len(results),
            "hits": hits,
            "accuracy": round(acc, 4),
            "downbeat_4_4_consistent": db_ok,
            "downbeat_4_4_fraction": round(db_ok / len(results), 4) if results else 0.0,
            "total_infer_seconds": round(sum(r["seconds_infer"] for r in results), 2),
        }
        print(json.dumps(summary, indent=2))
        out = Path(args.out) if args.out else REPO / "docs" / "measurements" / "beat_this_onnx_beatport.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8")
        print("wrote", out)
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
