"""T003: build a DJ-style reference mix with boundaries known by construction.

Takes real tracks from an M3U/M3U8 playlist, joins them with equal-power
crossfades (FFmpeg ``acrossfade``) and writes

  * ``<out>.flac``            the mix
  * ``<out>.boundaries.txt``  one boundary per line = crossfade midpoint (s)
  * ``<out>.tracks.json``     order, source SHA-256, duration, label key/BPM
                              parsed from the Beatport file name, mix start/end

The boundaries are exact because they follow from the construction, not from
any analyzer. Labels for key/BPM are the vendor file-name labels and are only
a reference, not verified ground truth.

Usage:
    python scripts/dev/t003_build_reference_mix.py PLAYLIST --count 8 --xfade 8 --out DIR/name
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

FFMPEG = Path("tools/ffmpeg/bin/ffmpeg.exe")
FFPROBE = Path("tools/ffmpeg/bin/ffprobe.exe")
LABEL = re.compile(r"_(\d{2,3})__\((?P<genre>[^)]*)\)_(?P<key>[A-G][b#]?_(?:Major|Minor))_")


def tracks_from_playlist(path: Path) -> list[Path]:
    out = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(Path(line.replace("/", "\\")))
    return out


def duration(path: Path) -> float:
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(path)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("playlist", type=Path)
    ap.add_argument("--count", type=int, default=8)
    ap.add_argument("--xfade", type=float, default=8.0)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    tracks = [t for t in tracks_from_playlist(a.playlist) if t.is_file()][: a.count]
    if len(tracks) < 2:
        raise SystemExit("need at least two existing tracks")
    durs = [duration(t) for t in tracks]

    inputs: list[str] = []
    for t in tracks:
        inputs += ["-i", str(t)]
    chain, prev = [], "[0:a]"
    for i in range(1, len(tracks)):
        label = f"[x{i}]"
        chain.append(f"{prev}[{i}:a]acrossfade=d={a.xfade}:c1=qsin:c2=qsin{label}")
        prev = label
    a.out.parent.mkdir(parents=True, exist_ok=True)
    flac = a.out.with_suffix(".flac")
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", *inputs,
                    "-filter_complex", ";".join(chain), "-map", prev,
                    "-ar", "44100", "-ac", "2", "-c:a", "flac", str(flac)], check=True)

    records, start, boundaries = [], 0.0, []
    for i, (t, d) in enumerate(zip(tracks, durs)):
        if i > 0:
            start -= a.xfade
            boundaries.append(round(start + a.xfade / 2, 3))
        m = LABEL.search(t.name)
        records.append({"order": i, "file": t.name, "sha256": sha256(t),
                        "duration": round(d, 3), "mix_start": round(start, 3),
                        "mix_end": round(start + d, 3),
                        "label_bpm": int(m.group(1)) if m else None,
                        "label_key": m.group("key").replace("_", " ") if m else None})
        start += d
    a.out.with_suffix(".boundaries.txt").write_text(
        "# crossfade midpoints, seconds, exact by construction\n"
        + "\n".join(f"{b:.3f}" for b in boundaries) + "\n", encoding="utf-8")
    a.out.with_suffix(".tracks.json").write_text(json.dumps(
        {"xfade_seconds": a.xfade, "expected_duration": round(start, 3),
         "mix_sha256": sha256(flac), "tracks": records}, indent=2), encoding="utf-8")
    print(f"mix {flac} {start:.1f}s, {len(boundaries)} boundaries")


if __name__ == "__main__":
    main()
