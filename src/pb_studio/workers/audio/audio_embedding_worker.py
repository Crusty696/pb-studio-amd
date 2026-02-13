"""
Audio Embedding Worker for PB Studio AMD

Extracts audio embeddings using CLAP for similarity matching.
VRAM Budget: 800 MB (runs on CPU, but reserves memory for potential GPU offload)
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

import numpy as np

from ..base_worker import BaseWorker
from ...ai.clap_pytorch import CLAPPyTorch, CLAP_SAMPLE_RATE, CLAP_DURATION
from ...models.audio import AudioEmbeddingResult

logger = logging.getLogger(__name__)

# Chunking configuration
CHUNK_DURATION_SEC = 10.0  # CLAP processes 10-second chunks
CHUNK_OVERLAP_SEC = 2.0    # Overlap for smoother transitions


class AudioEmbeddingWorker(BaseWorker):
    """
    Worker for extracting CLAP audio embeddings.

    Processes audio in 10-second chunks and generates 512-dimensional
    embeddings for each chunk. These embeddings can be used for:
    - Audio similarity search
    - Mood/genre classification
    - Content-based retrieval

    VRAM Budget: 800 MB (primarily CPU, but model may use GPU if available)
    """

    def __init__(
        self,
        wav_path: str,
        chunk_duration: float = CHUNK_DURATION_SEC,
        chunk_overlap: float = CHUNK_OVERLAP_SEC
    ):
        """
        Initialize the audio embedding worker.

        Args:
            wav_path: Path to the WAV file to process
            chunk_duration: Duration of each chunk in seconds (default: 10s)
            chunk_overlap: Overlap between chunks in seconds (default: 2s)
        """
        super().__init__("AudioEmbeddingWorker", vram_budget_mb=800)
        self.wav_path = wav_path
        self.chunk_duration = chunk_duration
        self.chunk_overlap = chunk_overlap
        self._clap: Optional[CLAPPyTorch] = None

    def _execute(self) -> AudioEmbeddingResult:
        """
        Execute the embedding extraction operation.

        Returns:
            AudioEmbeddingResult with embeddings and timestamps
        """
        self.emit_progress(0, "Initializing CLAP model...")
        self._check_cancelled()

        # Validate input file
        if not os.path.exists(self.wav_path):
            raise FileNotFoundError(f"Input file not found: {self.wav_path}")

        # Initialize CLAP
        self._clap = CLAPPyTorch()

        if not self._clap.load():
            raise RuntimeError("Failed to load CLAP model. Check transformers installation.")

        try:
            self.emit_progress(20, "Loading audio file...")
            self._check_cancelled()

            # Load full audio for chunking
            import librosa
            audio, sr = librosa.load(self.wav_path, sr=CLAP_SAMPLE_RATE, mono=True)

            audio_duration = len(audio) / sr
            logger.info(f"Audio loaded: {audio_duration:.1f}s at {sr}Hz")

            self.emit_progress(30, "Extracting embeddings...")
            self._check_cancelled()

            # Calculate chunk positions
            chunk_positions = self._calculate_chunk_positions(audio_duration)
            total_chunks = len(chunk_positions)

            if total_chunks == 0:
                # Audio too short for even one chunk - process entire file
                logger.warning("Audio shorter than chunk duration, processing entire file")
                chunk_positions = [0.0]
                total_chunks = 1

            # Extract embeddings for each chunk
            embeddings: List[List[float]] = []
            timestamps: List[float] = []

            for i, start_time in enumerate(chunk_positions):
                self._check_cancelled()

                # Update progress
                progress = 30 + int(60 * (i + 1) / total_chunks)
                self.emit_progress(progress, f"Processing chunk {i + 1}/{total_chunks}...")

                # Extract chunk
                start_sample = int(start_time * sr)
                end_sample = int((start_time + self.chunk_duration) * sr)
                end_sample = min(end_sample, len(audio))

                chunk = audio[start_sample:end_sample]

                # Pad if necessary
                target_length = int(CLAP_DURATION * CLAP_SAMPLE_RATE)
                if len(chunk) < target_length:
                    chunk = np.pad(chunk, (0, target_length - len(chunk)), mode='constant')

                # Get embedding for this chunk
                embedding = self._get_chunk_embedding(chunk)

                if embedding is not None:
                    embeddings.append(embedding.tolist())
                    timestamps.append(start_time + self.chunk_duration / 2)  # Center timestamp

            self.emit_progress(95, "Finalizing results...")
            self._check_cancelled()

            logger.info(f"Embedding extraction complete: {len(embeddings)} embeddings")
            self.emit_progress(100, "Extraction complete")

            return AudioEmbeddingResult(
                embeddings=embeddings,
                timestamps=timestamps,
                model_name="clap-htsat-unfused",
                embedding_dim=512 if embeddings else 0
            )

        finally:
            # CLAP immer freigeben (auch bei Fehler/Cancel)
            if self._clap is not None:
                try:
                    self._clap.unload()
                except Exception as e:
                    logger.warning(f"CLAP unload error: {e}")

    def _calculate_chunk_positions(self, audio_duration: float) -> List[float]:
        """
        Calculate start positions for each chunk.

        Args:
            audio_duration: Total audio duration in seconds

        Returns:
            List of start times for each chunk
        """
        positions = []
        step = self.chunk_duration - self.chunk_overlap

        current_pos = 0.0
        while current_pos + self.chunk_duration <= audio_duration:
            positions.append(current_pos)
            current_pos += step

        # Add final chunk if there's remaining audio
        if current_pos < audio_duration and audio_duration - current_pos > self.chunk_overlap:
            positions.append(audio_duration - self.chunk_duration)

        return positions

    def _get_chunk_embedding(self, chunk: np.ndarray) -> Optional[np.ndarray]:
        """
        Get CLAP embedding for a single audio chunk.

        Args:
            chunk: Audio samples (numpy array at 48kHz)

        Returns:
            512-dimensional embedding vector or None on error
        """
        try:
            import torch

            with torch.no_grad():
                inputs = self._clap.processor(
                    audios=chunk,
                    sampling_rate=CLAP_SAMPLE_RATE,
                    return_tensors="pt"
                )
                inputs = {k: v.to(self._clap.device) for k, v in inputs.items()}

                audio_features = self._clap.model.get_audio_features(**inputs)
                embedding = audio_features.cpu().numpy().flatten()

            return embedding

        except Exception as e:
            logger.error(f"Failed to get chunk embedding: {e}")
            return None
