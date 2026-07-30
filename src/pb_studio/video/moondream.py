"""
Moondream Vision-Language Model - ONNX Implementation with DirectML.

This module provides image captioning and analysis using the Moondream2 model
exported to ONNX format. Optimized for AMD GPUs via DirectML.

Architecture:
- Vision Encoder: SigLIP-based image encoder
- Text Decoder: Phi-based autoregressive decoder
"""

import logging
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Any
from PIL import Image

from pb_studio.core.gpu_lock import gpu_inference_lock
from pb_studio.core.directml_adapter import (
    configure_directml_session_options,
    enforce_directml_session,
    get_directml_adapter,
    get_directml_provider,
)


try:
    import onnxruntime as ort
except ImportError:  # pragma: no cover - optional dependency in test envs
    class _FallbackSessionOptions:
        def __init__(self):
            self.enable_mem_pattern = True
            self.graph_optimization_level = None
            self.enable_cpu_mem_arena = True
            self.intra_op_num_threads = 0
            self.inter_op_num_threads = 0

    class _FallbackGraphOptimizationLevel:
        ORT_ENABLE_ALL = "ORT_ENABLE_ALL"

    class _FallbackOrt:
        SessionOptions = _FallbackSessionOptions
        GraphOptimizationLevel = _FallbackGraphOptimizationLevel
        InferenceSession = object

        @staticmethod
        def get_available_providers() -> List[str]:
            return []

    ort = _FallbackOrt()

logger = logging.getLogger(__name__)

# Moondream2 preprocessing constants (SigLIP)
SIGLIP_IMAGE_SIZE = 384
SIGLIP_MEAN = np.array([0.5, 0.5, 0.5], dtype=np.float32)
SIGLIP_STD = np.array([0.5, 0.5, 0.5], dtype=np.float32)

# Generation defaults
DEFAULT_MAX_TOKENS = 256
DEFAULT_TEMPERATURE = 0.0  # Greedy decoding
EOS_TOKEN_ID = 50256  # GPT2/Phi EOS token


def onnx_models_available(models_dir: Optional[str] = None) -> bool:
    """Cheap filesystem check ob Moondream-ONNX-Dateien vorhanden sind.

    Vermeidet, dass Aufrufer einen with_gpu_task-Slot fuer eine Inferenz
    reservieren, die per IRON RULE (kein CPU-Fallback) ohnehin nur
    fehlschlagen kann, wenn die ONNX-Modelle fehlen.
    """
    if models_dir is None:
        from pb_studio.config_manager import ConfigManager
        models_dir = ConfigManager().get("paths", {}).get("models_dir", "./models")
    models_path = Path(models_dir)
    encoder_candidates = [
        models_path / "moondream_encoder.onnx",
        models_path / "moondream_vision.onnx",
    ]
    combined_path = models_path / "moondream.onnx"
    return any(c.exists() for c in encoder_candidates) or combined_path.exists()


class MoondreamAnalyzer:
    """
    Moondream2 Vision-Language Model for image captioning and analysis.

    Uses ONNX Runtime with DirectML for AMD GPU acceleration.
    Fails closed if DirectML is unavailable.

    Model Structure (expected ONNX files):
    - moondream_encoder.onnx: Vision encoder (SigLIP)
    - moondream_decoder.onnx: Text decoder (Phi)
    OR
    - moondream.onnx: Combined model
    """

    def __init__(self, models_dir: Optional[str] = None, lazy_load: bool = False):
        """
        Initialize the Moondream analyzer.

        Args:
            models_dir: Directory containing ONNX model files.
                       If None, uses ConfigManager default.
            lazy_load: If True, defer model loading until first use.
        """
        # Import here to avoid circular imports
        from pb_studio.config_manager import ConfigManager

        self.config = ConfigManager()
        self._models_dir = models_dir or self.config.get("paths", {}).get("models_dir", "./models")

        # Session states
        self.encoder_session: Optional[ort.InferenceSession] = None
        self.decoder_session: Optional[ort.InferenceSession] = None
        self.combined_session: Optional[ort.InferenceSession] = None

        # Tokenizer
        self.tokenizer = None

        # Model metadata
        self._is_combined_model = False
        self._hybrid_mode = False
        self._active_provider = "Unknown"
        self._initialized = False
        self._pytorch_fallback = None

        if not lazy_load:
            self._init_model()

    def _create_session_options(self) -> ort.SessionOptions:
        """Create optimized session options for DirectML compatibility."""
        sess_options = configure_directml_session_options(ort.SessionOptions())

        # KRITISCH fuer DirectML: beide Memory-Flags MÜSSEN False sein.
        # R16: enable_cpu_mem_arena=True war falsch — CPU-Arena konkurriert mit
        # DmlExecutionProvider-Allocator und kann OOM / Instabilität verursachen.
        # Graph-Optimierungen aktivieren
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = 0  # Auto
        sess_options.inter_op_num_threads = 0  # Auto

        return sess_options

    def _get_providers(self) -> List[Any]:
        """Get available execution providers — DirectML only (AMD IRON RULE: no CPU fallback)."""
        available = ort.get_available_providers()

        if 'DmlExecutionProvider' in available:
            adapter = get_directml_adapter()
            logger.info(
                "DirectML provider available "
                "(device_id=%d, luid=%s, adapter=%s) - "
                "using AMD GPU acceleration",
                adapter.device_id,
                adapter.luid,
                adapter.name,
            )
            return [get_directml_provider()]

        # IRON RULE: AMD DirectML ONLY — kein sekundärer Provider
        return []

    @staticmethod
    def _create_onnx_session(
        model_path: Path,
        session_options: ort.SessionOptions,
        providers: List[Any],
    ) -> ort.InferenceSession:
        return enforce_directml_session(
            ort.InferenceSession(
                str(model_path),
                session_options,
                providers=providers,
            )
        )

    def _init_tokenizer(self) -> bool:
        """Initialize the tokenizer for text processing."""
        try:
            from transformers import CodeGenTokenizerFast

            # Versuche lokalen Cache zuerst
            local_tokenizer_path = Path(self._models_dir) / "moondream_tokenizer"

            if local_tokenizer_path.exists():
                self.tokenizer = CodeGenTokenizerFast.from_pretrained(str(local_tokenizer_path), local_files_only=True)
                logger.info(f"Loaded tokenizer from local cache: {local_tokenizer_path}")
            else:
                # Versuche von HuggingFace Hub (Offline-Modus erzwungen)
                try:
                    self.tokenizer = CodeGenTokenizerFast.from_pretrained("vikhyat/moondream2", local_files_only=True)
                    logger.info("Loaded tokenizer from HuggingFace Hub")

                    # Speichere lokal fuer zukuenftige Verwendung
                    try:
                        local_tokenizer_path.mkdir(parents=True, exist_ok=True)
                        self.tokenizer.save_pretrained(str(local_tokenizer_path))
                        logger.info(f"Cached tokenizer to: {local_tokenizer_path}")
                    except Exception as e:
                        logger.warning(f"Could not cache tokenizer: {e}")

                except Exception as e:
                    logger.warning(f"Could not load tokenizer from hub: {e}")
                    return False

            return True

        except ImportError:
            logger.error("transformers library not installed. Run: pip install transformers")
            return False
        except Exception as e:
            logger.error(f"Tokenizer initialization failed: {e}")
            return False

    def _init_model(self) -> bool:
        """
        Initialize ONNX model sessions.

        Supports two model architectures:
        1. Split models: encoder.onnx + decoder.onnx
        2. Combined model: moondream.onnx
        3. PyTorch fallback if no ONNX models exist
        """
        if self._initialized:
            return True

        models_path = Path(self._models_dir)

        # Pruefe ob ONNX-Modelle existieren (mehrere Dateinamen unterstuetzt)
        encoder_candidates = [
            models_path / "moondream_encoder.onnx",
            models_path / "moondream_vision.onnx",
        ]
        decoder_path = models_path / "moondream_decoder.onnx"
        combined_path = models_path / "moondream.onnx"

        # Finde den ersten vorhandenen Encoder
        encoder_path = None
        for candidate in encoder_candidates:
            if candidate.exists():
                encoder_path = candidate
                break

        # Wenn keine ONNX-Modelle vorhanden → kein PyTorch-Fallback (IRON RULE)
        has_onnx_models = (
            (encoder_path is not None and decoder_path.exists()) or
            encoder_path is not None or
            combined_path.exists()
        )

        if not has_onnx_models:
            logger.warning(
                "Moondream ONNX-Modelle nicht gefunden. "
                "Kein CPU-Fallback (IRON RULE: AMD DirectML only). "
                "generate_caption() gibt Platzhaltertext zurück."
            )
            return False

        # Initialize tokenizer first
        if not self._init_tokenizer():
            logger.warning("Tokenizer not available - text generation will be limited")

        has_real_ort = (
            hasattr(ort, "InferenceSession") and
            ort.InferenceSession is not object and
            isinstance(ort.InferenceSession, type)
        )
        if not has_real_ort:
            logger.warning(
                "onnxruntime nicht installiert — Moondream deaktiviert. "
                "Kein PyTorch-Fallback (IRON RULE: kein CPU-Fallback)."
            )
            return False

        # Session options und providers
        sess_options = self._create_session_options()
        providers = self._get_providers()

        if not providers:
            logger.warning(
                "Moondream: DmlExecutionProvider nicht verfügbar. "
                "Moondream deaktiviert (IRON RULE: kein CPU-Fallback)."
            )
            return False

        try:
            if encoder_path is not None and decoder_path.exists():
                # Split Model Architecture (Encoder + Decoder ONNX)
                logger.info(f"Loading split Moondream model from {models_path}")

                self.encoder_session = self._create_onnx_session(
                    encoder_path,
                    sess_options,
                    providers,
                )
                self.decoder_session = self._create_onnx_session(
                    decoder_path,
                    sess_options,
                    providers,
                )

                self._is_combined_model = False
                self._active_provider = self.encoder_session.get_providers()[0]

                logger.info(f"Moondream encoder loaded. Provider: {self._active_provider}")
                logger.info(f"Moondream decoder loaded. Provider: {self.decoder_session.get_providers()[0]}")

            elif encoder_path is not None and not decoder_path.exists():
                # Encoder-only ONNX — kein PyTorch-Decoder-Fallback (IRON RULE)
                logger.info(f"Loading Moondream ONNX encoder only (no decoder found): {encoder_path}")

                self.encoder_session = self._create_onnx_session(
                    encoder_path,
                    sess_options,
                    providers,
                )

                self._is_combined_model = False
                self._active_provider = self.encoder_session.get_providers()[0]
                # Hybrid-Mode bleibt False — kein PyTorch-Decoder
                logger.info(f"Moondream encoder loaded (encoder-only mode). Provider: {self._active_provider}")
                logger.warning(
                    "Moondream-Decoder (ONNX) fehlt — Textgenerierung nicht verfügbar. "
                    "Kein PyTorch-Fallback (IRON RULE)."
                )

            elif combined_path.exists():
                # Combined Model Architecture
                logger.info(f"Loading combined Moondream model from {combined_path}")

                self.combined_session = self._create_onnx_session(
                    combined_path,
                    sess_options,
                    providers,
                )

                self._is_combined_model = True
                self._active_provider = self.combined_session.get_providers()[0]

                logger.info(f"Moondream combined model loaded. Provider: {self._active_provider}")

            else:
                logger.warning(
                    "Moondream ONNX model not found. Expected one of:\n"
                    f"  - moondream_encoder.onnx or moondream_vision.onnx\n"
                    f"  - {combined_path}\n"
                    "Run: python download_models.py --moondream"
                )
                return False

            self._initialized = True
            self._log_model_info()
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Moondream model: {e}")
            self.encoder_session = None
            self.decoder_session = None
            self.combined_session = None
            self._initialized = False  # Flag zuruecksetzen bei Fehler
            return False

    def _log_model_info(self):
        """Log model input/output information for debugging."""
        session = self.combined_session or self.encoder_session
        if session:
            logger.debug("Model Inputs:")
            for inp in session.get_inputs():
                logger.debug(f"  {inp.name}: {inp.shape} ({inp.type})")

            logger.debug("Model Outputs:")
            for out in session.get_outputs():
                logger.debug(f"  {out.name}: {out.shape} ({out.type})")

    def preprocess_image(self, image: Image.Image) -> np.ndarray:
        """
        Preprocess image for SigLIP vision encoder.

        Steps:
        1. Resize to 384x384 (bicubic interpolation)
        2. Convert to float32 [0, 1]
        3. Normalize with SigLIP mean/std
        4. Transpose to NCHW format

        Args:
            image: PIL Image (RGB)

        Returns:
            Preprocessed image tensor [1, 3, 384, 384]
        """
        # Konvertiere zu RGB falls noetig
        if image.mode != 'RGB':
            image = image.convert('RGB')

        session = self.combined_session or self.encoder_session
        target_size = SIGLIP_IMAGE_SIZE
        if session is not None:
            shape = session.get_inputs()[0].shape
            if len(shape) >= 4 and isinstance(shape[-1], int):
                target_size = shape[-1]

        # Resize mit hochwertiger Interpolation
        image = image.resize((target_size, target_size), Image.Resampling.BICUBIC)

        # Zu numpy array konvertieren und normalisieren
        img_array = np.array(image, dtype=np.float32) / 255.0

        # SigLIP Normalisierung
        img_array = (img_array - SIGLIP_MEAN) / SIGLIP_STD

        # HWC -> NCHW
        img_array = np.transpose(img_array, (2, 0, 1))  # CHW
        img_array = np.expand_dims(img_array, axis=0)   # NCHW

        return img_array.astype(np.float32)

    def encode_image(self, image: Image.Image) -> Optional[np.ndarray]:
        """
        Encode image to vision embeddings.

        Args:
            image: PIL Image

        Returns:
            Image embeddings tensor or None on error
        """
        if not self._initialized:
            if not self._init_model():
                return None

        try:
            img_tensor = self.preprocess_image(image)

            with gpu_inference_lock:
                if self._is_combined_model:
                    # Combined model - encoder teil
                    # Typische Input-Namen: "pixel_values", "image"
                    input_name = self.combined_session.get_inputs()[0].name

                    # Nur encoder-output zurueckgeben (erster Output typisch)
                    outputs = self.combined_session.run(
                        None,  # Alle outputs
                        {input_name: img_tensor}
                    )
                    return outputs[0]
                else:
                    # Split model - dedizierter encoder
                    input_name = self.encoder_session.get_inputs()[0].name

                    outputs = self.encoder_session.run(
                        None,
                        {input_name: img_tensor}
                    )
                    return outputs[0]

        except Exception as e:
            logger.error(f"Image encoding failed: {e}")
            return None

    def prepare_prompt(self, prompt: str, image_embeddings: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Prepare inputs for text generation.

        Args:
            prompt: Text prompt for the model
            image_embeddings: Encoded image features

        Returns:
            Dictionary of model inputs
        """
        if self.tokenizer is None:
            raise RuntimeError("Tokenizer not initialized")

        # Moondream2 Prompt-Format
        # <image> token wird durch Bild-Embeddings ersetzt
        formatted_prompt = f"<image>\n\nQuestion: {prompt}\n\nAnswer:"

        # Tokenize
        tokens = self.tokenizer.encode(formatted_prompt, return_tensors="np")

        # Attention mask
        attention_mask = np.ones_like(tokens, dtype=np.int64)

        return {
            "input_ids": tokens.astype(np.int64),
            "attention_mask": attention_mask,
            "image_embeddings": image_embeddings.astype(np.float32)
        }

    def generate_tokens(
        self,
        inputs: Dict[str, np.ndarray],
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE
    ) -> List[int]:
        """
        Generate text tokens autoregressively.

        Args:
            inputs: Prepared model inputs
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0 = greedy)

        Returns:
            List of generated token IDs
        """
        session = self.decoder_session or self.combined_session
        if session is None:
            raise RuntimeError("Model not initialized")

        generated_tokens = []
        input_ids = inputs["input_ids"].copy()
        attention_mask = inputs["attention_mask"].copy()
        image_embeddings = inputs["image_embeddings"]

        # Autoregressive Generation Loop
        for _ in range(max_tokens):
            try:
                # Prepare decoder inputs
                decoder_inputs = self._prepare_decoder_inputs(
                    input_ids,
                    attention_mask,
                    image_embeddings
                )

                # Run decoder under global GPU lock
                with gpu_inference_lock:
                    outputs = session.run(None, decoder_inputs)

                # Get logits for next token (last position)
                logits = outputs[0]  # Shape: [batch, seq_len, vocab]
                next_token_logits = np.asarray(logits[0, -1, :], dtype=np.float32)
                next_token_logits = np.nan_to_num(
                    next_token_logits,
                    nan=-1e9,
                    posinf=1e9,
                    neginf=-1e9,
                )

                # BUG-076 FIX: Explicit check for temperature=0 (greedy decoding)
                if temperature > 1e-6:
                    # Temperature sampling
                    probs = self._softmax(next_token_logits / temperature)
                    if np.any(~np.isfinite(probs)) or np.any(probs < 0) or probs.sum() <= 0:
                        logger.warning("Invalid Moondream probabilities; falling back to greedy")
                        next_token = int(np.argmax(next_token_logits))
                    else:
                        next_token = int(np.random.choice(len(probs), p=probs))
                else:
                    # Greedy decoding
                    next_token = int(np.argmax(next_token_logits))

                # Check for EOS
                if next_token == EOS_TOKEN_ID:
                    break

                generated_tokens.append(next_token)

                # Update inputs for next iteration
                input_ids = np.concatenate([
                    input_ids,
                    np.array([[next_token]], dtype=np.int64)
                ], axis=1)

                attention_mask = np.concatenate([
                    attention_mask,
                    np.array([[1]], dtype=np.int64)
                ], axis=1)

            except Exception as e:
                logger.error(f"Token generation error: {e}")
                break

        return generated_tokens

    def _prepare_decoder_inputs(
        self,
        input_ids: np.ndarray,
        attention_mask: np.ndarray,
        image_embeddings: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """Prepare inputs matching decoder's expected format."""
        session = self.decoder_session or self.combined_session
        input_names = [inp.name for inp in session.get_inputs()]

        inputs = {}

        # Mapping gaengiger Input-Namen
        for name in input_names:
            name_lower = name.lower()

            if "input_id" in name_lower or name == "input_ids":
                inputs[name] = input_ids
            elif "attention" in name_lower or "mask" in name_lower:
                inputs[name] = attention_mask
            elif "image" in name_lower or "visual" in name_lower or "embed" in name_lower:
                inputs[name] = image_embeddings
            elif "position" in name_lower:
                # Position IDs
                seq_len = input_ids.shape[1]
                inputs[name] = np.arange(seq_len, dtype=np.int64).reshape(1, -1)

        return inputs

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        """Compute numerically stable softmax values."""
        x = np.asarray(x, dtype=np.float32)
        x = np.nan_to_num(x, nan=-1e9, posinf=1e9, neginf=-1e9)
        x = x - np.max(x)
        x = np.clip(x, -80.0, 80.0)
        e_x = np.exp(x)
        denom = float(np.sum(e_x))
        if not np.isfinite(denom) or denom <= 0:
            probs = np.zeros_like(x, dtype=np.float32)
            probs[int(np.argmax(x))] = 1.0
            return probs
        return (e_x / denom).astype(np.float32)

    def generate_caption(
        self,
        image: Image.Image,
        prompt: str = "Describe this image in detail.",
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE
    ) -> str:
        """
        Generate a caption or answer for an image.

        This is the main high-level API for image analysis.

        Args:
            image: PIL Image to analyze
            prompt: Question or instruction for the model
            max_tokens: Maximum response length
            temperature: Sampling temperature

        Returns:
            Generated text response
        """
        if not self._initialized:
            if not self._init_model():
                return "[Moondream-Modell nicht gefunden]"

        if self.tokenizer is None:
            return "[Error: Tokenizer not available]"

        try:
            # 1. Encode Image
            logger.debug(f"Encoding image for prompt: {prompt[:50]}...")
            image_embeddings = self.encode_image(image)

            if image_embeddings is None:
                return "[Error: Image encoding failed]"

            # 2. Prepare Prompt
            inputs = self.prepare_prompt(prompt, image_embeddings)

            # 3. Generate Tokens
            generated_tokens = self.generate_tokens(inputs, max_tokens, temperature)

            if not generated_tokens:
                return "[No response generated]"

            # 4. Decode to Text
            response = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)

            return response.strip()

        except Exception as e:
            logger.error(f"Caption generation failed: {e}")
            return f"[Error: {str(e)}]"

    def analyze_frame(
        self,
        frame_array: np.ndarray,
        prompt: str = "Describe this video frame."
    ) -> str:
        """
        Analyze a video frame (numpy array from OpenCV).

        Convenience method for video processing pipelines.

        Args:
            frame_array: BGR numpy array from cv2.imread/VideoCapture
            prompt: Analysis prompt

        Returns:
            Generated analysis text
        """
        try:
            # OpenCV BGR -> PIL RGB
            import cv2
            rgb_array = cv2.cvtColor(frame_array, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb_array)

            return self.generate_caption(image, prompt)

        except Exception as e:
            logger.error(f"Frame analysis failed: {e}")
            return f"[Error: {str(e)}]"

    def batch_analyze(
        self,
        images: List[Image.Image],
        prompt: str = "Describe this image.",
        max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> List[str]:
        """
        Analyze multiple images.

        Note: Currently processes sequentially. Batch processing
        requires model changes for batched inference.

        Args:
            images: List of PIL Images
            prompt: Common prompt for all images
            max_tokens: Maximum tokens per response

        Returns:
            List of generated captions
        """
        results = []

        for i, img in enumerate(images):
            logger.debug(f"Analyzing image {i+1}/{len(images)}")
            caption = self.generate_caption(img, prompt, max_tokens)
            results.append(caption)

        return results

    def get_scene_description(self, image: Image.Image) -> Dict[str, Any]:
        """
        Get structured scene analysis.

        Returns multiple aspects of the image in a dictionary.

        Args:
            image: PIL Image to analyze

        Returns:
            Dictionary with scene analysis results
        """
        prompts = {
            "description": "Describe this image in one sentence.",
            "objects": "List the main objects visible in this image.",
            "mood": "What is the mood or atmosphere of this image?",
            "action": "What action or activity is happening in this image?"
        }

        results = {}
        for key, prompt in prompts.items():
            results[key] = self.generate_caption(image, prompt, max_tokens=100)

        return results

    @property
    def is_ready(self) -> bool:
        """Check if model is initialized and ready for inference."""
        if not self._initialized:
            return False

        # Hybrid Mode: Encoder ONNX + PyTorch Decoder
        if self._hybrid_mode and self.encoder_session is not None:
            return True

        # Reiner PyTorch-Fallback
        if self._pytorch_fallback is not None and self.encoder_session is None:
            return True

        # Volle ONNX Pipeline
        return (
            self.combined_session is not None or
            (self.encoder_session is not None and self.decoder_session is not None)
        )

    @property
    def is_vision_ready(self) -> bool:
        """True when the Moondream vision encoder can run on DirectML."""
        return self._initialized and (
            self.combined_session is not None or self.encoder_session is not None
        )

    @property
    def active_provider(self) -> str:
        """Get the active execution provider name."""
        return self._active_provider

    def unload(self):
        """Release model resources."""
        self.encoder_session = None
        self.decoder_session = None
        self.combined_session = None
        self._hybrid_mode = False
        if self._pytorch_fallback is not None:
            try:
                self._pytorch_fallback.unload()
            except Exception:
                pass
            self._pytorch_fallback = None
        self._initialized = False

        # DirectML gibt VRAM erst bei GC frei
        import gc
        gc.collect()

        logger.info("Moondream model unloaded")
