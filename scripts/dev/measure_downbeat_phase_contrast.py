"""Misst reproduzierbar, ob in Audiomaterial eine Taktposition herausragt.

Hintergrund: `derive_downbeats_from_strengths` waehlt den Taktanfang ueber den
Phasenkontrast der Anschlagstaerken. An echter Musik gemessen greift dieses
Merkmal daneben (es folgt der Snare, nicht dem Kick). Dieses Werkzeug misst
mehrere Merkmale auf DEMSELBEN Beat-Raster und beantwortet zwei Fragen:

1. Welches Merkmal traegt die Taktinformation?
2. Ab welchem Kontrast ist ein Befund von Zufall unterscheidbar?

Frage 2 wird nicht geraten, sondern per Permutationstest beantwortet: die
Merkmalswerte werden wiederholt ueber die Beats gemischt und der maximale
Phasenkontrast neu berechnet. Der p-Wert ist der Anteil der Mischungen, die
mindestens so kontrastreich sind wie die echte Anordnung.

REPRODUZIERBARKEIT — die Zusicherungen dieses Skripts:
  * Beat-Raster exakt wie im Produktionscode: librosa.load(sr=22050) +
    librosa.beat.beat_track (siehe BeatDetector._detect_beats_librosa).
  * Anschlagstaerken ueber BeatDetector.compute_beat_strengths, also dieselbe
    Funktion, die die Ableitung im Betrieb fuettert.
  * Fensterlagen deterministisch aus der Dateidauer abgeleitet, nicht zufaellig.
  * Permutationen mit festem Seed je (Datei, Fenster, Merkmal).
  * Jede Zeile der Ausgabe traegt SHA-256 und Groesse der Quelldatei sowie die
    Versionen von librosa/numpy. Zwei Laeufe auf derselben Datei muessen
    identische Zahlen liefern; `--selftest` prueft das.

Aufruf:
    python scripts/dev/measure_downbeat_phase_contrast.py --dir "C:/.../Music" --out mess.json
    python scripts/dev/measure_downbeat_phase_contrast.py --files a.mp3 b.wav --selftest
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

SAMPLE_RATE = 22050          # wie BeatDetector._detect_beats_librosa
HOP_LENGTH = 512
N_FFT = 2048
BEATS_PER_BAR = 4
WINDOW_SECONDS = 120.0
MIN_BEATS = 32               # unter 8 Takten ist der Phasenmittelwert wertlos
PERMUTATIONS = 2000

# Merkmal -> (untere, obere) Frequenzgrenze; None = kein Bandmerkmal
FEATURES: dict[str, tuple[float, float] | None] = {
    "onset_strength": None,      # das aktuell verwendete Merkmal
    "bass_20_120": (20.0, 120.0),
    "lowmid_120_500": (120.0, 500.0),
    "high_2k_8k": (2000.0, 8000.0),
    "rms": (0.0, 0.0),           # Sonderfall, siehe _feature_values
}


@dataclass
class WindowResult:
    file: str
    sha256_16: str
    size_bytes: int
    duration_s: float
    window_index: int
    window_offset_s: float
    window_length_s: float
    bpm: float
    bpm_from_name: float
    tempo_ratio: float          # erkannt / Dateiname; 1.0 = passt, 2.0/0.5 = Oktavfehler
    beat_count: int
    feature: str
    phase_means: list[float]
    best_phase: int
    contrast: float
    p_value: float
    null_median_contrast: float
    p_value_parity: float
    amp_period4: float
    amp_period2: float
    phase_stable_halves: bool
    grid_outliers: int
    # Fuer den Fenstervergleich in ABSOLUTER Zeit. Der Phasenindex allein ist
    # fensterrelativ, weil beat_track in jedem Fenster neu ansetzt; erst mit
    # diesen beiden Feldern laesst sich das Downbeat-Raster rekonstruieren und
    # zwischen Fenstern vergleichen.
    first_downbeat_abs_s: float
    beat_interval_s: float


def _sha256_16(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _window_offsets(duration: float) -> list[float]:
    """Deterministische, NICHT ueberlappende Fensterlagen.

    Die erste Fassung nahm 25/50/75 % der Dauer; bei einem 4-Minuten-Track
    ueberlappten die drei Fenster dadurch zu ueber der Haelfte, und "drei
    Fenster einig" war fast tautologisch statt ein dreifacher Beleg.
    """
    if duration <= WINDOW_SECONDS * 1.5:
        return [0.0]
    usable = duration - WINDOW_SECONDS
    count = min(3, max(1, int(usable // WINDOW_SECONDS) + 1))
    if count == 1:
        return [usable / 2.0]
    return [usable * index / (count - 1) for index in range(count)]


_BPM_IN_NAME = re.compile(r"_(\d{2,3})__")


def _bpm_from_filename(path: Path) -> float:
    """BPM aus dem Dateinamen, falls vorhanden (Beatport-Namensschema).

    Erlaubt den Abgleich des erkannten Tempos gegen die Wahrheit und damit das
    Erkennen von Oktavfehlern - bei doppeltem Tempo sind die Phasen 0 und 2
    beide Taktanfang, was den ganzen Befund entwertet.
    """
    match = _BPM_IN_NAME.search(path.name)
    return float(match.group(1)) if match else float("nan")


def _feature_values(
    name: str,
    audio: np.ndarray,
    sample_rate: int,
    beats: np.ndarray,
) -> np.ndarray:
    """Ein Merkmalswert je Beat, alle auf demselben Beat-Raster abgetastet."""
    from pb_studio.audio.beat_detector import BeatDetector

    if name == "onset_strength":
        return np.asarray(
            BeatDetector.compute_beat_strengths(audio, sample_rate, beats.tolist()),
            dtype=float,
        )
    if name == "rms":
        rms = librosa.feature.rms(y=audio, hop_length=HOP_LENGTH)[0]
        times = librosa.frames_to_time(
            np.arange(len(rms)), sr=sample_rate, hop_length=HOP_LENGTH
        )
        return np.interp(beats, times, rms)

    low, high = FEATURES[name]  # type: ignore[misc]
    spectrum = np.abs(
        librosa.stft(audio, n_fft=N_FFT, hop_length=HOP_LENGTH)
    )
    freqs = librosa.fft_frequencies(sr=sample_rate, n_fft=N_FFT)
    band = spectrum[(freqs >= low) & (freqs < high)].mean(axis=0)
    times = librosa.frames_to_time(
        np.arange(len(band)), sr=sample_rate, hop_length=HOP_LENGTH
    )
    return np.interp(beats, times, band)


def _contrast(values: np.ndarray) -> tuple[int, float, list[float]]:
    """Bester Phasenmittelwert gegen den Mittelwert der uebrigen."""
    means = [float(np.mean(values[phase::BEATS_PER_BAR])) for phase in range(BEATS_PER_BAR)]
    best = int(np.argmax(means))
    others = [m for index, m in enumerate(means) if index != best]
    rest = float(np.mean(others)) if others else 0.0
    contrast = means[best] / rest if rest > 0 else 0.0
    return best, contrast, means


def _free_null(values: np.ndarray, seed: int) -> tuple[float, float]:
    """Freie Permutation. NUR ZUM VERGLEICH mitgefuehrt - sie ist fuer die
    Taktfrage FALSCH: sie zerstoert auch die Periode 2 und meldet deshalb jedes
    Backbeat-/Off-Beat-Muster als Taktbefund. Belegt an einer Kontrollreihe mit
    reiner Periode 2 und ohne jede Taktinformation: p = 0.0005.
    """
    rng = np.random.default_rng(seed)
    observed = _contrast(values)[1]
    shuffled = np.empty(PERMUTATIONS, dtype=float)
    working = values.copy()
    for index in range(PERMUTATIONS):
        rng.shuffle(working)
        shuffled[index] = _contrast(working)[1]
    p_value = (1.0 + float(np.sum(shuffled >= observed))) / (PERMUTATIONS + 1.0)
    return p_value, float(np.median(shuffled))


def _parity_null(values: np.ndarray, seed: int) -> float:
    """Die richtige Null: mischt INNERHALB der geraden und der ungeraden
    Beat-Positionen. Damit bleibt die Periode-2-Struktur (Backbeat,
    Off-Beat-HiHat) erhalten und nur die Taktausrichtung wird zerstoert.
    Dieselbe Kontrollreihe wie oben liefert hier p = 0.886.

    (1+c)/(B+1): mit endlich vielen Ziehungen ist p = 0 nicht belegbar.
    """
    rng = np.random.default_rng(seed)
    observed = _contrast(values)[1]
    index = np.arange(len(values))
    even, odd = index[index % 2 == 0], index[index % 2 == 1]
    working = values.copy()
    hits = 0
    for _ in range(PERMUTATIONS):
        working[even] = values[rng.permutation(even)]
        working[odd] = values[rng.permutation(odd)]
        if _contrast(working)[1] >= observed:
            hits += 1
    return (1.0 + hits) / (PERMUTATIONS + 1.0)


def _period_components(values: np.ndarray) -> tuple[float, float]:
    """Relative Amplitude der Periode-4- und der Periode-2-Komponente.

    Nur die Periode 4 traegt Taktinformation. Der Kontrast max/rest mischt
    beide und kann deshalb nicht zwischen Taktanfang und Gegenschlag
    unterscheiden.
    """
    k = np.arange(len(values))
    mean = float(np.mean(values))
    if mean <= 0.0:
        return 0.0, 0.0
    amp4 = abs(np.mean(values * np.exp(-2j * np.pi * k / 4.0))) / mean
    amp2 = abs(np.mean(values * np.exp(-1j * np.pi * k)).real) / mean
    return float(amp4), float(amp2)


def measure_file(path: Path) -> list[WindowResult]:
    duration = float(librosa.get_duration(path=str(path)))
    bpm_name = _bpm_from_filename(path)
    sha = _sha256_16(path)
    size = path.stat().st_size
    results: list[WindowResult] = []

    for window_index, offset in enumerate(_window_offsets(duration)):
        offset = max(0.0, offset)
        length = WINDOW_SECONDS if duration > WINDOW_SECONDS * 1.5 else duration
        audio, sample_rate = librosa.load(
            str(path), sr=SAMPLE_RATE, mono=True, offset=offset, duration=length
        )
        if audio.size < sample_rate * 5:
            continue
        tempo, beat_frames = librosa.beat.beat_track(y=audio, sr=sample_rate)
        beats = librosa.frames_to_time(beat_frames, sr=sample_rate)
        if len(beats) < MIN_BEATS:
            continue
        bpm = float(np.atleast_1d(tempo)[0])
        intervals = np.diff(beats)
        median_ibi = float(np.median(intervals))
        grid_outliers = int(np.sum(np.abs(intervals - median_ibi) > 0.10 * median_ibi))

        for feature_index, feature in enumerate(FEATURES):
            values = _feature_values(feature, audio, sample_rate, beats)
            if not np.all(np.isfinite(values)) or float(np.ptp(values)) == 0.0:
                continue
            best, contrast, means = _contrast(values)
            beat_interval = float(np.median(np.diff(beats))) if len(beats) > 1 else 0.0
            first_downbeat_abs = offset + float(beats[best])
            seed = int(sha[:8], 16) ^ (window_index << 8) ^ feature_index
            p_value, null_median = _free_null(values, seed)
            p_parity = _parity_null(values, seed ^ 0x5A5A)
            amp4, amp2 = _period_components(values)
            half = len(values) // 2
            phase_stable = bool(
                _contrast(values[:half])[0] == _contrast(values[half:])[0] == best
            )
            results.append(
                WindowResult(
                    file=str(path),
                    sha256_16=sha,
                    size_bytes=size,
                    duration_s=round(duration, 2),
                    window_index=window_index,
                    window_offset_s=round(offset, 2),
                    window_length_s=round(length, 2),
                    bpm=round(bpm, 2),
                    bpm_from_name=bpm_name,
                    tempo_ratio=round(bpm / bpm_name, 4) if bpm_name == bpm_name and bpm_name > 0 else float("nan"),
                    beat_count=len(beats),
                    feature=feature,
                    phase_means=[round(m, 6) for m in means],
                    best_phase=best,
                    contrast=round(contrast, 4),
                    p_value=round(p_value, 5),
                    null_median_contrast=round(null_median, 4),
                    p_value_parity=round(p_parity, 5),
                    amp_period4=round(amp4, 6),
                    amp_period2=round(amp2, 6),
                    phase_stable_halves=phase_stable,
                    grid_outliers=grid_outliers,
                    first_downbeat_abs_s=round(first_downbeat_abs, 4),
                    beat_interval_s=round(beat_interval, 6),
                )
            )
    return results


def _collect_files(args: argparse.Namespace) -> list[Path]:
    paths: list[Path] = []
    if args.files:
        paths.extend(Path(f) for f in args.files)
    if args.dir:
        extensions = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".opus", ".aiff", ".aif"}
        for candidate in sorted(Path(args.dir).rglob("*")):
            if candidate.suffix.lower() in extensions and candidate.is_file():
                paths.append(candidate)
    unique = sorted({p.resolve() for p in paths if p.exists()})
    return unique[: args.limit] if args.limit else unique


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", nargs="*", default=[])
    parser.add_argument("--dir")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", default="downbeat_phase_contrast.json")
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="misst die erste Datei zweimal und verlangt identische Zahlen",
    )
    args = parser.parse_args()

    files = _collect_files(args)
    if not files:
        print("Keine Audiodateien gefunden.", file=sys.stderr)
        return 2

    if args.selftest:
        first = files[0]
        run_a = [asdict(r) for r in measure_file(first)]
        run_b = [asdict(r) for r in measure_file(first)]
        identical = run_a == run_b
        print(f"Selbsttest auf {first.name}: {len(run_a)} Messwerte")
        print("REPRODUZIERBAR" if identical else "NICHT REPRODUZIERBAR")
        if not identical:
            for a, b in zip(run_a, run_b):
                if a != b:
                    print("  erste Abweichung:", a["feature"], a["window_index"])
                    print("   A:", a)
                    print("   B:", b)
                    break
        return 0 if identical else 1

    payload: dict[str, object] = {
        "schema_version": 4,
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "librosa": librosa.__version__,
        },
        "parameters": {
            "sample_rate": SAMPLE_RATE,
            "hop_length": HOP_LENGTH,
            "n_fft": N_FFT,
            "beats_per_bar": BEATS_PER_BAR,
            "window_seconds": WINDOW_SECONDS,
            "min_beats": MIN_BEATS,
            "permutations": PERMUTATIONS,
        },
        "measurements": [],
    }

    for index, path in enumerate(files, start=1):
        try:
            rows = measure_file(path)
        except Exception as exc:  # noqa: BLE001 - eine kaputte Datei stoppt den Lauf nicht
            print(f"[{index}/{len(files)}] FEHLER {path.name}: {exc}", file=sys.stderr)
            continue
        payload["measurements"].extend(asdict(row) for row in rows)  # type: ignore[union-attr]
        print(f"[{index}/{len(files)}] {path.name}: {len(rows)} Messwerte", flush=True)

    Path(args.out).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nGeschrieben: {args.out} ({len(payload['measurements'])} Messwerte)")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
