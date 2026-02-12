"""
Worker Registry for PB Studio AMD

Singleton registry for managing worker types and their VRAM budgets.
"""

from typing import Dict, List, Optional, Type
import threading

from .base_worker import BaseWorker


class WorkerRegistry:
    """
    Singleton registry for worker classes.

    Allows registration and retrieval of worker classes by name,
    along with their associated VRAM budgets.

    Example:
        # Register a worker
        registry = WorkerRegistry()
        registry.register_worker("stem_separator", StemSeparatorWorker, vram_budget=2048)

        # Get and instantiate a worker
        worker_class = registry.get_worker("stem_separator")
        worker = worker_class(audio_file="song.mp3")

        # Check VRAM budget before running
        vram_needed = registry.get_vram_budget("stem_separator")
        if vram_arbiter.can_allocate(vram_needed):
            thread_pool.start(worker)
    """

    _instance: Optional['WorkerRegistry'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'WorkerRegistry':
        """Ensure singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                # Double-check locking
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the registry (only once)."""
        if self._initialized:
            return

        self._workers: Dict[str, Type[BaseWorker]] = {}
        self._vram_budgets: Dict[str, int] = {}
        self._initialized = True

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

        if name in self._workers:
            raise ValueError(f"Worker '{name}' is already registered")

        self._workers[name] = worker_class
        self._vram_budgets[name] = vram_budget

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
            VRAM budget in MB

        Raises:
            KeyError: If no worker is registered with that name
        """
        if name not in self._vram_budgets:
            raise KeyError(f"No worker registered with name '{name}'")

        return self._vram_budgets[name]

    def list_workers(self) -> List[str]:
        """
        List all registered worker names.

        Returns:
            List of registered worker names (sorted alphabetically)
        """
        return sorted(self._workers.keys())

    def is_registered(self, name: str) -> bool:
        """
        Check if a worker is registered.

        Args:
            name: Name to check

        Returns:
            True if registered, False otherwise
        """
        return name in self._workers

    def unregister_worker(self, name: str) -> None:
        """
        Unregister a worker.

        Args:
            name: Name of the worker to unregister

        Raises:
            KeyError: If no worker is registered with that name
        """
        if name not in self._workers:
            raise KeyError(f"No worker registered with name '{name}'")

        del self._workers[name]
        del self._vram_budgets[name]

    def clear(self) -> None:
        """Remove all registered workers (mainly for testing)."""
        self._workers.clear()
        self._vram_budgets.clear()
