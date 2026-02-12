"""
PB Studio Workers Module

Provides base worker infrastructure for async task execution,
specialized workers for audio/video/generation pipelines,
and orchestration utilities.

VRAM Budget Overview (in MB):
- audio_import: 0 (CPU only)
- audio_analyze: 0 (CPU only)
- audio_stem: 2000 (ONNX DirectML)
- audio_embedding: 800 (CLAP model)
- video_import: 0 (CPU only)
- video_scene: 0 (CPU only)
- video_motion: 1500 (RAFT optical flow)
- video_vision: 2500 (Moondream VLM)
- pacing: 0 (CPU only)
- render: 500 (AMF encoder)
- concat: 500 (AMF encoder)
- export: 500 (AMF encoder)
"""

# Base infrastructure
from .base_worker import BaseWorker, CancelledError
from .worker_registry import WorkerRegistry

# Setup utilities
from .registry_setup import (
    setup_worker_registry,
    get_worker_vram_requirements,
    get_gpu_workers,
    get_cpu_workers,
    calculate_pipeline_vram,
    get_worker_class,
)

# Orchestrator
from .orchestrator import (
    WorkerOrchestrator,
    AudioPipelineResult,
    VideoPipelineResult,
)

# Audio Workers
from .audio import (
    AudioImportWorker,
    AudioAnalyzeWorker,
    AudioStemWorker,
    AudioEmbeddingWorker,
)

# Video Workers
from .video import (
    VideoImportWorker,
    VideoSceneWorker,
    VideoMotionWorker,
    VideoVisionWorker,
)

# Generation Workers
from .generation import (
    PacingWorker,
    RenderWorker,
    ConcatWorker,
    ExportWorker,
)

__all__ = [
    # Base infrastructure
    'BaseWorker',
    'CancelledError',
    'WorkerRegistry',

    # Setup utilities
    'setup_worker_registry',
    'get_worker_vram_requirements',
    'get_gpu_workers',
    'get_cpu_workers',
    'calculate_pipeline_vram',
    'get_worker_class',

    # Orchestrator
    'WorkerOrchestrator',
    'AudioPipelineResult',
    'VideoPipelineResult',

    # Audio Workers
    'AudioImportWorker',
    'AudioAnalyzeWorker',
    'AudioStemWorker',
    'AudioEmbeddingWorker',

    # Video Workers
    'VideoImportWorker',
    'VideoSceneWorker',
    'VideoMotionWorker',
    'VideoVisionWorker',

    # Generation Workers
    'PacingWorker',
    'RenderWorker',
    'ConcatWorker',
    'ExportWorker',
]
