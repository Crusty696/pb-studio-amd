"""
Test Suite for SigLIP and VideoSpecialist modules.

Tests the AMD DirectML-optimized SigLIP image encoder and video analysis pipeline.
"""

import pytest
import numpy as np
from pathlib import Path
from PIL import Image
import cv2

from pb_studio.ai import SigLIPWrapper, VideoSpecialist, VideoClip


@pytest.fixture
def siglip_wrapper():
    """Create SigLIP wrapper instance."""
    return SigLIPWrapper(lazy_load=False)


@pytest.fixture
def video_specialist():
    """Create VideoSpecialist instance."""
    return VideoSpecialist()


@pytest.fixture
def dummy_image():
    """Create a dummy RGB image."""
    # 384x384 random RGB image
    img_array = np.random.randint(0, 255, (384, 384, 3), dtype=np.uint8)
    return Image.fromarray(img_array, mode='RGB')


@pytest.fixture
def dummy_video(tmp_path):
    """Create a dummy video file for testing."""
    video_path = tmp_path / "test_video.mp4"

    # Create a simple 5-second video at 30 FPS
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(video_path), fourcc, 30.0, (640, 480))

    for i in range(150):  # 5 seconds at 30 FPS
        # Create frame with changing colors
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:, :] = [i % 255, (i * 2) % 255, (i * 3) % 255]
        out.write(frame)

    out.release()

    return str(video_path)


class TestSigLIPWrapper:
    """Test SigLIP wrapper functionality."""

    def test_initialization(self, siglip_wrapper):
        """Test wrapper initialization."""
        # Note: Will fail if model not downloaded, but should not crash
        assert siglip_wrapper is not None
        assert hasattr(siglip_wrapper, 'vision_session')

    def test_preprocess_image(self, siglip_wrapper, dummy_image):
        """Test image preprocessing."""
        preprocessed = siglip_wrapper.preprocess_image(dummy_image)

        assert preprocessed is not None
        assert preprocessed.shape == (1, 3, 384, 384)
        assert preprocessed.dtype == np.float32

    def test_encode_image_mock(self, siglip_wrapper, dummy_image):
        """Test image encoding (mock if model not available)."""
        embedding = siglip_wrapper.encode_image(dummy_image)

        if siglip_wrapper.is_ready:
            # Model loaded - verify output
            assert embedding is not None
            assert embedding.shape == (1152,)
            assert embedding.dtype == np.float32

            # Check normalization
            norm = np.linalg.norm(embedding)
            assert abs(norm - 1.0) < 0.01  # Should be normalized
        else:
            # Model not available
            assert embedding is None

    def test_encode_images_batch(self, siglip_wrapper, dummy_image):
        """Test batch image encoding."""
        images = [dummy_image, dummy_image, dummy_image]
        embeddings = siglip_wrapper.encode_images_batch(images)

        if siglip_wrapper.is_ready:
            assert embeddings is not None
            assert embeddings.shape == (3, 1152)
        else:
            assert embeddings is None

    def test_encode_text_mock(self, siglip_wrapper):
        """Test text encoding (mock if model not available)."""
        texts = ["a photo of a cat", "a photo of a dog"]

        if not siglip_wrapper.has_text_encoder:
            pytest.skip("Text encoder not available")

        embeddings = siglip_wrapper.encode_text(texts)

        if embeddings is not None:
            assert embeddings.shape == (2, 1152)
            assert embeddings.dtype == np.float32

    def test_similarity(self, siglip_wrapper):
        """Test similarity computation."""
        # Create two random normalized embeddings
        emb1 = np.random.randn(1152).astype(np.float32)
        emb1 = emb1 / np.linalg.norm(emb1)

        emb2 = np.random.randn(1152).astype(np.float32)
        emb2 = emb2 / np.linalg.norm(emb2)

        sim = siglip_wrapper.similarity(emb1, emb2)

        assert isinstance(sim, float)
        assert 0.0 <= sim <= 1.0

    def test_classify_image_mock(self, siglip_wrapper, dummy_image):
        """Test zero-shot classification (mock if model not available)."""
        if not siglip_wrapper.has_text_encoder:
            pytest.skip("Text encoder not available")

        labels = ["landscape", "portrait", "abstract"]
        results = siglip_wrapper.classify_image(dummy_image, labels)

        if siglip_wrapper.is_ready:
            assert isinstance(results, list)
            assert len(results) == 3

            # Check format
            for label, score in results:
                assert isinstance(label, str)
                assert isinstance(score, float)
                assert 0.0 <= score <= 1.0

            # Check sorted by score
            scores = [score for _, score in results]
            assert scores == sorted(scores, reverse=True)

    def test_properties(self, siglip_wrapper):
        """Test wrapper properties."""
        assert isinstance(siglip_wrapper.is_ready, bool)
        assert isinstance(siglip_wrapper.has_text_encoder, bool)
        assert siglip_wrapper.embedding_dimension == 1152
        assert isinstance(siglip_wrapper.active_provider, str)


class TestVideoSpecialist:
    """Test VideoSpecialist functionality."""

    def test_initialization(self, video_specialist):
        """Test specialist initialization."""
        assert video_specialist is not None
        assert video_specialist.siglip is not None
        assert video_specialist.num_clips == 0

    def test_extract_keyframes(self, video_specialist, dummy_video):
        """Test keyframe extraction."""
        frames = video_specialist.extract_keyframes(dummy_video, interval=1.0)

        assert isinstance(frames, list)
        assert len(frames) > 0

        # Check frame format
        for frame in frames:
            assert isinstance(frame, np.ndarray)
            assert frame.ndim == 3  # H, W, C
            assert frame.shape[2] == 3  # BGR

    def test_extract_keyframes_with_limit(self, video_specialist, dummy_video):
        """Test keyframe extraction with max_frames limit."""
        frames = video_specialist.extract_keyframes(dummy_video, interval=0.5, max_frames=5)

        assert isinstance(frames, list)
        assert len(frames) <= 5

    def test_embed_frames_mock(self, video_specialist, dummy_video):
        """Test frame embedding."""
        frames = video_specialist.extract_keyframes(dummy_video, interval=2.0, max_frames=3)
        embeddings = video_specialist.embed_frames(frames)

        if video_specialist.is_ready:
            assert isinstance(embeddings, list)
            assert len(embeddings) > 0

            for emb in embeddings:
                assert emb.shape == (1152,)
                assert emb.dtype == np.float32

    def test_embed_video_mock(self, video_specialist, dummy_video):
        """Test video embedding."""
        embedding = video_specialist.embed_video(dummy_video, interval=2.0, max_frames=5)

        if video_specialist.is_ready:
            assert embedding is not None
            assert embedding.shape == (1152,)
            assert embedding.dtype == np.float32

            # Check normalization
            norm = np.linalg.norm(embedding)
            assert abs(norm - 1.0) < 0.01

    def test_add_clip(self, video_specialist, dummy_video):
        """Test adding a clip to database."""
        clip = video_specialist.add_clip(
            video_path=dummy_video,
            start_time=0.0,
            end_time=2.0,
            metadata={"tag": "test"},
            compute_embedding=False  # Skip embedding computation
        )

        assert isinstance(clip, VideoClip)
        assert clip.clip_id == 0
        assert clip.video_path == dummy_video
        assert clip.start_time == 0.0
        assert clip.end_time == 2.0
        assert clip.duration == 2.0
        assert clip.metadata["tag"] == "test"

        assert video_specialist.num_clips == 1

    def test_find_similar_clips_mock(self, video_specialist, dummy_video):
        """Test finding similar clips."""
        # Add some clips
        video_specialist.add_clip(dummy_video, 0.0, 2.0, compute_embedding=False)
        video_specialist.add_clip(dummy_video, 2.0, 4.0, compute_embedding=False)

        # Create query embedding
        query_emb = np.random.randn(1152).astype(np.float32)
        query_emb = query_emb / np.linalg.norm(query_emb)

        # Manually set embeddings for testing
        for clip in video_specialist.clips.values():
            clip.embedding = np.random.randn(1152).astype(np.float32)
            clip.embedding = clip.embedding / np.linalg.norm(clip.embedding)

        # Search
        results = video_specialist.find_similar_clips(query_emb, k=2)

        assert isinstance(results, list)
        assert len(results) <= 2

        for clip, score in results:
            assert isinstance(clip, VideoClip)
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0

    def test_tag_video_mock(self, video_specialist, dummy_video):
        """Test video tagging."""
        if not video_specialist.siglip.has_text_encoder:
            pytest.skip("Text encoder not available")

        tags = ["action", "calm", "colorful"]
        tag_scores = video_specialist.tag_video(dummy_video, tags, interval=2.0)

        if video_specialist.is_ready:
            assert isinstance(tag_scores, dict)

            for tag, score in tag_scores.items():
                assert tag in tags
                assert isinstance(score, float)
                assert 0.0 <= score <= 1.0

    def test_get_video_metadata(self, video_specialist, dummy_video):
        """Test video metadata extraction."""
        metadata = video_specialist.get_video_metadata(dummy_video)

        assert isinstance(metadata, dict)
        assert "path" in metadata
        assert "fps" in metadata
        assert "frame_count" in metadata
        assert "width" in metadata
        assert "height" in metadata
        assert "duration" in metadata

        assert metadata["path"] == dummy_video
        assert metadata["fps"] > 0
        assert metadata["frame_count"] > 0
        assert metadata["width"] == 640
        assert metadata["height"] == 480

    def test_clear_clips(self, video_specialist, dummy_video):
        """Test clearing clips."""
        video_specialist.add_clip(dummy_video, 0.0, 2.0, compute_embedding=False)
        video_specialist.add_clip(dummy_video, 2.0, 4.0, compute_embedding=False)

        assert video_specialist.num_clips == 2

        video_specialist.clear_clips()

        assert video_specialist.num_clips == 0
        assert len(video_specialist.clips) == 0


class TestVideoClip:
    """Test VideoClip data class."""

    def test_initialization(self):
        """Test VideoClip initialization."""
        clip = VideoClip(
            clip_id=1,
            video_path="/path/to/video.mp4",
            start_time=0.0,
            end_time=5.0,
            metadata={"tag": "test"}
        )

        assert clip.clip_id == 1
        assert clip.video_path == "/path/to/video.mp4"
        assert clip.start_time == 0.0
        assert clip.end_time == 5.0
        assert clip.duration == 5.0
        assert clip.metadata["tag"] == "test"
        assert clip.embedding is None

    def test_repr(self):
        """Test string representation."""
        clip = VideoClip(
            clip_id=42,
            video_path="/path/to/test_video.mp4",
            start_time=1.5,
            end_time=3.7
        )

        repr_str = repr(clip)

        assert "VideoClip" in repr_str
        assert "id=42" in repr_str
        assert "test_video.mp4" in repr_str
        assert "1.50" in repr_str
        assert "3.70" in repr_str


class TestIntegration:
    """Integration tests for SigLIP and VideoSpecialist."""

    def test_full_pipeline_mock(self, video_specialist, dummy_video):
        """Test full video analysis pipeline."""
        if not video_specialist.is_ready:
            pytest.skip("Models not available")

        # 1. Extract metadata
        metadata = video_specialist.get_video_metadata(dummy_video)
        assert metadata["duration"] > 0

        # 2. Compute video embedding
        video_emb = video_specialist.embed_video(dummy_video, interval=1.0, max_frames=10)
        assert video_emb is not None

        # 3. Add clips with embeddings
        clip1 = video_specialist.add_clip(dummy_video, 0.0, 2.0, compute_embedding=True)
        clip2 = video_specialist.add_clip(dummy_video, 2.0, 4.0, compute_embedding=True)

        assert video_specialist.num_clips == 2

        # 4. Find similar clips
        results = video_specialist.find_similar_clips(video_emb, k=2)
        assert len(results) <= 2

        # 5. Tag video (if text encoder available)
        if video_specialist.siglip.has_text_encoder:
            tags = ["motion", "static", "colorful"]
            tag_scores = video_specialist.tag_video(dummy_video, tags)
            assert isinstance(tag_scores, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
