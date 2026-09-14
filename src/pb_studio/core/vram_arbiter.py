"""
VRAM Arbiter - Legacy Interface with Budget Manager Integration

This module provides backward-compatible VRAM allocation checking.
Now integrated with VRAMBudgetManager for proper tracking.

DEPRECATED: New code should use VRAMBudgetManager directly.
This class is kept for compatibility with existing code.

LEGACY — kein Produktionsaufrufer (Zustandsaufnahme 2026-08-30, E-3).

Null Produktionsaufrufer; `vram_budget_manager.py:364` haelt das im Kommentar
bereits fest. Die weiter unten beschriebene Dual-Verification laeuft im
heutigen Betrieb NICHT: die Buchfuehrung macht `VRAMBudgetManager`, die
Messung der im Lifespan verdrahtete Sensor.

Bewacht von `Tests/test_legacy_symbols_have_no_production_callers.py`.
"""

import logging
from typing import Optional
from pb_studio.core.system_monitor import SystemMonitor
from pb_studio.core.directml_adapter import get_directml_adapter
from pb_studio.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class VRAMArbiter:
    """
    Traffic Cop for GPU Memory.
    Prevents OOM by denying resource requests if VRAM is too full.

    UPGRADED: Now integrates with VRAMBudgetManager for proper tracking.
    The reserved_mb field is now synchronized with the central manager.
    """

    def __init__(self, monitor: SystemMonitor):
        self.monitor = monitor
        self.config = ConfigManager()
        self.adapter = get_directml_adapter()

        # Safety buffer: Don't let apps use 100% of VRAM. Leave 500MB for OS/Desktop.
        self.safety_buffer = 500

        # Connect to Budget Manager (lazy init to avoid circular imports)
        self._budget_manager = None
        self.max_vram = self.budget_manager.get_stats()["max_vram_mb"]

    @property
    def budget_manager(self):
        """Lazy-load the budget manager to avoid circular imports."""
        if self._budget_manager is None:
            from pb_studio.core.vram_budget_manager import get_vram_manager
            self._budget_manager = get_vram_manager(monitor=self.monitor)
        return self._budget_manager

    @property
    def reserved_mb(self) -> int:
        """Get total reserved VRAM from budget manager."""
        return self.budget_manager.total_reserved_mb + self.budget_manager.total_committed_mb

    def can_allocate(self, required_mb: int, model_id: Optional[str] = None) -> bool:
        """
        Check if we can safely fit 'required_mb' into VRAM.

        Uses dual-verification:
        1. Check Budget Manager's internal tracking (proactive)
        2. Check actual VRAM from LHM sensor (reactive, if available)

        Args:
            required_mb: VRAM needed in MB
            model_id: Optional model ID for budget-aware checking

        Returns:
            True if allocation is safe
        """
        # Method 1: Budget Manager Check (proactive)
        if model_id:
            budget_ok = self.budget_manager.can_fit(model_id)
        else:
            budget_ok = self.budget_manager.available_vram_mb >= required_mb

        # Method 2: LHM Sensor Check (reactive, if reliable)
        current_stats = self.monitor.get_stats(force_refresh=True)
        used_real = current_stats.get("gpu_memory_used", 0)
        total_phys = current_stats.get("gpu_memory_total", 0)

        sensor_matches = (
            current_stats.get("adapter_luid") == self.adapter.luid
            and current_stats.get("monitoring_status") == "ready"
        )
        if total_phys > 0 and sensor_matches:
            # LHM is reporting - use real data as additional check
            # BUG-082 FIX: available_real is already total - used. 
            # We check if (free_vram - buffer) is enough for the request.
            free_vram = total_phys - used_real
            available_real = free_vram - self.safety_buffer
            sensor_ok = available_real >= required_mb

            # Log discrepancy if budget and sensor disagree significantly
            budget_available = self.budget_manager.available_vram_mb
            if abs(available_real - budget_available) > 500:
                logger.warning(
                    f"VRAM tracking discrepancy: Budget={budget_available}MB, "
                    f"Sensor={available_real}MB (diff={abs(available_real - budget_available)}MB)"
                )

            # Conservative: both must agree
            can_alloc = budget_ok and sensor_ok

        else:
            # LHM not reliable - trust budget manager only
            can_alloc = budget_ok

        if not can_alloc:
            logger.warning(
                f"VRAM DENIED: Need {required_mb}MB, "
                f"Budget Available={self.budget_manager.available_vram_mb}MB, "
                f"Real Used={used_real}MB"
            )

        return can_alloc

    def reserve(self, amount_mb: int, model_id: Optional[str] = None) -> bool:
        """
        Reserve VRAM for a pending allocation.

        UPGRADED: Now registers with Budget Manager if model_id provided.

        Args:
            amount_mb: VRAM to reserve in MB
            model_id: Optional model identifier for tracking

        Returns:
            True if reservation successful
        """
        if model_id:
            # Use Budget Manager
            self.budget_manager.register_model(
                model_id=model_id,
                name=model_id,
                estimated_vram_mb=amount_mb
            )
            success = self.budget_manager.reserve(model_id)
            if success:
                logger.info(f"VRAM Reserved via BudgetManager: {model_id} ({amount_mb}MB)")
            return success
        else:
            # Legacy anonymous reservation - not recommended
            logger.warning("Anonymous VRAM reservation (no model_id) - tracking may be inaccurate")
            return self.can_allocate(amount_mb)

    def commit(self, model_id: str) -> bool:
        """
        Commit a reservation after model is loaded.

        Args:
            model_id: Model identifier

        Returns:
            True if commit successful
        """
        success = self.budget_manager.commit(model_id)
        if success:
            logger.info(f"VRAM Committed: {model_id}")
        return success

    def release(self, amount_mb: int = 0, model_id: Optional[str] = None) -> bool:
        """
        Release reserved or committed VRAM.

        Args:
            amount_mb: VRAM to release (ignored if model_id provided)
            model_id: Model identifier (preferred)

        Returns:
            True if release successful
        """
        if model_id:
            success = self.budget_manager.release(model_id)
            if success:
                logger.info(f"VRAM Released via BudgetManager: {model_id}")
            return success
        else:
            # Legacy - can't do much without model_id
            logger.warning("Anonymous VRAM release (no model_id) - tracking may be inaccurate")
            return True

    def get_stats(self) -> dict:
        """Get combined VRAM statistics."""
        budget_stats = self.budget_manager.get_stats()
        sensor_stats = self.monitor.get_stats()

        return {
            "adapter_index": self.adapter.device_id,
            "adapter_luid": self.adapter.luid,
            "adapter_name": self.adapter.name,
            # Budget Manager data
            "budget_max_mb": budget_stats["max_vram_mb"],
            "budget_usable_mb": budget_stats["usable_vram_mb"],
            "budget_reserved_mb": budget_stats["reserved_mb"],
            "budget_committed_mb": budget_stats["committed_mb"],
            "budget_available_mb": budget_stats["available_mb"],
            "loaded_models": budget_stats["loaded_models"],

            # Sensor data
            "sensor_used_mb": sensor_stats.get("gpu_memory_used", 0),
            "sensor_total_mb": sensor_stats.get("gpu_memory_total", 0),
            "gpu_load_percent": sensor_stats.get("gpu_load", 0),
            "gpu_temp_c": sensor_stats.get("gpu_temp", 0),

            # Model details
            "models": budget_stats["models"]
        }

    def allocate_with_eviction(self, required_mb: int, model_id: str, priority=None) -> bool:
        """
        Try to allocate VRAM. If not enough:
        1. Find evictable models
        2. Unload them
        3. Retry allocation
        """
        from pb_studio.core.vram_budget_manager import ModelPriority
        if priority is None:
            priority = ModelPriority.MEDIUM

        # Register the model first so the budget manager is aware of it
        self.budget_manager.register_model(
            model_id=model_id,
            name=model_id,
            estimated_vram_mb=required_mb,
            priority=priority
        )

        logger.info(f"Attempting VRAM reservation for {model_id} ({required_mb}MB)...")
        
        # Use reserve with force=True which handles eviction safely under lock
        success = self.budget_manager.reserve(model_id, force=True)
        if success:
            logger.info(f"VRAM Reserved successfully for {model_id} ({required_mb}MB).")
            return True
        else:
            logger.error(f"Could not reserve {required_mb}MB for {model_id} even after eviction attempt.")
            return False

    def evict_if_needed(self, required_mb: int, exclude_models: Optional[list] = None) -> bool:
        """
        Evict models to free space if needed.

        Args:
            required_mb: VRAM needed
            exclude_models: Model IDs to never evict

        Returns:
            True if space is available (with or without eviction)
        """
        if self.budget_manager.available_vram_mb >= required_mb:
            return True

        # Try to evict
        freed_mb, callbacks = self.budget_manager._evict_for_space(required_mb, exclude=exclude_models)
        
        # K11: Unload callbacks ausführen, um Modelle physisch zu entladen
        for name, callback, budget in callbacks:
            try:
                logger.info(f"Triggering unload callback for evicted model: {name}")
                callback()
            except Exception as e:
                logger.error(f"Error executing unload callback for evicted model {name}: {e}", exc_info=True)
                budget.metadata["eviction_error"] = True

        return freed_mb >= required_mb
