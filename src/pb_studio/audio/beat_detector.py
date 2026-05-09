"""
BeatDetector mit BeatNet für präzise KI-basierte Beat- & Downbeat-Erkennung.

AMD-Version: BeatNet läuft ausschließlich auf CPU (kein CUDA, kein DirectML nötig).
Bietet state-of-the-art Accuracy für Beats und Downbeats.
"""

import gc
import logging
from pathlib import Path
from typing import Callable, List, Tuple

import numpy as np
import librosa

logger = logging.getLogger(__name__)

# Type für Progress-Callback
ProgressCallback = Callable[[str, float], None] | None

# Versuche BeatNet zu importieren
BEATNET_AVAILABLE = False
try:
    # ============================================================================
    # PYTHON 3.11 KOMPATIBILITÄTS-PATCHES für BeatNet's madmom Dependency
    # ============================================================================
    import collections
    import collections.abc
    if not hasattr(collections, 'MutableMapping'):
        collections.MutableMapping = collections.abc.MutableMapping
    if not hasattr(collections, 'Iterable'):
        collections.Iterable = collections.abc.Iterable
    if not hasattr(collections, 'Mapping'):
        collections.Mapping = collections.abc.Mapping
    if not hasattr(collections, 'MutableSequence'):
        collections.MutableSequence = collections.abc.MutableSequence
    if not hasattr(collections, 'Sequence'):
        collections.Sequence = collections.abc.Sequence
    if not hasattr(collections, 'Callable'):
        collections.Callable = collections.abc.Callable

    # Patch 2: NumPy veraltete Typen
    import warnings
    warnings.filterwarnings('ignore', category=FutureWarning, module='.*beat_detector.*')

    if not hasattr(np, 'float'):
        np.float = float
    if not hasattr(np, 'int'):
        np.int = int
    if not hasattr(np, 'bool'):
        np.bool = bool

    # Patch 3: PyAudio Mock (BeatNet importiert pyaudio global)
    try:
        import pyaudio
    except ImportError:
        import sys
        from types import ModuleType
        m_pa = ModuleType("pyaudio")
        sys.modules["pyaudio"] = m_pa
        class MockPyAudio:
            """Mock-Klasse für PyAudio (nur für BeatNet Import benötigt)."""
            def open(self, *args, **kwargs): return None
        m_pa.PyAudio = MockPyAudio
        m_pa.paFloat32 = 1

    from BeatNet.BeatNet import BeatNet
    BEATNET_AVAILABLE = True
    logger.info("BeatNet verfügbar")
except ImportError as e:
    logger.warning(f"BeatNet nicht verfügbar: {e}. Verwende librosa Fallback.")


class BeatDetector:
    """KI-basierte Beat-Detection mit BeatNet.

    Verwendet BeatNet (TCN/CNN) für präzise Beat- und Downbeat-Erkennung.
    Läuft ausschließlich auf CPU (AMD-kompatibel).
    """

    def __init__(self, beatnet_model: int = 1, mode: str = 'online', inference_model: str = 'PF'):
        self.beatnet_model = beatnet_model
        self.mode = mode
        self.inference_model = inference_model
        self._estimator = None
        self._progress_callback: ProgressCallback = None

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        self._progress_callback = callback

    def _report_progress(self, phase: str, progress: float) -> None:
        if self._progress_callback:
            try:
                self._progress_callback(phase, progress)
            except Exception as e:
                logger.warning(f"Progress-Callback Fehler: {e}")

    def _init_estimator(self) -> bool:
        if not BEATNET_AVAILABLE:
            return False
        if self._estimator is None:
            try:
                logger.info(f"Initialisiere BeatNet Modell {self.beatnet_model} ({self.mode}/{self.inference_model})...")
                # AMD: BeatNet IMMER auf CPU (kein CUDA, kein DirectML für BeatNet)
                self._estimator = BeatNet(
                    self.beatnet_model,
                    mode=self.mode,
                    inference_model=self.inference_model,
                    plot=[],
                    thread=False,
                    device='cpu'
                )
                logger.info("BeatNet Modell initialisiert (CPU)")
                return True
            except Exception as e:
                logger.error(f"BeatNet Initialisierung fehlgeschlagen: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return False
        return True

    @staticmethod
    def _safe_emit(on_progress, pct: float) -> None:
        """Ruft on_progress(pct) auf, schluckt Exceptions."""
        if on_progress is None:
            return
        try:
            on_progress(float(pct))
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"on_progress callback Fehler: {e}")

    def detect_beats(
        self,
        audio_path: str | Path,
        duration: float | None = None,
        progress_callback: ProgressCallback = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> List[float]:
        """Detect beats und emit Progress (0..100) via on_progress.

        Args:
            audio_path: Pfad zum Audio.
            duration: Optionale Limit-Dauer (Sekunden).
            progress_callback: Legacy-Callback (phase: str, progress: float in [0..1]).
            on_progress: Neuer Callback (pct: float in [0..100]).
                Wird bei Stage-Transitions aufgerufen — sowohl im
                BeatNet- als auch im librosa-Fallback-Pfad.

        Returns:
            Liste von Beat-Zeitpunkten (Sekunden).
        """
        if progress_callback:
            self.set_progress_callback(progress_callback)
        audio_path = str(audio_path)

        # Stage 0/4: Start
        self._safe_emit(on_progress, 0.0)

        # BeatNet hängt bei langen Dateien (>600s) - direkt librosa nutzen
        total_dur = librosa.get_duration(path=audio_path)
        if total_dur > 600:
            logger.info(f"Lange Datei ({total_dur:.0f}s) -> direkt Librosa")
            return self._detect_beats_librosa(audio_path, duration=duration, on_progress=on_progress)

        if not BEATNET_AVAILABLE:
            return self._detect_beats_librosa(audio_path, duration=duration, on_progress=on_progress)
        if not self._init_estimator():
            return self._detect_beats_librosa(audio_path, duration=duration, on_progress=on_progress)

        try:
            logger.info(f"Starte BeatNet Analysis: {Path(audio_path).name}")
            self._report_progress("beatnet_start", 0.1)
            # Stage 1/4: Probe done, BeatNet ready -> beginnt Inferenz
            self._safe_emit(on_progress, 30.0)

            output = self._estimator.process(audio_path)

            # Stage 2/4: TCN inference fertig
            self._safe_emit(on_progress, 90.0)
            self._report_progress("beatnet_done", 1.0)

            if output is None or len(output) == 0:
                return self._detect_beats_librosa(audio_path, on_progress=on_progress)

            beat_times = output[:, 0].tolist()
            logger.info(f"BeatNet: {len(beat_times)} Beats erkannt")

            # Stage 3/4: Beats extrahiert
            self._safe_emit(on_progress, 100.0)
            return beat_times
        except Exception as e:
            logger.error(f"BeatNet Error: {e}")
            return self._detect_beats_librosa(audio_path, on_progress=on_progress)

    def get_downbeats(self, audio_path: str | Path) -> List[float]:
        audio_path = str(audio_path)
        if not BEATNET_AVAILABLE or not self._init_estimator():
            return []
        try:
            output = self._estimator.process(audio_path)
            if output is None or len(output) == 0:
                return []
            downbeats = [row[0] for row in output if row[1] == 1.0]
            logger.info(f"BeatNet: {len(downbeats)} Downbeats erkannt")
            return downbeats
        except Exception as e:
            logger.error(f"BeatNet Downbeat Error: {e}")
            return []

    def scan(self, audio_path: str | Path) -> Tuple[List[float], List[float]]:
        audio_path = str(audio_path)
        if not BEATNET_AVAILABLE or not self._init_estimator():
            b = self._detect_beats_librosa(audio_path)
            return b, []
        try:
            output = self._estimator.process(audio_path)
            if output is None or len(output) == 0:
                return self._detect_beats_librosa(audio_path), []
            beats = output[:, 0].tolist()
            downbeats = [row[0] for row in output if row[1] == 1.0]
            logger.info(f"BeatNet: {len(beats)} Beats, {len(downbeats)} Downbeats")
            return beats, downbeats
        except Exception as e:
            logger.error(f"BeatNet Scan Error: {e}")
            return self._detect_beats_librosa(audio_path), []

    def detect_beats_streaming(
        self, audio_path: str | Path, total_duration: float,
        progress_callback: ProgressCallback = None,
    ) -> List[float]:
        return self.detect_beats(audio_path=audio_path, duration=total_duration, progress_callback=progress_callback)

    def get_bpm(self, beat_times: List[float]) -> float | None:
        if not beat_times or len(beat_times) < 2:
            return None
        intervals = np.diff(beat_times)
        if len(intervals) == 0:
            return None
        median_interval = np.median(intervals)
        if median_interval <= 0:
            return None
        return float(60.0 / median_interval)

    def _detect_beats_librosa(
        self,
        audio_path: str,
        duration: float | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> List[float]:
        try:
            # BUG-088 FIX: Move get_duration inside try block
            total_dur = librosa.get_duration(path=audio_path)
            load_dur = duration if duration else total_dur
            logger.info(f"Librosa Fallback: {Path(audio_path).name} ({load_dur:.0f}s von {total_dur:.0f}s)")

            # Stage: vor Audio-Load (librosa-Pfad ist single-shot)
            self._safe_emit(on_progress, 30.0)
            y, sr = librosa.load(audio_path, sr=22050, duration=load_dur)

            # Stage: nach Load, vor beat_track
            self._safe_emit(on_progress, 60.0)
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)
            logger.info(f"Librosa: {len(beat_times)} Beats ({float(np.atleast_1d(tempo)[0]):.1f} BPM)")
            del y
            gc.collect()

            # Stage: fertig
            self._safe_emit(on_progress, 100.0)
            return beat_times.tolist()
        except Exception as e:
            logger.error(f"Librosa Fallback failed: {e}")
            # Auch im Fehlerfall: 100% emittieren, damit der Caller-SSE-Stream nicht hängt.
            self._safe_emit(on_progress, 100.0)
            return []


# ============================================================================
# FACTORY-PATTERN & HELPER-FUNKTIONEN
# ============================================================================

def is_beatnet_available() -> bool:
    """Prüft ob BeatNet verfügbar ist."""
    return BEATNET_AVAILABLE


def get_beat_detector(version: str = 'auto', **kwargs: object) -> BeatDetector:
    """Factory-Funktion: Gibt einen BeatDetector zurück.

    AMD-Version: Nur BeatNet (CPU) als KI-Backend verfügbar.
    beat_this wird nicht unterstützt (benötigt torch.cuda).

    Args:
        version: 'auto' oder 'legacy' (beide liefern BeatDetector)
        **kwargs: Argumente für BeatDetector

    Returns:
        BeatDetector Instanz
    """
    if is_beatnet_available():
        logger.info("BeatDetector: BeatNet (CPU)")
        return BeatDetector(**kwargs)
    else:
        logger.warning("Kein Beat-Detector verfügbar, nutze Librosa-Fallback")
        return BeatDetector(**kwargs)  # Nutzt internen Librosa-Fallback
