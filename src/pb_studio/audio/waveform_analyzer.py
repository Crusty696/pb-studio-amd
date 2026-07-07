"""
3-Band Waveform Analyzer (Rekordbox-Style)

Extracts low/mid/high frequency band RMS envelopes for waveform visualization.
Optimized for performance with DirectML-accelerated audio analysis.
"""
import logging
import numpy as np
from typing import Dict, Optional
from pathlib import Path
from scipy.signal import butter, sosfiltfilt
import librosa

logger = logging.getLogger(__name__)


class WaveformAnalyzer:
    """
    3-Band Frequency Analyzer for Audio Waveforms.

    Separates audio into frequency bands (Low/Mid/High) using Butterworth filters
    and computes RMS envelopes for each band. This provides Rekordbox-style
    multi-band waveform visualization data.
    """

    def __init__(self, sr: int = 22050, filter_order: int = 4):
        """
        Initialize WaveformAnalyzer.

        Args:
            sr: Target sample rate for analysis (default 44100Hz)
            filter_order: Butterworth filter order (default 4 = 24dB/octave)
        """
        self.sr = sr
        self.filter_order = filter_order

        # Frequency bands (Rekordbox-style separation)
        # These ranges are optimized for dance music visualization
        self.bands = {
            'low': (20, 200),       # Bass frequencies (Kick, Sub-bass)
            'mid': (200, 2000),     # Midrange (Vocals, Snare, most instruments)
            'high': (2000, 20000)   # High frequencies (Cymbals, Hi-hats, Air)
        }

        logger.info(f"WaveformAnalyzer initialized: {sr}Hz, Order {filter_order}")

    def extract_3band_waveform(
        self,
        audio_path: str,
        hop_length: int = 512,
        target_sr: Optional[int] = None
    ) -> Dict[str, np.ndarray]:
        """
        Extract 3-band RMS envelopes from audio file.

        Args:
            audio_path: Path to audio file
            hop_length: Hop size for RMS calculation (default 512 samples = ~11.6ms at 44.1kHz)
            target_sr: Override sample rate (default uses self.sr)

        Returns:
            Dictionary with keys 'low', 'mid', 'high' containing RMS envelope arrays

        Example:
            >>> analyzer = WaveformAnalyzer()
            >>> waveform = analyzer.extract_3band_waveform("track.mp3")
            >>> print(waveform['low'].shape)  # (N,) array of RMS values
        """
        try:
            logger.info(f"Loading audio: {Path(audio_path).name}")

            # Load audio (mono, target sample rate)
            use_sr = target_sr if target_sr is not None else self.sr

            # AP4.5 (Audit 2026-06-10): Langdatei-Guard — 90-min-Mix @22050 wäre
            # ~480MB float32, sosfiltfilt verdreifacht das intern in float64.
            # Für reine Waveform-VISUALISIERUNG reicht bei sehr langen Files eine
            # niedrigere Abtastrate (High-Band wird dann bei Nyquist gekappt).
            if target_sr is None:
                try:
                    _probe_dur = float(librosa.get_duration(path=audio_path))
                except Exception:
                    _probe_dur = 0.0
                if _probe_dur > 1800.0:  # > 30 min
                    use_sr = 11025
                    logger.info(
                        f"Lange Datei ({_probe_dur:.0f}s) — Waveform-SR auf {use_sr}Hz reduziert (RAM-Guard)"
                    )

            y, sr = librosa.load(audio_path, sr=use_sr, mono=True)

            if len(y) == 0:
                logger.warning("Empty audio file")
                return self._empty_waveform()

            # Normalize to prevent clipping in filters
            y = y / (np.max(np.abs(y)) + 1e-8)

            logger.info(f"Audio loaded: {len(y)} samples, {sr}Hz")

            # Extract each frequency band
            result = {}
            for band_name, (low_freq, high_freq) in self.bands.items():
                logger.debug(f"Processing {band_name} band: {low_freq}-{high_freq}Hz")

                # Apply bandpass filter
                y_filtered = self._bandpass_filter(y, low_freq, high_freq, sr)

                # Compute RMS envelope
                rms_envelope = self._compute_rms_envelope(y_filtered, hop_length)

                result[band_name] = rms_envelope
                logger.debug(f"{band_name}: {len(rms_envelope)} RMS frames")
                del y_filtered
                import gc; gc.collect()

            logger.info(f"3-band extraction complete: {len(result['low'])} frames")
            return result

        except Exception as e:
            logger.error(f"Failed to extract waveform: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return self._empty_waveform()

    def _bandpass_filter(
        self,
        y: np.ndarray,
        low_freq: int,
        high_freq: int,
        sr: int
    ) -> np.ndarray:
        """
        Apply Butterworth bandpass filter to audio signal.

        Args:
            y: Input audio signal
            low_freq: Lower cutoff frequency (Hz)
            high_freq: Upper cutoff frequency (Hz)
            sr: Sample rate of audio

        Returns:
            Filtered audio signal
        """
        # Nyquist frequency
        nyquist = sr / 2.0

        # Normalize frequencies to Nyquist
        low_norm = max(0.001, low_freq / nyquist)
        high_norm = min(0.999, high_freq / nyquist)

        # Design Butterworth bandpass filter (Second-Order Sections for stability)
        sos = butter(
            self.filter_order,
            [low_norm, high_norm],
            btype='band',
            output='sos'
        )

        # Apply zero-phase filtering (forward + backward)
        # This eliminates phase distortion which is critical for beat alignment
        # AP4.5: sofort zurück auf float32 — sosfiltfilt arbeitet intern in
        # float64; ohne Downcast hielte jedes Band das Doppelte im RAM.
        y_filtered = sosfiltfilt(sos, y).astype(np.float32)

        return y_filtered

    def _compute_rms_envelope(
        self,
        y: np.ndarray,
        hop_length: int = 512
    ) -> np.ndarray:
        """
        Compute RMS (Root Mean Square) envelope of audio signal.

        The RMS envelope represents the energy/loudness over time.
        Perfect for waveform visualization.

        Args:
            y: Input audio signal
            hop_length: Window hop size (smaller = more detail, larger = smoother)

        Returns:
            RMS envelope array
        """
        # Librosa's built-in RMS with frame-based analysis
        # frame_length = 2048 (default) provides good time/frequency resolution
        rms = librosa.feature.rms(
            y=y,
            frame_length=2048,
            hop_length=hop_length
        )[0]  # [0] to get 1D array

        # Normalize to 0-1 range for consistent visualization
        if np.max(rms) > 0:
            rms = rms / np.max(rms)

        return rms

    def get_downsampled_waveform(
        self,
        audio_path: str,
        target_points: int = 1000,
        hop_length: int = 512
    ) -> Dict[str, np.ndarray]:
        """
        Extract downsampled 3-band waveform for efficient GUI rendering.

        This reduces the number of data points to match display resolution,
        preventing unnecessary processing and improving render performance.

        Args:
            audio_path: Path to audio file
            target_points: Target number of waveform points (default 1000)
            hop_length: Initial hop size before downsampling

        Returns:
            Dictionary with 'low', 'mid', 'high' downsampled arrays

        Example:
            >>> analyzer = WaveformAnalyzer()
            >>> waveform = analyzer.get_downsampled_waveform("track.mp3", target_points=500)
            >>> # Perfect for a 500-pixel wide waveform display
        """
        # Extract full-resolution waveform
        full_waveform = self.extract_3band_waveform(audio_path, hop_length)

        # Downsample each band
        downsampled = {}
        for band_name, rms_data in full_waveform.items():
            if len(rms_data) == 0:
                downsampled[band_name] = np.array([])
                continue

            # Downsample by averaging windows
            if len(rms_data) <= target_points:
                # Already small enough
                downsampled[band_name] = rms_data
            else:
                # Compute window size for averaging
                window_size = len(rms_data) // target_points

                # Reshape and average (handles remainder by truncation)
                num_complete_windows = (len(rms_data) // window_size) * window_size
                truncated = rms_data[:num_complete_windows]
                reshaped = truncated.reshape(-1, window_size)

                # Average each window (preserves peaks better than simple decimation)
                downsampled[band_name] = np.mean(reshaped, axis=1)

        logger.info(f"Downsampled to {len(downsampled['low'])} points")
        return downsampled

    def get_time_axis(
        self,
        num_frames: int,
        hop_length: int = 512
    ) -> np.ndarray:
        """
        Generate time axis for waveform frames.

        Args:
            num_frames: Number of RMS frames
            hop_length: Hop size used in RMS calculation

        Returns:
            Time array in seconds
        """
        return librosa.frames_to_time(
            np.arange(num_frames),
            sr=self.sr,
            hop_length=hop_length
        )

    def _empty_waveform(self) -> Dict[str, np.ndarray]:
        """Return empty waveform structure."""
        return {
            'low': np.array([]),
            'mid': np.array([]),
            'high': np.array([])
        }

    def analyze_frequency_content(self, audio_path: str) -> Dict[str, float]:
        """
        Analyze overall frequency content distribution.

        Returns average energy per band as percentages.
        Useful for genre detection or EQ recommendations.

        Args:
            audio_path: Path to audio file

        Returns:
            Dictionary with 'low_pct', 'mid_pct', 'high_pct' keys
        """
        waveform = self.extract_3band_waveform(audio_path)

        # Calculate average energy per band
        low_energy = np.mean(waveform['low'] ** 2) if len(waveform['low']) > 0 else 0
        mid_energy = np.mean(waveform['mid'] ** 2) if len(waveform['mid']) > 0 else 0
        high_energy = np.mean(waveform['high'] ** 2) if len(waveform['high']) > 0 else 0

        total_energy = low_energy + mid_energy + high_energy

        if total_energy == 0:
            return {'low_pct': 0.0, 'mid_pct': 0.0, 'high_pct': 0.0}

        return {
            'low_pct': (low_energy / total_energy) * 100,
            'mid_pct': (mid_energy / total_energy) * 100,
            'high_pct': (high_energy / total_energy) * 100
        }
