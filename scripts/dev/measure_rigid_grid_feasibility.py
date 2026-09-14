"""Misst, ob ein starres Beatgrid besser auf der Musik sitzt als beat_track.

Ausgangslage: `librosa.beat.beat_track()` liefert in 33.7 % der Fenster ein
Tempo, das in keinem einfachen Verhaeltnis zur Wahrheit steht, und ein
Tempo-Prior richtet das nicht (selbst die wahre BPM als start_bpm: 45.2 %
korrekt). Siehe docs/measurements/2026-08-30-tempo-strategien.json.

Naechste Frage, vor jedem Bau: taugt der Ansatz "starres Raster", den
professionelle DJ-Software verwendet? Ein Grid ist dort Tempo + Anker, nicht
eine Liste einzeln gesuchter Beats.

VERFAHREN, bewusst ohne Referenz-Beatzeiten (die es fuer dieses Material nicht
gibt), dafuer mit einem Mass, das auch fuer DJ-Mixe gilt:

  Guete eines Rasters = mittlere Onset-Staerke an den Rasterpositionen,
  normiert auf die mittlere Onset-Staerke ueberhaupt.

  1.0 = das Raster sitzt auf durchschnittlichem Material, traegt also nichts.
  > 1 = die Rasterpositionen fallen ueberdurchschnittlich auf Anschlaege.

Verglichen werden auf DEMSELBEN Onset-Envelope:

  beat_track   die Beats, die heute in Produktion entstehen
  rigid_scan   Tempo aus dem Tempogramm (mehrere Kandidaten, KEIN 120-BPM-Prior),
               Anker durch feines Abtasten der Phase, starres Raster
  rigid_true   dasselbe, aber Tempo auf die wahre BPM festgenagelt

Ein Tempo-Shift, wie er in DJ-Mixen vorkommt (Track laeuft schneller oder
langsamer als das Original), ist hier ausdruecklich zugelassen: `rigid_scan`
bekommt die wahre BPM NICHT und muss das Tempo selbst finden. `rigid_true`
zeigt, was ein perfekt bekanntes Tempo brauechte - und ist deshalb fuer Mixe
NICHT die Referenz, sondern nur die Obergrenze fuer unveraenderte Originale.

Aufruf:
    python scripts/dev/measure_rigid_grid_feasibility.py --dir "D:/beatport_tracks_2025-08" --out grid.json
    python scripts/dev/measure_rigid_grid_feasibility.py --dir "..." --limit 2 --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

import librosa  # noqa: E402

SAMPLE_RATE = 22050
HOP_LENGTH = 512
WINDOW_SECONDS = 120.0
MIN_BEATS = 32
TEMPO_RANGE = (60.0, 200.0)     # plausibler Bereich fuer elektronische Musik
TEMPO_CANDIDATES = 6            # Spitzen im Tempogramm
PHASE_STEPS = 200               # Aufloesung der Ankersuche innerhalb eines Beats
AUDIO_EXTENSIONS = {".aiff", ".aif", ".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus"}

_BPM_IN_NAME = re.compile(r"_(\d{2,3})__")


@dataclass
class GridResult:
    file: str
    sha256_16: str
    window_index: int
    window_offset_s: float
    true_bpm: float
    method: str
    grid_bpm: float
    anchor_s: float
    onset_score: float          # mittlere Onset-Staerke am Raster / Gesamtmittel
    beat_count: int
    folded_true: float
    folded_grid: float
    tempo_correct_2pct: bool


def _sha256_16(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _bpm_from_filename(path: Path) -> float:
    match = _BPM_IN_NAME.search(path.name)
    return float(match.group(1)) if match else float("nan")


def _fold(bpm: float, low: float = 90.0) -> float:
    if not np.isfinite(bpm) or bpm <= 0:
        return float("nan")
    value = float(bpm)
    while value < low:
        value *= 2.0
    while value >= 2.0 * low:
        value /= 2.0
    return value


def _window_offsets(duration: float) -> list[float]:
    if duration <= WINDOW_SECONDS * 1.5:
        return [0.0]
    usable = duration - WINDOW_SECONDS
    count = min(3, max(1, int(usable // WINDOW_SECONDS) + 1))
    if count == 1:
        return [usable / 2.0]
    return [usable * index / (count - 1) for index in range(count)]


def _score_grid(
    envelope: np.ndarray,
    times: np.ndarray,
    bpm: float,
    anchor: float,
    span: float,
) -> tuple[float, int]:
    """Mittlere Onset-Staerke an den Rasterpositionen, normiert aufs Gesamtmittel."""
    if bpm <= 0:
        return 0.0, 0
    interval = 60.0 / bpm
    positions = np.arange(anchor, span, interval)
    if len(positions) < MIN_BEATS:
        return 0.0, len(positions)
    sampled = np.interp(positions, times, envelope)
    overall = float(np.mean(envelope))
    if overall <= 0:
        return 0.0, len(positions)
    return float(np.mean(sampled) / overall), len(positions)


def _best_anchor(
    envelope: np.ndarray, times: np.ndarray, bpm: float, span: float
) -> tuple[float, float, int]:
    """Feine Ankersuche ueber genau ein Beat-Intervall."""
    interval = 60.0 / bpm
    best = (0.0, 0.0, 0)
    for step in range(PHASE_STEPS):
        anchor = interval * step / PHASE_STEPS
        score, count = _score_grid(envelope, times, bpm, anchor, span)
        if score > best[1]:
            best = (anchor, score, count)
    return best


def _tempo_candidates(envelope: np.ndarray, sr: int) -> list[float]:
    """Tempo-Spitzen aus dem Tempogramm - ohne den 120-BPM-Prior von librosa."""
    tempogram = librosa.feature.tempogram(
        onset_envelope=envelope, sr=sr, hop_length=HOP_LENGTH
    )
    frequencies = librosa.tempo_frequencies(tempogram.shape[0], hop_length=HOP_LENGTH, sr=sr)
    strength = np.mean(tempogram, axis=1)
    usable = (frequencies >= TEMPO_RANGE[0]) & (frequencies <= TEMPO_RANGE[1])
    if not np.any(usable):
        return []
    order = np.argsort(strength[usable])[::-1]
    return [float(frequencies[usable][i]) for i in order[:TEMPO_CANDIDATES]]


def measure_file(path: Path) -> list[GridResult]:
    duration = float(librosa.get_duration(path=str(path)))
    true_bpm = _bpm_from_filename(path)
    sha = _sha256_16(path)
    results: list[GridResult] = []

    for window_index, offset in enumerate(_window_offsets(duration)):
        offset = max(0.0, offset)
        length = WINDOW_SECONDS if duration > WINDOW_SECONDS * 1.5 else duration
        audio, sr = librosa.load(
            str(path), sr=SAMPLE_RATE, mono=True, offset=offset, duration=length
        )
        if audio.size < sr * 5:
            continue
        envelope = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=HOP_LENGTH)
        times = librosa.frames_to_time(
            np.arange(len(envelope)), sr=sr, hop_length=HOP_LENGTH
        )
        span = float(times[-1])
        overall = float(np.mean(envelope))

        def emit(method: str, bpm: float, anchor: float, score: float, count: int) -> None:
            ft, fg = _fold(true_bpm), _fold(bpm)
            results.append(
                GridResult(
                    file=str(path), sha256_16=sha, window_index=window_index,
                    window_offset_s=round(offset, 2), true_bpm=true_bpm, method=method,
                    grid_bpm=round(bpm, 3), anchor_s=round(anchor, 4),
                    onset_score=round(score, 4), beat_count=count,
                    folded_true=round(ft, 3) if np.isfinite(ft) else float("nan"),
                    folded_grid=round(fg, 3) if np.isfinite(fg) else float("nan"),
                    tempo_correct_2pct=bool(
                        np.isfinite(ft) and np.isfinite(fg) and abs(fg - ft) / ft <= 0.02
                    ),
                )
            )

        # 1) Was heute herauskommt
        tempo, frames = librosa.beat.beat_track(
            onset_envelope=envelope, sr=sr, hop_length=HOP_LENGTH
        )
        beats = librosa.frames_to_time(frames, sr=sr, hop_length=HOP_LENGTH)
        if len(beats) >= MIN_BEATS and overall > 0:
            score = float(np.mean(np.interp(beats, times, envelope)) / overall)
            emit("beat_track", float(np.atleast_1d(tempo)[0]), float(beats[0]), score, len(beats))

        # 2) Starres Raster, Tempo selbst gesucht
        best = (0.0, 0.0, 0.0, 0)
        for candidate in _tempo_candidates(envelope, sr):
            anchor, score, count = _best_anchor(envelope, times, candidate, span)
            if score > best[1]:
                best = (candidate, score, anchor, count)
        if best[1] > 0:
            emit("rigid_scan", best[0], best[2], best[1], best[3])

        # 3) Starres Raster mit wahrem Tempo - Obergrenze fuer unveraenderte Originale
        if np.isfinite(true_bpm):
            forced = true_bpm if true_bpm >= 90 else true_bpm * 2
            anchor, score, count = _best_anchor(envelope, times, forced, span)
            if score > 0:
                emit("rigid_true", forced, anchor, score, count)
    return results


def _collect(args: argparse.Namespace) -> list[Path]:
    paths: list[Path] = []
    if args.dir:
        for candidate in sorted(Path(args.dir).rglob("*")):
            if candidate.is_file() and candidate.suffix.lower() in AUDIO_EXTENSIONS:
                paths.append(candidate)
    paths.extend(Path(f) for f in (args.files or []))
    unique = sorted({p.resolve() for p in paths if p.exists()})
    return unique[: args.limit] if args.limit else unique


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir")
    parser.add_argument("--files", nargs="*", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", default="rigid_grid.json")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    files = _collect(args)
    if not files:
        print("Keine Audiodateien gefunden.", file=sys.stderr)
        return 2

    if args.selftest:
        first = files[0]
        a = [asdict(r) for r in measure_file(first)]
        b = [asdict(r) for r in measure_file(first)]
        print(f"Selbsttest auf {first.name}: {len(a)} Messwerte")
        print("REPRODUZIERBAR" if a == b else "NICHT REPRODUZIERBAR")
        return 0 if a == b else 1

    payload: dict[str, object] = {
        "schema_version": 1,
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "librosa": librosa.__version__,
        },
        "parameters": {
            "sample_rate": SAMPLE_RATE, "hop_length": HOP_LENGTH,
            "window_seconds": WINDOW_SECONDS, "min_beats": MIN_BEATS,
            "tempo_range": TEMPO_RANGE, "tempo_candidates": TEMPO_CANDIDATES,
            "phase_steps": PHASE_STEPS,
        },
        "measurements": [],
    }
    for index, path in enumerate(files, start=1):
        try:
            rows = measure_file(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[{index}/{len(files)}] FEHLER {path.name}: {exc}", file=sys.stderr)
            continue
        payload["measurements"].extend(asdict(r) for r in rows)  # type: ignore[union-attr]
        print(f"[{index}/{len(files)}] {path.name}: {len(rows)} Messwerte", flush=True)

    Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nGeschrieben: {args.out} ({len(payload['measurements'])} Messwerte)")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
