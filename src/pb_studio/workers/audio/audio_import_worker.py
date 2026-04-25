"""
Audio Import Worker for PB Studio AMD

Imports audio files and converts them to WAV format using FFmpeg.
VRAM Budget: 0 MB (CPU-only operation)
"""

import logging
import os
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..base_worker import BaseWorker
from ...models.audio import AudioMetadata
from ...video.encoder_utils import _get_ffmpeg_path, _get_ffprobe_path

logger = logging.getLogger(__name__)


@dataclass
class AudioImportResult:
    """Result of audio import operation."""
    metadata: AudioMetadata
    temp_wav_path: str
    original_path: str
    project_id: Optional[str]


class AudioImportWorker(BaseWorker):
    """
    Worker for importing and converting audio files to WAV.

    Uses FFmpeg to extract audio and convert to 16-bit PCM WAV.
    This ensures compatibility with all downstream audio processing.

    VRAM Budget: 0 MB (CPU-only, FFmpeg subprocess)
    """

    def __init__(self, file_path: str, project_id: Optional[str] = None):
        """
        Initialize the audio import worker.

        Args:
            file_path: Path to the audio/video file to import
            project_id: Optional project ID for organization
        """
        super().__init__("AudioImportWorker", vram_budget_mb=0)
        self.file_path = file_path
        self.project_id = project_id
        self.temp_wav_path: Optional[str] = None

    def _execute(self) -> AudioImportResult:
        """
        Execute the audio import operation.

        Returns:
            AudioImportResult with metadata and temp WAV path
        """
        self.emit_progress(0, "Starting audio import...")
        self._check_cancelled()

        # Validate input file
        input_path = Path(self.file_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {self.file_path}")

        self.emit_progress(10, "Probing audio metadata...")
        self._check_cancelled()

        # Probe file for metadata
        metadata = self._probe_audio_metadata()

        self.emit_progress(30, "Converting to WAV...")
        self._check_cancelled()

        try:
            # Convert to WAV
            self.temp_wav_path = self._convert_to_wav()

            self.emit_progress(90, "Validating output...")
            self._check_cancelled()

            # Validate output
            if not Path(self.temp_wav_path).exists():
                raise RuntimeError("WAV conversion failed: output file not created")

            output_size = Path(self.temp_wav_path).stat().st_size
            if output_size == 0:
                raise RuntimeError("WAV conversion failed: output file is empty")

            logger.info(f"Audio import complete: {self.temp_wav_path} ({output_size} bytes)")
            self.emit_progress(100, "Import complete")

            return AudioImportResult(
                metadata=metadata,
                temp_wav_path=self.temp_wav_path,
                original_path=self.file_path,
                project_id=self.project_id
            )
        except Exception:
            # BUG-087 FIX: Cleanup temp file on error/cancel
            if self.temp_wav_path and Path(self.temp_wav_path).exists():
                try:
                    os.remove(self.temp_wav_path)
                except Exception as e:
                    logger.debug(f"Could not delete temp WAV: {e}")
            raise

    def _probe_audio_metadata(self) -> AudioMetadata:
        """
        Probe audio file for metadata using FFprobe.

        Returns:
            AudioMetadata with duration, sample_rate, channels, codec
        """
        try:
            # FFprobe command for JSON output
            command = [
                _get_ffprobe_path(),
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-select_streams", "a:0",
                self.file_path
            ]

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.warning(f"FFprobe failed: {result.stderr}")
                return self._get_fallback_metadata()

            import json
            probe_data = json.loads(result.stdout)

            if not probe_data.get("streams"):
                logger.warning("No audio streams found in file")
                return self._get_fallback_metadata()

            stream = probe_data["streams"][0]

            # Extract metadata
            duration = float(stream.get("duration", 0))
            sample_rate = int(stream.get("sample_rate", 44100))
            channels = int(stream.get("channels", 2))
            codec = stream.get("codec_name", "unknown")

            return AudioMetadata(
                duration=duration,
                sample_rate=sample_rate,
                channels=channels,
                codec=codec
            )

        except Exception as e:
            logger.warning(f"Metadata probe failed: {e}")
            return self._get_fallback_metadata()

    def _get_fallback_metadata(self) -> AudioMetadata:
        """Return fallback metadata when probing fails."""
        return AudioMetadata(
            duration=0.0,
            sample_rate=44100,
            channels=2,
            codec="unknown"
        )

    def _convert_to_wav(self) -> str:
        """
        Convert audio file to 16-bit PCM WAV using FFmpeg.

        Returns:
            Path to the temporary WAV file
        """
        # Generate unique temp file path
        temp_dir = tempfile.gettempdir()
        unique_name = f"pb_studio_import_{uuid.uuid4().hex}.wav"
        output_path = str(Path(temp_dir) / unique_name)

        # FFmpeg command: convert to 16-bit PCM WAV, 44.1kHz stereo
        command = [
            _get_ffmpeg_path(),
            "-y",  # Overwrite output
            "-i", self.file_path,
            "-vn",  # No video
            "-acodec", "pcm_s16le",  # 16-bit PCM
            "-ar", "44100",  # 44.1kHz sample rate
            "-ac", "2",  # Stereo
            output_path
        ]

        logger.info(f"Converting audio: {self.file_path} -> {output_path}")

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for long files
        )

        if result.returncode != 0:
            error_msg = result.stderr[:500] if result.stderr else "Unknown error"
            raise RuntimeError(f"FFmpeg conversion failed: {error_msg}")

        return output_path

    def cleanup(self) -> None:
        """
        Clean up temporary files.

        Call this after processing is complete to free disk space.
        """
        if self.temp_wav_path and Path(self.temp_wav_path).exists():
            try:
                os.remove(self.temp_wav_path)
                logger.debug(f"Cleaned up temp file: {self.temp_wav_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file: {e}")
