"""
Audio Stem Worker for PB Studio AMD

Performs stem separation using audio-separator with DirectML acceleration.
VRAM Budget: 2000 MB (GPU-accelerated ONNX models)
"""

import logging
import os
from pathlib import Path
from typing import Optional

from ..base_worker import BaseWorker
from ...audio.separator import StemSeparator
from ...models.audio import StemResult

logger = logging.getLogger(__name__)

# Default models for different separation types
DEFAULT_VOCAL_MODEL = "UVR-MDX-NET-Inst_HQ_3.onnx"
DEMUCS_MODEL = "htdemucs_ft"  # Full 4-stem separation
MDX_VOCALS_MODEL = "UVR-MDX-NET-Voc_FT.onnx"


class AudioStemWorker(BaseWorker):
    """
    Worker for audio stem separation.

    Uses the existing StemSeparator with DirectML patch for AMD GPUs.
    ONNX models (MDX) get GPU acceleration, PyTorch models (Demucs) run on CPU.

    VRAM Budget: 2000 MB (ONNX DirectML inference)
    """

    def __init__(
        self,
        file_path: str,
        model_name: str = DEFAULT_VOCAL_MODEL,
        output_dir: Optional[str] = None
    ):
        """
        Initialize the stem separation worker.

        Args:
            file_path: Path to the audio file to separate
            model_name: Name of the separation model to use
            output_dir: Optional output directory (uses temp if not specified)
        """
        super().__init__("AudioStemWorker", vram_budget_mb=2000)
        self.file_path = file_path
        self.model_name = model_name
        self.output_dir = output_dir
        self._separator: Optional[StemSeparator] = None

    def _execute(self) -> StemResult:
        """
        Execute the stem separation operation.

        Returns:
            StemResult with paths to separated stems
        """
        self.emit_progress(0, "Initializing stem separator...")
        self._check_cancelled()

        # Validate input file
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Input file not found: {self.file_path}")

        # Initialize separator
        self._separator = StemSeparator()

        if self._separator.separator is None:
            raise RuntimeError("Stem separator failed to initialize. Check audio-separator installation.")

        self.emit_progress(10, f"Loading model: {self.model_name}...")
        self._check_cancelled()

        # Set custom output directory if specified
        if self.output_dir:
            os.makedirs(self.output_dir, exist_ok=True)
            self._separator.separator.output_dir = self.output_dir

        self.emit_progress(20, "Running stem separation...")
        self._check_cancelled()

        try:
            # Run separation
            result = self._separator.separate(self.file_path, self.model_name)

            self.emit_progress(90, "Processing outputs...")
            self._check_cancelled()

            # Check for errors
            if "error" in result:
                raise RuntimeError(f"Separation failed: {result['error']}")

            # Parse output files
            stem_paths = result.get("stems", [])
            stem_result = self._parse_stem_outputs(stem_paths)

            logger.info(f"Stem separation complete: {len(stem_paths)} files generated")
            self.emit_progress(100, "Separation complete")

            return stem_result

        except Exception:
            # ONNX-Session freigeben bei Fehler
            if self._separator is not None and hasattr(self._separator, 'unload'):
                try:
                    self._separator.unload()
                except Exception as e:
                    logger.warning(f"Separator unload error: {e}")
            raise

    def _parse_stem_outputs(self, stem_paths: list) -> StemResult:
        """
        Parse separation output files into StemResult.

        The output filenames depend on the model used:
        - MDX models: *_(Vocals).wav, *_(Instrumental).wav
        - Demucs: vocals.wav, drums.wav, bass.wav, other.wav

        Args:
            stem_paths: List of output file paths

        Returns:
            StemResult with categorized stem paths
        """
        vocals_path = None
        instrumental_path = None
        drums_path = None
        bass_path = None
        other_path = None

        for path in stem_paths:
            path_lower = path.lower()
            filename = Path(path).stem.lower()

            # Check various naming conventions
            if "vocal" in path_lower or filename.endswith("vocals"):
                vocals_path = path
            elif "instrumental" in path_lower or "inst" in filename:
                instrumental_path = path
            elif "drum" in path_lower:
                drums_path = path
            elif "bass" in path_lower:
                bass_path = path
            elif "other" in path_lower or "no_vocals" in path_lower:
                # Some models output "no_vocals" instead of "instrumental"
                if instrumental_path is None:
                    instrumental_path = path
                else:
                    other_path = path

        # If we only got 2 stems and no drums/bass, assume vocal/instrumental split
        if len(stem_paths) == 2 and drums_path is None and bass_path is None:
            for path in stem_paths:
                if vocals_path != path and instrumental_path is None:
                    instrumental_path = path

        return StemResult(
            vocals_path=vocals_path,
            instrumental_path=instrumental_path,
            drums_path=drums_path,
            bass_path=bass_path,
            other_path=other_path
        )

    def get_available_models(self) -> dict:
        """
        Get list of available separation models.

        Returns:
            Dictionary of model categories and names
        """
        if self._separator is None:
            self._separator = StemSeparator()

        return self._separator.list_models()
