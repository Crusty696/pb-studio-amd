"""
SigLIP Image Encoder - ONNX Implementation with DirectML.

This module provides image and text embedding using the SigLIP model
(Sigmoid Loss for Language-Image Pre-training) exported to ONNX format.
Optimized for AMD GPUs via DirectML.
"""

import logging
import numpy as np
from pathlib import Path
from typing import Optional, List, Union, Tuple, Any
from PIL import Image

try:
    import onnxruntime as ort
except ImportError:
    class _FallbackOrt:
        SessionOptions = object
        GraphOptimizationLevel = object
        InferenceSession = object
        @staticmethod
        def get_available_providers() -> List[str]: return ["CPUExecutionProvider"]
    ort = _FallbackOrt()

logger = logging.getLogger(__name__)

# SigLIP preprocessing constants
SIGLIP_IMAGE_SIZE = 384
SIGLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
SIGLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
EMBEDDING_DIM = 1152


class SigLIPWrapper:
    """SigLIP Image and Text Encoder with DirectML acceleration."""

    def __init__(self, models_dir: Optional[str] = None, lazy_load: bool = False):
        from pb_studio.config_manager import ConfigManager
        self.config = ConfigManager()
        self._models_dir = models_dir or self.config.get("paths", {}).get("models_dir", "./models")

        self.vision_session: Optional[ort.InferenceSession] = None
        self.text_session: Optional[ort.InferenceSession] = None
        self.text_model_fallback: Optional[Any] = None
        self.tokenizer = None

        self._active_provider = "Unknown"
        self._initialized = False

        if not lazy_load:
            self._init_model()

    def _create_session_options(self) -> ort.SessionOptions:
        sess_options = ort.SessionOptions()
        sess_options.enable_mem_pattern = False
        sess_options.enable_cpu_mem_arena = False
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        return sess_options

    def _get_providers(self) -> List[str]:
        """IRC-1 / IRON RULE 1: AMD DirectML ONLY — kein CPU-Fallback.

        Wenn DmlExecutionProvider nicht verfuegbar ist, scheitert die
        Initialisierung explizit (loud) statt silent in CPU-Mode zu rutschen
        (~10x langsamer, VRAMBudgetManager sieht den Speicher nicht)."""
        available = ort.get_available_providers()
        if 'DmlExecutionProvider' not in available:
            raise RuntimeError(
                "SigLIP benoetigt DmlExecutionProvider (IRON RULE 1: AMD DirectML ONLY). "
                "onnxruntime-directml ist nicht korrekt installiert oder DML ist nicht verfuegbar."
            )
        return ['DmlExecutionProvider']

    def _init_tokenizer(self) -> bool:
        try:
            from transformers import AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained("google/siglip-so400m-patch14-384")
            return True
        except Exception:
            return False

    def _init_text_fallback(self) -> bool:
        try:
            from transformers import SiglipTextModel
            logger.info("Loading SigLIP text model (PyTorch fallback)...")
            self.text_model_fallback = SiglipTextModel.from_pretrained("google/siglip-so400m-patch14-384")
            self.text_model_fallback.eval()
            return True
        except Exception as e:
            logger.error(f"Text fallback fail: {e}")
            return False

    def _init_model(self) -> bool:
        if self._initialized: return True
        self._init_tokenizer()
        models_path = Path(self._models_dir)
        sess_options = self._create_session_options()
        providers = self._get_providers()

        try:
            vision_path = models_path / "siglip_vision.onnx"
            text_path = models_path / "siglip_text.onnx"

            if vision_path.exists():
                self.vision_session = ort.InferenceSession(str(vision_path), sess_options, providers=providers)
                self._active_provider = self.vision_session.get_providers()[0]
                if text_path.exists():
                    self.text_session = ort.InferenceSession(str(text_path), sess_options, providers=providers)
                else:
                    self._init_text_fallback()
                self._initialized = True
                return True
            return False
        except Exception:
            return False

    def preprocess_image(self, image: Image.Image) -> np.ndarray:
        """Preprocess image for SigLIP (Required by tests)."""
        img = image.convert('RGB').resize((SIGLIP_IMAGE_SIZE, SIGLIP_IMAGE_SIZE), Image.Resampling.BICUBIC)
        arr = (np.array(img, dtype=np.float32) / 255.0 - SIGLIP_MEAN) / SIGLIP_STD
        return np.transpose(arr, (2, 0, 1))[np.newaxis, :]

    def encode_image(self, image: Image.Image) -> Optional[np.ndarray]:
        if not self._initialized and not self._init_model(): return None
        try:
            tensor = self.preprocess_image(image)
            outputs = self.vision_session.run(None, {self.vision_session.get_inputs()[0].name: tensor})
            emb = outputs[0].squeeze()
            if emb.ndim == 2: emb = np.mean(emb, axis=0)
            return emb / (np.linalg.norm(emb) + 1e-8)
        except Exception:
            return None

    def encode_images_batch(self, images: List[Image.Image]) -> Optional[np.ndarray]:
        """Encode multiple images (Required by tests)."""
        embs = [self.encode_image(img) for img in images]
        valid = [e for e in embs if e is not None]
        return np.stack(valid) if valid else None

    def encode_text(self, texts: Union[str, List[str]]) -> Optional[np.ndarray]:
        if not self._initialized and not self._init_model(): return None
        if self.text_session is None and self.text_model_fallback is None: return None
        if isinstance(texts, str): texts = [texts]
        try:
            inputs = self.tokenizer(texts, padding="max_length", max_length=64, truncation=True, return_tensors="np")
            if self.text_session:
                feed = {inp.name: inputs["input_ids"] if "input_ids" in inp.name else inputs["attention_mask"] for inp in self.text_session.get_inputs()}
                embeddings = self.text_session.run(None, feed)[0]
            else:
                import torch
                with torch.no_grad():
                    pt_in = {k: torch.from_numpy(v) for k, v in inputs.items() if k in ["input_ids", "attention_mask"]}
                    embeddings = self.text_model_fallback(**pt_in).pooler_output.cpu().numpy()
            embeddings = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-8)
            return embeddings[0] if len(texts) == 1 and not isinstance(texts, list) else embeddings
        except Exception:
            return None

    def similarity(self, image_embedding: np.ndarray, text_embedding: np.ndarray) -> float:
        sim = np.dot(image_embedding, text_embedding)
        return float((sim + 1.0) / 2.0)

    def classify_image(self, image: Image.Image, labels: List[str]) -> List[Tuple[str, float]]:
        img_emb = self.encode_image(image)
        txt_embs = self.encode_text(labels)
        if img_emb is None or txt_embs is None: return []
        results = [(labels[i], self.similarity(img_emb, txt_embs[i])) for i in range(len(labels))]
        return sorted(results, key=lambda x: x[1], reverse=True)

    @property
    def is_ready(self) -> bool: return self._initialized and self.vision_session is not None

    @property
    def has_text_encoder(self) -> bool: return (self.text_session is not None) or (self.text_model_fallback is not None)

    @property
    def active_provider(self) -> str: return self._active_provider

    @property
    def embedding_dimension(self) -> int: return EMBEDDING_DIM

    def unload(self):
        self.vision_session = self.text_session = self.tokenizer = None
        self._initialized = False
        import gc; gc.collect()

def encode_image(image_path: str) -> Optional[np.ndarray]:
    wrapper = SigLIPWrapper()
    return wrapper.encode_image(Image.open(image_path))
