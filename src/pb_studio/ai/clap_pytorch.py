"""
CLAP Audio Specialist - PyTorch Implementation (No ONNX)

This module provides zero-shot audio classification using CLAP
directly via PyTorch/Transformers, without requiring ONNX export.

This is a workaround for AMD systems where CLAP ONNX export fails
due to model architecture complexity (HTSAT encoder).

Model: laion/clap-htsat-unfused
"""

import logging
import numpy as np
import torch
import librosa
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union

logger = logging.getLogger(__name__)

# CLAP Audio Processing Constants
CLAP_SAMPLE_RATE = 48000
CLAP_DURATION = 10.0
CLAP_EMBEDDING_DIM = 512

# Comprehensive Labels for Music Analysis
DEFAULT_MOOD_LABELS = [
    "energetic", "calm", "relaxed", "intense", "powerful", "gentle",
    "happy", "sad", "melancholic", "uplifting", "dark", "bright",
    "romantic", "aggressive", "peaceful", "anxious", "hopeful",
    "rhythmic", "melodic", "atmospheric", "ambient", "epic",
    "dramatic", "playful", "serious", "mysterious", "dreamy",
    "electronic", "acoustic", "orchestral", "rock", "jazz",
    "classical", "hip-hop", "pop", "cinematic", "experimental",
    "fast", "slow", "driving", "pulsing", "flowing", "sparse", "dense"
]

INSTRUMENT_LABELS = [
    "piano", "guitar", "drums", "bass", "violin", "synthesizer",
    "vocals", "brass", "strings", "woodwinds", "percussion"
]

GENRE_LABELS = [
    "rock", "pop", "electronic", "hip-hop", "jazz", "classical",
    "ambient", "metal", "folk", "country", "blues", "reggae",
    "techno", "house", "drum and bass", "dubstep"
]


class CLAPPyTorch:
    """
    CLAP Audio Classification using PyTorch directly.

    This implementation uses the Transformers library to run CLAP
    without requiring ONNX conversion.

    Note: Runs on CPU by default. For GPU acceleration, the model
    would need CUDA (not available on AMD) or a custom DirectML implementation.
    """

    def __init__(self, model_id: str = "laion/clap-htsat-unfused", device: str = "cpu"):
        """
        Initialize CLAP with PyTorch.

        Args:
            model_id: HuggingFace model ID
            device: Device to run on ('cpu' for AMD systems)
        """
        self.model_id = model_id
        self.device = device
        self.model = None
        self.processor = None
        self._loaded = False

        logger.info(f"CLAPPyTorch initialized (device: {device})")

    def load(self) -> bool:
        """Load the CLAP model."""
        if self._loaded:
            return True

        try:
            from transformers import ClapModel, ClapProcessor

            logger.info(f"Loading CLAP model: {self.model_id}")

            self.processor = ClapProcessor.from_pretrained(self.model_id, local_files_only=True)
            self.model = ClapModel.from_pretrained(self.model_id, local_files_only=True)
            self.model.to(self.device)
            self.model.eval()

            self._loaded = True
            logger.info("[OK] CLAP model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load CLAP: {e}")
            return False

    def unload(self):
        """Unload model to free memory."""
        if self.model is not None:
            del self.model
            del self.processor
            self.model = None
            self.processor = None
            self._loaded = False
            # AMD-only build - kein CUDA verfuegbar
            import gc
            gc.collect()
            logger.info("CLAP model unloaded")

    def _load_audio(self, audio_path: Union[str, Path]) -> np.ndarray:
        """Load and preprocess audio file."""
        try:
            # BUG-088 FIX: Handle potential librosa load errors
            audio, sr = librosa.load(str(audio_path), sr=CLAP_SAMPLE_RATE, mono=True)
        except Exception as e:
            logger.error(f"CLAP failed to load audio {audio_path}: {e}")
            # Return silence/zeros as fallback to prevent crash
            return np.zeros(int(CLAP_SAMPLE_RATE * CLAP_DURATION), dtype=np.float32)

        # Ensure 10 seconds
        target_length = int(CLAP_SAMPLE_RATE * CLAP_DURATION)

        if len(audio) > target_length:
            # Take center crop
            start = (len(audio) - target_length) // 2
            audio = audio[start:start + target_length]
        elif len(audio) < target_length:
            # Pad with zeros
            padding = target_length - len(audio)
            audio = np.pad(audio, (0, padding), mode='constant')

        return audio

    def get_audio_embedding(self, audio_path: Union[str, Path]) -> Optional[np.ndarray]:
        """
        Get audio embedding for a file.

        Args:
            audio_path: Path to audio file

        Returns:
            512-dimensional embedding vector or None on error
        """
        if not self._loaded and not self.load():
            return None

        try:
            audio = self._load_audio(audio_path)

            with torch.no_grad():
                inputs = self.processor(
                    audios=audio,
                    sampling_rate=CLAP_SAMPLE_RATE,
                    return_tensors="pt"
                )
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

                audio_features = self.model.get_audio_features(**inputs)
                embedding = audio_features.cpu().numpy().flatten()

            return embedding

        except Exception as e:
            logger.error(f"Failed to get audio embedding: {e}")
            return None

    def get_text_embeddings(self, labels: List[str]) -> Optional[np.ndarray]:
        """
        Get text embeddings for label list.

        Args:
            labels: List of text labels

        Returns:
            Array of shape (n_labels, 512) or None on error
        """
        if not self._loaded and not self.load():
            return None

        try:
            with torch.no_grad():
                inputs = self.processor(
                    text=labels,
                    return_tensors="pt",
                    padding=True
                )
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

                text_features = self.model.get_text_features(**inputs)
                embeddings = text_features.cpu().numpy()

            return embeddings

        except Exception as e:
            logger.error(f"Failed to get text embeddings: {e}")
            return None

    def classify_audio(
        self,
        audio_path: Union[str, Path],
        labels: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Zero-shot audio classification.

        Args:
            audio_path: Path to audio file
            labels: Labels to classify against (default: mood labels)
            top_k: Number of top results to return

        Returns:
            List of (label, probability) tuples
        """
        if labels is None:
            labels = DEFAULT_MOOD_LABELS

        if not self._loaded and not self.load():
            return []

        try:
            audio = self._load_audio(audio_path)

            with torch.no_grad():
                # Process audio
                audio_inputs = self.processor(
                    audios=audio,
                    sampling_rate=CLAP_SAMPLE_RATE,
                    return_tensors="pt"
                )
                audio_inputs = {k: v.to(self.device) for k, v in audio_inputs.items()}

                # Process text
                text_inputs = self.processor(
                    text=labels,
                    return_tensors="pt",
                    padding=True
                )
                text_inputs = {k: v.to(self.device) for k, v in text_inputs.items()}

                # Get features
                audio_features = self.model.get_audio_features(**audio_inputs)
                text_features = self.model.get_text_features(**text_inputs)

                # Normalize
                audio_features = audio_features / audio_features.norm(dim=-1, keepdim=True)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)

                # Compute similarity
                similarity = (audio_features @ text_features.T).squeeze(0)
                probs = torch.softmax(similarity * 100, dim=-1)  # Temperature scaling

                # Get top-k
                top_probs, top_indices = probs.topk(min(top_k, len(labels)))

                results = [
                    (labels[idx], prob.item())
                    for idx, prob in zip(top_indices.cpu().numpy(), top_probs.cpu().numpy())
                ]

            return results

        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return []

    def detect_mood(self, audio_path: Union[str, Path], top_k: int = 5) -> List[Tuple[str, float]]:
        """Detect mood/atmosphere of audio."""
        return self.classify_audio(audio_path, DEFAULT_MOOD_LABELS, top_k)

    def detect_instruments(self, audio_path: Union[str, Path], top_k: int = 5) -> List[Tuple[str, float]]:
        """Detect instruments in audio."""
        return self.classify_audio(audio_path, INSTRUMENT_LABELS, top_k)

    def detect_genre(self, audio_path: Union[str, Path], top_k: int = 3) -> List[Tuple[str, float]]:
        """Detect music genre."""
        return self.classify_audio(audio_path, GENRE_LABELS, top_k)

    def analyze_audio(self, audio_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Full audio analysis combining mood, instruments, and genre.

        Args:
            audio_path: Path to audio file

        Returns:
            Dictionary with analysis results
        """
        return {
            "mood": self.detect_mood(audio_path, top_k=5),
            "instruments": self.detect_instruments(audio_path, top_k=5),
            "genre": self.detect_genre(audio_path, top_k=3),
            "embedding": self.get_audio_embedding(audio_path)
        }


# Convenience function
def get_clap_analyzer() -> CLAPPyTorch:
    """Get a shared CLAP analyzer instance."""
    if not hasattr(get_clap_analyzer, '_instance'):
        get_clap_analyzer._instance = CLAPPyTorch()
    return get_clap_analyzer._instance
