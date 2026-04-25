"""
Streaming Audio Analyzer für PB_studio (AMD DirectML Version)

Optimiert für sehr lange Audiodateien (1-4 Stunden) mit begrenztem VRAM und RAM.
Verarbeitet Audio blockweise ohne die gesamte Datei in den Speicher zu laden.

AMD-Version: Kein CUDA. Nutzt DirectML für ONNX-Modelle, CPU für BeatNet/librosa.
SigLIP ONNX ersetzt CLAP für Audio-Embeddings.
"""

import gc
import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Generator

import numpy as np
import soundfile as sf
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

FloatArray = NDArray[np.floating]
ProgressCallback = Callable[[str, float], None] | None


class AnalysisPhase(Enum):
    INIT = "init"
    METADATA = "metadata"
    STEM_SEPARATION = "stem_separation"
    BEAT_DETECTION = "beat_detection"
    ONSET_DETECTION = "onset_detection"
    RMS_ANALYSIS = "rms_analysis"
    FINALIZE = "finalize"
    DONE = "done"
    ERROR = "error"


@dataclass
class AnalysisProgress:
    phase: AnalysisPhase = AnalysisPhase.INIT
    progress: float = 0.0
    last_completed_phase: AnalysisPhase | None = None
    processed_chunks: int = 0
    total_chunks: int = 0
    error_message: str | None = None

    def to_dict(self) -> dict:
        return {
            "phase": self.phase.value,
            "progress": self.progress,
            "last_completed_phase": self.last_completed_phase.value if self.last_completed_phase else None,
            "processed_chunks": self.processed_chunks,
            "total_chunks": self.total_chunks,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AnalysisProgress":
        return cls(
            phase=AnalysisPhase(data.get("phase", "init")),
            progress=data.get("progress", 0.0),
            last_completed_phase=AnalysisPhase(data["last_completed_phase"]) if data.get("last_completed_phase") else None,
            processed_chunks=data.get("processed_chunks", 0),
            total_chunks=data.get("total_chunks", 0),
            error_message=data.get("error_message"),
        )


@dataclass
class StreamingAnalysisResult:
    file_path: str
    file_hash: str
    duration: float
    sample_rate: int
    channels: int
    bpm: float = 0.0
    beat_times: list[float] = field(default_factory=list)
    onset_times: list[float] = field(default_factory=list)
    stems: dict[str, str] = field(default_factory=dict)
    rms_times: list[float] = field(default_factory=list)
    rms_values: list[float] = field(default_factory=list)
    analysis_mode: str = "streaming"

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "file_hash": self.file_hash,
            "duration": self.duration,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bpm": self.bpm,
            "beat_times": self.beat_times,
            "onset_times": self.onset_times,
            "stems": self.stems,
            "rms_times": self.rms_times,
            "rms_values": self.rms_values,
            "analysis_mode": self.analysis_mode,
        }


class AudioStreamLoader:
    """Streaming-basierter Audio-Loader für sehr lange Dateien.

    Lädt Audio blockweise mit soundfile für minimalen RAM-Verbrauch.
    """

    DEFAULT_BLOCK_DURATION = 30.0
    DEFAULT_SR = 22050

    def __init__(self, target_sr: int = DEFAULT_SR, block_duration: float = DEFAULT_BLOCK_DURATION, mono: bool = True):
        self.target_sr = target_sr
        self.block_duration = block_duration
        self.mono = mono

    def get_metadata(self, audio_path: str | Path) -> tuple[int, float, int]:
        audio_path = Path(audio_path)
        with sf.SoundFile(str(audio_path)) as f:
            sr = f.samplerate
            duration = f.frames / sr
            channels = f.channels
        logger.info(f"Audio-Metadaten: {duration:.1f}s, {sr}Hz, {channels}ch")
        return sr, duration, channels

    def stream_blocks(
        self, audio_path: str | Path, start_time: float = 0.0, end_time: float | None = None
    ) -> Generator[tuple[FloatArray, float, float], None, None]:
        audio_path = Path(audio_path)
        with sf.SoundFile(str(audio_path)) as f:
            native_sr = f.samplerate
            total_duration = f.frames / native_sr
            if end_time is None:
                end_time = total_duration

            block_samples = int(self.block_duration * native_sr)
            start_frame = int(start_time * native_sr)
            f.seek(start_frame)
            current_time = start_time

            while current_time < end_time:
                remaining = int((end_time - current_time) * native_sr)
                frames_to_read = min(block_samples, remaining)
                audio_block = f.read(frames_to_read, dtype='float32')
                if len(audio_block) == 0:
                    break

                if self.mono and audio_block.ndim > 1:
                    audio_block = np.mean(audio_block, axis=1)

                if native_sr != self.target_sr:
                    try:
                        import librosa
                        audio_block = librosa.resample(audio_block, orig_sr=native_sr, target_sr=self.target_sr)
                    except Exception as e:
                        logger.warning(f"Resampling fehlgeschlagen: {e}")

                block_duration = len(audio_block) / self.target_sr
                block_end = current_time + block_duration
                yield audio_block, current_time, block_end
                current_time = block_end

    def load_segment(self, audio_path: str | Path, start_time: float, duration: float) -> tuple[FloatArray, int]:
        audio_path = Path(audio_path)
        with sf.SoundFile(str(audio_path)) as f:
            native_sr = f.samplerate
            f.seek(int(start_time * native_sr))
            audio = f.read(int(duration * native_sr), dtype='float32')
            if self.mono and audio.ndim > 1:
                audio = np.mean(audio, axis=1)
            if native_sr != self.target_sr:
                try:
                    import librosa
                    audio = librosa.resample(audio, orig_sr=native_sr, target_sr=self.target_sr)
                except Exception:
                    return audio, native_sr
            return audio, self.target_sr


class StreamingRMSAnalyzer:
    """Streaming-basierte RMS-Energie-Analyse."""

    def __init__(self, window_size: float = 0.1, hop_size: float = 0.1):
        self.window_size = window_size
        self.hop_size = hop_size

    def analyze_streaming(
        self, audio_path: str | Path, sr: int = 22050,
        progress_callback: ProgressCallback = None,
    ) -> tuple[list[float], list[float]]:
        import librosa
        audio_path = Path(audio_path)
        loader = AudioStreamLoader(target_sr=sr)

        try:
            native_sr, total_duration, _ = loader.get_metadata(audio_path)
        except Exception as e:
            logger.error(f"Metadaten-Fehler: {e}")
            return [], []

        frame_length = int(self.window_size * sr)
        hop_length = int(self.hop_size * sr)
        all_times = []
        all_rms = []

        for audio_block, block_start, block_end in loader.stream_blocks(audio_path):
            rms = librosa.feature.rms(y=audio_block, frame_length=frame_length, hop_length=hop_length)[0]
            times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
            all_times.extend((times + block_start).tolist())
            all_rms.extend(rms.tolist())

            if progress_callback:
                progress_callback("rms", min(block_end / total_duration, 1.0))

            del audio_block, rms
            gc.collect()

        logger.info(f"RMS-Analyse: {len(all_times)} Werte über {total_duration:.1f}s")
        return all_times, all_rms


class StreamingAudioAnalyzer:
    """Hauptklasse für vollständige Streaming-basierte Audio-Analyse.

    AMD-Version: Kein CUDA VRAMManager. Stem-Separation via Demucs DirectML.
    Kein CLAP (AMD nutzt SigLIP ONNX für Video-Embeddings, nicht Audio).

    Kombiniert:
    - Stem-Separation (Demucs DirectML)
    - Beat/Onset-Detection auf Drum-Stem (BeatNet CPU)
    - RMS-Energie-Analyse (librosa CPU)
    """

    def __init__(
        self,
        cache_dir: str | Path = "audio_cache",
        stems_dir: str | Path = "media/stems",
        use_drum_stem_for_beats: bool = True,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.stems_dir = Path(stems_dir)
        self.use_drum_stem_for_beats = use_drum_stem_for_beats

        self.loader = AudioStreamLoader()
        self.rms_analyzer = StreamingRMSAnalyzer()
        self._progress_callback: ProgressCallback = None

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        self._progress_callback = callback

    def _report_progress(self, phase: str, progress: float) -> None:
        if self._progress_callback:
            try:
                self._progress_callback(phase, progress)
            except Exception as e:
                logger.warning(f"Progress-Callback Fehler: {e}")

    def _get_file_hash(self, file_path: Path) -> str:
        """Berechnet SHA-256 Hash blockweise (blockiert Thread nicht bei riesigen Dateien)."""
        # BUG-088 FIX: Groessere Chunks (1MB) und Fortschritts-Logging
        hasher = hashlib.sha256()
        file_size = file_path.stat().st_size
        bytes_read = 0
        last_log = 0.0
        
        logger.info(f"Berechne Hash für {file_path.name} ({file_size / 1024 / 1024:.1f} MB)...")
        
        with open(file_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
                bytes_read += len(chunk)
                
                # Alle 25% loggen um "Hängen" zu vermeiden
                progress = bytes_read / file_size if file_size > 0 else 1.0
                if progress >= last_log + 0.25:
                    logger.debug(f"Hashing: {progress*100:.0f}%...")
                    last_log = progress
                    
        return hasher.hexdigest()

    def _settings_suffix(self) -> str:
        """Kurzer Suffix der Analyse-Einstellungen für den Cache-Key.

        Verhindert falsche Cache-Treffer wenn dieselbe Datei mit unterschiedlichen
        Einstellungen (z.B. use_drum_stem_for_beats) analysiert wird.
        """
        return f"_drums{int(self.use_drum_stem_for_beats)}"

    def _get_cache_path(self, file_hash: str) -> Path:
        return self.cache_dir / f"streaming_analysis_{file_hash}{self._settings_suffix()}.json"

    def _get_progress_path(self, file_hash: str) -> Path:
        return self.cache_dir / f"progress_{file_hash}{self._settings_suffix()}.json"

    def _save_progress(self, file_hash: str, progress: AnalysisProgress) -> None:
        with open(self._get_progress_path(file_hash), "w", encoding="utf-8") as f:
            json.dump(progress.to_dict(), f, indent=2)

    def _load_progress(self, file_hash: str) -> AnalysisProgress | None:
        pp = self._get_progress_path(file_hash)
        if pp.exists():
            try:
                with open(pp, encoding="utf-8") as f:
                    return AnalysisProgress.from_dict(json.load(f))
            except Exception as e:
                logger.warning(f"Fortschritt laden fehlgeschlagen: {e}")
        return None

    def analyze_full(
        self, audio_path: str | Path, resume: bool = True,
        progress_callback: ProgressCallback = None,
    ) -> StreamingAnalysisResult | None:
        """Führt vollständige Streaming-Analyse durch.

        Args:
            audio_path: Pfad zur Audio-Datei
            resume: Bei Fehler vom letzten Checkpoint fortsetzen
            progress_callback: Fortschritts-Callback

        Returns:
            StreamingAnalysisResult oder None bei Fehler
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            logger.error(f"Audio-Datei nicht gefunden: {audio_path}")
            return None

        if progress_callback:
            self._progress_callback = progress_callback

        logger.info(f"Starte Streaming-Analyse: {audio_path.name}")

        self._report_progress("hashing", 0.0)
        file_hash = self._get_file_hash(audio_path)

        # Cache prüfen
        cache_path = self._get_cache_path(file_hash)
        if cache_path.exists():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    cached = json.load(f)
                result = StreamingAnalysisResult(
                    file_path=str(audio_path), file_hash=file_hash,
                    duration=cached["duration"], sample_rate=cached["sample_rate"],
                    channels=cached["channels"], bpm=cached.get("bpm", 0.0),
                    beat_times=cached.get("beat_times", []),
                    onset_times=cached.get("onset_times", []),
                    stems=cached.get("stems", {}),
                    rms_times=cached.get("rms_times", []),
                    rms_values=cached.get("rms_values", []),
                )
                logger.info(f"Analyse aus Cache: {audio_path.name}")
                self._report_progress("done", 1.0)
                return result
            except Exception as e:
                logger.warning(f"Cache laden fehlgeschlagen: {e}")

        progress = None
        if resume:
            progress = self._load_progress(file_hash)
        if not progress:
            progress = AnalysisProgress()

        try:
            # 1. Metadaten
            self._report_progress("metadata", 0.02)
            sr, duration, channels = self.loader.get_metadata(audio_path)
            result = StreamingAnalysisResult(
                file_path=str(audio_path), file_hash=file_hash,
                duration=duration, sample_rate=sr, channels=channels,
            )
            progress.phase = AnalysisPhase.METADATA
            progress.last_completed_phase = AnalysisPhase.METADATA
            self._save_progress(file_hash, progress)

            # 2. Stem-Separation (optional, via bestehender separator.py)
            self._report_progress("stem_separation", 0.05)
            progress.phase = AnalysisPhase.STEM_SEPARATION
            try:
                from .separator import StemSeparator
                sep = StemSeparator()
                raw_stems = sep.separate(str(audio_path))
                if raw_stems:
                    # StemSeparator returns {"stems": [path1, path2, ...]}
                    # Map to named stems by filename pattern
                    stems_dict = {}
                    stem_list = raw_stems.get("stems", []) if isinstance(raw_stems, dict) else []
                    for sp in stem_list:
                        sp_lower = str(sp).lower()
                        if "drum" in sp_lower:
                            stems_dict["drums"] = str(sp)
                        elif "vocal" in sp_lower:
                            stems_dict["vocals"] = str(sp)
                        elif "bass" in sp_lower:
                            stems_dict["bass"] = str(sp)
                        elif "other" in sp_lower or "no_" in sp_lower:
                            stems_dict["other"] = str(sp)
                        else:
                            stems_dict.setdefault("other", str(sp))
                    result.stems = stems_dict if stems_dict else raw_stems
                    logger.info(f"Stems: {list(result.stems.keys())}")
            except Exception as e:
                logger.warning(f"Stem-Separation übersprungen: {e}")
            progress.last_completed_phase = AnalysisPhase.STEM_SEPARATION
            self._save_progress(file_hash, progress)

            # 3. Beat-Detection
            self._report_progress("beat_detection", 0.30)
            progress.phase = AnalysisPhase.BEAT_DETECTION
            beat_source = audio_path
            if self.use_drum_stem_for_beats and result.stems.get("drums"):
                beat_source = Path(result.stems["drums"])
                logger.info("Verwende Drum-Stem für Beat-Detection")

            beat_times, bpm = self._detect_beats_streaming(beat_source, duration)
            result.beat_times = beat_times
            result.bpm = bpm
            progress.last_completed_phase = AnalysisPhase.BEAT_DETECTION
            self._save_progress(file_hash, progress)

            # 4. Onset-Detection
            self._report_progress("onset_detection", 0.50)
            progress.phase = AnalysisPhase.ONSET_DETECTION
            result.onset_times = self._detect_onsets_streaming(audio_path, duration)
            progress.last_completed_phase = AnalysisPhase.ONSET_DETECTION
            self._save_progress(file_hash, progress)

            # 5. RMS-Analyse
            self._report_progress("rms_analysis", 0.65)
            progress.phase = AnalysisPhase.RMS_ANALYSIS
            rms_t, rms_v = self.rms_analyzer.analyze_streaming(audio_path, sr=22050)
            result.rms_times = rms_t
            result.rms_values = rms_v
            progress.last_completed_phase = AnalysisPhase.RMS_ANALYSIS
            self._save_progress(file_hash, progress)

            # 6. Finalisierung
            self._report_progress("finalize", 0.95)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)

            pp = self._get_progress_path(file_hash)
            if pp.exists():
                pp.unlink()

            gc.collect()
            logger.info(f"Streaming-Analyse fertig: {audio_path.name}")
            logger.info(f"  BPM={result.bpm:.1f}, Beats={len(result.beat_times)}, Onsets={len(result.onset_times)}, RMS={len(result.rms_values)}")
            self._report_progress("done", 1.0)
            return result

        except Exception as e:
            logger.error(f"Streaming-Analyse fehlgeschlagen: {e}", exc_info=True)
            progress.phase = AnalysisPhase.ERROR
            progress.error_message = str(e)
            self._save_progress(file_hash, progress)
            gc.collect()
            return None

    def _detect_beats_streaming(
        self, audio_path: Path, total_duration: float
    ) -> tuple[list[float], float]:
        from .beat_detector import get_beat_detector, is_beatnet_available

        if is_beatnet_available():
            detector = get_beat_detector(version='auto')
            beat_times = detector.detect_beats_streaming(audio_path, total_duration)
            bpm = detector.get_bpm(beat_times) or 120.0
        else:
            beat_times = self._detect_beats_librosa_streaming(audio_path, total_duration)
            bpm = self._calculate_bpm_from_beats(beat_times)
        return beat_times, bpm

    def _detect_beats_librosa_streaming(
        self, audio_path: Path, total_duration: float
    ) -> list[float]:
        import librosa
        try:
            # BUG-088 FIX: Handle potential librosa load errors
            y_init, sr = librosa.load(str(audio_path), sr=22050, duration=180.0)
        except Exception as e:
            logger.error(f"Failed to load audio for streaming analysis {audio_path}: {e}")
            return []
            
        tempo, _ = librosa.beat.beat_track(y=y_init, sr=sr)
        if isinstance(tempo, np.ndarray):
            tempo = tempo[0]
        del y_init
        gc.collect()
        if tempo <= 0:
            tempo = 120.0
        beat_interval = 60.0 / tempo
        beat_times = np.arange(0, total_duration, beat_interval).tolist()
        logger.info(f"Librosa Beat-Interpolation: {len(beat_times)} Beats bei {tempo:.1f} BPM")
        return beat_times

    def _detect_onsets_streaming(
        self, audio_path: Path, total_duration: float
    ) -> list[float]:
        import librosa
        all_onsets = []
        sr = 22050
        hop_length = 512

        for audio_block, block_start, block_end in self.loader.stream_blocks(audio_path):
            onset_frames = librosa.onset.onset_detect(
                y=audio_block, sr=sr, hop_length=hop_length, backtrack=False, units='frames'
            )
            onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)
            all_onsets.extend((onset_times + block_start).tolist())

            del audio_block
            gc.collect()

        logger.info(f"Streaming-Onset-Detection: {len(all_onsets)} Onsets")
        return all_onsets

    def _calculate_bpm_from_beats(self, beat_times: list[float]) -> float:
        if len(beat_times) < 2:
            return 120.0
        intervals = np.diff(beat_times)
        median = np.median(intervals)
        valid = intervals[(intervals > median * 0.5) & (intervals < median * 1.5)]
        if len(valid) == 0:
            return 120.0
        return 60.0 / np.mean(valid)
