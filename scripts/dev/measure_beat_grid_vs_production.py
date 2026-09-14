"""Stellt den Beatgrid-Estimator dem heutigen Produktionspfad gegenueber.

`src/pb_studio/audio/beat_grid.py` ist bisher nur an synthetischen Klickspuren
geprueft. Bevor er verdrahtet wird, muss er an echter Musik gegen das antreten,
was heute laeuft:

  Produktion   librosa.beat_track auf 22050 Hz (wie BeatDetector._detect_beats_librosa)
  Estimator    estimate_beat_grid - Tempogramm ohne 120-BPM-Prior, feine
               Nachoptimierung, verpflichtende Oktavpruefung gegen Kick-Zeiten

Wahrheit ist die BPM im Beatport-Dateinamen (Schema `_143__`), oktavnormiert
mit 2 % Toleranz. Referenzwert aus der frueheren Messung: der Produktionspfad
trifft das Tempo in 39,4 % der Fenster und liefert ueber 104 Fenster nur sechs
verschiedene BPM-Werte.

Zusaetzlich zum Tempo wird die Rasterlage gemessen - ein richtiges Tempo mit
falscher Phase nuetzt nichts. Mass ist der phasennormierte Kontrast, wie in
`measure_grid_span.py`.

Aufruf:
    python scripts/dev/measure_beat_grid_vs_production.py --dir "D:/beatport_tracks_2025-08" --out vergleich.json
    python scripts/dev/measure_beat_grid_vs_production.py --dir "..." --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

import librosa  # noqa: E402

from pb_studio.audio.band_params import KICK_BAND, band_stft_params  # noqa: E402
from pb_studio.audio.beat_grid import estimate_beat_grid  # noqa: E402

SAMPLE_RATE = 22050
HOP_LENGTH = 512
WINDOW_SECONDS = 120.0
MIN_BEATS = 32
PHASE_STEPS = 64
TEMPO_TOLERANCE = 0.02
AUDIO_EXTENSIONS = {".aiff", ".aif", ".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus"}

_BPM_IN_NAME = re.compile(r"_(\d{2,3})__")


@dataclass
class ComparisonResult:
    file: str
    sha256_16: str
    window_index: int
    window_offset_s: float
    true_bpm: float
    method: str
    detected_bpm: float
    folded_true: float
    folded_detected: float
    tempo_ratio: float
    tempo_correct: bool
    grid_contrast: float
    seconds: float
    status: str
    kick_recall: float | None
    kick_precision: float | None


def _sha256_16(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _true_bpm(path: Path) -> float:
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
    if duration <= WINDOW_SECONDS * 1.2:
        return [0.0]
    return [WINDOW_SECONDS * i for i in range(int(duration // WINDOW_SECONDS))][:6]


def _kick_times(audio: np.ndarray, sr: int) -> list[float]:
    """Kick-Kette wie im Router - gemeinsame Bandparameter."""
    n_fft, n_mels = band_stft_params(sr, *KICK_BAND)
    envelope = librosa.onset.onset_strength(
        y=librosa.effects.preemphasis(audio), sr=sr, hop_length=HOP_LENGTH,
        aggregate=np.median, fmin=KICK_BAND[0], fmax=KICK_BAND[1],
        n_fft=n_fft, n_mels=n_mels,
    )
    frames = librosa.onset.onset_detect(
        onset_envelope=envelope, sr=sr, hop_length=HOP_LENGTH
    )
    return librosa.frames_to_time(frames, sr=sr, hop_length=HOP_LENGTH).tolist()


def _grid_contrast(envelope, times, bpm: float, anchor: float, span: float) -> float:
    """Phasennormierter Kontrast eines Rasters - dichteunabhaengig."""
    if bpm <= 0:
        return 0.0
    interval = 60.0 / bpm
    overall = float(np.mean(envelope))
    if overall <= 0:
        return 0.0
    scores = []
    for step in range(PHASE_STEPS):
        positions = np.arange(interval * step / PHASE_STEPS, span, interval)
        if len(positions) < 8:
            return 0.0
        scores.append(float(np.mean(np.interp(positions, times, envelope)) / overall))
    array = np.asarray(scores)
    mean = float(np.mean(array))
    if mean <= 0:
        return 0.0
    # Kontrast an der TATSAECHLICH gewaehlten Phase, nicht an der besten -
    # sonst misst man das Optimum statt das Ergebnis.
    own = np.arange(anchor % interval, span, interval)
    if len(own) < 8:
        return 0.0
    own_score = float(np.mean(np.interp(own, times, envelope)) / overall)
    return own_score / mean


def measure_file(path: Path) -> list[ComparisonResult]:
    true_bpm = _true_bpm(path)
    if not np.isfinite(true_bpm):
        return []
    duration = float(librosa.get_duration(path=str(path)))
    sha = _sha256_16(path)
    results: list[ComparisonResult] = []

    for window_index, offset in enumerate(_window_offsets(duration)):
        length = min(WINDOW_SECONDS, duration - offset)
        if length < 30.0:
            continue
        audio, sr = librosa.load(
            str(path), sr=SAMPLE_RATE, mono=True, offset=offset, duration=length
        )
        if audio.size < sr * 5:
            continue
        envelope = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=HOP_LENGTH)
        times = librosa.times_like(envelope, sr=sr, hop_length=HOP_LENGTH)
        span = float(times[-1])
        kicks = _kick_times(audio, sr)
        folded_true = _fold(true_bpm)

        def emit(method, bpm, anchor, seconds, status, recall, precision):
            folded = _fold(bpm)
            ratio = folded / folded_true if folded_true > 0 else float("nan")
            results.append(
                ComparisonResult(
                    file=str(path), sha256_16=sha, window_index=window_index,
                    window_offset_s=round(offset, 2), true_bpm=true_bpm,
                    method=method, detected_bpm=round(float(bpm), 4),
                    folded_true=round(folded_true, 3),
                    folded_detected=round(folded, 3) if np.isfinite(folded) else float("nan"),
                    tempo_ratio=round(ratio, 5) if np.isfinite(ratio) else float("nan"),
                    tempo_correct=bool(
                        np.isfinite(ratio) and abs(ratio - 1.0) <= TEMPO_TOLERANCE
                    ),
                    grid_contrast=round(
                        _grid_contrast(envelope, times, bpm, anchor, span), 5
                    ),
                    seconds=round(seconds, 3), status=status,
                    kick_recall=recall, kick_precision=precision,
                )
            )

        # 1) Heutiger Produktionspfad
        started = time.perf_counter()
        tempo, frames = librosa.beat.beat_track(y=audio, sr=sr, hop_length=HOP_LENGTH)
        beats = librosa.frames_to_time(frames, sr=sr, hop_length=HOP_LENGTH)
        elapsed = time.perf_counter() - started
        if len(beats) >= MIN_BEATS:
            emit("production_beat_track", float(np.atleast_1d(tempo)[0]),
                 float(beats[0]), elapsed, "n/a", None, None)

        # 2) Estimator
        started = time.perf_counter()
        grid = estimate_beat_grid(audio, sr, kick_times=kicks)
        elapsed = time.perf_counter() - started
        emit("beat_grid_estimator", grid.bpm, grid.anchor_s, elapsed,
             grid.status, grid.kick_recall, grid.kick_precision)

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
    parser.add_argument("--out", default="beat_grid_comparison.json")
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
        # Laufzeiten unterscheiden sich zwangslaeufig - sie sind kein Ergebnis.
        for rows in (a, b):
            for row in rows:
                row.pop("seconds", None)
        print(f"Selbsttest auf {first.name}: {len(a)} Messwerte")
        print("REPRODUZIERBAR" if a == b else "NICHT REPRODUZIERBAR")
        return 0 if a == b else 1

    payload: dict[str, object] = {
        "schema_version": 1,
        "environment": {
            "python": sys.version.split()[0], "numpy": np.__version__,
            "librosa": librosa.__version__,
        },
        "parameters": {
            "sample_rate": SAMPLE_RATE, "hop_length": HOP_LENGTH,
            "window_seconds": WINDOW_SECONDS, "tempo_tolerance": TEMPO_TOLERANCE,
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

    Path(args.out).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nGeschrieben: {args.out} ({len(payload['measurements'])} Messwerte)")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
