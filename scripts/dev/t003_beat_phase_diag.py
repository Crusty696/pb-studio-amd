"""Residual phase error (ms) vs rekordbox after half-beat disambiguation, plus fine refinement variants."""
import json
import sys
from pathlib import Path

import librosa
import numpy as np

C = Path(sys.argv[1])
SR, HOP = 22050, 512


def wrap(x):
    return (x + 0.5) % 1.0 - 0.5


out = {"prod": [], "flip": [], "flip_ref_lowflux": [], "flip_ref_subE": [], "flip_ref_onset": []}
for f in sorted(C.glob("*.npz")):
    z = np.load(f)
    meta = json.loads(str(z["meta"]))
    bpm, anchor, _ = z["grid"]
    if abs(bpm / meta["rb_bpm"] - 1) > 0.02:
        continue
    y = z["excerpt"].astype(np.float32) / 32767
    start, period = 60.0, 60.0 / bpm
    mel = librosa.feature.melspectrogram(y=y, sr=SR, hop_length=HOP, n_mels=128, fmax=11025)
    freqs = librosa.mel_frequencies(n_mels=128, fmax=11025)
    t = librosa.times_like(mel[0], sr=SR, hop_length=HOP)
    span = t[-1]
    sub = mel[(freqs >= 20) & (freqs < 90)].sum(axis=0)
    db = librosa.power_to_db(mel)
    lowflux = np.maximum(0, np.diff(db, axis=1, prepend=db[:, :1]))[(freqs >= 40) & (freqs < 120)].mean(axis=0)
    onset = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)

    def at(e, ph):
        return float(np.mean(np.interp(np.arange(ph % period, span, period), t, e)))

    a = (anchor - start) % period
    flip = at(sub, a + period / 2) > at(sub, a)
    a2 = a + period / 2 if flip else a

    def refine(e):
        cands = a2 + np.linspace(-0.2, 0.2, 41) * period
        return cands[int(np.argmax([at(e, c) for c in cands]))]

    def err(ph):
        return 1000 * period * wrap(((ph + start) - meta["rb_anchor"]) / (60.0 / meta["rb_bpm"]))

    out["prod"].append(err(a))
    out["flip"].append(err(a2))
    out["flip_ref_lowflux"].append(err(refine(lowflux)))
    out["flip_ref_subE"].append(err(refine(sub)))
    out["flip_ref_onset"].append(err(refine(onset)))
for k, v in out.items():
    v = np.array(v)
    print(f"{k:18s} n={v.size} |err|<=70ms: {np.mean(np.abs(v) <= 70):.2f}  <=35ms: {np.mean(np.abs(v) <= 35):.2f}  median={np.median(v):.1f}ms  q25/75={np.percentile(v, 25):.1f}/{np.percentile(v, 75):.1f}")
