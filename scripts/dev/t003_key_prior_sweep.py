"""Key-detection variants on cached features. Tune set = 'tune_*', report set = 'test_*'."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t003_rekordbox_reference_eval import camelot_to_key, mirex  # noqa: E402

C = Path(sys.argv[1])
PROF = {
    "kk": ([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88],
           [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]),
    "temperley": ([5.0, 2.0, 3.5, 2.0, 4.5, 4.0, 2.0, 4.5, 2.0, 3.5, 1.5, 4.0],
                  [5.0, 2.0, 3.5, 4.5, 2.0, 4.0, 2.0, 4.5, 3.5, 2.0, 1.5, 4.0]),
}
rows = []
for f in sorted(C.glob("*.npz")):
    z = np.load(f, allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    ref = camelot_to_key(meta["tonality"])
    rows.append((meta["set"], ref, z))
print(len(rows), "tracks;", "minor share:", np.mean([r[1][1] == "minor" for r in rows]))


def fold(cqt, lo_oct=0, hi_oct=7):
    c = cqt[lo_oct * 12:hi_oct * 12]
    return c.reshape(-1, 12, c.shape[1]).sum(axis=0)


def vec(z, variant):
    if variant == "prod":
        return z["prod_mean"]
    if variant == "harm_chroma":
        return z["chroma_h_pool"].mean(axis=1)
    src, lo, hi, comp = variant.split(":")
    cq = z["cqt_h_pool"] if src == "h" else z["cqt_pool"]
    ch = fold(cq, int(lo), int(hi))
    if comp == "log":
        ch = np.log1p(100 * ch / (ch.max(axis=0, keepdims=True) + 1e-12))
    else:
        ch = ch / (ch.max(axis=0, keepdims=True) + 1e-12)
    return ch.mean(axis=1)


def decide(v, maj, mnr, bias=0.0):
    best, key = -9, None
    for i in range(12):
        cm = np.corrcoef(v, np.roll(maj, i))[0, 1]
        cn = np.corrcoef(v, np.roll(mnr, i))[0, 1] + bias
        if cm > best:
            best, key = cm, (i, "major")
        if cn > best:
            best, key = cn, (i, "minor")
    return key


def learn(vs, refs):
    acc = {"major": np.zeros(12), "minor": np.zeros(12)}
    for v, (t, m) in zip(vs, refs):
        acc[m] += np.roll(v / v.sum(), -t)
    return acc["major"] / max(1, sum(r[1] == "major" for r in refs)), acc["minor"] / max(1, sum(r[1] == "minor" for r in refs))


def score(sel, variant, prof, bias):
    res = []
    for _, ref, z in sel:
        est = decide(vec(z, variant), *prof, bias)
        res.append(mirex(est, ref)[0])
    return sum(r == "exact" for r in res), len(res), {k: res.count(k) for k in set(res)}


variants = ["prod", "harm_chroma"] + [f"{s}:{lo}:{hi}:{c}" for s in ("o", "h") for lo, hi in ((0, 7), (1, 6), (2, 6), (1, 5)) for c in ("max", "log")]
tune = [r for r in rows if r[0] == "tune"]
test = [r for r in rows if r[0] == "test"]
out = []
for variant in variants:
    profs = dict((k, (np.array(a), np.array(b))) for k, (a, b) in PROF.items())
    tv = [vec(z, variant) for _, _, z in tune]
    profs["learned"] = learn(tv, [r for _, r, _ in tune])
    for pname, prof in profs.items():
        for bias in (0.0, 0.02, 0.05, 0.1):
            a, n, _ = score(tune, variant, prof, bias)
            b, m, d = score(test, variant, prof, bias)
            out.append((a / n, b / m, variant, pname, bias, a, n, b, m, d))
out.sort(key=lambda r: -r[0])
for r in out[:25]:
    print(f"tune {r[5]}/{r[6]}  test {r[7]}/{r[8]}  {r[2]:14s} {r[3]:9s} bias={r[4]}  {r[9]}")
for r in out:
    if r[2] == "prod" and r[3] == "kk" and r[4] == 0.0:
        print("BASELINE", r[5], r[6], r[7], r[8], r[9])
kk = tuple(np.array(x) for x in PROF["kk"])
for bias in (0.0, 0.03, 0.05, 0.075, 0.1, 0.125, 0.15, 0.2):
    line = []
    for name, sel in (("tune", tune), ("test", test), ("all", rows)):
        ex = {"major": [0, 0], "minor": [0, 0]}
        for _, ref, z in sel:
            est = decide(vec(z, "prod"), *kk, bias)
            ex[ref[1]][1] += 1
            ex[ref[1]][0] += est == ref
        line.append(f"{name}: minor {ex['minor'][0]}/{ex['minor'][1]} major {ex['major'][0]}/{ex['major'][1]}")
    print(f"KK prod bias={bias}: " + " | ".join(line))
