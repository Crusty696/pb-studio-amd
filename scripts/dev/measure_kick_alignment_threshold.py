"""Kalibriert die Kick-Gegenprobe des Beat-Rasters an echtem Material.

Hintergrund: `_evaluate_beat_grid` (backend/routers/audio_router.py) prueft das
Beat-Raster gegen die unabhaengig gewonnenen `kick_times` und meldet es als
`suspect`, wenn weniger als `_BEAT_GRID_KICK_ALIGNMENT_MIN` der Kicks nahe an
einer Beat-Position liegen. Diese Schwelle steht auf 0.75 und war beim Einbau
ausdruecklich NICHT aus Messdaten kalibriert, sondern als Mittelpunkt zwischen
zwei Erwartungen gesetzt: korrektes Raster ~1.0, Halbtempo-Raster ~0.5.

Dieses Werkzeug misst, ob dieser Wert an echtem Material trennt.

Aufbau: fuer jedes Fenster wird
  * das Beat-Raster ueber den Produktionspfad bestimmt (librosa.beat_track auf
    22050 Hz, wie `BeatDetector._detect_beats_librosa`),
  * die Kick-Kette wie im Router aufgebaut (gemeinsame Bandparameter),
  * `_evaluate_beat_grid` mit genau diesen Daten aufgerufen - die echte
    Produktionsfunktion, keine Nachbildung,
  * die Wahrheit aus der Dateinamen-BPM abgeleitet (Beatport-Schema `_143__`),
    oktavnormiert und mit 2 % Toleranz.

Damit laesst sich fragen: trennt `kick_alignment` die Faelle mit korrekt
erkanntem Tempo von denen mit falschem? Und wo laege die beste Schwelle?

Bekannte Grenze, die diese Messung NICHT aufheben kann: ein um Faktor zwei zu
schnelles Raster enthaelt die wahren Beats als Teilmenge und trifft die Kicks
weiterhin zu ~100 %. Die Gegenprobe faengt Halbtempo, nicht Doppeltempo.

WARNUNG: der Import von `backend.routers.audio_router` zieht den
Recovery-Bootstrap. Dieses Werkzeug NICHT parallel zu einem pytest-Lauf
starten. Es meldet die DB-Zaehlstaende vor und nach dem Lauf.

Aufruf:
    python scripts/dev/measure_kick_alignment_threshold.py --dir "D:/beatport_tracks_2025-08" --out kick.json
    python scripts/dev/measure_kick_alignment_threshold.py --dir "..." --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "src", REPO_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import librosa  # noqa: E402

from pb_studio.audio.band_params import KICK_BAND, band_stft_params  # noqa: E402

SAMPLE_RATE = 22050
HOP_LENGTH = 512
WINDOW_SECONDS = 120.0
MIN_BEATS = 32
TEMPO_TOLERANCE = 0.02
# Toleranz-Sweep in Hop-Frames (1 Frame = 512/22050 = 23,2 ms).
# Produktion steht auf 3.
TOLERANCE_FRAMES = (1, 2, 3, 4, 6)
AUDIO_EXTENSIONS = {".aiff", ".aif", ".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus"}

_BPM_IN_NAME = re.compile(r"_(\d{2,3})__")


@dataclass
class AlignmentResult:
    file: str
    sha256_16: str
    window_index: int
    window_offset_s: float
    true_bpm: float
    detected_bpm: float
    folded_true: float
    folded_detected: float
    tempo_ratio: float
    tempo_correct: bool
    beat_count: int
    kick_count: int
    kick_alignment: float | None
    interval_regularity: float | None
    regular: bool | None
    tolerance_seconds: float | None
    status: str
    kick_cross_check: str
    # Gegenvorschlag zur reinen Trefferquote: dieselbe Quote, aber normiert
    # gegen phasenverschobene Raster desselben Tempos. Der absolute Anteil
    # haengt stark davon ab, wie viele der detektierten "Kicks" ueberhaupt
    # Kicks sind; der Quotient kuerzt diesen Basisanteil weg.
    alignment_contrast: float | None
    null_alignment_mean: float | None
    # Trefferquote und Zufallserwartung je Toleranz, in Hop-Frames gemessen.
    # Die Produktionstoleranz von 3 Frames (69,7 ms) deckt bei 143 BPM ein
    # Drittel der Zeitachse ab - so viel trifft bereits per Zufall. Ohne diesen
    # Sweep laesst sich nicht sagen, ob die Gegenprobe grundsaetzlich taugt
    # oder nur zu grob eingestellt ist.
    alignment_by_frames: dict[str, float]
    null_by_frames: dict[str, float]


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
    """Nicht ueberlappende Fenster - sonst zaehlt dieselbe Stelle mehrfach."""
    if duration <= WINDOW_SECONDS * 1.2:
        return [0.0]
    return [WINDOW_SECONDS * index for index in range(int(duration // WINDOW_SECONDS))][:6]


def _kick_times(audio: np.ndarray, sr: int) -> list[float]:
    """Kick-Kette wie im Router - gemeinsame Bandparameter, gleiche Reihenfolge."""
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


def _alignment_at(beats: np.ndarray, kicks: np.ndarray, tolerance: float) -> float:
    """Anteil der Kicks, die naeher als `tolerance` an einer Beat-Position liegen."""
    if beats.size == 0 or kicks.size == 0:
        return 0.0
    idx = np.searchsorted(beats, kicks)
    left = np.clip(idx - 1, 0, beats.size - 1)
    right = np.clip(idx, 0, beats.size - 1)
    distance = np.minimum(np.abs(kicks - beats[left]), np.abs(kicks - beats[right]))
    return float(np.mean(distance <= tolerance))


def _alignment_contrast(
    beats: list[float], kicks: list[float], tolerance: float, steps: int = 16
) -> tuple[float | None, float | None]:
    """Trefferquote des echten Rasters gegen die phasenverschobener Raster.

    Die Null verschiebt dasselbe Raster ueber ein volles Beat-Intervall. Sie
    erhaelt Tempo und Gleichmaessigkeit und zerstoert nur die Ausrichtung -
    genau die Eigenschaft, die geprueft werden soll. Der Quotient ist damit
    unabhaengig davon, wie gross der Anteil echter Kicks unter den detektierten
    Onsets ist.
    """
    if len(beats) < 2 or not kicks:
        return None, None
    grid = np.asarray(sorted(beats), dtype=np.float64)
    hits = np.asarray(sorted(kicks), dtype=np.float64)
    interval = float(np.median(np.diff(grid)))
    if interval <= 0:
        return None, None

    observed = _alignment_at(grid, hits, tolerance)
    null_scores = [
        _alignment_at(grid + interval * step / steps, hits, tolerance)
        for step in range(1, steps)
    ]
    null_mean = float(np.mean(null_scores)) if null_scores else 0.0
    if null_mean <= 0.0:
        return None, null_mean
    return observed / null_mean, null_mean


def measure_file(path: Path, evaluate) -> list[AlignmentResult]:
    true_bpm = _true_bpm(path)
    if not np.isfinite(true_bpm):
        return []
    duration = float(librosa.get_duration(path=str(path)))
    sha = _sha256_16(path)

    results: list[AlignmentResult] = []
    for window_index, offset in enumerate(_window_offsets(duration)):
        length = min(WINDOW_SECONDS, duration - offset)
        if length < 30.0:
            continue
        audio, sr = librosa.load(
            str(path), sr=SAMPLE_RATE, mono=True, offset=offset, duration=length
        )
        if audio.size < sr * 5:
            continue

        tempo, frames = librosa.beat.beat_track(y=audio, sr=sr, hop_length=HOP_LENGTH)
        beats = librosa.frames_to_time(frames, sr=sr, hop_length=HOP_LENGTH).tolist()
        if len(beats) < MIN_BEATS:
            continue
        detected = float(np.atleast_1d(tempo)[0])
        kicks = _kick_times(audio, sr)

        provenance = evaluate(
            beats, kicks, bpm=detected, method="librosa_beat_track"
        )

        contrast, null_mean = _alignment_contrast(
            beats, kicks, float(provenance.get("tolerance_seconds") or 0.0)
        )

        grid = np.asarray(sorted(beats), dtype=np.float64)
        hits = np.asarray(sorted(kicks), dtype=np.float64)
        interval = float(np.median(np.diff(grid))) if grid.size > 1 else 0.0
        alignment_by_frames: dict[str, float] = {}
        null_by_frames: dict[str, float] = {}
        for frames_count in TOLERANCE_FRAMES:
            tolerance = frames_count * HOP_LENGTH / sr
            alignment_by_frames[str(frames_count)] = round(
                _alignment_at(grid, hits, tolerance), 5
            )
            # Zufallserwartung: dieselbe Toleranz auf phasenverschobenen
            # Rastern desselben Tempos.
            if interval > 0:
                null_by_frames[str(frames_count)] = round(
                    float(np.mean([
                        _alignment_at(grid + interval * step / 16, hits, tolerance)
                        for step in range(1, 16)
                    ])), 5
                )

        folded_true, folded_detected = _fold(true_bpm), _fold(detected)
        ratio = folded_detected / folded_true if folded_true > 0 else float("nan")
        results.append(
            AlignmentResult(
                file=str(path), sha256_16=sha, window_index=window_index,
                window_offset_s=round(offset, 2), true_bpm=true_bpm,
                detected_bpm=round(detected, 3),
                folded_true=round(folded_true, 3),
                folded_detected=round(folded_detected, 3),
                tempo_ratio=round(ratio, 5),
                tempo_correct=bool(abs(ratio - 1.0) <= TEMPO_TOLERANCE),
                beat_count=len(beats), kick_count=len(kicks),
                kick_alignment=provenance.get("kick_alignment"),
                interval_regularity=provenance.get("interval_regularity"),
                regular=provenance.get("regular"),
                tolerance_seconds=provenance.get("tolerance_seconds"),
                status=provenance.get("status", "unavailable"),
                kick_cross_check=provenance.get("kick_cross_check", "not_possible"),
                alignment_contrast=(
                    round(contrast, 5) if contrast is not None else None
                ),
                null_alignment_mean=(
                    round(null_mean, 5) if null_mean is not None else None
                ),
                alignment_by_frames=alignment_by_frames,
                null_by_frames=null_by_frames,
            )
        )
    return results


def _db_counts() -> tuple[int, int, str]:
    database = REPO_ROOT / "data" / "pb_studio.db"
    if not database.exists():
        return (-1, -1, "missing")
    connection = sqlite3.connect(str(database))
    try:
        projects = connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        media = connection.execute("SELECT COUNT(*) FROM media").fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        return (projects, media, integrity)
    finally:
        connection.close()


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
    parser.add_argument("--out", default="kick_alignment.json")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    files = _collect(args)
    if not files:
        print("Keine Audiodateien gefunden.", file=sys.stderr)
        return 2

    before = _db_counts()
    print(f"DB vor Lauf: projects={before[0]} media={before[1]} integrity={before[2]}")

    # Erst hier importieren: zieht den Recovery-Bootstrap.
    from backend.routers.audio_router import (  # noqa: E402
        _BEAT_GRID_KICK_ALIGNMENT_MIN,
        _evaluate_beat_grid,
    )

    print(f"Geprueft wird die Produktionsschwelle {_BEAT_GRID_KICK_ALIGNMENT_MIN}")

    if args.selftest:
        first = files[0]
        a = [asdict(r) for r in measure_file(first, _evaluate_beat_grid)]
        b = [asdict(r) for r in measure_file(first, _evaluate_beat_grid)]
        print(f"Selbsttest auf {first.name}: {len(a)} Messwerte")
        print("REPRODUZIERBAR" if a == b else "NICHT REPRODUZIERBAR")
        after = _db_counts()
        print(f"DB nach Lauf: projects={after[0]} media={after[1]} integrity={after[2]}")
        return 0 if a == b and after == before else 1

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
            "tempo_tolerance": TEMPO_TOLERANCE,
            "production_threshold": float(_BEAT_GRID_KICK_ALIGNMENT_MIN),
            "kick_band": list(KICK_BAND),
            "tolerance_frames": list(TOLERANCE_FRAMES),
        },
        "db_before": {"projects": before[0], "media": before[1], "integrity": before[2]},
        "measurements": [],
    }
    for index, path in enumerate(files, start=1):
        try:
            rows = measure_file(path, _evaluate_beat_grid)
        except Exception as exc:  # noqa: BLE001
            print(f"[{index}/{len(files)}] FEHLER {path.name}: {exc}", file=sys.stderr)
            continue
        payload["measurements"].extend(asdict(r) for r in rows)  # type: ignore[union-attr]
        print(f"[{index}/{len(files)}] {path.name}: {len(rows)} Messwerte", flush=True)

    after = _db_counts()
    payload["db_after"] = {
        "projects": after[0], "media": after[1], "integrity": after[2]
    }
    print(f"DB nach Lauf: projects={after[0]} media={after[1]} integrity={after[2]}")
    if after != before:
        print("ACHTUNG: DB-Zaehlstaende haben sich geaendert!", file=sys.stderr)

    Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nGeschrieben: {args.out} ({len(payload['measurements'])} Messwerte)")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
