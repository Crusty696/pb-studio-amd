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

import onnxruntime as ort

logger = logging.getLogger(__name__)

from pb_studio.core.gpu_lock import gpu_inference_lock
from pb_studio.core.directml_adapter import (
    enforce_directml_session,
    get_directml_provider,
)


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

        self._active_provider = "Unknown"
        self._initialized = False
        self._init_failed = False
        self._classification_available = False
        self._unavailable_reason: Optional[str] = "CLAP ONNX wurde noch nicht initialisiert"
        self._processor = None
        self._preprocess_stats: Optional[Dict[str, np.ndarray]] = None

        if not lazy_load:
            self._init_model()

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
        return [get_directml_provider()]

    def _init_model(self) -> bool:
        if self._initialized: return True
        if self._init_failed: return False

        try:
            self._get_providers()
            from pb_studio.core.model_loader import ModelLoader
            loader = ModelLoader()

            self.combined_session = loader.load_model("clap_combined", force=True)
            if self.combined_session is not None:
                loader.register_session_owner(
                    "clap_combined",
                    self._release_loader_session,
                )
                self._validate_dml_session(self.combined_session)
                self._active_provider = "DmlExecutionProvider"
                self._initialized = True
                return True

            self.audio_encoder_session = loader.load_model("clap_audio", force=True)
            if self.audio_encoder_session is not None:
                loader.register_session_owner(
                    "clap_audio",
                    self._release_loader_session,
                )
            self.text_encoder_session = loader.load_model("clap_text", force=True)
            if self.text_encoder_session is not None:
                loader.register_session_owner(
                    "clap_text",
                    self._release_loader_session,
                )
            if self.audio_encoder_session is not None and self.text_encoder_session is not None:
                self._validate_dml_session(self.audio_encoder_session)
                self._validate_dml_session(self.text_encoder_session)
                self._init_processor()
                self._active_provider = "DmlExecutionProvider"
                self._initialized = True
                self._classification_available = True
                self._unavailable_reason = None
                return True

            self._unavailable_reason = (
                "Registrierte CLAP-ONNX-Modelle fehlen oder konnten nicht über "
                "DmlExecutionProvider geladen werden"
            )
            loader.unload_model("clap_combined")
            loader.unload_model("clap_audio")
            loader.unload_model("clap_text")
            self.audio_encoder_session = None
            self.text_encoder_session = None
            self.combined_session = None
            self._init_failed = True
            return False
        except Exception as e:
            self._unavailable_reason = f"CLAP ONNX nicht verfügbar: {e}"
            logger.error("Failed to initialize CLAP: %s", e)
            self.unload()
            self._init_failed = True
            return False

    @staticmethod
    def _validate_dml_session(session: ort.InferenceSession) -> None:
        enforce_directml_session(session)

    def load(self) -> bool:
        """Load registered CLAP ONNX assets without any runtime fallback."""
        return self._init_model()

    def _init_processor(self) -> None:
        """Load the pinned local CLAP processor and deterministic resize data."""
        from transformers import ClapProcessor

        models_path = Path(self._models_dir)
        processor_path = models_path / "clap_processor"
        stats_path = models_path / "clap_audio_preprocess.npz"
        if not processor_path.is_dir() or not stats_path.is_file():
            raise RuntimeError(
                "CLAP processor assets are incomplete "
                "(clap_processor/ and clap_audio_preprocess.npz required)"
            )

        self._processor = ClapProcessor.from_pretrained(
            str(processor_path),
            local_files_only=True,
        )
        with np.load(stats_path, allow_pickle=False) as stats:
            required = {
                "weight",
                "bias",
                "running_mean",
                "running_var",
                "epsilon",
            }
            missing = required.difference(stats.files)
            if missing:
                raise RuntimeError(
                    "CLAP preprocessing statistics missing: "
                    + ", ".join(sorted(missing))
                )
            self._preprocess_stats = {
                name: np.asarray(stats[name], dtype=np.float32).copy()
                for name in required
            }

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
        """Build the pinned CLAP log-mel input and externalized cubic resize."""
        if self._processor is None or self._preprocess_stats is None:
            raise RuntimeError("CLAP processor is not initialized")

        features = self._processor(
            audios=np.asarray(audio, dtype=np.float32),
            sampling_rate=CLAP_SAMPLE_RATE,
            return_tensors="np",
        )["input_features"].astype(np.float32)
        stats = self._preprocess_stats
        weight = stats["weight"][None, None, None, :]
        bias = stats["bias"][None, None, None, :]
        mean = stats["running_mean"][None, None, None, :]
        variance = stats["running_var"][None, None, None, :]
        epsilon = float(stats["epsilon"][0])
        normalized = (
            (features - mean)
            / np.sqrt(variance + np.float32(epsilon))
            * weight
            + bias
        )

        # The source export contains one cubic Resize node that DirectML 1.19.2
        # cannot own. It is deterministic input preprocessing, not inference.
        import torch

        resized = torch.nn.functional.interpolate(
            torch.from_numpy(normalized),
            size=(1024, CLAP_N_MELS),
            mode="bicubic",
            align_corners=True,
        )
        return resized.numpy().astype(np.float32, copy=False)

    def encode_audio(self, audio_path: Union[str, Path]) -> Optional[np.ndarray]:
        if not self._initialized and not self._init_model(): return None

        try:
            audio = self.load_audio(audio_path)
            audio_input = self.preprocess_audio(audio)
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
        if not self._initialized and not self._init_model():
            return None
        if self._processor is None:
            return None
        session = self.combined_session or self.text_encoder_session
        if session is None:
            return None

        embeddings = []
        try:
            for text in text_list:
                tokens = self._processor(
                    text=[str(text)],
                    padding="max_length",
                    truncation=True,
                    max_length=77,
                    return_tensors="np",
                )
                inputs = {
                    meta.name: np.asarray(tokens[meta.name], dtype=np.int64)
                    for meta in session.get_inputs()
                }
                with gpu_inference_lock:
                    embedding = session.run(None, inputs)[0].squeeze()
                embedding = embedding.astype(np.float32, copy=False)
                embedding /= np.linalg.norm(embedding) + 1e-8
                embeddings.append(embedding)
        except Exception as e:
            logger.error("Text encode fail: %s", e)
            return None
        return np.stack(embeddings) if embeddings else np.empty(
            (0, CLAP_EMBEDDING_DIM),
            dtype=np.float32,
        )

    def classify_audio(self, audio_path: Union[str, Path], labels: List[str], top_k: int = 5) -> List[Tuple[str, float]]:
        if not self._initialized and not self._init_model():
            raise RuntimeError(self._unavailable_reason or "CLAP ONNX nicht verfügbar")
        if not labels:
            return []
        audio_embedding = self.encode_audio(audio_path)
        text_embeddings = self.encode_text(labels)
        if audio_embedding is None or text_embeddings is None:
            raise RuntimeError("CLAP Audio/Text-Encoding fehlgeschlagen")

        similarities = text_embeddings @ audio_embedding
        similarities = similarities - float(np.max(similarities))
        probabilities = np.exp(similarities)
        probabilities /= float(np.sum(probabilities)) + 1e-8
        limit = min(max(0, int(top_k)), len(labels))
        order = np.argsort(probabilities)[::-1][:limit]
        return [
            (labels[int(index)], float(probabilities[int(index)]))
            for index in order
        ]

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

    @property
    def is_semantic_ready(self) -> bool:
        """True only when real ONNX zero-shot classification is functional."""
        return self._initialized and self._classification_available

    @property
    def unavailable_reason(self) -> Optional[str]:
        if self.is_semantic_ready:
            return None
        if self._initialized:
            return (
                "CLAP ONNX Encoder geladen, aber Audio/Text-Klassifikation "
                "ist nicht implementiert"
            )
        return self._unavailable_reason

    @property
    def active_provider(self) -> str:
        return self._active_provider

    def _release_loader_session(self, model_id: str) -> None:
        if model_id == "clap_combined":
            self.combined_session = None
        elif model_id == "clap_audio":
            self.audio_encoder_session = None
        elif model_id == "clap_text":
            self.text_encoder_session = None
        if self.combined_session is None and (
            self.audio_encoder_session is None
            or self.text_encoder_session is None
        ):
            self._initialized = False
            self._classification_available = False
            self._active_provider = "Unknown"

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
        self._classification_available = False
        self._processor = None
        self._preprocess_stats = None
        import gc; gc.collect()

def analyze_audio_mood(audio_path: Union[str, Path], top_k: int = 5) -> List[str]:
    analyzer = CLAPAnalyzer()
    return analyzer.get_mood_tags(audio_path, top_k=top_k)
