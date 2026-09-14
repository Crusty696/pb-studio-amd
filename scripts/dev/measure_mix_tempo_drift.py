"""Wechselt in einem DJ-Mix das Tempo - und wie lang traegt ein Segment?

Offene Frage aus `2026-08-30-beatgrid-machbarkeit.md`: dort wurde gemessen, dass
ein starres Raster ueber 120 s genauso gut sitzt wie ueber 8 s. Diese Messung
lief aber auf **Originalen mit konstantem Tempo**, und der Schluss "Spanne egal"
ist ausdruecklich NICHT auf Mixe uebertragbar: ein Mix wechselt an jedem
Uebergang Tempo und Phase, und einzelne Tracks laufen hoch- oder
heruntergepitcht.

Hier wird dasselbe an echtem Mix-Material gemessen. Es gibt keine
Referenz-BPM - Mixe tragen keine im Dateinamen -, deshalb ist die Frage anders
gestellt:

  1. Wie stark schwankt das je Segment frei geschaetzte Tempo ueber den Mix?
     Ein konstantes Tempo waere ein flacher Verlauf; Uebergaenge muessten sich
     als Spruenge zeigen.
  2. Wie gut sitzt ein Raster, dessen Tempo aus dem GANZEN Mix stammt, gegen
     eines, dessen Tempo je Segment neu bestimmt wird? Die Differenz ist genau
     der Gewinn, den Segmentierung braechte.

Guetemass ist der phasennormierte Kontrast aus `measure_grid_span.py`:

    kontrast = score(beste Phase) / mittelwert(score ueber alle Phasen)

Zaehler und Nenner haben dieselbe Punktzahl, der Dichte-Bias kuerzt sich weg.
Die Tempo-Suche laeuft ueber das Tempogramm ohne den 120-BPM-Prior von librosa,
weil der die Schaetzung nachweislich auf wenige Attraktoren zieht.

Aufruf:
    python scripts/dev/measure_mix_tempo_drift.py --dir "C:/Users/david/Music" --out mix.json
    python scripts/dev/measure_mix_tempo_drift.py --dir "..." --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
SEGMENT_SECONDS = 30.0
PHASE_STEPS = 32
MIN_POSITIONS = 8
TEMPO_RANGE = (70.0, 190.0)
TEMPO_CANDIDATES = 4
REFINE_REL = 0.02
REFINE_STEPS = 41
MIN_DURATION = 300.0
MAX_SEGMENTS = 40
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aiff", ".aif", ".ogg", ".opus"}


@dataclass
class SegmentResult:
    file: str
    sha256_16: str
    duration_s: float
    segment_index: int
    segment_start_s: float
    # Tempo frei je Segment geschaetzt
    local_bpm: float
    local_contrast: float
    # Tempo aus dem ganzen Mix, nur die Phase je Segment neu gesetzt
    global_bpm: float
    global_contrast: float


def _sha256_16(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _phase_contrast(
    envelope: np.ndarray, times: np.ndarray, bpm: float, start: float, span: float
) -> float:
    """Wie stark hebt sich die beste Phase vom Phasenmittel ab - dichteunabhaengig."""
    interval = 60.0 / bpm
    overall = float(np.mean(envelope))
    if overall <= 0 or interval <= 0:
        return 0.0
    scores = []
    for step in range(PHASE_STEPS):
        positions = np.arange(start + interval * step / PHASE_STEPS, start + span, interval)
        if len(positions) < MIN_POSITIONS:
            return 0.0
        scores.append(float(np.mean(np.interp(positions, times, envelope)) / overall))
    array = np.asarray(scores)
    mean = float(np.mean(array))
    return float(np.max(array) / mean) if mean > 0 else 0.0


def _tempo_candidates(envelope: np.ndarray, sr: int) -> list[float]:
    """Tempo-Spitzen aus dem Tempogramm - ohne den 120-BPM-Prior von librosa."""
    tempogram = librosa.feature.tempogram(
        onset_envelope=envelope, sr=sr, hop_length=HOP_LENGTH
    )
    frequencies = librosa.tempo_frequencies(
        tempogram.shape[0], hop_length=HOP_LENGTH, sr=sr
    )
    strength = np.mean(tempogram, axis=1)
    usable = (frequencies >= TEMPO_RANGE[0]) & (frequencies <= TEMPO_RANGE[1])
    if not np.any(usable):
        return []
    order = np.argsort(strength[usable])[::-1]
    return [float(frequencies[usable][i]) for i in order[:TEMPO_CANDIDATES]]


def _best_tempo(
    envelope: np.ndarray, times: np.ndarray, start: float, span: float, sr: int,
    seed_candidates: list[float] | None = None,
) -> tuple[float, float]:
    """Bestes Tempo und sein Kontrast, mit feiner Nachoptimierung."""
    candidates = seed_candidates
    if candidates is None:
        lo = int(start * sr / HOP_LENGTH)
        hi = int((start + span) * sr / HOP_LENGTH)
        window = envelope[lo:hi]
        if window.size < 32:
            return 0.0, 0.0
        candidates = _tempo_candidates(window, sr)
    best = (0.0, 0.0)
    for candidate in candidates:
        for bpm in np.linspace(
            candidate * (1 - REFINE_REL), candidate * (1 + REFINE_REL), REFINE_STEPS
        ):
            contrast = _phase_contrast(envelope, times, float(bpm), start, span)
            if contrast > best[1]:
                best = (float(bpm), contrast)
    return best


def measure_file(path: Path) -> list[SegmentResult]:
    duration = float(librosa.get_duration(path=str(path)))
    if duration < MIN_DURATION:
        return []
    sha = _sha256_16(path)
    audio, sr = librosa.load(str(path), sr=SAMPLE_RATE, mono=True)
    envelope = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=HOP_LENGTH)
    times = librosa.times_like(envelope, sr=sr, hop_length=HOP_LENGTH)
    total = float(times[-1])
    del audio

    # Ein Tempo fuer den ganzen Mix - der heutige Produktionsansatz.
    global_candidates = _tempo_candidates(envelope, sr)
    if not global_candidates:
        return []
    global_bpm = global_candidates[0]

    results: list[SegmentResult] = []
    count = min(MAX_SEGMENTS, int(total // SEGMENT_SECONDS))
    for index in range(count):
        start = SEGMENT_SECONDS * index
        local_bpm, local_contrast = _best_tempo(
            envelope, times, start, SEGMENT_SECONDS, sr
        )
        if local_bpm <= 0:
            continue
        # Globales Tempo, nur Phase je Segment neu - so verhaelt sich ein
        # einziges Raster ueber den ganzen Mix.
        global_contrast = _phase_contrast(
            envelope, times, global_bpm, start, SEGMENT_SECONDS
        )
        results.append(
            SegmentResult(
                file=str(path), sha256_16=sha, duration_s=round(duration, 2),
                segment_index=index, segment_start_s=round(start, 2),
                local_bpm=round(local_bpm, 4),
                local_contrast=round(local_contrast, 5),
                global_bpm=round(global_bpm, 4),
                global_contrast=round(global_contrast, 5),
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
    parser.add_argument("--out", default="mix_tempo_drift.json")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    files = _collect(args)
    if not files:
        print("Keine Audiodateien gefunden.", file=sys.stderr)
        return 2

    if args.selftest:
        for candidate in files:
            rows = measure_file(candidate)
            if rows:
                again = measure_file(candidate)
                print(f"Selbsttest auf {candidate.name}: {len(rows)} Segmente")
                same = [asdict(r) for r in rows] == [asdict(r) for r in again]
                print("REPRODUZIERBAR" if same else "NICHT REPRODUZIERBAR")
                return 0 if same else 1
        print("Keine Datei lang genug fuer den Selbsttest.", file=sys.stderr)
        return 2

    payload: dict[str, object] = {
        "schema_version": 1,
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "librosa": librosa.__version__,
        },
        "parameters": {
            "sample_rate": SAMPLE_RATE, "hop_length": HOP_LENGTH,
            "segment_seconds": SEGMENT_SECONDS, "phase_steps": PHASE_STEPS,
            "tempo_range": list(TEMPO_RANGE), "refine_rel": REFINE_REL,
            "min_duration_seconds": MIN_DURATION,
            "measure": "contrast = best-phase score / mean score over all phases",
        },
        "measurements": [],
    }
    for index, path in enumerate(files, start=1):
        try:
            rows = measure_file(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[{index}/{len(files)}] FEHLER {path.name}: {exc}", file=sys.stderr)
            continue
        if not rows:
            continue
        payload["measurements"].extend(asdict(r) for r in rows)  # type: ignore[union-attr]
        print(f"[{index}/{len(files)}] {path.name}: {len(rows)} Segmente", flush=True)

    Path(args.out).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nGeschrieben: {args.out} ({len(payload['measurements'])} Segmente)")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
