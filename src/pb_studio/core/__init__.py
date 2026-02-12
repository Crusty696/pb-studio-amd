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

from src.pb_studio.core.system_monitor import SystemMonitor
from src.pb_studio.core.vram_arbiter import VRAMArbiter
from src.pb_studio.core.vram_budget_manager import (
    VRAMBudgetManager,
    ModelPriority,
    VRAMContext,
    get_vram_manager,
    KNOWN_MODEL_BUDGETS
)
from src.pb_studio.core.model_loader import (
    ModelLoader,
    ModelSpec,
    ModelType,
    get_model_loader,
    load_model,
    unload_model
)
from src.pb_studio.core.task_queue import TaskQueue, TaskPriority, TaskItem
from src.pb_studio.core.thread_pool import ThreadPoolManager, Worker
from src.pb_studio.core.crash_handler import CrashHandler

__all__ = [
    # Monitoring
    "SystemMonitor",

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
