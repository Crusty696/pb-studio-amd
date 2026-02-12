"""
Clip Selector - Intelligent Video Segment Selection

Uses vector embeddings (FAISS) to match video clips with desired characteristics:
- Semantic similarity (content matching)
- Motion energy (activity level)
- Audio energy alignment (beat synchronization)

This module integrates with the VectorStore to enable content-aware video selection.
"""

import logging
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClipMetadata:
    """Metadata for a video clip segment."""
    video_id: int
    file_path: str
    start_time: float
    duration: float
    motion_score: float = 0.0
    energy_score: float = 0.0
    tags: List[str] = None
    embedding: Optional[np.ndarray] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class ClipSelector:
    """
    Selects video clips based on semantic similarity, motion, and energy.

    Uses FAISS vector store for fast similarity search and filtering
    by motion/energy thresholds.
    """

    def __init__(self, vector_store=None):
        """
        Initialize ClipSelector with optional vector store.

        Args:
            vector_store: VectorStore instance for embedding search.
                         If None, similarity-based selection is disabled.
        """
        self.vector_store = vector_store
        self.clip_cache: Dict[int, ClipMetadata] = {}

    def add_clip(self, clip: ClipMetadata) -> int:
        """
        Add a clip to the selection pool.

        Args:
            clip: ClipMetadata instance with embedding and metadata

        Returns:
            Clip ID for later reference
        """
        if clip.embedding is not None and self.vector_store is not None:
            # Add to vector store
            meta_info = {
                "video_id": clip.video_id,
                "file_path": clip.file_path,
                "start_time": clip.start_time,
                "duration": clip.duration,
                "motion_score": clip.motion_score,
                "energy_score": clip.energy_score,
                "tags": clip.tags
            }

            faiss_id = self.vector_store.add_embedding(clip.embedding, meta_info)
            self.clip_cache[faiss_id] = clip
            return faiss_id
        else:
            # Fallback: Use video_id as key
            clip_id = clip.video_id
            self.clip_cache[clip_id] = clip
            return clip_id

    def select_by_similarity(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        exclude_ids: Optional[List[int]] = None
    ) -> List[Tuple[ClipMetadata, float]]:
        """
        Select clips by semantic similarity to query embedding.

        Args:
            query_embedding: Target embedding vector (768-dim)
            k: Number of results to return
            exclude_ids: Optional list of clip IDs to exclude from results

        Returns:
            List of (ClipMetadata, similarity_score) tuples, sorted by score
        """
        if self.vector_store is None or self.vector_store.index.ntotal == 0:
            logger.warning("VectorStore not available or empty. Using random selection.")
            return self._random_selection(k)

        # Search vector store
        results = self.vector_store.search(query_embedding, k=k*2)  # Get extra for filtering

        # Build output list
        selected = []
        exclude_set = set(exclude_ids) if exclude_ids else set()

        for meta, score in results:
            faiss_id = meta.get("video_id", -1)

            # Skip excluded clips
            if faiss_id in exclude_set:
                continue

            # Reconstruct ClipMetadata
            clip = ClipMetadata(
                video_id=meta.get("video_id", -1),
                file_path=meta.get("file_path", ""),
                start_time=meta.get("start_time", 0.0),
                duration=meta.get("duration", 0.0),
                motion_score=meta.get("motion_score", 0.0),
                energy_score=meta.get("energy_score", 0.0),
                tags=meta.get("tags", [])
            )

            selected.append((clip, float(score)))

            if len(selected) >= k:
                break

        return selected

    def select_by_motion(
        self,
        motion_threshold: float,
        operator: str = "greater",
        k: int = 10
    ) -> List[ClipMetadata]:
        """
        Filter clips by motion intensity.

        Args:
            motion_threshold: Motion score threshold (0.0 to 1.0)
            operator: "greater", "less", or "equal"
            k: Maximum number of results

        Returns:
            List of ClipMetadata matching the motion criteria
        """
        filtered = []

        for clip in self.clip_cache.values():
            if operator == "greater" and clip.motion_score > motion_threshold:
                filtered.append(clip)
            elif operator == "less" and clip.motion_score < motion_threshold:
                filtered.append(clip)
            elif operator == "equal" and abs(clip.motion_score - motion_threshold) < 0.1:
                filtered.append(clip)

        # Sort by motion score (descending)
        filtered.sort(key=lambda c: c.motion_score, reverse=True)

        return filtered[:k]

    def select_by_energy(
        self,
        energy_level: float,
        tolerance: float = 0.2,
        k: int = 10
    ) -> List[ClipMetadata]:
        """
        Select clips matching a target energy level.

        Args:
            energy_level: Target energy (0.0 to 1.0)
            tolerance: Acceptable deviation from target
            k: Maximum number of results

        Returns:
            List of ClipMetadata with energy_score near target
        """
        filtered = []

        for clip in self.clip_cache.values():
            energy_diff = abs(clip.energy_score - energy_level)

            if energy_diff <= tolerance:
                filtered.append((clip, energy_diff))

        # Sort by closeness to target energy
        filtered.sort(key=lambda x: x[1])

        return [clip for clip, _ in filtered[:k]]

    def select_by_tags(
        self,
        required_tags: List[str],
        any_match: bool = False,
        k: int = 10
    ) -> List[ClipMetadata]:
        """
        Select clips by tag matching.

        Args:
            required_tags: List of tags to match
            any_match: If True, match ANY tag. If False, match ALL tags.
            k: Maximum number of results

        Returns:
            List of ClipMetadata with matching tags
        """
        filtered = []
        required_set = set(required_tags)

        for clip in self.clip_cache.values():
            clip_tags = set(clip.tags)

            if any_match:
                # Match if ANY tag overlaps
                if clip_tags & required_set:
                    filtered.append(clip)
            else:
                # Match if ALL required tags present
                if required_set.issubset(clip_tags):
                    filtered.append(clip)

        return filtered[:k]

    def select_hybrid(
        self,
        query_embedding: Optional[np.ndarray] = None,
        energy_target: Optional[float] = None,
        motion_threshold: Optional[float] = None,
        required_tags: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        k: int = 5
    ) -> List[Tuple[ClipMetadata, float]]:
        """
        Hybrid selection combining multiple criteria with weighted scoring.

        Args:
            query_embedding: Optional semantic similarity target
            energy_target: Optional energy level to match
            motion_threshold: Optional minimum motion score
            required_tags: Optional tags for filtering
            weights: Optional dict of weights {"similarity": 0.5, "energy": 0.3, "motion": 0.2}
            k: Number of results to return

        Returns:
            List of (ClipMetadata, combined_score) tuples
        """
        # Default weights
        if weights is None:
            weights = {
                "similarity": 0.5,
                "energy": 0.3,
                "motion": 0.2
            }

        # Start with all clips
        candidates = list(self.clip_cache.values())

        # Apply hard filters first
        if required_tags:
            candidates = [c for c in candidates if set(required_tags).issubset(set(c.tags))]

        if motion_threshold is not None:
            candidates = [c for c in candidates if c.motion_score >= motion_threshold]

        if not candidates:
            logger.warning("No clips match the filtering criteria.")
            return []

        # Score each candidate
        scored = []

        for clip in candidates:
            score = 0.0

            # Similarity score
            if query_embedding is not None and clip.embedding is not None:
                sim = self._cosine_similarity(query_embedding, clip.embedding)
                score += sim * weights.get("similarity", 0.0)

            # Energy score (inverse of distance from target)
            if energy_target is not None:
                energy_match = 1.0 - abs(clip.energy_score - energy_target)
                score += energy_match * weights.get("energy", 0.0)

            # Motion score
            score += clip.motion_score * weights.get("motion", 0.0)

            scored.append((clip, score))

        # Sort by score (descending)
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored[:k]

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _random_selection(self, k: int) -> List[Tuple[ClipMetadata, float]]:
        """Fallback: Random clip selection."""
        import random
        clips = list(self.clip_cache.values())

        if not clips:
            return []

        selected = random.sample(clips, min(k, len(clips)))
        return [(clip, 0.5) for clip in selected]  # Neutral score

    def clear_cache(self):
        """Clear the clip cache (useful for new projects)."""
        self.clip_cache.clear()
        logger.info("Clip cache cleared.")

    def get_statistics(self) -> Dict[str, any]:
        """Get statistics about the clip pool."""
        if not self.clip_cache:
            return {
                "total_clips": 0,
                "avg_motion": 0.0,
                "avg_energy": 0.0,
                "unique_tags": []
            }

        motion_scores = [c.motion_score for c in self.clip_cache.values()]
        energy_scores = [c.energy_score for c in self.clip_cache.values()]
        all_tags = set()

        for clip in self.clip_cache.values():
            all_tags.update(clip.tags)

        return {
            "total_clips": len(self.clip_cache),
            "avg_motion": np.mean(motion_scores) if motion_scores else 0.0,
            "avg_energy": np.mean(energy_scores) if energy_scores else 0.0,
            "unique_tags": sorted(list(all_tags))
        }
