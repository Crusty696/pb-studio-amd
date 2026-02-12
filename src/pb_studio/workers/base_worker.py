"""
Base Worker Class for PB Studio AMD

Provides a reusable base class for all async workers using QRunnable.
"""

from abc import abstractmethod
from typing import Any
import traceback

from PyQt6.QtCore import QRunnable

from ..core.worker_signals import WorkerSignals


class CancelledError(Exception):
    """Raised when a worker is cancelled."""
    pass


class BaseWorker(QRunnable):
    """
    Base class for all PB Studio workers.

    Provides common functionality for async task execution:
    - Signal emission (progress, status, result, error, finished)
    - Cancellation support
    - VRAM budget tracking

    Subclasses must implement _execute() method.

    Example:
        class MyWorker(BaseWorker):
            def __init__(self, data):
                super().__init__("MyWorker", vram_budget_mb=512)
                self.data = data

            def _execute(self):
                for i in range(100):
                    self._check_cancelled()
                    # Process data...
                    self.emit_progress(i + 1, f"Processing {i + 1}/100")
                return {"result": "done"}
    """

    def __init__(self, worker_name: str, vram_budget_mb: int = 0):
        """
        Initialize the base worker.

        Args:
            worker_name: Human-readable name for this worker
            vram_budget_mb: VRAM budget in MB (0 = no GPU usage)
        """
        super().__init__()

        self.worker_name = worker_name
        self.vram_budget_mb = vram_budget_mb
        self.signals = WorkerSignals()
        self._is_cancelled = False

    @property
    def is_cancelled(self) -> bool:
        """Check if the worker has been cancelled."""
        return self._is_cancelled

    def cancel(self) -> None:
        """
        Request cancellation of this worker.

        The worker will stop at the next _check_cancelled() call.
        """
        self._is_cancelled = True
        self.emit_status(f"{self.worker_name}: Cancellation requested")

    def emit_progress(self, percent: int, message: str = "") -> None:
        """
        Emit progress update.

        Args:
            percent: Progress percentage (0-100)
            message: Optional progress message
        """
        self.signals.progress.emit({
            "percent": percent,
            "message": message,
            "worker": self.worker_name
        })

    def emit_status(self, message: str) -> None:
        """
        Emit status message.

        Args:
            message: Status message to emit
        """
        self.signals.status.emit(message)

    def emit_result(self, data: Any) -> None:
        """
        Emit result data.

        Args:
            data: Result data to emit
        """
        self.signals.result.emit(data)

    def emit_error(self, exception: Exception) -> None:
        """
        Emit error information.

        Args:
            exception: The exception that occurred
        """
        exc_type = type(exception)
        exc_value = exception
        exc_tb = traceback.format_exc()
        self.signals.error.emit((exc_type, exc_value, exc_tb))

    def _check_cancelled(self) -> None:
        """
        Check if cancellation was requested and raise if so.

        Call this periodically in _execute() to support cancellation.

        Raises:
            CancelledError: If cancel() was called
        """
        if self._is_cancelled:
            raise CancelledError(f"{self.worker_name} was cancelled")

    def run(self) -> None:
        """
        Main entry point called by QThreadPool.

        Do not override this method. Implement _execute() instead.
        """
        try:
            self.emit_status(f"{self.worker_name}: Starting")
            result = self._execute()

            if not self._is_cancelled:
                self.emit_result(result)
                self.emit_status(f"{self.worker_name}: Completed")

        except CancelledError:
            self.emit_status(f"{self.worker_name}: Cancelled")

        except Exception as e:
            self.emit_error(e)
            self.emit_status(f"{self.worker_name}: Failed - {str(e)}")

        finally:
            self.signals.finished.emit()

    @abstractmethod
    def _execute(self) -> Any:
        """
        Execute the worker's main task.

        Subclasses must implement this method.

        Returns:
            Result data to be emitted via emit_result()

        Raises:
            CancelledError: If _check_cancelled() detects cancellation
            Exception: Any exception will be caught and emitted via emit_error()
        """
        raise NotImplementedError("Subclasses must implement _execute()")
