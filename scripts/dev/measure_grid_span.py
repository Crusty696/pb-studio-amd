"""Wie lang traegt ein starres Beat-Raster?

Vorgeschichte: die erste Fassung dieser Messung (measure_rigid_grid_feasibility.py)
benutzte als Guetemass `mittlere Onset-Staerke an den Rasterpositionen / Gesamtmittel`.
Das Mass ist untauglich, weil es einen Dichte-Bias hat: ein duenneres Raster kann
selektiver auf Peaks sitzen. Gemessen an einer Datei, jeweils beste Phase:

    572.0 BPM -> 1.101      143.0 BPM -> 1.135       35.8 BPM -> 1.160
    286.0 BPM -> 1.122       71.5 BPM -> 1.163       17.9 BPM -> 1.370

Der Score steigt monoton mit sinkendem Tempo. Ein Vergleich zwischen Tempi war
damit wertlos - und genau darauf beruhte der Schluss "starres Raster sitzt
schlechter als beat_track". Dieser Schluss ist zurueckgezogen.

Hier stattdessen ein phasennormiertes Mass:

    kontrast = score(beste Phase) / mittelwert(score ueber alle Phasen)

Zaehler und Nenner haben dieselbe Punktzahl, der Dichte-Bias kuerzt sich weg.
Der Kontrast misst nur, ob sich EINE Phase abhebt - also ob an dieser Stelle
ueberhaupt ein Raster dieses Tempos sitzt.

Gemessene Frage: fuer welche Fensterlaenge traegt ein einziges starres Raster?
Ein Tempofehler laeuft linear mit der Zeit auf; ueber 120 s reichen schon
Bruchteile eines BPM, um die Phase am Fensterende um einen ganzen Beat zu
verschieben. Kurze Fenster muessten daher deutlich besser tragen - und wenn das
so ist, ist die Konsequenz fuer die App ein Raster aus mehreren Ankern statt
eines globalen Tempos, so wie DJ-Programme es halten.

Zwei Werte je Segment:
  contrast_fixed_tempo - Tempo hart auf der Dateinamen-BPM, zeigt die reine Drift
  contrast             - Tempo eng nachoptimiert, zeigt was mit gutem Tempo geht

Aufruf:
    python scripts/dev/measure_grid_span.py --dir "D:/beatport_tracks_2025-08" --out spans.json
    python scripts/dev/measure_grid_span.py --dir "..." --selftest
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
PHASE_STEPS = 64
MIN_POSITIONS = 8
SPANS = (8.0, 16.0, 30.0, 60.0, 120.0)
TEMPO_SEARCH_REL = 0.02
TEMPO_SEARCH_STEPS = 81
MAX_SEGMENTS_PER_SPAN = 6
AUDIO_EXTENSIONS = {".aiff", ".aif", ".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus"}

_BPM_IN_NAME = re.compile(r"_(\d{2,3})__")


@dataclass
class SpanResult:
    file: str
    sha256_16: str
    span_s: float
    segment_index: int
    segment_offset_s: float
    true_bpm: float
    grid_bpm: float
    tempo_offset_pct: float
    anchor_s: float
    positions: int
    contrast: float
    contrast_fixed_tempo: float


def _sha256_16(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _true_bpm(path: Path) -> float:
    match = _BPM_IN_NAME.search(path.name)
    if not match:
        return float("nan")
    value = float(match.group(1))
    return value * 2.0 if value < 90.0 else value


def _phase_scores(
    envelope: np.ndarray, times: np.ndarray, bpm: float, start: float, span: float
) -> np.ndarray:
    """Score fuer jede der PHASE_STEPS Phasen - gleiche Punktzahl, daher vergleichbar."""
    interval = 60.0 / bpm
    overall = float(np.mean(envelope))
    if overall <= 0 or interval <= 0:
        return np.zeros(0)
    scores = []
    for step in range(PHASE_STEPS):
        positions = np.arange(start + interval * step / PHASE_STEPS, start + span, interval)
        if len(positions) < MIN_POSITIONS:
            return np.zeros(0)
        scores.append(float(np.mean(np.interp(positions, times, envelope)) / overall))
    return np.asarray(scores)


def _contrast(scores: np.ndarray) -> tuple[float, int]:
    """Wie stark hebt sich die beste Phase vom Phasenmittel ab - dichteunabhaengig."""
    if scores.size == 0:
        return 0.0, 0
    mean = float(np.mean(scores))
    best = int(np.argmax(scores))
    return (float(scores[best] / mean) if mean > 0 else 0.0), best


def measure_file(path: Path) -> list[SpanResult]:
    true_bpm = _true_bpm(path)
    if not np.isfinite(true_bpm):
        return []
    duration = float(librosa.get_duration(path=str(path)))
    sha = _sha256_16(path)
    analysed = min(duration, 240.0)
    offset = max(0.0, (duration - analysed) / 2.0)
    audio, sr = librosa.load(
        str(path), sr=SAMPLE_RATE, mono=True, offset=offset, duration=analysed
    )
    envelope = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=HOP_LENGTH)
    times = librosa.times_like(envelope, sr=sr, hop_length=HOP_LENGTH)
    total = float(times[-1])

    tempo_grid = np.linspace(
        true_bpm * (1.0 - TEMPO_SEARCH_REL),
        true_bpm * (1.0 + TEMPO_SEARCH_REL),
        TEMPO_SEARCH_STEPS,
    )

    results: list[SpanResult] = []
    for span in SPANS:
        if total < span * 1.2:
            continue
        segment_count = min(MAX_SEGMENTS_PER_SPAN, int(total // span))
        for segment_index in range(segment_count):
            start = span * segment_index

            # a) Tempo hart auf der Dateinamen-BPM: zeigt die reine Driftwirkung.
            contrast_fixed, _ = _contrast(
                _phase_scores(envelope, times, true_bpm, start, span)
            )

            # b) Tempo eng nachoptimiert: zeigt, was mit gutem Tempo erreichbar ist.
            best_contrast = 0.0
            best_bpm = true_bpm
            best_anchor = 0.0
            for bpm in tempo_grid:
                scores = _phase_scores(envelope, times, float(bpm), start, span)
                contrast, phase = _contrast(scores)
                if contrast > best_contrast:
                    interval = 60.0 / float(bpm)
                    best_contrast = contrast
                    best_bpm = float(bpm)
                    best_anchor = interval * phase / PHASE_STEPS
            if best_contrast <= 0.0:
                continue

            results.append(
                SpanResult(
                    file=str(path),
                    sha256_16=sha,
                    span_s=span,
                    segment_index=segment_index,
                    segment_offset_s=round(offset + start, 2),
                    true_bpm=true_bpm,
                    grid_bpm=round(best_bpm, 4),
                    tempo_offset_pct=round(100.0 * (best_bpm - true_bpm) / true_bpm, 4),
                    anchor_s=round(best_anchor, 5),
                    positions=int(span / (60.0 / best_bpm)),
                    contrast=round(best_contrast, 5),
                    contrast_fixed_tempo=round(contrast_fixed, 5),
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
    parser.add_argument("--out", default="grid_span.json")
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
            "phase_steps": PHASE_STEPS,
            "spans_seconds": list(SPANS),
            "tempo_search_rel": TEMPO_SEARCH_REL,
            "tempo_search_steps": TEMPO_SEARCH_STEPS,
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
        payload["measurements"].extend(asdict(r) for r in rows)  # type: ignore[union-attr]
        print(f"[{index}/{len(files)}] {path.name}: {len(rows)} Messwerte", flush=True)

    Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nGeschrieben: {args.out} ({len(payload['measurements'])} Messwerte)")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
