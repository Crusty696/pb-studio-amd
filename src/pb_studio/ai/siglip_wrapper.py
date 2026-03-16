"""
SigLIP Image Encoder - ONNX Implementation with DirectML.

This module provides image and text embedding using the SigLIP model
(Sigmoid Loss for Language-Image Pre-training) exported to ONNX format.
Optimized for AMD GPUs via DirectML.

Model: google/siglip-so400m-patch14-384
- Input: 384x384 RGB Image
- Output: 1152-dimensional embedding
- Text encoder: 1152-dimensional text embeddings

Architecture:
- Vision Encoder: ViT-SO400M (patch size 14, image size 384)
- Text Encoder: Transformer-based text encoder
- Similarity: Cosine similarity between image and text embeddings
"""

import logging
import numpy as np
from pathlib import Path
from typing import Optional, List, Union, Tuple
from PIL import Image

try:
    import onnxruntime as ort
except ImportError:  # pragma: no cover - exercised via degraded test envs
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
            return ["CPUExecutionProvider"]

    ort = _FallbackOrt()

logger = logging.getLogger(__name__)

# SigLIP preprocessing constants
SIGLIP_IMAGE_SIZE = 384
SIGLIP_MEAN = np.array([0.5, 0.5, 0.5], dtype=np.float32)
SIGLIP_STD = np.array([0.5, 0.5, 0.5], dtype=np.float32)
EMBEDDING_DIM = 1152  # SigLIP-SO400M output dimension


class SigLIPWrapper:
    """
    SigLIP Image and Text Encoder for zero-shot classification and similarity.

    Uses ONNX Runtime with DirectML for AMD GPU acceleration.
    Falls back to CPU if DirectML is unavailable.

    Model Structure (expected ONNX files):
    - siglip_vision.onnx: Vision encoder (images -> embeddings)
    - siglip_text.onnx: Text encoder (text -> embeddings)
    OR
    - siglip.onnx: Combined model (both vision and text)
    """

    def __init__(self, models_dir: Optional[str] = None, lazy_load: bool = False):
        """
        Initialize the SigLIP wrapper.

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
        self.vision_session: Optional[ort.InferenceSession] = None
        self.text_session: Optional[ort.InferenceSession] = None

        # Tokenizer
        self.tokenizer = None

        # Model metadata
        self._active_provider = "Unknown"
        self._initialized = False

        if not lazy_load:
            self._init_model()

    def _create_session_options(self) -> ort.SessionOptions:
        """Create optimized session options for DirectML compatibility."""
        sess_options = ort.SessionOptions()

        # KRITISCH fuer DirectML: beide Memory-Flags MÜSSEN False sein.
        # R16: enable_cpu_mem_arena=True war falsch — CPU-Arena konkurriert mit
        # DmlExecutionProvider-Allocator und kann OOM / Instabilität verursachen.
        sess_options.enable_mem_pattern = False
        sess_options.enable_cpu_mem_arena = False

        # Graph-Optimierungen aktivieren
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.intra_op_num_threads = 0  # Auto
        sess_options.inter_op_num_threads = 0  # Auto

        return sess_options

    def _get_providers(self) -> List[str]:
        """Get available execution providers with DirectML priority."""
        available = ort.get_available_providers()

        # Prioritaet: DirectML > CPU
        providers = []

        if 'DmlExecutionProvider' in available:
            providers.append('DmlExecutionProvider')
            logger.info("DirectML provider available - using AMD GPU acceleration")

        # CPU als Fallback immer hinzufuegen
        providers.append('CPUExecutionProvider')

        return providers

    def _init_tokenizer(self) -> bool:
        """Initialize the tokenizer for text processing."""
        try:
            from transformers import AutoTokenizer

            # Versuche lokalen Cache zuerst
            local_tokenizer_path = Path(self._models_dir) / "siglip_tokenizer"

            if local_tokenizer_path.exists():
                self.tokenizer = AutoTokenizer.from_pretrained(str(local_tokenizer_path))
                logger.info(f"Loaded tokenizer from local cache: {local_tokenizer_path}")
            else:
                # Versuche von HuggingFace Hub
                try:
                    self.tokenizer = AutoTokenizer.from_pretrained("google/siglip-so400m-patch14-384")
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
        1. Split models: siglip_vision.onnx + siglip_text.onnx
        2. Combined model: siglip.onnx (less common)
        """
        if self._initialized:
            return True

        models_path = Path(self._models_dir)

        # Initialize tokenizer first
        if not self._init_tokenizer():
            logger.warning("Tokenizer not available - text encoding will be limited")

        if not hasattr(ort, "InferenceSession") or ort.InferenceSession is object:
            logger.warning("onnxruntime not installed - SigLIP model loading disabled")
            return False

        # Session options und providers
        sess_options = self._create_session_options()
        providers = self._get_providers()

        try:
            # Pruefe auf Split-Modell-Architektur
            vision_path = models_path / "siglip_vision.onnx"
            text_path = models_path / "siglip_text.onnx"

            if vision_path.exists():
                # Vision Model (required)
                logger.info(f"Loading SigLIP vision model from {vision_path}")

                self.vision_session = ort.InferenceSession(
                    str(vision_path),
                    sess_options,
                    providers=providers
                )

                self._active_provider = self.vision_session.get_providers()[0]
                logger.info(f"SigLIP vision encoder loaded. Provider: {self._active_provider}")

                # Text Model (optional)
                if text_path.exists():
                    logger.info(f"Loading SigLIP text model from {text_path}")

                    self.text_session = ort.InferenceSession(
                        str(text_path),
                        sess_options,
                        providers=providers
                    )

                    logger.info(f"SigLIP text encoder loaded. Provider: {self.text_session.get_providers()[0]}")
                else:
                    logger.warning(f"Text model not found: {text_path}")
                    logger.warning("Text encoding will not be available")

                self._initialized = True
                self._log_model_info()
                return True

            else:
                logger.warning(
                    f"SigLIP ONNX model not found. Expected:\n"
                    f"  - {vision_path} (required)\n"
                    f"  - {text_path} (optional)\n"
                    "Run model download script or convert from PyTorch."
                )
                return False

        except Exception as e:
            logger.error(f"Failed to initialize SigLIP model: {e}")
            self.vision_session = None
            self.text_session = None
            return False

    def _log_model_info(self):
        """Log model input/output information for debugging."""
        if self.vision_session:
            logger.debug("Vision Model Inputs:")
            for inp in self.vision_session.get_inputs():
                logger.debug(f"  {inp.name}: {inp.shape} ({inp.type})")

            logger.debug("Vision Model Outputs:")
            for out in self.vision_session.get_outputs():
                logger.debug(f"  {out.name}: {out.shape} ({out.type})")

        if self.text_session:
            logger.debug("Text Model Inputs:")
            for inp in self.text_session.get_inputs():
                logger.debug(f"  {inp.name}: {inp.shape} ({inp.type})")

            logger.debug("Text Model Outputs:")
            for out in self.text_session.get_outputs():
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

        # Resize mit hochwertiger Interpolation
        image = image.resize((SIGLIP_IMAGE_SIZE, SIGLIP_IMAGE_SIZE), Image.Resampling.BICUBIC)

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
        Encode image to embedding vector.

        Args:
            image: PIL Image

        Returns:
            Image embedding [1152] or None on error
        """
        if not self._initialized:
            if not self._init_model():
                return None

        if self.vision_session is None:
            logger.error("Vision model not loaded")
            return None

        try:
            img_tensor = self.preprocess_image(image)

            # Get input name
            input_name = self.vision_session.get_inputs()[0].name

            # Run inference
            outputs = self.vision_session.run(None, {input_name: img_tensor})

            # Extract embedding (first output, squeeze batch dimension)
            embedding = outputs[0].squeeze()

            # Handle token-level outputs: mean-pool to get single embedding
            # Some SigLIP ONNX exports output (num_patches, dim) instead of (dim,)
            if embedding.ndim == 2:
                # Mean pooling over patch tokens
                embedding = np.mean(embedding, axis=0)

            # Normalize for cosine similarity
            embedding = embedding / (np.linalg.norm(embedding) + 1e-8)

            return embedding

        except Exception as e:
            logger.error(f"Image encoding failed: {e}")
            return None

    def encode_images_batch(self, images: List[Image.Image]) -> Optional[np.ndarray]:
        """
        Encode multiple images to embedding vectors.

        Note: Currently processes sequentially. Batch processing would require
        model changes to accept dynamic batch sizes.

        Args:
            images: List of PIL Images

        Returns:
            Image embeddings [N, 1152] or None on error
        """
        embeddings = []

        for i, img in enumerate(images):
            logger.debug(f"Encoding image {i+1}/{len(images)}")
            emb = self.encode_image(img)

            if emb is None:
                logger.warning(f"Failed to encode image {i+1}")
                continue

            embeddings.append(emb)

        if not embeddings:
            return None

        return np.stack(embeddings, axis=0)

    def preprocess_text(self, texts: List[str]) -> dict:
        """
        Preprocess text for SigLIP text encoder.

        Args:
            texts: List of text strings

        Returns:
            Dictionary with tokenized inputs
        """
        if self.tokenizer is None:
            raise RuntimeError("Tokenizer not initialized")

        # Tokenize with padding and truncation
        encoding = self.tokenizer(
            texts,
            padding="max_length",
            max_length=64,  # SigLIP typical max length
            truncation=True,
            return_tensors="np"
        )

        return {
            "input_ids": encoding["input_ids"].astype(np.int64),
            "attention_mask": encoding["attention_mask"].astype(np.int64)
        }

    def encode_text(self, texts: Union[str, List[str]]) -> Optional[np.ndarray]:
        """
        Encode text to embedding vectors.

        Args:
            texts: Single text string or list of strings

        Returns:
            Text embeddings [N, 1152] or [1152] for single text
        """
        if not self._initialized:
            if not self._init_model():
                return None

        if self.text_session is None:
            logger.error("Text model not loaded")
            return None

        if self.tokenizer is None:
            logger.error("Tokenizer not initialized")
            return None

        # Ensure list format
        if isinstance(texts, str):
            texts = [texts]
            single_text = True
        else:
            single_text = False

        try:
            # Preprocess text
            inputs = self.preprocess_text(texts)

            # Get input names
            input_names = [inp.name for inp in self.text_session.get_inputs()]

            # Prepare feed dict
            feed_dict = {}
            for name in input_names:
                if "input_ids" in name.lower():
                    feed_dict[name] = inputs["input_ids"]
                elif "attention" in name.lower() or "mask" in name.lower():
                    feed_dict[name] = inputs["attention_mask"]

            # Run inference
            outputs = self.text_session.run(None, feed_dict)

            # Extract embeddings (first output)
            embeddings = outputs[0]

            # Normalize for cosine similarity
            embeddings = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)

            # Return single embedding if single text
            if single_text:
                return embeddings[0]

            return embeddings

        except Exception as e:
            logger.error(f"Text encoding failed: {e}")
            return None

    def similarity(
        self,
        image_embedding: np.ndarray,
        text_embedding: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between image and text embeddings.

        Args:
            image_embedding: Image embedding vector [1152]
            text_embedding: Text embedding vector [1152]

        Returns:
            Similarity score in range [0, 1]
        """
        # Normalize embeddings
        img_norm = image_embedding / (np.linalg.norm(image_embedding) + 1e-8)
        txt_norm = text_embedding / (np.linalg.norm(text_embedding) + 1e-8)

        # Cosine similarity
        sim = np.dot(img_norm, txt_norm)

        # Convert to [0, 1] range (cosine is [-1, 1])
        sim = (sim + 1.0) / 2.0

        return float(sim)

    def classify_image(
        self,
        image: Image.Image,
        labels: List[str]
    ) -> List[Tuple[str, float]]:
        """
        Zero-shot image classification using text labels.

        Args:
            image: PIL Image to classify
            labels: List of text labels

        Returns:
            List of (label, score) tuples sorted by score
        """
        # Encode image
        img_emb = self.encode_image(image)
        if img_emb is None:
            return []

        # Encode labels
        label_embs = self.encode_text(labels)
        if label_embs is None:
            return []

        # Compute similarities
        results = []
        for label, label_emb in zip(labels, label_embs):
            score = self.similarity(img_emb, label_emb)
            results.append((label, score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    @property
    def is_ready(self) -> bool:
        """Check if model is initialized and ready for inference."""
        return self._initialized and self.vision_session is not None

    @property
    def has_text_encoder(self) -> bool:
        """Check if text encoder is available."""
        return self.text_session is not None and self.tokenizer is not None

    @property
    def active_provider(self) -> str:
        """Get the active execution provider name."""
        return self._active_provider

    @property
    def embedding_dimension(self) -> int:
        """Get embedding dimension."""
        return EMBEDDING_DIM

    def unload(self):
        """Release model resources."""
        self.vision_session = None
        self.text_session = None
        self.tokenizer = None
        self._initialized = False

        # DirectML gibt VRAM erst bei GC frei
        import gc
        gc.collect()

        logger.info("SigLIP model unloaded")


# Convenience functions for quick usage
def encode_image(image_path: str) -> Optional[np.ndarray]:
    """
    Quick image encoding function.

    Args:
        image_path: Path to image file

    Returns:
        Image embedding [1152] or None on error
    """
    wrapper = SigLIPWrapper()
    image = Image.open(image_path)
    return wrapper.encode_image(image)


def image_similarity(image1_path: str, image2_path: str) -> float:
    """
    Compute similarity between two images.

    Args:
        image1_path: Path to first image
        image2_path: Path to second image

    Returns:
        Similarity score in range [0, 1]
    """
    wrapper = SigLIPWrapper()
    img1 = Image.open(image1_path)
    img2 = Image.open(image2_path)

    emb1 = wrapper.encode_image(img1)
    emb2 = wrapper.encode_image(img2)

    if emb1 is None or emb2 is None:
        return 0.0

    return wrapper.similarity(emb1, emb2)


def classify_image(image_path: str, labels: List[str]) -> List[Tuple[str, float]]:
    """
    Zero-shot image classification.

    Args:
        image_path: Path to image file
        labels: List of text labels

    Returns:
        List of (label, score) tuples sorted by score
    """
    wrapper = SigLIPWrapper()
    image = Image.open(image_path)
    return wrapper.classify_image(image, labels)
