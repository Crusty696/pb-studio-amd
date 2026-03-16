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
try:
    from .registry_setup import (
        setup_worker_registry,
        get_worker_vram_requirements,
        get_gpu_workers,
        get_cpu_workers,
        calculate_pipeline_vram,
        get_worker_class,
    )
except ImportError:
    setup_worker_registry = None
    get_worker_vram_requirements = None
    get_gpu_workers = None
    get_cpu_workers = None
    calculate_pipeline_vram = None
    get_worker_class = None

# Orchestrator
try:
    from .orchestrator import (
        WorkerOrchestrator,
        AudioPipelineResult,
        VideoPipelineResult,
    )
except ImportError:
    WorkerOrchestrator = None
    AudioPipelineResult = None
    VideoPipelineResult = None

# Audio Workers
try:
    from .audio import (
        AudioImportWorker,
        AudioAnalyzeWorker,
        AudioStemWorker,
        AudioEmbeddingWorker,
    )
except ImportError:
    AudioImportWorker = None
    AudioAnalyzeWorker = None
    AudioStemWorker = None
    AudioEmbeddingWorker = None

# Video Workers
try:
    from .video import (
        VideoImportWorker,
        VideoSceneWorker,
        VideoMotionWorker,
        VideoVisionWorker,
    )
except ImportError:
    VideoImportWorker = None
    VideoSceneWorker = None
    VideoMotionWorker = None
    VideoVisionWorker = None

# Generation Workers
try:
    from .generation import (
        PacingWorker,
        RenderWorker,
        ConcatWorker,
        ExportWorker,
    )
except ImportError:
    PacingWorker = None
    RenderWorker = None
    ConcatWorker = None
    ExportWorker = None

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
