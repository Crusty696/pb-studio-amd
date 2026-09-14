"""Hilft `librosa.feature.tempogram_ratio` gegen den Vielfachfehler?

Ausgangslage, an eigenen Messungen belegt:

* `librosa.beat_track` trifft das Tempo in 37,0 % der Fenster; seine drei
  haeufigsten Werte sind exakt die Tempogramm-Frequenzen fuer k = 18, 19, 28.
* Der eigene Estimator kommt auf 48,8 %.
* In DJ-Mixen liegen **97,2 %** der Segmenttempi auf einem einfachen
  Vielfachen des Datei-Medians; faltet man die Faktoren heraus, sinkt die
  Spannweite von 33,3 % auf 0,1 %. Der Fehler ist also fast ausschliesslich
  ein Vielfachfehler, keine echte Tempoaenderung.

Wenn das stimmt, muss eine gute Vielfachkorrektur den groessten Teil der
verbleibenden Fehler beheben. `tempogram_ratio` misst genau das: die relative
Energie bei metrischen Unterteilungen des geschaetzten Tempos.

Gemessen wird deshalb dreifach auf denselben Fenstern:

    A estimator          der heutige Stand
    B ratio_corrected    Estimator, danach ueber tempogram_ratio auf das
                         staerkste Vielfache gezogen
    C upper_bound        das BEKANNTE wahre Tempo (aus dem Dateinamen), auf
                         das naechste Vielfache des Estimator-Ergebnisses
                         gefaltet. Keine Schaetzung und kein Bestandteil des
                         Produkts, sondern eine Rechnung mit bekannter
                         Wahrheit: sie sagt, wie oft das Verfahren traefe,
                         wenn es immer den bestmoeglichen Faktor waehlte.

C ist der wichtigste Wert, weil er die Frage beantwortet, die man sonst nicht
beantworten kann: liegt er weit ueber A, ist der Fehler ueberhaupt ein
Vielfachfehler und die Korrektur lohnt. Liegt er nahe A, ist er es NICHT -
dann waere jede Arbeit an der Vielfachkorrektur vergeblich, egal wie gut sie
gemacht ist.

Aufruf:
    python scripts/dev/measure_tempo_ratio_correction.py --dir "D:/beatport_tracks_2025-08" --out ratio.json
    python scripts/dev/measure_tempo_ratio_correction.py --dir "..." --selftest
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

from pb_studio.audio.band_params import KICK_BAND, band_stft_params  # noqa: E402
from pb_studio.audio.beat_grid import estimate_beat_grid  # noqa: E402

SAMPLE_RATE = 22050
HOP_LENGTH = 512
WINDOW_SECONDS = 120.0
TEMPO_TOLERANCE = 0.02
TEMPO_MIN, TEMPO_MAX = 60.0, 200.0
AUDIO_EXTENSIONS = {".aiff", ".aif", ".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus"}

# Faktoren, um die ein Tempo danebenliegen kann. Reihenfolge egal, die
# Bewertung entscheidet.
CANDIDATE_FACTORS = (1.0, 2.0, 0.5, 1.5, 2.0 / 3.0, 3.0, 1.0 / 3.0, 4.0 / 3.0, 0.75)

_BPM_IN_NAME = re.compile(r"_(\d{2,3})__")


@dataclass
class RatioResult:
    file: str
    sha256_16: str
    window_index: int
    true_bpm: float
    method: str
    detected_bpm: float
    applied_factor: float
    tempo_ratio: float
    tempo_correct: bool


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


def _kick_times(audio: np.ndarray, sr: int) -> list[float]:
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


def _ratio_correct(
    envelope: np.ndarray, sr: int, bpm: float
) -> tuple[float, float]:
    """Zieht ein Tempo auf das staerkste einfache Vielfache.

    `tempogram_ratio` liefert die relative Energie bei metrischen
    Unterteilungen des uebergebenen Tempos. Ein Vielfaches, das deutlich mehr
    Energie traegt als der Kandidat selbst, ist der bessere Puls.

    Returns:
        ``(korrigiertes_bpm, angewandter_faktor)``.
    """
    if bpm <= 0 or envelope.size < 16:
        return bpm, 1.0
    frames = envelope.shape[-1]
    factors = np.asarray(CANDIDATE_FACTORS, dtype=float)
    try:
        ratios = librosa.feature.tempogram_ratio(
            onset_envelope=envelope, sr=sr, hop_length=HOP_LENGTH,
            bpm=np.full(frames, float(bpm)), factors=factors,
            aggregate=np.mean,
        )
    except Exception:  # noqa: BLE001 - eine Datei darf den Lauf nicht stoppen
        return bpm, 1.0

    strengths = np.asarray(ratios, dtype=float).reshape(-1)
    if strengths.size != factors.size:
        return bpm, 1.0

    best_index = 0
    best_value = -np.inf
    for index, factor in enumerate(factors):
        candidate = bpm / factor
        if not (TEMPO_MIN <= candidate <= TEMPO_MAX):
            continue
        value = float(strengths[index])
        # Der unveraenderte Kandidat bekommt einen kleinen Bonus: ohne ihn
        # wechselt die Wahl schon bei Messrauschen.
        if factor == 1.0:
            value *= 1.05
        if value > best_value:
            best_value, best_index = value, index

    factor = float(factors[best_index])
    return bpm / factor, factor


def _upper_bound_fold(detected: float, true_bpm: float) -> tuple[float, float]:
    """Obergrenze jeder denkbaren Vielfachkorrektur.

    Rechnet mit der BEKANNTEN Wahrheit und waehlt den bestmoeglichen Faktor.
    Das ist keine Schaetzung und laeuft nie im Produkt - es misst, ob der
    Fehler ueberhaupt ein Vielfachfehler ist: eine Korrektur kann ihn nur
    beheben, wenn erkanntes und wahres Tempo in einem der geprueften
    Verhaeltnisse stehen.
    """
    if detected <= 0 or not np.isfinite(true_bpm):
        return detected, 1.0
    best_factor, best_error = 1.0, np.inf
    for factor in CANDIDATE_FACTORS:
        candidate = detected / factor
        error = abs(_fold(candidate) - _fold(true_bpm)) / _fold(true_bpm)
        if error < best_error:
            best_error, best_factor = error, factor
    return detected / best_factor, best_factor


def measure_file(path: Path) -> list[RatioResult]:
    true_bpm = _true_bpm(path)
    if not np.isfinite(true_bpm):
        return []
    duration = float(librosa.get_duration(path=str(path)))
    sha = _sha256_16(path)
    offsets = ([0.0] if duration <= WINDOW_SECONDS * 1.2
               else [WINDOW_SECONDS * i for i in range(int(duration // WINDOW_SECONDS))][:6])

    results: list[RatioResult] = []
    for window_index, offset in enumerate(offsets):
        length = min(WINDOW_SECONDS, duration - offset)
        if length < 30.0:
            continue
        audio, sr = librosa.load(
            str(path), sr=SAMPLE_RATE, mono=True, offset=offset, duration=length
        )
        if audio.size < sr * 5:
            continue
        envelope = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=HOP_LENGTH)
        grid = estimate_beat_grid(audio, sr, kick_times=_kick_times(audio, sr))
        folded_true = _fold(true_bpm)

        def emit(method: str, bpm: float, factor: float) -> None:
            folded = _fold(bpm)
            ratio = folded / folded_true if folded_true > 0 else float("nan")
            results.append(
                RatioResult(
                    file=str(path), sha256_16=sha, window_index=window_index,
                    true_bpm=true_bpm, method=method,
                    detected_bpm=round(float(bpm), 4),
                    applied_factor=round(float(factor), 5),
                    tempo_ratio=round(ratio, 5) if np.isfinite(ratio) else float("nan"),
                    tempo_correct=bool(
                        np.isfinite(ratio) and abs(ratio - 1.0) <= TEMPO_TOLERANCE
                    ),
                )
            )

        emit("A_estimator", grid.bpm, 1.0)
        corrected, factor = _ratio_correct(envelope, sr, grid.bpm)
        emit("B_ratio_corrected", corrected, factor)
        bound, bound_factor = _upper_bound_fold(grid.bpm, true_bpm)
        emit("C_upper_bound", bound, bound_factor)

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
    parser.add_argument("--out", default="tempo_ratio_correction.json")
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
            "python": sys.version.split()[0], "numpy": np.__version__,
            "librosa": librosa.__version__,
        },
        "parameters": {
            "sample_rate": SAMPLE_RATE, "hop_length": HOP_LENGTH,
            "window_seconds": WINDOW_SECONDS, "tempo_tolerance": TEMPO_TOLERANCE,
            "candidate_factors": list(CANDIDATE_FACTORS),
            "tempo_bounds": [TEMPO_MIN, TEMPO_MAX],
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
