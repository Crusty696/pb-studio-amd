"""
Video Specialist - Video Analysis and Clip Matching with SigLIP.

This module provides video analysis capabilities using the SigLIP image encoder:
- Keyframe extraction from videos
- Video embedding (averaged frame embeddings)
- Clip similarity search
- Video tagging with text labels

Optimized for AMD GPUs via DirectML through the SigLIP wrapper.
"""

import logging
import numpy as np
import cv2
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image

from .siglip_wrapper import SigLIPWrapper

logger = logging.getLogger(__name__)


class VideoClip:
    """Data class representing a video clip with embeddings."""

    def __init__(
        self,
        clip_id: int,
        video_path: str,
        start_time: float,
        end_time: float,
        embedding: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a video clip.

        Args:
            clip_id: Unique identifier for the clip
            video_path: Path to source video file
            start_time: Start time in seconds
            end_time: End time in seconds
            embedding: Pre-computed embedding vector [1152]
            metadata: Additional clip metadata
        """
        self.clip_id = clip_id
        self.video_path = video_path
        self.start_time = start_time
        self.end_time = end_time
        self.embedding = embedding
        self.metadata = metadata or {}
        self.duration = end_time - start_time

    def __repr__(self) -> str:
        return (
            f"VideoClip(id={self.clip_id}, "
            f"path={Path(self.video_path).name}, "
            f"time={self.start_time:.2f}-{self.end_time:.2f}s)"
        )


class VideoSpecialist:
    """
    Video analysis specialist using SigLIP embeddings.

    Provides functionality for:
    - Extracting keyframes from videos
    - Computing video embeddings
    - Finding similar video clips
    - Tagging videos with text labels
    """

    def __init__(
        self,
        models_dir: Optional[str] = None,
        vector_store: Optional[Any] = None
    ):
        """
        Initialize the video specialist.

        Args:
            models_dir: Directory containing ONNX model files
            vector_store: Optional VectorStore instance for persistence
        """
        # Initialize SigLIP wrapper
        self.siglip = SigLIPWrapper(models_dir=models_dir, lazy_load=True)

        # Vector store for clip embeddings
        self.vector_store = vector_store

        # Clip database (in-memory)
        self.clips: Dict[int, VideoClip] = {}
        self._next_clip_id = 0

    def extract_keyframes(
        self,
        video_path: str,
        interval: float = 1.0,
        max_frames: Optional[int] = None
    ) -> List[np.ndarray]:
        """
        Extract keyframes from video at regular intervals.

        Args:
            video_path: Path to video file
            interval: Time interval between keyframes in seconds
            max_frames: Maximum number of frames to extract (None = no limit)

        Returns:
            List of frame arrays (BGR format)
        """
        if not Path(video_path).exists():
            logger.error(f"Video file not found: {video_path}")
            return []

        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                return []

            try:
                fps = cap.get(cv2.CAP_PROP_FPS)
                if fps <= 0:
                    logger.warning(f"Invalid FPS {fps}, using default 30")
                    fps = 30.0

                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration = total_frames / fps

                # Calculate frame interval
                frame_interval = int(interval * fps)
                if frame_interval < 1:
                    frame_interval = 1

                logger.info(
                    f"Extracting keyframes from {Path(video_path).name}: "
                    f"duration={duration:.2f}s, fps={fps:.2f}, interval={interval}s"
                )

                frames = []
                frame_idx = 0
                extracted_count = 0

                while True:
                    # Check max_frames limit
                    if max_frames and extracted_count >= max_frames:
                        break

                    # Set frame position
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

                    ret, frame = cap.read()
                    if not ret:
                        break

                    frames.append(frame)
                    extracted_count += 1

                    # Next frame position
                    frame_idx += frame_interval

                    if frame_idx >= total_frames:
                        break
            finally:
                cap.release()

            logger.info(f"Extracted {len(frames)} keyframes from {Path(video_path).name}")
            return frames

        except Exception as e:
            logger.error(f"Keyframe extraction failed: {e}")
            return []

    def embed_frames(self, frames: List[np.ndarray]) -> List[np.ndarray]:
        """
        Encode video frames to embeddings.

        Args:
            frames: List of frame arrays (BGR format from OpenCV)

        Returns:
            List of embedding vectors [1152]
        """
        embeddings = []

        for i, frame in enumerate(frames):
            try:
                # Convert BGR to RGB
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Convert to PIL Image
                pil_image = Image.fromarray(rgb_frame)

                # Encode image
                embedding = self.siglip.encode_image(pil_image)

                if embedding is None:
                    logger.warning(f"Failed to encode frame {i}")
                    continue

                embeddings.append(embedding)

            except Exception as e:
                logger.error(f"Frame {i} encoding failed: {e}")
                continue

        logger.debug(f"Encoded {len(embeddings)}/{len(frames)} frames")
        return embeddings

    def embed_video(
        self,
        video_path: str,
        interval: float = 1.0,
        max_frames: Optional[int] = None,
        aggregation: str = "mean"
    ) -> Optional[np.ndarray]:
        """
        Compute video embedding by aggregating frame embeddings.

        Args:
            video_path: Path to video file
            interval: Keyframe extraction interval in seconds
            max_frames: Maximum number of frames to process
            aggregation: Aggregation method ("mean", "max", or "median")

        Returns:
            Video embedding [1152] or None on error
        """
        # Extract keyframes
        frames = self.extract_keyframes(video_path, interval, max_frames)

        if not frames:
            logger.error(f"No frames extracted from {video_path}")
            return None

        # Encode frames
        embeddings = self.embed_frames(frames)

        if not embeddings:
            logger.error(f"No embeddings generated from {video_path}")
            return None

        # Aggregate embeddings
        embeddings_array = np.stack(embeddings, axis=0)

        if aggregation == "mean":
            video_embedding = np.mean(embeddings_array, axis=0)
        elif aggregation == "max":
            video_embedding = np.max(embeddings_array, axis=0)
        elif aggregation == "median":
            video_embedding = np.median(embeddings_array, axis=0)
        else:
            logger.warning(f"Unknown aggregation '{aggregation}', using mean")
            video_embedding = np.mean(embeddings_array, axis=0)

        # Normalize
        video_embedding = video_embedding / (np.linalg.norm(video_embedding) + 1e-8)

        return video_embedding

    def add_clip(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        metadata: Optional[Dict[str, Any]] = None,
        compute_embedding: bool = True
    ) -> VideoClip:
        """
        Add a video clip to the database.

        Args:
            video_path: Path to video file
            start_time: Clip start time in seconds
            end_time: Clip end time in seconds
            metadata: Additional clip metadata
            compute_embedding: Whether to compute embedding immediately

        Returns:
            Created VideoClip instance
        """
        clip_id = self._next_clip_id
        self._next_clip_id += 1

        # Initialize clip without embedding
        clip = VideoClip(
            clip_id=clip_id,
            video_path=video_path,
            start_time=start_time,
            end_time=end_time,
            metadata=metadata
        )

        # Compute embedding if requested
        if compute_embedding:
            embedding = self._compute_clip_embedding(clip)
            clip.embedding = embedding

            # Store in vector store if available
            if self.vector_store and embedding is not None:
                try:
                    meta_info = {
                        "clip_id": clip_id,
                        "video_path": video_path,
                        "start_time": start_time,
                        "end_time": end_time,
                        "type": "video_clip"
                    }
                    if metadata:
                        meta_info.update(metadata)
                    self.vector_store.add_embedding(embedding, meta_info)
                except Exception as e:
                    logger.error(f"Failed to store embedding in vector store: {e}")

        # Add to in-memory database
        self.clips[clip_id] = clip

        logger.info(f"Added clip: {clip}")
        return clip

    def _compute_clip_embedding(self, clip: VideoClip) -> Optional[np.ndarray]:
        """
        Compute embedding for a specific clip segment.

        Args:
            clip: VideoClip instance

        Returns:
            Clip embedding [1152] or None on error
        """
        try:
            cap = cv2.VideoCapture(clip.video_path)
            if not cap.isOpened():
                logger.error(f"Failed to open video: {clip.video_path}")
                return None

            try:
                fps = cap.get(cv2.CAP_PROP_FPS)
                if fps <= 0:
                    fps = 30.0

                # Convert time to frame indices
                start_frame = int(clip.start_time * fps)
                end_frame = int(clip.end_time * fps)
                num_samples = max(1, min(10, end_frame - start_frame))

                # Sample frames from clip (max 10 frames)
                # BUG-081 FIX: Ensure num is at least 1 to avoid crash/empty array
                frame_indices = np.linspace(start_frame, end_frame, num_samples, dtype=int)

                frames = []
                for frame_idx in frame_indices:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = cap.read()
                    if ret:
                        frames.append(frame)
            finally:
                cap.release()

            if not frames:
                logger.warning(f"No frames extracted from clip {clip.clip_id}")
                return None

            # Encode and aggregate
            embeddings = self.embed_frames(frames)
            if not embeddings:
                return None

            # Mean aggregation
            clip_embedding = np.mean(np.stack(embeddings, axis=0), axis=0)

            # Normalize
            clip_embedding = clip_embedding / (np.linalg.norm(clip_embedding) + 1e-8)

            return clip_embedding

        except Exception as e:
            logger.error(f"Clip embedding computation failed: {e}")
            return None

    def find_similar_clips(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        min_score: float = 0.0
    ) -> List[Tuple[VideoClip, float]]:
        """
        Find similar clips using embedding similarity.

        Args:
            query_embedding: Query embedding vector [1152]
            k: Number of results to return
            min_score: Minimum similarity score threshold

        Returns:
            List of (VideoClip, score) tuples sorted by similarity
        """
        # Use vector store if available
        if self.vector_store:
            try:
                results = self.vector_store.search(query_embedding, k=k)
                clip_results = []

                for meta, score in results:
                    if score < min_score:
                        continue

                    clip_id = meta.get("clip_id")
                    if clip_id is not None and clip_id in self.clips:
                        clip_results.append((self.clips[clip_id], float(score)))

                return clip_results

            except Exception as e:
                logger.error(f"Vector store search failed: {e}")

        # Fallback: in-memory search
        results = []

        for clip in self.clips.values():
            if clip.embedding is None:
                continue

            # BUG-073 FIX: Normalize vectors before dot product for proper cosine similarity
            q_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
            c_norm = clip.embedding / (np.linalg.norm(clip.embedding) + 1e-8)
            
            sim = np.dot(q_norm, c_norm)
            sim = float((sim + 1.0) / 2.0)  # Convert to [0, 1]

            if sim >= min_score:
                results.append((clip, sim))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:k]

    def find_similar_clips_by_video(
        self,
        video_path: str,
        k: int = 5,
        interval: float = 1.0
    ) -> List[Tuple[VideoClip, float]]:
        """
        Find clips similar to a query video.

        Args:
            video_path: Path to query video
            k: Number of results to return
            interval: Keyframe extraction interval

        Returns:
            List of (VideoClip, score) tuples sorted by similarity
        """
        # Compute query embedding
        query_embedding = self.embed_video(video_path, interval=interval)

        if query_embedding is None:
            logger.error(f"Failed to embed query video: {video_path}")
            return []

        return self.find_similar_clips(query_embedding, k=k)

    def tag_video(
        self,
        video_path: str,
        tags: List[str],
        interval: float = 2.0,
        threshold: float = 0.3
    ) -> Dict[str, float]:
        """
        Tag a video with text labels using zero-shot classification.

        Args:
            video_path: Path to video file
            tags: List of possible tags
            interval: Keyframe extraction interval
            threshold: Minimum score threshold for tag inclusion

        Returns:
            Dictionary of tag -> score mappings
        """
        if not self.siglip.has_text_encoder:
            logger.error("Text encoder not available for tagging")
            return {}

        # Extract and encode keyframes
        frames = self.extract_keyframes(video_path, interval=interval, max_frames=20)

        if not frames:
            logger.error(f"No frames extracted from {video_path}")
            return {}

        embeddings = self.embed_frames(frames)

        if not embeddings:
            logger.error(f"No embeddings generated from {video_path}")
            return {}

        # Encode tags
        tag_embeddings = self.siglip.encode_text(tags)

        if tag_embeddings is None:
            logger.error("Failed to encode tags")
            return {}

        # Compute average similarity for each tag across all frames
        tag_scores = {}

        for tag, tag_emb in zip(tags, tag_embeddings):
            scores = []

            for frame_emb in embeddings:
                sim = self.siglip.similarity(frame_emb, tag_emb)
                scores.append(sim)

            # Average score across frames
            avg_score = float(np.mean(scores))

            if avg_score >= threshold:
                tag_scores[tag] = avg_score

        # Sort by score descending
        tag_scores = dict(sorted(tag_scores.items(), key=lambda x: x[1], reverse=True))

        return tag_scores

    def get_video_metadata(self, video_path: str) -> Dict[str, Any]:
        """
        Extract basic video metadata.

        Args:
            video_path: Path to video file

        Returns:
            Dictionary with video metadata
        """
        cap = None
        try:
            cap = cv2.VideoCapture(video_path)

            if not cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                return {}

            metadata = {
                "path": video_path,
                "fps": float(cap.get(cv2.CAP_PROP_FPS)),
                "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            }

            # Calculate duration
            if metadata["fps"] > 0:
                metadata["duration"] = metadata["frame_count"] / metadata["fps"]
            else:
                metadata["duration"] = 0.0

            return metadata

        except Exception as e:
            logger.error(f"Failed to extract metadata: {e}")
            return {}
        finally:
            if cap is not None:
                cap.release()

    @property
    def is_ready(self) -> bool:
        """Check if the specialist is ready for use."""
        return self.siglip.is_ready

    @property
    def num_clips(self) -> int:
        """Get number of clips in database."""
        return len(self.clips)

    def clear_clips(self):
        """Clear all clips from memory."""
        self.clips.clear()
        self._next_clip_id = 0
        logger.info("Cleared all clips from memory")


# Convenience functions
def analyze_video_similarity(
    video1_path: str,
    video2_path: str,
    interval: float = 1.0
) -> float:
    """
    Compute similarity between two videos.

    Args:
        video1_path: Path to first video
        video2_path: Path to second video
        interval: Keyframe extraction interval

    Returns:
        Similarity score in range [0, 1]
    """
    specialist = VideoSpecialist()

    emb1 = specialist.embed_video(video1_path, interval=interval)
    emb2 = specialist.embed_video(video2_path, interval=interval)

    if emb1 is None or emb2 is None:
        return 0.0

    sim = np.dot(emb1, emb2)
    return float((sim + 1.0) / 2.0)


def tag_video_quick(
    video_path: str,
    tags: List[str],
    threshold: float = 0.3
) -> Dict[str, float]:
    """
    Quick video tagging function.

    Args:
        video_path: Path to video file
        tags: List of possible tags
        threshold: Minimum score threshold

    Returns:
        Dictionary of tag -> score mappings
    """
    specialist = VideoSpecialist()
    return specialist.tag_video(video_path, tags, threshold=threshold)
