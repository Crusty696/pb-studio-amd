"""Misst, ob ein Tempo-Prior das Beat-Raster verlaesslich richtet.

Ausgangslage (siehe docs/measurements/2026-08-30-downbeat-ableitung-befund.md):
gegen die BPM im Beatport-Dateinamen gemessen steht das von
`librosa.beat.beat_track()` erkannte Tempo in 33.7 % der Fenster in keinem
einfachen Verhaeltnis zur Wahrheit. Ueber 104 Fenster gab es nur sechs
verschiedene erkannte Werte.

Verdacht: `beat_track` baut seinen Prior aus `start_bpm=120` mit sehr enger
Streuung; Stuecke abseits von 120 BPM werden dorthin gezogen.

Dieses Werkzeug vergleicht Strategien auf demselben Audio und demselben
Onset-Envelope, damit der Unterschied wirklich am Tempo-Prior liegt und nicht
an der Vorverarbeitung:

  A default        beat_track()                          - heutiger Produktionsstand
  B track_prior    Tempo einmal ueber den ganzen Track schaetzen,
                   als start_bpm ins Fenster geben       - in Produktion machbar
  C track_fixed    dasselbe Tempo hart als bpm=          - in Produktion machbar
  D wide_prior     beat_track mit breitem Prior          - in Produktion machbar
  E oracle_start   start_bpm = wahre BPM                 - NICHT verfuegbar, Obergrenze
  F oracle_fixed   bpm = wahre BPM                       - NICHT verfuegbar, Obergrenze

Die beiden Orakel sind bewusst dabei: liefern sie kein gutes Raster, liegt es
nicht am Prior, und ein Prior kann das Problem grundsaetzlich nicht loesen.

Wahrheit: BPM aus dem Dateinamen (Beatport-Schema `_143__`). Verglichen wird
oktavnormiert, weil 70 und 140 dieselbe Musik meinen.

Aufruf:
    python scripts/dev/measure_tempo_strategies.py --dir "D:/beatport_tracks_2025-08" --out tempo.json
    python scripts/dev/measure_tempo_strategies.py --dir "..." --selftest
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
import scipy.stats  # noqa: E402

SAMPLE_RATE = 22050
HOP_LENGTH = 512
WINDOW_SECONDS = 120.0
MIN_BEATS = 32
AUDIO_EXTENSIONS = {".aiff", ".aif", ".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus"}

_BPM_IN_NAME = re.compile(r"_(\d{2,3})__")


@dataclass
class StrategyResult:
    file: str
    sha256_16: str
    duration_s: float
    window_index: int
    window_offset_s: float
    true_bpm: float
    strategy: str
    available_in_production: bool
    detected_bpm: float
    folded_true: float
    folded_detected: float
    relative_error: float
    correct_within_2pct: bool
    beat_count: int
    first_beat_abs_s: float
    median_interval_s: float


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
    """Auf ein Oktavband [low, 2*low) falten - 70 und 140 meinen dieselbe Musik."""
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


def _scalar(value) -> float:
    return float(np.atleast_1d(value)[0])


def _track_tempo(path: Path, duration: float) -> float:
    """Ein Tempo fuer den ganzen Track - das, was Produktion vorschalten koennte.

    Bewusst mit breitem Prior (std_bpm=4) statt der librosa-Vorgabe 1.0, die
    Stuecke abseits von 120 BPM zu 120 hin zieht.
    """
    span = min(duration, 240.0)
    offset = max(0.0, (duration - span) / 2.0)
    audio, sr = librosa.load(str(path), sr=SAMPLE_RATE, mono=True, offset=offset, duration=span)
    envelope = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=HOP_LENGTH)
    estimate = librosa.feature.tempo(
        onset_envelope=envelope, sr=sr, hop_length=HOP_LENGTH,
        start_bpm=120.0, std_bpm=4.0, aggregate=np.median,
    )
    return _scalar(estimate)


def measure_file(path: Path) -> list[StrategyResult]:
    duration = float(librosa.get_duration(path=str(path)))
    true_bpm = _bpm_from_filename(path)
    sha = _sha256_16(path)
    track_bpm = _track_tempo(path, duration)
    results: list[StrategyResult] = []

    for window_index, offset in enumerate(_window_offsets(duration)):
        offset = max(0.0, offset)
        length = WINDOW_SECONDS if duration > WINDOW_SECONDS * 1.5 else duration
        audio, sr = librosa.load(
            str(path), sr=SAMPLE_RATE, mono=True, offset=offset, duration=length
        )
        if audio.size < sr * 5:
            continue
        # EIN Onset-Envelope fuer alle Strategien: der Unterschied soll am
        # Tempo-Prior liegen, nicht an der Vorverarbeitung.
        envelope = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=HOP_LENGTH)

        wide = scipy.stats.lognorm(loc=np.log(120.0), scale=120.0, s=1.0)
        strategies: dict[str, tuple[dict, bool]] = {
            "A_default": ({}, True),
            "B_track_prior": ({"start_bpm": track_bpm}, True),
            "C_track_fixed": ({"bpm": track_bpm}, True),
            "D_wide_prior": ({"prior": wide}, True),
            "E_oracle_start": ({"start_bpm": true_bpm if true_bpm >= 90 else true_bpm * 2}, False),
            "F_oracle_fixed": ({"bpm": true_bpm if true_bpm >= 90 else true_bpm * 2}, False),
        }

        for name, (kwargs, available) in strategies.items():
            if not np.isfinite(true_bpm) and name.startswith(("E_", "F_")):
                continue
            try:
                tempo, frames = librosa.beat.beat_track(
                    onset_envelope=envelope, sr=sr, hop_length=HOP_LENGTH, **kwargs
                )
            except Exception:  # noqa: BLE001 - eine Strategie darf den Lauf nicht stoppen
                continue
            beats = librosa.frames_to_time(frames, sr=sr, hop_length=HOP_LENGTH)
            if len(beats) < MIN_BEATS:
                continue
            detected = _scalar(tempo)
            ft, fd = _fold(true_bpm), _fold(detected)
            rel = abs(fd - ft) / ft if np.isfinite(ft) and ft > 0 else float("nan")
            results.append(
                StrategyResult(
                    file=str(path),
                    sha256_16=sha,
                    duration_s=round(duration, 2),
                    window_index=window_index,
                    window_offset_s=round(offset, 2),
                    true_bpm=true_bpm,
                    strategy=name,
                    available_in_production=available,
                    detected_bpm=round(detected, 3),
                    folded_true=round(ft, 3) if np.isfinite(ft) else float("nan"),
                    folded_detected=round(fd, 3) if np.isfinite(fd) else float("nan"),
                    relative_error=round(rel, 5) if np.isfinite(rel) else float("nan"),
                    correct_within_2pct=bool(np.isfinite(rel) and rel <= 0.02),
                    beat_count=len(beats),
                    first_beat_abs_s=round(offset + float(beats[0]), 4),
                    median_interval_s=round(float(np.median(np.diff(beats))), 6),
                )
            )
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
    parser.add_argument("--out", default="tempo_strategies.json")
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
            "sample_rate": SAMPLE_RATE,
            "hop_length": HOP_LENGTH,
            "window_seconds": WINDOW_SECONDS,
            "min_beats": MIN_BEATS,
            "fold_low_bpm": 90.0,
            "correct_tolerance": 0.02,
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
