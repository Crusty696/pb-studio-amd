"""Einfacher Profiler und Context-Manager für Performance-Messung."""

import logging
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def profile_block(name: str):
    """Context-Manager zum Profilen eines Codeblocks."""
    start = time.perf_counter()
    try:
        yield
    finally:
        dur = time.perf_counter() - start
        logger.info(f"[PROFILE] {name}: {dur:.4f}s")


class Profiler:
    """Einfache Profiler-Klasse mit benannten Timern."""

    def __init__(self):
        self.timers: dict[str, float] = {}

    def start(self, name: str) -> None:
        self.timers[name] = time.perf_counter()

    def stop(self, name: str) -> None:
        if name in self.timers:
            dur = time.perf_counter() - self.timers[name]
            logger.info(f"[PROFILE] {name}: {dur:.4f}s")
            del self.timers[name]
