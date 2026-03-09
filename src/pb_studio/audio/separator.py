"""
Stem Separator for AMD GPUs (DirectML Patched)

The standard audio-separator library only auto-detects CUDA (NVIDIA) or MPS (Apple).
This wrapper forces DirectML usage for ONNX Runtime, enabling AMD GPU acceleration.
"""
import logging
import os
import onnxruntime as ort
from pathlib import Path
from pb_studio.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class StemSeparator:
    def __init__(self):
        self.config = ConfigManager()
        self.separator = None
        self._init_engine()

    def _init_engine(self):
        try:
            from audio_separator.separator import Separator
            
            # Get config paths
            model_dir = self.config.get("paths", {}).get("models_dir", "./models")
            output_dir = self.config.get("paths", {}).get("temp_dir", "./temp")
            
            # Create dirs if needed
            os.makedirs(model_dir, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)
            
            # Initialize Separator
            self.separator = Separator(
                model_file_dir=model_dir,
                output_dir=output_dir,
                output_format="WAV"
            )
            
            # === AMD DirectML PATCH ===
            # Override the ONNX execution provider AFTER init
            # This forces DirectML usage for ONNX-based models (MDX, MDXC)
            available_providers = ort.get_available_providers()

            if "DmlExecutionProvider" in available_providers:
                logger.info("AMD DirectML detected. Patching audio-separator for GPU acceleration.")
                self.separator.onnx_execution_provider = ["DmlExecutionProvider", "CPUExecutionProvider"]
                logger.info(f"ONNX Provider set to: {self.separator.onnx_execution_provider}")

                # SessionOptions Patch wird nur während separate() aktiv gehalten
                # (siehe _apply_directml_patch / _restore_directml_patch)
                self._has_directml = True
            else:
                logger.warning("DirectML not available. Running in CPU mode.")
                self._has_directml = False
            # === END PATCH ===
            
            logger.info("StemSeparator initialized (DirectML Patched).")
            
        except ImportError as e:
            logger.error(f"AudioSeparator import failed: {e}")
            self.separator = None
        except Exception as e:
            logger.error(f"StemSeparator init error: {e}")
            self.separator = None

    def _apply_directml_patch(self):
        """Apply SessionOptions monkey-patch for DirectML (scoped)."""
        if not getattr(self, '_has_directml', False):
            return
        self._original_session_options_init = ort.SessionOptions.__init__
        def _patched_init(self_opts, *args, **kwargs):
            self._original_session_options_init(self_opts, *args, **kwargs)
            self_opts.enable_mem_pattern = False
        ort.SessionOptions.__init__ = _patched_init
        logger.debug("SessionOptions patch applied for DirectML separation")

    def _restore_directml_patch(self):
        """Restore original SessionOptions.__init__ after separation."""
        original = getattr(self, '_original_session_options_init', None)
        if original is not None:
            ort.SessionOptions.__init__ = original
            self._original_session_options_init = None
            logger.debug("SessionOptions patch restored")

    def separate(self, file_path: str, model_name: str = "UVR-MDX-NET-Inst_HQ_3.onnx"):
        """
        Separates audio into stems.

        Args:
            file_path: Path to audio file.
            model_name: Name of the model to use.
                       ONNX models (MDX): Get DirectML acceleration.
                       PyTorch models (Demucs): Run on CPU (PyTorch has no DML).

        Returns:
            dict with 'stems' list or 'error' string.
        """
        if not self.separator:
            return {"error": "Separator not initialized"}

        if not Path(file_path).exists():
            return {"error": f"File not found: {file_path}"}

        # Scoped DirectML patch: nur während Separation aktiv
        self._apply_directml_patch()
        try:
            logger.info(f"Loading model: {model_name}")
            self.separator.load_model(model_name)

            logger.info(f"Starting separation for: {file_path}")
            logger.info(f"Using ONNX Provider: {self.separator.onnx_execution_provider}")

            output_files = self.separator.separate(file_path)

            logger.info(f"Separation complete. Files: {output_files}")
            return {"stems": output_files}

        except Exception as e:
            logger.error(f"Separation failed: {e}")
            return {"error": str(e)}
        finally:
            self._restore_directml_patch()

    def list_models(self):
        """Returns available models grouped by type."""
        if not self.separator:
            return {}
        try:
            return self.separator.list_supported_model_files()
        except Exception as e:
            logger.debug(f"Could not list models: {e}")
            return {}
