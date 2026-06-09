"""
Global GPU inference lock for PB Studio AMD.

Provides a process-wide synchronous lock to serialize direct ML and ONNX Runtime
inference calls, preventing parallel VRAM overcommits on systems with limited GPU memory.
"""
import threading
import logging

logger = logging.getLogger(__name__)

# Synchronous Lock to serialize model inference runs across all threads
gpu_inference_lock = threading.Lock()

def get_gpu_inference_lock() -> threading.Lock:
    """Get the global process-wide GPU inference lock."""
    return gpu_inference_lock
