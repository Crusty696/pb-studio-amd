"""
PB Studio Core Module - AMD DirectML Edition

This module provides core infrastructure for GPU resource management.

Components:
- VRAMBudgetManager: Central VRAM allocation and tracking
- VRAMArbiter: Legacy interface (uses BudgetManager internally)
- ModelLoader: VRAM-aware model loading
- SystemMonitor: Hardware monitoring via LibreHardwareMonitor
- TaskQueue: Priority-based task scheduling
- ThreadPool: Worker thread management
"""

from pb_studio.core.system_monitor import SystemMonitor
from pb_studio.core.directml_adapter import (
    DirectMLAdapter,
    DirectMLAdapterError,
    enumerate_dxgi_adapters,
    get_directml_adapter,
    get_directml_provider,
)
from pb_studio.core.vram_arbiter import VRAMArbiter
from pb_studio.core.vram_budget_manager import (
    VRAMBudgetManager,
    ModelPriority,
    VRAMContext,
    get_vram_manager,
    KNOWN_MODEL_BUDGETS
)
try:
    from pb_studio.core.model_loader import (
        ModelLoader,
        ModelSpec,
        ModelType,
        get_model_loader,
        load_model,
        unload_model
    )
except ImportError:  # Optional in verification envs without onnxruntime
    ModelLoader = None
    ModelSpec = None
    ModelType = None
    get_model_loader = None
    load_model = None
    unload_model = None

from pb_studio.core.task_queue import TaskQueue, TaskPriority, TaskItem
try:
    from pb_studio.core.thread_pool import ThreadPoolManager, Worker
except ImportError:
    ThreadPoolManager = None
    Worker = None  # PyQt6 nicht verfügbar (z.B. Linux CI ohne Windows-.venv)
from pb_studio.core.crash_handler import CrashHandler

__all__ = [
    # Monitoring
    "SystemMonitor",
    "DirectMLAdapter",
    "DirectMLAdapterError",
    "enumerate_dxgi_adapters",
    "get_directml_adapter",
    "get_directml_provider",

    # VRAM Management
    "VRAMArbiter",
    "VRAMBudgetManager",
    "ModelPriority",
    "VRAMContext",
    "get_vram_manager",
    "KNOWN_MODEL_BUDGETS",

    # Model Loading
    "ModelLoader",
    "ModelSpec",
    "ModelType",
    "get_model_loader",
    "load_model",
    "unload_model",

    # Task Management
    "TaskQueue",
    "TaskPriority",
    "TaskItem",
    "ThreadPoolManager",
    "Worker",

    # Error Handling
    "CrashHandler",
]
