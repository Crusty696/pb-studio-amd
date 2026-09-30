"""Evaluate CURRENT production key/beat-grid code on the cached 160-track feature set."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t003_rekordbox_reference_eval import camelot_to_key, mirex, parse_key  # noqa: E402
from pb_studio.audio.beat_grid import estimate_beat_grid  # noqa: E402
from pb_studio.audio.key_detector import KeyDetector  # noqa: E402

C = Path(sys.argv[1])
kd = KeyDetector()
stats = {}
for f in sorted(C.glob("*.npz")):
    z = np.load(f)
    meta = json.loads(str(z["meta"]))
    s = stats.setdefault(meta["set"], {"n": 0, "key_exact": 0, "verdicts": {}, "bpm2": 0, "hit70": [], "old_hit70": []})
    s["n"] += 1
    ref = camelot_to_key(meta["tonality"])
    v = mirex(parse_key(kd.detect_key_from_chroma(z["prod_mean"])), ref)[0]
    s["key_exact"] += v == "exact"
    s["verdicts"][v] = s["verdicts"].get(v, 0) + 1
    y = z["excerpt"].astype(np.float32) / 32767
    g = estimate_beat_grid(y, 22050)
    rb_bpm, rb_anchor = meta["rb_bpm"], meta["rb_anchor"]
    s["bpm2"] += abs(g.bpm / rb_bpm - 1) <= 0.02

    def hit(bpm, anchor):
        period = 60.0 / bpm
        est = anchor + np.arange(np.ceil((60 - anchor) / period), np.floor((180 - anchor) / period) + 1) * period
        rp = 60.0 / rb_bpm
        ref_t = rb_anchor + np.arange(np.ceil((60 - rb_anchor) / rp), np.floor((180 - rb_anchor) / rp) + 1) * rp
        return float(np.mean(np.min(np.abs(est[:, None] - ref_t[None, :]), axis=1) <= 0.07))

    s["hit70"].append(hit(g.bpm, g.anchor_s + 60.0))
    ob, oa, _ = z["grid"]
    s["old_hit70"].append(hit(ob, oa))
for name, s in stats.items():
    h, o = np.array(s["hit70"]), np.array(s["old_hit70"])
    print(f"{name}: n={s['n']} key_exact={s['key_exact']} {s['verdicts']} bpm2%={s['bpm2']} "
          f"beat_hit70 median old={np.median(o):.2f} new={np.median(h):.2f}; tracks>=0.9 old={int(np.sum(o >= 0.9))} new={int(np.sum(h >= 0.9))}; <=0.1 old={int(np.sum(o <= 0.1))} new={int(np.sum(h <= 0.1))}")
