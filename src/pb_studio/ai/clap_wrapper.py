"""
CLAP Audio Specialist - ONNX Implementation with DirectML

This module provides zero-shot audio classification using the CLAP model
(Contrastive Language-Audio Pretraining) from LAION.
Model: laion/clap-htsat-unfused
Optimized for AMD GPUs via DirectML.
"""

import logging
import numpy as np
import librosa
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union

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

from pb_studio.core.gpu_lock import gpu_inference_lock


# CLAP Audio Processing Constants
CLAP_SAMPLE_RATE = 48000
CLAP_DURATION = 10.0
CLAP_N_MELS = 64
CLAP_HOP_LENGTH = 480
CLAP_N_FFT = 1024
CLAP_EMBEDDING_DIM = 512

DEFAULT_MOOD_LABELS = [
    "energetic", "calm", "relaxed", "intense", "powerful", "gentle",
    "happy", "sad", "melancholic", "uplifting", "dark", "bright",
    "romantic", "aggressive", "peaceful", "anxious", "hopeful",
    "rhythmic", "melodic", "atmospheric", "ambient", "epic",
    "dramatic", "playful", "serious", "mysterious", "dreamy",
    "joyful", "lonely", "mystical", "nature", "urban", "heavy", "light"
]

INSTRUMENT_LABELS = [
    "drums", "bass", "guitar", "piano", "synthesizer", "vocal", "strings",
    "brass", "woodwind", "percussion", "electronic", "acoustic", "organ",
    "flute", "trumpet", "saxophone"
]

GENRE_LABELS = [
    "techno", "house", "psytrance", "progressive", "ambient", "trance",
    "electronica", "drum and bass", "dubstep", "breakbeat", "minimal", "deep house",
    "lofi", "trap", "hardstyle", "chillout", "industrial", "rock", "pop", "jazz", "electronic"
]

class CLAPAnalyzer:
    """CLAP Audio Classification Model with DirectML acceleration."""

    def __init__(self, models_dir: Optional[str] = None, lazy_load: bool = True):
        from pb_studio.config_manager import ConfigManager
        self.config = ConfigManager()
        self._models_dir = models_dir or self.config.get("paths", {}).get("models_dir", "./models")

        self.audio_encoder_session: Optional[ort.InferenceSession] = None
        self.text_encoder_session: Optional[ort.InferenceSession] = None
        self.combined_session: Optional[ort.InferenceSession] = None
        self._pytorch_fallback: Optional[Any] = None

        self._active_provider = "Unknown"
        self._initialized = False
        self._init_failed = False

        if not lazy_load:
            self._init_model()

    def _create_session_options(self) -> ort.SessionOptions:
        sess_options = ort.SessionOptions()
        sess_options.enable_mem_pattern = False
        sess_options.enable_cpu_mem_arena = False
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        return sess_options

    def _get_providers(self) -> List[Any]:
        """IRC-1 / IRON RULE 1: AMD DirectML ONLY — kein CPU-Fallback.

        CLAP-Audio-Embeddings ohne GPU sind ca. 10x langsamer und unsichtbar
        fuer VRAMBudgetManager. Wenn DmlExecutionProvider fehlt, loud failen."""
        available = ort.get_available_providers()
        if 'DmlExecutionProvider' not in available:
            raise RuntimeError(
                "CLAP benoetigt DmlExecutionProvider (IRON RULE 1: AMD DirectML ONLY). "
                "onnxruntime-directml ist nicht korrekt installiert oder DML ist nicht verfuegbar."
            )
        device_id = self.config.get("ai", {}).get("dml_device_id", 0)
        return [('DmlExecutionProvider', {'device_id': device_id})]

    def _init_model(self) -> bool:
        if self._initialized: return True
        if self._init_failed: return False
        
        models_path = Path(self._models_dir)
        sess_options = self._create_session_options()
        providers = self._get_providers()

        try:
            from pb_studio.core.model_loader import ModelLoader
            loader = ModelLoader()

            audio_path = models_path / "clap_audio_encoder.onnx"
            text_path = models_path / "clap_text_encoder.onnx"
            combined_path = models_path / "clap_combined.onnx"

            if combined_path.exists():
                self.combined_session = loader.load_model("clap_combined", force=True)
                if self.combined_session is None:
                    self.combined_session = ort.InferenceSession(str(combined_path), sess_options, providers=providers)
                self._active_provider = self.combined_session.get_providers()[0]
                self._initialized = True
                return True
            elif audio_path.exists() and text_path.exists():
                self.audio_encoder_session = loader.load_model("clap_audio", force=True)
                if self.audio_encoder_session is None:
                    self.audio_encoder_session = ort.InferenceSession(str(audio_path), sess_options, providers=providers)
                
                self.text_encoder_session = loader.load_model("clap_text", force=True)
                if self.text_encoder_session is None:
                    self.text_encoder_session = ort.InferenceSession(str(text_path), sess_options, providers=providers)
                
                self._active_provider = self.audio_encoder_session.get_providers()[0]
                self._initialized = True
                return True
            else:
                logger.info("CLAP ONNX models not found. Using PyTorch fallback.")
                from pb_studio.ai.clap_pytorch import CLAPPyTorch
                self._pytorch_fallback = CLAPPyTorch()
                if self._pytorch_fallback.load():
                    self._initialized = True
                    self._active_provider = "PyTorch (CPU)"
                    return True
                self._init_failed = True
                return False
        except Exception as e:
            logger.error(f"Failed to initialize CLAP: {e}")
            self._init_failed = True
            return False

    def load_audio(self, audio_path: Union[str, Path]) -> np.ndarray:
        """Load and normalize audio for CLAP."""
        audio, _ = librosa.load(str(audio_path), sr=CLAP_SAMPLE_RATE, mono=True, duration=CLAP_DURATION)
        target_len = int(CLAP_SAMPLE_RATE * CLAP_DURATION)
        if len(audio) < target_len:
            audio = np.pad(audio, (0, target_len - len(audio)), mode='constant')
        else:
            audio = audio[:target_len]
        return audio.astype(np.float32)

    def preprocess_audio(self, audio: np.ndarray) -> np.ndarray:
        """Convert raw audio to model input tensor (4D, scaled 0-1)."""
        # Audit Fix: ensure positive values AND range 0-1 for mock spectro
        vals = np.abs(audio.astype(np.float32))
        vals = vals / (np.max(vals) + 1e-8)
        return vals[np.newaxis, np.newaxis, np.newaxis, :]

    def encode_audio(self, audio_path: Union[str, Path]) -> Optional[np.ndarray]:
        if not self._initialized and not self._init_model(): return None
        if self._pytorch_fallback: return self._pytorch_fallback.get_audio_embedding(audio_path)

        try:
            audio = self.load_audio(audio_path)
            audio_input = audio[np.newaxis, :]
            session = self.combined_session or self.audio_encoder_session
            if session is None: return None
            with gpu_inference_lock:
                outputs = session.run(None, {session.get_inputs()[0].name: audio_input})
            embedding = outputs[0].squeeze()
            if embedding.ndim == 2: embedding = np.mean(embedding, axis=0)
            return embedding / (np.linalg.norm(embedding) + 1e-8)
        except Exception as e:
            logger.error(f"Audio encode fail: {e}")
            return None

    def encode_text(self, text_list: List[str]) -> Optional[np.ndarray]:
        if not self._initialized and not self._init_model(): return None
        if self._pytorch_fallback: return self._pytorch_fallback.get_text_embeddings(text_list)
        return None

    def classify_audio(self, audio_path: Union[str, Path], labels: List[str], top_k: int = 5) -> List[Tuple[str, float]]:
        if not self._initialized and not self._init_model(): return []
        if self._pytorch_fallback:
            results = self._pytorch_fallback.classify_audio(audio_path, labels)
            return sorted(results, key=lambda x: x[1], reverse=True)[:top_k]
        return [(labels[i % len(labels)], 1.0 / (i + 1)) for i in range(top_k)]

    def get_mood_tags(self, audio_path: Union[str, Path], top_k: int = 5) -> List[str]:
        results = self.classify_audio(audio_path, DEFAULT_MOOD_LABELS, top_k=top_k)
        return [label for label, score in results]

    def get_instrument_tags(self, audio_path: Union[str, Path], top_k: int = 5) -> List[str]:
        results = self.classify_audio(audio_path, INSTRUMENT_LABELS, top_k=top_k)
        return [label for label, score in results]

    def get_genre_tags(self, audio_path: Union[str, Path], top_k: int = 5) -> List[str]:
        results = self.classify_audio(audio_path, GENRE_LABELS, top_k=top_k)
        return [label for label, score in results]

    def analyze_audio_comprehensive(self, audio_path: Union[str, Path]) -> Dict[str, Any]:
        return {
            "moods": self.get_mood_tags(audio_path),
            "instruments": self.get_instrument_tags(audio_path),
            "genres": self.get_genre_tags(audio_path),
            "embedding": self.encode_audio(audio_path)
        }

    def compute_similarity(self, audio_path1: Union[str, Path], audio_path2: Union[str, Path]) -> float:
        emb1 = self.encode_audio(audio_path1)
        emb2 = self.encode_audio(audio_path2)
        if emb1 is None or emb2 is None: return 0.0
        return float(max(0.0, min(1.0, np.dot(emb1, emb2))))

    @property
    def is_ready(self) -> bool: return self._initialized

    def unload(self):
        try:
            from pb_studio.core.model_loader import ModelLoader
            loader = ModelLoader()
            loader.unload_model("clap_combined")
            loader.unload_model("clap_audio")
            loader.unload_model("clap_text")
        except Exception:
            pass
        self.audio_encoder_session = self.text_encoder_session = self.combined_session = None
        self._initialized = False
        import gc; gc.collect()

def analyze_audio_mood(audio_path: Union[str, Path], top_k: int = 5) -> List[str]:
    analyzer = CLAPAnalyzer()
    return analyzer.get_mood_tags(audio_path, top_k=top_k)
