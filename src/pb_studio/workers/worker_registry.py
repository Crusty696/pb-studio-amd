"""
Worker Registry for PB Studio AMD

Singleton registry for managing worker classes and their VRAM budgets.
"""

import logging
import threading
from typing import Dict, Type, List

from .base_worker import BaseWorker

logger = logging.getLogger(__name__)

class WorkerRegistry:
    """
    Registry for worker classes and their VRAM requirements.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(WorkerRegistry, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the registry (only once)."""
        if self._initialized:
            return
            
        self._workers: Dict[str, Type[BaseWorker]] = {}
        self._vram_budgets: Dict[str, int] = {}
        self._initialized = True
        self._lock = threading.Lock() # Instance lock for operations

    def register_worker(
        self,
        name: str,
        worker_class: Type[BaseWorker],
        vram_budget: int = 0
    ) -> None:
        """
        Register a worker class.

        Args:
            name: Unique name for this worker type
            worker_class: The worker class (must be subclass of BaseWorker)
            vram_budget: Default VRAM budget in MB (0 = no GPU usage)

        Raises:
            TypeError: If worker_class is not a subclass of BaseWorker
            ValueError: If name is already registered
        """
        if not isinstance(worker_class, type) or not issubclass(worker_class, BaseWorker):
            raise TypeError(
                f"worker_class must be a subclass of BaseWorker, got {type(worker_class)}"
            )

        with self._lock:
            if name in self._workers:
                raise ValueError(f"Worker '{name}' is already registered")

            self._workers[name] = worker_class
            self._vram_budgets[name] = vram_budget
            logger.debug(f"Worker registered: {name} (VRAM: {vram_budget}MB)")

    def get_worker(self, name: str) -> Type[BaseWorker]:
        """
        Get a registered worker class by name.

        Args:
            name: Name of the registered worker

        Returns:
            The worker class

        Raises:
            KeyError: If no worker is registered with that name
        """
        with self._lock:
            if name not in self._workers:
                available = ", ".join(self._workers.keys()) or "(none)"
                raise KeyError(
                    f"No worker registered with name '{name}'. Available: {available}"
                )

            return self._workers[name]

    def get_vram_budget(self, name: str) -> int:
        """
        Get the VRAM budget for a registered worker.

        Args:
            name: Name of the registered worker

        Returns:
            The VRAM budget in MB
        """
        with self._lock:
            return self._vram_budgets.get(name, 0)

    def list_workers(self) -> List[str]:
        """
        List all registered worker names.

        Returns:
            List of worker names
        """
        with self._lock:
            return list(self._workers.keys())

    def is_registered(self, name: str) -> bool:
        """
        Check if a worker is registered.

        Args:
            name: Name to check

        Returns:
            True if registered, False otherwise
        """
        with self._lock:
            return name in self._workers

    def unregister_worker(self, name: str) -> None:
        """
        Unregister a worker.

        Args:
            name: Name of the worker to unregister

        Raises:
            KeyError: If no worker is registered with that name
        """
        with self._lock:
            if name not in self._workers:
                raise KeyError(f"No worker registered with name '{name}'")

            del self._workers[name]
            del self._vram_budgets[name]

    def clear(self) -> None:
        """Remove all registered workers (mainly for testing)."""
        with self._lock:
            self._workers.clear()
            self._vram_budgets.clear()
