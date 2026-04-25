"""
Audio Service für PB_studio AMD

High-Level Service für Audio-Operationen mit Stem-Separation-Integration.
Angepasst für AMD: Nutzt UVR-MDX-NET via StemSeparator statt Demucs-Enums.
"""

import logging
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str, Optional[int], Optional[int]], None]


class AudioService:
    """High-Level Service für Audio-Operationen (AMD Version)."""

    def __init__(
        self,
        stems_output_dir: Optional[Path] = None,
        default_model: str = "UVR-MDX-NET-Inst_HQ_3.onnx",
    ):
        self.stems_output_dir = stems_output_dir
        self.default_model = default_model
        self._stem_separator = None
        logger.info(f"AudioService initialisiert: model={default_model}")

    def get_stem_separator(self):
        """Lazy-Initialisierung des StemSeparators."""
        if self._stem_separator is None:
            from ..audio.separator import StemSeparator
            # BUG-060 FIX: StemSeparator erwartet kein output_dir im __init__
            self._stem_separator = StemSeparator()
        return self._stem_separator

    def separate(
        self,
        audio_path: str | Path,
        model_name: Optional[str] = None,
    ) -> dict:
        """
        Führt Stem-Separation durch.

        Args:
            audio_path: Pfad zur Audiodatei
            model_name: UVR-Modell (None = default)

        Returns:
            Dict mit Pfaden zu den separierten Stems
        """
        separator = self.get_stem_separator()
        model = model_name or self.default_model
        return separator.separate(str(audio_path), model_name=model)

    def clear_cache(self) -> None:
        """Löscht den Stem-Cache."""
        if self._stem_separator and hasattr(self._stem_separator, "clear_cache"):
            self._stem_separator.clear_cache()
            logger.info("Stem-Cache gelöscht")


_audio_service: Optional[AudioService] = None


def get_audio_service(
    stems_output_dir: Optional[Path] = None,
) -> AudioService:
    """Gibt die globale AudioService-Instanz zurück."""
    global _audio_service
    if _audio_service is None:
        _audio_service = AudioService(stems_output_dir=stems_output_dir)
    return _audio_service
