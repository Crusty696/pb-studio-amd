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
    python scripts/dev/t003_build_reference_mix.py "Psy-Trance AIFF" --xml F:/pioneer_xml/rekordbox.xml \
        --remap D:/=F:/ --skip 10 --count 10 --xfade 32 --match-bpm 140 --out DIR/name

With ``--xml`` the playlist is read from a rekordbox export (tracks in
playlist order, ``--skip`` leaves out tracks already used by another mix).
``--match-bpm`` time-stretches every track (FFmpeg ``atempo``, pitch kept) from
its rekordbox ``AverageBpm`` to one common tempo - the beatmatched case of a
real DJ mix, in which a tempo step can no longer reveal a track change. The
boundaries account for the stretched durations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.parse
import xml.etree.ElementTree as ET
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


def tracks_from_rekordbox(xml: Path, playlist: str, remap: str) -> list[tuple[Path, float]]:
    root = ET.parse(xml).getroot()
    by_id = {t.get("TrackID"): t for t in root.find("COLLECTION").findall("TRACK")}
    old, new = remap.split("=", 1) if remap else ("", "")
    for node in root.iter("NODE"):
        if node.get("Name") == playlist and node.get("Type") == "1":
            out = []
            for key in node.findall("TRACK"):
                t = by_id.get(key.get("Key"))
                if t is None:
                    continue
                p = urllib.parse.unquote(t.get("Location").replace("file://localhost/", ""))
                if old and p.startswith(old):
                    p = new + p[len(old):]
                out.append((Path(p), float(t.get("AverageBpm") or 0.0)))
            return out
    raise SystemExit(f"playlist not found: {playlist}")


def _crossfade_to_flac(parts: list[Path], xfade: float, out: Path) -> list[float]:
    """Equal-power crossfades (sin/cos), streamed track by track.

    Ersetzt die acrossfade-Kette von ffmpeg: die stuerzte ab 48-s-Blenden mit
    0xC00000FD ab (ffmpeg 6.1, reproduziert mit sauberen 44,1-kHz-WAVs).
    Returns the duration of every part in seconds.
    """
    import numpy as np
    import soundfile as sf

    sr = 44100
    n_x = int(round(xfade * sr))
    ramp = (np.arange(n_x, dtype=np.float64) + 0.5) / n_x
    fade_in = np.sin(ramp * np.pi / 2)[:, None]
    fade_out = np.cos(ramp * np.pi / 2)[:, None]
    durs: list[float] = []
    tail = None
    with sf.SoundFile(str(out), "w", samplerate=sr, channels=2, format="FLAC",
                      subtype="PCM_16") as dst:
        for index, part in enumerate(parts):
            y, rate = sf.read(str(part), dtype="float64", always_2d=True)
            if rate != sr or y.shape[1] != 2:
                raise SystemExit(f"unexpected format in {part}")
            durs.append(y.shape[0] / sr)
            if y.shape[0] < 2 * n_x:
                raise SystemExit(f"track shorter than two crossfades: {part}")
            if tail is not None:
                y[:n_x] = tail * fade_out + y[:n_x] * fade_in
            last = index == len(parts) - 1
            body = y if last else y[:-n_x]
            dst.write(np.clip(body, -1.0, 1.0))
            tail = None if last else y[-n_x:].copy()
    return durs


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
    ap.add_argument("--xml", type=Path)
    ap.add_argument("--remap", default="")
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--match-bpm", type=float, default=0.0)
    a = ap.parse_args()

    if a.xml:
        listed = [(p, b) for p, b in tracks_from_rekordbox(a.xml, str(a.playlist), a.remap)
                  if p.is_file()]
    else:
        listed = [(t, 0.0) for t in tracks_from_playlist(a.playlist) if t.is_file()]
    listed = listed[a.skip: a.skip + a.count]
    if a.match_bpm and any(b <= 0 for _, b in listed):
        raise SystemExit("--match-bpm needs a rekordbox AverageBpm for every track")
    tracks = [t for t, _ in listed]
    if len(tracks) < 2:
        raise SystemExit("need at least two existing tracks")
    def _ratio(bpm: float) -> float:
        if not a.match_bpm:
            return 1.0
        r = a.match_bpm / bpm
        while r > 1.5:  # rekordbox meldet manchmal das halbe Tempo
            r /= 2.0
        while r < 0.75:
            r *= 2.0
        return r

    ratios = [_ratio(b) for _, b in listed]
    a.out.parent.mkdir(parents=True, exist_ok=True)

    # Jede Quelle erst einzeln auf 44,1 kHz Stereo-PCM bringen (und ggf.
    # strecken). Zehn gemischte Eingaenge (WAV 48 kHz + AIFF) direkt im
    # acrossfade-Graphen liessen ffmpeg mit 0xC00000FD abstuerzen. Die Dauer
    # wird an der gerenderten Datei gemessen, nicht hochgerechnet.
    work = a.out.parent / (a.out.name + "_src")
    work.mkdir(exist_ok=True)
    rendered: list[Path] = []
    for i, (t, r) in enumerate(zip(tracks, ratios)):
        target = work / f"{i:02d}.wav"
        stretch = ["-af", f"atempo={r:.6f}"] if abs(r - 1.0) > 1e-6 else []
        subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-i", str(t),
                        *stretch, "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(target)],
                       check=True)
        rendered.append(target)
    flac = a.out.with_suffix(".flac")
    durs = _crossfade_to_flac(rendered, a.xfade, flac)
    for p in rendered:
        p.unlink()
    work.rmdir()

    records, start, boundaries = [], 0.0, []
    for i, (t, d) in enumerate(zip(tracks, durs)):
        if i > 0:
            start -= a.xfade
            boundaries.append(round(start + a.xfade / 2, 3))
        m = LABEL.search(t.name)
        records.append({"order": i, "file": t.name, "sha256": sha256(t),
                        "rekordbox_bpm": listed[i][1] or None, "stretch": round(ratios[i], 6),
                        "duration": round(d, 3), "mix_start": round(start, 3),
                        "mix_end": round(start + d, 3),
                        "label_bpm": int(m.group(1)) if m else None,
                        "label_key": m.group("key").replace("_", " ") if m else None})
        start += d
    a.out.with_suffix(".boundaries.txt").write_text(
        "# crossfade midpoints, seconds, exact by construction\n"
        + "\n".join(f"{b:.3f}" for b in boundaries) + "\n", encoding="utf-8")
    a.out.with_suffix(".tracks.json").write_text(json.dumps(
        {"xfade_seconds": a.xfade, "match_bpm": a.match_bpm or None,
         "playlist": str(a.playlist), "skip": a.skip,
         "expected_duration": round(start, 3),
         "mix_sha256": sha256(flac), "tracks": records}, indent=2), encoding="utf-8")
    print(f"mix {flac} {start:.1f}s, {len(boundaries)} boundaries")


if __name__ == "__main__":
    main()
