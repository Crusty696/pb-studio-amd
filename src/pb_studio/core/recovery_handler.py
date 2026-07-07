"""Error Recovery - Graceful restart after crashes"""

import logging
import traceback

from pb_studio.core.vram_arbiter import VRAMArbiter
from pb_studio.core.system_monitor import SystemMonitor

logger = logging.getLogger(__name__)

class RecoveryHandler:
    """
    Handles global errors like Out of Memory (OOM) and Worker thread crashes.
    Attempts to free resources and recover the system state.
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls) -> 'RecoveryHandler':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.monitor = SystemMonitor()
        self.arbiter = VRAMArbiter(self.monitor)

    def handle_oom_error(self, exception: Exception) -> bool:
        """
        Try to recover from OOM by freeing VRAM and RAM.
        
        Returns:
            True if recovery was attempted and resources freed.
        """
        logger.warning(f"OOM/Memory Error detected: {exception}")

        try:
            # Step 1: Identify memory hog & unload idle models
            logger.info("Unloading idle models from VRAMBudgetManager...")
            # We evict all models with LOW priority (or higher numbers)
            from pb_studio.core.vram_budget_manager import ModelPriority
            freed_vram = self.arbiter.budget_manager.evict_all(min_priority=ModelPriority.MEDIUM)
            logger.info(f"Freed {freed_vram}MB of VRAM during OOM recovery.")

            # Step 2: Run Python Garbage Collection
            # AP5.1 (Audit 2026-06-10): torch.cuda-Block entfernt (IRON RULE 1:
            # AMD DirectML only — cuda.empty_cache war auf Ziel-Hardware wirkungslos).
            # Toter Import pb_studio.data.global_cache entfernt (Modul existiert nicht).
            # DirectML-VRAM wird bereits in Step 1 über evict_all physisch freigegeben;
            # gc.collect() löst die letzten Session-Referenzen auf.
            import gc
            gc.collect()

            logger.info("OOM Recovery completed. Ready for retry.")
            return True
        except Exception as e:
            logger.error(f"OOM Recovery failed: {e}")
            logger.error(traceback.format_exc())
            return False

    def handle_worker_crash(self, exception: Exception, worker_name: str) -> None:
        """
        Handle worker thread crashes. Log the stack trace and inform the system.
        """
        logger.error(f"Worker '{worker_name}' crashed: {type(exception).__name__}: {exception}")
        logger.error(traceback.format_exc())

        # Check if it looks like an OOM error
        err_str = str(exception).lower()
        if "out of memory" in err_str or "oom" in err_str or "memoryerror" in err_str or "alloc" in err_str:
            self.handle_oom_error(exception)
            
        # The Orchestrator or UI will handle the state update via SSE.
