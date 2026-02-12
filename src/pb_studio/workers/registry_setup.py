"""
Worker Registry Setup for PB Studio AMD

Registers all workers with their VRAM budgets at application startup.
This module should be called once during application initialization.
"""

import logging
from typing import Optional

from .worker_registry import WorkerRegistry
from .base_worker import BaseWorker

# Audio workers
from .audio import (
    AudioImportWorker,
    AudioAnalyzeWorker,
    AudioStemWorker,
    AudioEmbeddingWorker,
)

# Video workers
from .video import (
    VideoImportWorker,
    VideoSceneWorker,
    VideoMotionWorker,
    VideoVisionWorker,
)

# Generation workers
from .generation import (
    PacingWorker,
    RenderWorker,
    ConcatWorker,
    ExportWorker,
)

logger = logging.getLogger(__name__)


# Worker definitions with VRAM budgets (in MB)
# Format: (name, worker_class, vram_budget_mb)
WORKER_DEFINITIONS = [
    # Audio Pipeline Workers
    ("audio_import", AudioImportWorker, 0),       # CPU only - FFmpeg subprocess
    ("audio_analyze", AudioAnalyzeWorker, 0),     # CPU only - BeatNet DBN inference
    ("audio_stem", AudioStemWorker, 2000),        # GPU - ONNX DirectML models
    ("audio_embedding", AudioEmbeddingWorker, 800),  # GPU - CLAP model

    # Video Pipeline Workers
    ("video_import", VideoImportWorker, 0),       # CPU only - FFprobe
    ("video_scene", VideoSceneWorker, 0),         # CPU only - PySceneDetect
    ("video_motion", VideoMotionWorker, 1500),    # GPU - RAFT optical flow
    ("video_vision", VideoVisionWorker, 2500),    # GPU - Moondream VLM

    # Generation Pipeline Workers
    ("pacing", PacingWorker, 0),                  # CPU only - Algorithm
    ("render", RenderWorker, 500),                # GPU - AMF encoder
    ("concat", ConcatWorker, 500),                # GPU - AMF encoder
    ("export", ExportWorker, 500),                # GPU - Shared with children
]


def setup_worker_registry(registry: Optional[WorkerRegistry] = None) -> WorkerRegistry:
    """
    Setup and populate the worker registry with all available workers.

    This function registers all worker classes with their VRAM budgets,
    making them available for lookup and instantiation throughout the app.

    Args:
        registry: Optional existing registry instance. If None, uses singleton.

    Returns:
        The populated WorkerRegistry instance.

    Example:
        # At application startup
        from pb_studio.workers import setup_worker_registry

        registry = setup_worker_registry()
        print(f"Registered {len(registry.list_workers())} workers")
    """
    if registry is None:
        registry = WorkerRegistry()

    registered_count = 0
    skipped_count = 0

    for name, worker_class, vram_budget in WORKER_DEFINITIONS:
        try:
            if registry.is_registered(name):
                logger.debug(f"Worker '{name}' already registered, skipping")
                skipped_count += 1
                continue

            registry.register_worker(
                name=name,
                worker_class=worker_class,
                vram_budget=vram_budget
            )
            registered_count += 1
            logger.debug(f"Registered worker: {name} (VRAM: {vram_budget}MB)")

        except Exception as e:
            logger.error(f"Failed to register worker '{name}': {e}")

    logger.info(
        f"Worker registry setup complete: {registered_count} registered, "
        f"{skipped_count} skipped"
    )

    return registry


def get_worker_vram_requirements() -> dict[str, int]:
    """
    Get VRAM requirements for all workers.

    Returns:
        Dictionary mapping worker names to their VRAM budgets in MB.
    """
    return {name: vram for name, _, vram in WORKER_DEFINITIONS}


def get_gpu_workers() -> list[str]:
    """
    Get list of workers that require GPU (VRAM > 0).

    Returns:
        List of worker names that use GPU acceleration.
    """
    return [name for name, _, vram in WORKER_DEFINITIONS if vram > 0]


def get_cpu_workers() -> list[str]:
    """
    Get list of CPU-only workers (VRAM = 0).

    Returns:
        List of worker names that run on CPU only.
    """
    return [name for name, _, vram in WORKER_DEFINITIONS if vram == 0]


def calculate_pipeline_vram(pipeline: str) -> int:
    """
    Calculate total VRAM needed for a specific pipeline.

    This calculates the PEAK VRAM usage, not simultaneous usage.
    Workers in a pipeline typically run sequentially.

    Args:
        pipeline: Pipeline name ("audio", "video", "generation", "full")

    Returns:
        Peak VRAM requirement in MB for the pipeline.
    """
    pipeline_workers = {
        "audio": ["audio_import", "audio_analyze", "audio_stem", "audio_embedding"],
        "video": ["video_import", "video_scene", "video_motion", "video_vision"],
        "generation": ["pacing", "render", "concat", "export"],
        "full": [name for name, _, _ in WORKER_DEFINITIONS],
    }

    if pipeline not in pipeline_workers:
        raise ValueError(f"Unknown pipeline: {pipeline}. Available: {list(pipeline_workers.keys())}")

    vram_dict = get_worker_vram_requirements()
    workers = pipeline_workers[pipeline]

    # Return the maximum VRAM used by any single worker in the pipeline
    # (since they run sequentially, peak usage is the max of individual workers)
    return max(vram_dict.get(w, 0) for w in workers)


# Convenience function for quick registry access
def get_worker_class(name: str) -> type[BaseWorker]:
    """
    Get a worker class by name.

    Convenience function that initializes registry if needed.

    Args:
        name: Registered worker name

    Returns:
        Worker class (subclass of BaseWorker)
    """
    registry = WorkerRegistry()
    if not registry.list_workers():
        setup_worker_registry(registry)
    return registry.get_worker(name)
