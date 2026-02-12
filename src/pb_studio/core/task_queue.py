import queue
import logging
from enum import IntEnum, auto
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

class TaskPriority(IntEnum):
    HIGH = 1   # UI interactions, immediate feedback
    MEDIUM = 2 # Audio processing, standard tasks
    LOW = 3    # Batch video rendering, background indexing

@dataclass(order=True)
class TaskItem:
    priority: int
    fn: Callable = field(compare=False)
    args: tuple = field(default=(), compare=False)
    kwargs: dict = field(default_factory=dict, compare=False)
    name: str = field(default="UnknownTask", compare=False)

class TaskQueue:
    def __init__(self):
        self._queue = queue.PriorityQueue()
        logger.info("TaskQueue initialized.")

    def add(self, fn, priority=TaskPriority.MEDIUM, name="Task", *args, **kwargs):
        """Add a task to the queue."""
        item = TaskItem(priority=priority, fn=fn, args=args, kwargs=kwargs, name=name)
        self._queue.put(item)
        logger.debug(f"Task added: {name} (Priority: {priority.name})")

    def get(self) -> TaskItem:
        """Get the next highest priority task."""
        return self._queue.get()

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.qsize()
