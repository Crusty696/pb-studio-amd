"""
SigLIP Video Specialist - Usage Examples

Historical API sketch for SigLIP/VideoSpecialist.

This file is retained as reference and is not the production project-media
workflow. Production callers use registered media IDs. Do not use this script
to provision or download model assets.

Requirements:
- SigLIP ONNX models in models/ directory
- Sample videos for testing
- AMD GPU with DirectML support (missing DML fails closed)
- Production videos imported into the active project's local media catalog
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pb_studio.ai import SigLIPWrapper, VideoSpecialist, VideoClip
from pb_studio.data.vector_store import VectorStore
from PIL import Image

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_1_image_encoding():
    """Example 1: Basic image encoding."""
    logger.info("=== Example 1: Image Encoding ===")

    # Initialize SigLIP wrapper
    siglip = SigLIPWrapper()

    if not siglip.is_ready:
        logger.warning("SigLIP capability unavailable; verify approved assets.")
        return

    # Load an image
    image_path = "sample_image.jpg"
    if not Path(image_path).exists():
        logger.warning(f"Sample image not found: {image_path}")
        return

    image = Image.open(image_path)

    # Encode image
    embedding = siglip.encode_image(image)

    logger.info(f"Embedding shape: {embedding.shape}")
    logger.info(f"Embedding dtype: {embedding.dtype}")
    logger.info(f"Embedding norm: {np.linalg.norm(embedding):.4f}")

    return embedding


def example_2_zero_shot_classification():
    """Example 2: Zero-shot image classification."""
    logger.info("=== Example 2: Zero-shot Classification ===")

    siglip = SigLIPWrapper()

    if not siglip.is_ready or not siglip.has_text_encoder:
        logger.warning("Text encoder not available. Skipping example.")
        return

    image_path = "sample_image.jpg"
    if not Path(image_path).exists():
        logger.warning(f"Sample image not found: {image_path}")
        return

    image = Image.open(image_path)

    # Define labels
    labels = [
        "a photo of a landscape",
        "a photo of a person",
        "a photo of an animal",
        "a photo of a building",
        "a photo of food",
        "abstract art"
    ]

    # Classify
    results = siglip.classify_image(image, labels)

    logger.info("Classification results:")
    for label, score in results:
        logger.info(f"  {label}: {score:.3f}")


def example_3_video_keyframes():
    """Example 3: Extract and encode video keyframes."""
    logger.info("=== Example 3: Video Keyframe Extraction ===")

    specialist = VideoSpecialist()

    if not specialist.is_ready:
        logger.warning("VideoSpecialist unavailable; verify approved assets.")
        return

    video_path = "sample_video.mp4"
    if not Path(video_path).exists():
        logger.warning(f"Sample video not found: {video_path}")
        return

    # Get video metadata
    metadata = specialist.get_video_metadata(video_path)
    logger.info(f"Video duration: {metadata['duration']:.2f}s")
    logger.info(f"Resolution: {metadata['width']}x{metadata['height']}")
    logger.info(f"FPS: {metadata['fps']:.2f}")

    # Extract keyframes
    frames = specialist.extract_keyframes(video_path, interval=2.0, max_frames=10)
    logger.info(f"Extracted {len(frames)} keyframes")

    # Encode frames
    embeddings = specialist.embed_frames(frames)
    logger.info(f"Generated {len(embeddings)} embeddings")

    return embeddings


def example_4_video_embedding():
    """Example 4: Compute full video embedding."""
    logger.info("=== Example 4: Video Embedding ===")

    specialist = VideoSpecialist()

    if not specialist.is_ready:
        logger.warning("VideoSpecialist not ready.")
        return

    video_path = "sample_video.mp4"
    if not Path(video_path).exists():
        logger.warning(f"Sample video not found: {video_path}")
        return

    # Compute video embedding with different aggregations
    for agg_method in ["mean", "max", "median"]:
        embedding = specialist.embed_video(
            video_path,
            interval=2.0,
            max_frames=15,
            aggregation=agg_method
        )

        if embedding is not None:
            logger.info(f"{agg_method.capitalize()} embedding norm: {np.linalg.norm(embedding):.4f}")


def example_5_clip_database():
    """Example 5: Build a clip database with similarity search."""
    logger.info("=== Example 5: Clip Database ===")

    specialist = VideoSpecialist()

    if not specialist.is_ready:
        logger.warning("VideoSpecialist not ready.")
        return

    # Add clips from different videos
    video_files = [
        "video1.mp4",
        "video2.mp4",
        "video3.mp4"
    ]

    for video_path in video_files:
        if not Path(video_path).exists():
            logger.warning(f"Video not found: {video_path}")
            continue

        # Get video duration
        metadata = specialist.get_video_metadata(video_path)
        duration = metadata.get("duration", 0)

        if duration == 0:
            continue

        # Split video into 5-second clips
        num_clips = int(duration / 5.0)

        for i in range(num_clips):
            start_time = i * 5.0
            end_time = min((i + 1) * 5.0, duration)

            clip = specialist.add_clip(
                video_path=video_path,
                start_time=start_time,
                end_time=end_time,
                metadata={
                    "video_name": Path(video_path).name,
                    "clip_index": i
                },
                compute_embedding=True
            )

            logger.info(f"Added clip: {clip}")

    logger.info(f"Total clips in database: {specialist.num_clips}")

    # Query similar clips
    if specialist.num_clips > 0:
        query_path = "query_video.mp4"
        if Path(query_path).exists():
            logger.info(f"Searching for clips similar to {query_path}...")

            results = specialist.find_similar_clips_by_video(query_path, k=5, interval=2.0)

            logger.info("Top 5 similar clips:")
            for clip, score in results:
                logger.info(f"  {clip} - Score: {score:.3f}")


def example_6_video_tagging():
    """Example 6: Tag video with semantic labels."""
    logger.info("=== Example 6: Video Tagging ===")

    specialist = VideoSpecialist()

    if not specialist.is_ready or not specialist.siglip.has_text_encoder:
        logger.warning("Text encoder not available.")
        return

    video_path = "sample_video.mp4"
    if not Path(video_path).exists():
        logger.warning(f"Sample video not found: {video_path}")
        return

    # Define tags
    tags = [
        "action",
        "calm",
        "outdoor",
        "indoor",
        "daytime",
        "nighttime",
        "people",
        "nature",
        "urban",
        "close-up"
    ]

    # Tag video
    tag_scores = specialist.tag_video(
        video_path,
        tags=tags,
        interval=2.0,
        threshold=0.3
    )

    logger.info("Video tags:")
    for tag, score in tag_scores.items():
        logger.info(f"  {tag}: {score:.3f}")


def example_7_vector_store_integration():
    """Example 7: Integrate with FAISS vector store."""
    logger.info("=== Example 7: Vector Store Integration ===")

    # Create vector store
    vector_store = VectorStore(index_name="video_clips_demo")

    # Initialize specialist with vector store
    specialist = VideoSpecialist(vector_store=vector_store)

    if not specialist.is_ready:
        logger.warning("VideoSpecialist not ready.")
        return

    video_path = "sample_video.mp4"
    if not Path(video_path).exists():
        logger.warning(f"Sample video not found: {video_path}")
        return

    # Add clips (automatically stored in vector store)
    metadata = specialist.get_video_metadata(video_path)
    duration = metadata.get("duration", 0)

    if duration > 0:
        num_clips = min(5, int(duration / 3.0))

        for i in range(num_clips):
            start_time = i * 3.0
            end_time = min((i + 1) * 3.0, duration)

            clip = specialist.add_clip(
                video_path,
                start_time,
                end_time,
                compute_embedding=True
            )

            logger.info(f"Added and indexed: {clip}")

        # Save vector store
        vector_store.save()
        logger.info(f"Vector store saved with {specialist.num_clips} clips")

        # Search using vector store
        if specialist.num_clips > 0:
            # Create query embedding
            query_embedding = specialist.embed_video(video_path, interval=3.0, max_frames=5)

            if query_embedding is not None:
                results = specialist.find_similar_clips(query_embedding, k=3)

                logger.info("Similar clips from vector store:")
                for clip, score in results:
                    logger.info(f"  {clip} - Score: {score:.3f}")


def example_8_batch_processing():
    """Example 8: Batch process multiple videos."""
    logger.info("=== Example 8: Batch Processing ===")

    specialist = VideoSpecialist()

    if not specialist.is_ready:
        logger.warning("VideoSpecialist not ready.")
        return

    # Find all videos in a directory
    video_dir = Path("data/video")
    if not video_dir.exists():
        logger.warning(f"Video directory not found: {video_dir}")
        return

    video_files = list(video_dir.glob("*.mp4"))

    if not video_files:
        logger.warning("No video files found")
        return

    logger.info(f"Processing {len(video_files)} videos...")

    results = {}

    for video_path in video_files:
        logger.info(f"Processing {video_path.name}...")

        # Compute embedding
        embedding = specialist.embed_video(
            str(video_path),
            interval=3.0,
            max_frames=20
        )

        if embedding is not None:
            results[video_path.name] = embedding
            logger.info(f"  ✓ Embedding computed")
        else:
            logger.warning(f"  ✗ Failed to compute embedding")

    logger.info(f"Successfully processed {len(results)}/{len(video_files)} videos")

    # Compute similarity matrix
    if len(results) > 1:
        logger.info("Computing similarity matrix...")

        import numpy as np

        video_names = list(results.keys())
        n = len(video_names)

        similarity_matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(i, n):
                emb_i = results[video_names[i]]
                emb_j = results[video_names[j]]

                sim = np.dot(emb_i, emb_j)
                sim = (sim + 1.0) / 2.0

                similarity_matrix[i, j] = sim
                similarity_matrix[j, i] = sim

        logger.info("Similarity matrix:")
        for i, name_i in enumerate(video_names):
            row = " ".join([f"{similarity_matrix[i, j]:.2f}" for j in range(n)])
            logger.info(f"  {name_i}: [{row}]")


def main():
    """Run all examples."""
    import numpy as np

    logger.info("Starting SigLIP Video Specialist Examples\n")

    try:
        # Run examples
        example_1_image_encoding()
        logger.info("")

        example_2_zero_shot_classification()
        logger.info("")

        example_3_video_keyframes()
        logger.info("")

        example_4_video_embedding()
        logger.info("")

        example_5_clip_database()
        logger.info("")

        example_6_video_tagging()
        logger.info("")

        example_7_vector_store_integration()
        logger.info("")

        example_8_batch_processing()
        logger.info("")

        logger.info("All examples completed!")

    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)


if __name__ == "__main__":
    main()
