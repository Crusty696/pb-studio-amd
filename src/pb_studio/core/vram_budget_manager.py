"""
VRAM Budget Manager - Central Authority for GPU Memory Management

This module provides proactive VRAM budgeting for AMD GPUs using DirectML.
Unlike reactive OOM handling, this system reserves memory BEFORE loading models.

Key Concepts:
- Budget: Pre-declared VRAM requirement for a model
- Reservation: Temporary hold on VRAM (before actual load)
- Commitment: Actual VRAM usage after model is loaded
- Eviction: Unloading models to free VRAM

DirectML Considerations:
- DirectML reports VRAM with delay (not real-time)
- Must use proactive budgeting, not reactive monitoring
- enable_mem_pattern = False is MANDATORY for all sessions
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Optional, Callable, List, Any
from collections import OrderedDict

logger = logging.getLogger(__name__)


class ModelPriority(IntEnum):
    """Model priority levels for eviction decisions."""
    CRITICAL = 1    # Never evict (e.g., currently processing)
    HIGH = 2        # User-requested, active use
    MEDIUM = 3      # Recently used, likely to be needed
    LOW = 4         # Idle, can be evicted
    BACKGROUND = 5  # Batch processing, evict first


@dataclass
class ModelBudget:
    """VRAM budget specification for a model."""
    model_id: str
    name: str
    estimated_vram_mb: int
    priority: ModelPriority = ModelPriority.MEDIUM
    is_loaded: bool = False
    is_reserved: bool = False
    last_used: float = field(default_factory=time.time)
    unload_callback: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self):
        """Update last used timestamp."""
        self.last_used = time.time()


# Pre-defined VRAM budgets for known models (AMD DirectML)
# These are conservative estimates including overhead
KNOWN_MODEL_BUDGETS = {
    # Vision-Language Models
    "moondream_fp16": 1800,      # Moondream2 FP16: ~1.5-1.8 GB
    "moondream_fp32": 3500,      # Moondream2 FP32: ~3.2-3.5 GB

    # Optical Flow
    "raft_small": 400,           # RAFT Small: ~300-400 MB
    "raft_standard": 800,        # RAFT Standard: ~600-800 MB

    # Embeddings
    "siglip_so400m": 2500,       # SigLIP SO400M: ~2.3-2.5 GB

    # Z1 / GPU-F3: Brain-Embedder (torch-directml) — vorher unsichtbar fuer
    # VRAMBudgetManager. CLAP ~600MB, SigLIP-2 (HuggingFace) ~1GB.
    "brain_clap": 600,           # CLAP (laion/larger_clap_music) torch-directml fp32
    "brain_siglip2": 1100,       # SigLIP-2 Vision-Tower torch-directml fp16

    # Combined budgets (mehrere Modelle gleichzeitig aktiv)
    "video_analysis_full": 2900, # RAFT Small + SigLIP SO400M kombiniert

    # Audio Separation (ONNX models)
    "mdx_net_inst": 600,         # MDX-NET Inst: ~500-600 MB
    "mdx_net_voc": 600,          # MDX-NET Vocal: ~500-600 MB
    "mdxc_models": 900,          # MDXC models: ~700-900 MB

    # Beat Detection
    "beatnet": 200,              # BeatNet: ~150-200 MB

    # DirectML Session Overhead
    "directml_overhead": 150,    # Base DirectML overhead per session
}


# =============================================================================
# Telemetry --- Histogram-Buckets + TelemetryEntry-Aggregat
# =============================================================================

# Latenz-Buckets (ms): jeweils "<= upper" Inklusiv-Grenze; alles darueber -> "+infms"
DURATION_BUCKETS_MS = (50, 200, 500, 1000, 2500, 5000, 10000, 30000, 60000)

# VRAM-Peak-Buckets (MB): jeweils "<= upper" Inklusiv-Grenze; alles darueber -> "+infMB"
VRAM_BUCKETS_MB = (100, 250, 500, 1000, 2000, 4000, 6000, 8000)


def _duration_bucket_label(ms: float) -> str:
    """Bucket-Label fuer Dauer-Wert (ms). Inklusiv-Obergrenze."""
    for upper in DURATION_BUCKETS_MS:
        if ms <= float(upper):
            return f"<= {upper}ms"
    return "+infms"


def _vram_bucket_label(mb: float) -> str:
    """Bucket-Label fuer VRAM-Peak (MB). Inklusiv-Obergrenze."""
    for upper in VRAM_BUCKETS_MB:
        if mb <= float(upper):
            return f"<= {upper}MB"
    return "+infMB"


def _empty_duration_histogram() -> Dict[str, int]:
    h = {f"<= {u}ms": 0 for u in DURATION_BUCKETS_MS}
    h["+infms"] = 0
    return h


def _empty_vram_histogram() -> Dict[str, int]:
    h = {f"<= {u}MB": 0 for u in VRAM_BUCKETS_MB}
    h["+infMB"] = 0
    return h


@dataclass
class TelemetryEntry:
    """Aggregierte Telemetrie pro model_id."""
    model_id: str
    count: int = 0
    success_count: int = 0
    failure_count: int = 0
    duration_min_ms: Optional[float] = None
    duration_max_ms: Optional[float] = None
    duration_sum_ms: float = 0.0
    vram_min_mb: Optional[float] = None
    vram_max_mb: Optional[float] = None
    duration_histogram: Dict[str, int] = field(default_factory=_empty_duration_histogram)
    vram_histogram: Dict[str, int] = field(default_factory=_empty_vram_histogram)
    last_error: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        avg = (self.duration_sum_ms / self.count) if self.count > 0 else None
        return {
            "model_id": self.model_id,
            "count": self.count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "duration_ms": {
                "min": self.duration_min_ms,
                "max": self.duration_max_ms,
                "avg": avg,
                "histogram": dict(self.duration_histogram),
            },
            "vram_peak_mb": {
                "min": self.vram_min_mb,
                "max": self.vram_max_mb,
                "histogram": dict(self.vram_histogram),
            },
            "last_error": self.last_error,
        }



class VRAMBudgetManager:
    """
    Central authority for GPU memory management.

    Implements a proactive budgeting system where models must:
    1. Register their VRAM requirements
    2. Request reservation before loading
    3. Commit after successful load
    4. Release when unloading

    Thread-safe for concurrent model access.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern - only one budget manager per app."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, monitor=None, max_vram_mb: Optional[int] = None):
        """
        Initialize the VRAM Budget Manager.

        Args:
            monitor: SystemMonitor instance for real VRAM readings
            max_vram_mb: Maximum VRAM to use (None = auto-detect)
        """
        if self._initialized:
            # Monitor nachtraeglich setzen wenn noch keiner vorhanden
            if monitor is not None and self.monitor is None:
                self.monitor = monitor
                logger.info("VRAMBudgetManager: Monitor nachtraeglich gesetzt")
            return

        from pb_studio.config_manager import ConfigManager

        self.config = ConfigManager()
        self.monitor = monitor

        # VRAM limits
        self._max_vram_mb = max_vram_mb or self._detect_vram_limit()
        self._safety_buffer_mb = 500  # Reserve for OS/Desktop
        self._usable_vram_mb = self._max_vram_mb - self._safety_buffer_mb

        # Model registry (ordered for LRU eviction)
        self._models: OrderedDict[str, ModelBudget] = OrderedDict()

        # Tracking
        self._reserved_mb = 0
        self._committed_mb = 0

        # Threading
        self._registry_lock = threading.RLock()

        # Telemetry --- pro model_id eine TelemetryEntry, separater Lock
        self._telemetry: Dict[str, TelemetryEntry] = {}
        self._telemetry_lock = threading.RLock()

        self._initialized = True
        logger.info(
            f"VRAMBudgetManager initialized: "
            f"Max={self._max_vram_mb}MB, Usable={self._usable_vram_mb}MB"
        )

    @classmethod
    def reset_for_testing(cls):
        """Reset the singleton instance for testing purposes."""
        with cls._lock:
            cls._instance = None

    def _detect_vram_limit(self) -> int:
        """
        Detect total VRAM using multiple methods.

        Priority:
        1. Config (if explicitly set > 0)
        2. SystemMonitor (LibreHardwareMonitor)
        3. WMI Win32_VideoController query
        4. Fallback: 8192MB
        """
        # 1. Config (nur wenn explizit gesetzt)
        config_limit = self.config.get("hardware", {}).get("vram_limit_mb", 0)
        if config_limit > 0:
            logger.info(f"Using configured VRAM limit: {config_limit}MB")
            return config_limit

        # 2. SystemMonitor (LibreHardwareMonitor)
        if self.monitor:
            try:
                stats = self.monitor.get_stats()
                total = stats.get("gpu_memory_total", 0)
                if total > 0:
                    logger.info(f"Detected VRAM from monitor: {total}MB")
                    return int(total)
            except Exception as e:
                logger.debug(f"Monitor VRAM detection failed: {e}")

        # 3. WMI Query (Windows-native GPU-Erkennung)
        try:
            import subprocess
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-CimInstance Win32_VideoController | "
                 "Where-Object { $_.AdapterRAM -gt 0 } | "
                 "Select-Object -First 1 -ExpandProperty AdapterRAM"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                adapter_ram = int(result.stdout.strip())
                # AdapterRAM ist in Bytes, konvertiere zu MB
                vram_mb = adapter_ram // (1024 * 1024)
                # WMI meldet bei >4GB GPUs manchmal nur 4GB (32-bit Limit)
                # In dem Fall ignorieren wir den Wert
                if vram_mb > 4096:
                    logger.info(f"Detected VRAM via WMI: {vram_mb}MB")
                    return vram_mb
                elif vram_mb > 0:
                    logger.debug(f"WMI reports {vram_mb}MB (possibly capped at 4GB)")
        except Exception as e:
            logger.debug(f"WMI VRAM detection failed: {e}")

        # 4. DirectX Adapter Query via dxdiag-artige Methode
        try:
            import subprocess
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance Win32_VideoController | "
                 "Where-Object { $_.Name -match 'AMD|Radeon' } | "
                 "Select-Object -First 1).AdapterRAM"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                adapter_ram = int(result.stdout.strip())
                vram_mb = adapter_ram // (1024 * 1024)
                if vram_mb > 0:
                    # Wenn 4GB gemeldet wird bei einer GPU die mehr hat,
                    # versuche den Namen zu matchen
                    logger.info(f"Detected AMD GPU VRAM via WMI: {vram_mb}MB")
                    if vram_mb <= 4096:
                        # WMI 32-bit Limit - schaetze anhand des GPU-Namens
                        name_result = subprocess.run(
                            ["powershell", "-Command",
                             "(Get-CimInstance Win32_VideoController | "
                             "Where-Object { $_.Name -match 'AMD|Radeon' } | "
                             "Select-Object -First 1).Name"],
                            capture_output=True, text=True, timeout=10
                        )
                        if name_result.returncode == 0:
                            gpu_name = name_result.stdout.strip().lower()
                            # Bekannte AMD GPU VRAM-Groessen
                            vram_by_name = {
                                "7900 xtx": 24576, "7900 xt": 20480,
                                "7900 gre": 16384, "7800 xt": 16384,
                                "7700 xt": 12288, "7600": 8192,
                                "6950 xt": 16384, "6900 xt": 16384,
                                "6800 xt": 16384, "6800": 16384,
                                "6700 xt": 12288, "6600 xt": 8192,
                            }
                            for model, vram in vram_by_name.items():
                                if model in gpu_name:
                                    logger.info(f"Matched GPU '{gpu_name}' -> {vram}MB VRAM")
                                    return vram
        except Exception as e:
            logger.debug(f"AMD GPU detection failed: {e}")

        # 5. Fallback
        logger.warning(
            "VRAM-Erkennung fehlgeschlagen! Alle Methoden (Config, Monitor, WMI, GPU-Name) "
            "konnten VRAM-Größe nicht bestimmen. Verwende konservativen Fallback von 8192MB. "
            "Empfehlung: Setze 'vram_limit_mb' in config.yaml unter 'hardware' für korrekte Werte."
        )
        return 8192

    @property
    def available_vram_mb(self) -> int:
        """Get available VRAM (usable - reserved - committed)."""
        with self._registry_lock:
            return max(0, self._usable_vram_mb - self._reserved_mb - self._committed_mb)

    @property
    def total_reserved_mb(self) -> int:
        """Get total reserved VRAM."""
        with self._registry_lock:
            return self._reserved_mb

    @property
    def total_committed_mb(self) -> int:
        """Get total committed VRAM."""
        with self._registry_lock:
            return self._committed_mb

    def get_stats(self) -> Dict[str, Any]:
        """Get current VRAM budget statistics."""
        with self._registry_lock:
            loaded_models = [m for m in self._models.values() if m.is_loaded]
            reserved_models = [m for m in self._models.values() if m.is_reserved and not m.is_loaded]

            return {
                "max_vram_mb": self._max_vram_mb,
                "usable_vram_mb": self._usable_vram_mb,
                "reserved_mb": self._reserved_mb,
                "committed_mb": self._committed_mb,
                "available_mb": self.available_vram_mb,
                "loaded_models": len(loaded_models),
                "reserved_models": len(reserved_models),
                "models": {
                    m.model_id: {
                        "name": m.name,
                        "vram_mb": m.estimated_vram_mb,
                        "is_loaded": m.is_loaded,
                        "priority": m.priority.name
                    }
                    for m in self._models.values()
                }
            }

    # =========================================================================
    # Model Registration
    # =========================================================================

    def register_model(
        self,
        model_id: str,
        name: str,
        estimated_vram_mb: int,
        priority: ModelPriority = ModelPriority.MEDIUM,
        unload_callback: Optional[Callable] = None,
        metadata: Optional[Dict] = None
    ) -> ModelBudget:
        """
        Register a model with its VRAM budget.

        Call this BEFORE attempting to load a model.

        Args:
            model_id: Unique identifier for the model
            name: Human-readable name
            estimated_vram_mb: Expected VRAM usage
            priority: Eviction priority
            unload_callback: Function to call when model must be unloaded
            metadata: Additional model info

        Returns:
            ModelBudget instance
        """
        with self._registry_lock:
            if model_id in self._models:
                logger.debug(f"Model {model_id} already registered, updating")
                budget = self._models[model_id]
                budget.priority = priority
                if unload_callback:
                    budget.unload_callback = unload_callback
                return budget

            budget = ModelBudget(
                model_id=model_id,
                name=name,
                estimated_vram_mb=estimated_vram_mb,
                priority=priority,
                unload_callback=unload_callback,
                metadata=metadata or {}
            )

            self._models[model_id] = budget
            logger.info(f"Registered model: {name} ({estimated_vram_mb}MB, {priority.name})")

            return budget

    def unregister_model(self, model_id: str) -> bool:
        """
        Remove a model from the registry.

        Will release any reservations/commitments first.

        Args:
            model_id: Model to unregister

        Returns:
            True if unregistered, False if not found
        """
        with self._registry_lock:
            if model_id not in self._models:
                return False

            budget = self._models[model_id]

            # Release resources
            if budget.is_loaded:
                self._committed_mb -= budget.estimated_vram_mb
            elif budget.is_reserved:
                self._reserved_mb -= budget.estimated_vram_mb

            del self._models[model_id]
            logger.info(f"Unregistered model: {budget.name}")

            return True

    # =========================================================================
    # Allocation Control
    # =========================================================================

    def can_fit(self, model_id: str) -> bool:
        """
        Check if a model can fit in available VRAM.

        Args:
            model_id: Registered model ID

        Returns:
            True if model can fit
        """
        with self._registry_lock:
            if model_id not in self._models:
                logger.warning(f"Model {model_id} not registered")
                return False

            budget = self._models[model_id]

            # Already loaded?
            if budget.is_loaded:
                return True

            # Already reserved?
            if budget.is_reserved:
                return True

            # Check space
            return budget.estimated_vram_mb <= self.available_vram_mb

    def reserve(self, model_id: str, force: bool = False) -> bool:
        """
        Reserve VRAM for a model (before loading).

        This is a soft reservation - actual VRAM is not used yet.
        Use this before calling model.load().

        Args:
            model_id: Registered model ID
            force: If True, evict other models to make space

        Returns:
            True if reservation successful
        """
        with self._registry_lock:
            if model_id not in self._models:
                logger.error(f"Cannot reserve: Model {model_id} not registered")
                return False

            budget = self._models[model_id]

            # Already reserved or loaded?
            if budget.is_reserved or budget.is_loaded:
                budget.touch()
                return True

            # Check space
            if budget.estimated_vram_mb > self.available_vram_mb:
                if force:
                    shortfall = budget.estimated_vram_mb - self.available_vram_mb
                    # Try eviction
                    freed = self._evict_for_space(shortfall, exclude=[model_id])
                    if freed < shortfall:
                        logger.error(
                            f"Cannot reserve {budget.name}: Need {budget.estimated_vram_mb}MB (Shortfall: {shortfall}MB), "
                            f"could only free {freed}MB"
                        )
                        return False
                else:
                    logger.warning(
                        f"Cannot reserve {budget.name}: Need {budget.estimated_vram_mb}MB, "
                        f"Available {self.available_vram_mb}MB"
                    )
                    return False

            # Reserve
            budget.is_reserved = True
            budget.touch()
            self._reserved_mb += budget.estimated_vram_mb

            # Move to end of OrderedDict (LRU tracking)
            self._models.move_to_end(model_id)

            logger.info(f"Reserved {budget.estimated_vram_mb}MB for {budget.name}")
            return True

    def commit(self, model_id: str) -> bool:
        """
        Commit a reservation (after model is loaded).

        Call this after successful model.load().
        Converts reservation to commitment.

        Args:
            model_id: Registered model ID

        Returns:
            True if commit successful
        """
        with self._registry_lock:
            if model_id not in self._models:
                logger.error(f"Cannot commit: Model {model_id} not registered")
                return False

            budget = self._models[model_id]

            # Already committed?
            if budget.is_loaded:
                budget.touch()
                return True

            # Must be reserved first
            if not budget.is_reserved:
                logger.warning(f"Committing {budget.name} without reservation (auto-reserving)")
                if not self.reserve(model_id):
                    return False

            # Convert reservation to commitment
            self._reserved_mb -= budget.estimated_vram_mb
            self._committed_mb += budget.estimated_vram_mb
            budget.is_reserved = False
            budget.is_loaded = True
            budget.touch()

            # Move to end (LRU)
            self._models.move_to_end(model_id)

            logger.info(f"Committed {budget.estimated_vram_mb}MB for {budget.name}")
            return True

    def release(self, model_id: str) -> bool:
        """
        Release VRAM when model is unloaded.

        Call this after model.unload().

        Args:
            model_id: Registered model ID

        Returns:
            True if release successful
        """
        with self._registry_lock:
            if model_id not in self._models:
                logger.warning(f"Cannot release: Model {model_id} not registered")
                return False

            budget = self._models[model_id]

            if budget.is_loaded:
                self._committed_mb -= budget.estimated_vram_mb
                budget.is_loaded = False
                logger.info(f"Released {budget.estimated_vram_mb}MB from {budget.name} (committed)")
            elif budget.is_reserved:
                self._reserved_mb -= budget.estimated_vram_mb
                budget.is_reserved = False
                logger.info(f"Released {budget.estimated_vram_mb}MB from {budget.name} (reserved)")
            else:
                logger.debug(f"Model {budget.name} has no allocation to release")
                return False

            return True

    def cancel_reservation(self, model_id: str) -> bool:
        """
        Cancel a reservation (if load failed).

        Args:
            model_id: Registered model ID

        Returns:
            True if cancellation successful
        """
        with self._registry_lock:
            if model_id not in self._models:
                return False

            budget = self._models[model_id]

            if budget.is_reserved and not budget.is_loaded:
                self._reserved_mb -= budget.estimated_vram_mb
                budget.is_reserved = False
                logger.info(f"Cancelled reservation for {budget.name}")
                return True

            return False

    # =========================================================================
    # Eviction Policy
    # =========================================================================

    def _evict_for_space(self, needed_mb: int, exclude: Optional[List[str]] = None) -> int:
        """
        Evict models to free up space.

        Uses LRU + Priority policy:
        1. Evict lowest priority first
        2. Within same priority, evict least recently used

        Args:
            needed_mb: VRAM to free
            exclude: Model IDs to never evict

        Returns:
            Amount of VRAM freed
        """
        with self._registry_lock:
            exclude = set(exclude or [])
            freed = 0

            # Sort by (priority descending, last_used ascending)
            # Higher priority number = lower importance = evict first
            candidates = [
                (m.priority, m.last_used, mid, m)
                for mid, m in self._models.items()
                if m.is_loaded and mid not in exclude and m.priority != ModelPriority.CRITICAL
            ]
            candidates.sort(key=lambda x: (-x[0], x[1]))  # Evict high number (low priority) first

            for _, _, model_id, budget in candidates:
                if freed >= needed_mb:
                    break

                logger.info(f"Evicting {budget.name} ({budget.priority.name}) to free {budget.estimated_vram_mb}MB")

                # Call unload callback
                callback_failed = False
                if budget.unload_callback:
                    try:
                        budget.unload_callback()
                    except Exception as e:
                        logger.error(f"Unload callback failed for {budget.name}: {e}")
                        callback_failed = True

                # IMMER VRAM freigeben, auch wenn Callback fehlschlägt
                self._committed_mb -= budget.estimated_vram_mb
                self._committed_mb = max(0, self._committed_mb)  # Clamp — konsistent mit evict_all
                budget.is_loaded = False
                freed += budget.estimated_vram_mb

                if callback_failed:
                    budget.metadata["eviction_error"] = True
                    logger.warning(
                        f"Model {budget.name} marked as evicted_with_error — "
                        f"VRAM budget freed but session may still be in memory"
                    )

            return freed

    def evict_all(self, min_priority: ModelPriority = ModelPriority.LOW) -> int:
        """
        Evict all models at or below a priority level.

        Args:
            min_priority: Minimum priority to evict (higher number = lower priority)

        Returns:
            Amount of VRAM freed
        """
        with self._registry_lock:
            freed = 0

            for model_id, budget in list(self._models.items()):
                if budget.is_loaded and budget.priority >= min_priority:
                    logger.info(f"Evicting {budget.name} ({budget.priority.name})")

                    try:
                        if budget.unload_callback:
                            budget.unload_callback()
                    except Exception as e:
                        logger.error(f"Unload callback failed für {model_id}: {e}")
                        budget.metadata["eviction_error"] = str(e)
                    finally:
                        # Immer Accounting aktualisieren — auch bei Fehler
                        self._committed_mb -= budget.estimated_vram_mb
                        self._committed_mb = max(0, self._committed_mb)  # nie negativ
                        budget.is_loaded = False
                        budget.metadata.setdefault("evicted", True)
                        freed += budget.estimated_vram_mb

            return freed

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def touch_model(self, model_id: str):
        """Update last-used timestamp for a model (prevents eviction)."""
        with self._registry_lock:
            if model_id in self._models:
                self._models[model_id].touch()
                self._models.move_to_end(model_id)

    def set_priority(self, model_id: str, priority: ModelPriority):
        """Change model priority."""
        with self._registry_lock:
            if model_id in self._models:
                self._models[model_id].priority = priority
                logger.debug(f"Set {model_id} priority to {priority.name}")

    def get_model(self, model_id: str) -> Optional[ModelBudget]:
        """Get model budget info (thread-safe snapshot)."""
        with self._registry_lock:
            return self._models.get(model_id)

    def is_model_loaded(self, model_id: str) -> bool:
        """Check if a model is currently loaded (thread-safe, read budget.is_loaded under lock)."""
        with self._registry_lock:
            budget = self._models.get(model_id)
            if budget is None:
                return False
            return budget.is_loaded  # read while holding lock to avoid race with evict_all

    # =========================================================================
    # Telemetry --- Beobachtungen, Histogram, Snapshot, Reset
    # =========================================================================

    def record_task_observation(
        self,
        model_id: str,
        duration_ms: float,
        vram_peak_mb: float,
        success: bool = True,
        error: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Eine GPU-Task-Beobachtung in die Telemetrie eintragen."""
        try:
            mid = (model_id or "").strip() or "_unknown"
            d = max(0.0, float(duration_ms))
            v = max(0.0, float(vram_peak_mb))

            with self._telemetry_lock:
                entry = self._telemetry.get(mid)
                if entry is None:
                    entry = TelemetryEntry(model_id=mid)
                    self._telemetry[mid] = entry

                entry.count += 1
                if success:
                    entry.success_count += 1
                else:
                    entry.failure_count += 1
                    if error is not None:
                        entry.last_error = dict(error)

                # Min/Max/Sum fuer Dauer
                if entry.duration_min_ms is None or d < entry.duration_min_ms:
                    entry.duration_min_ms = d
                if entry.duration_max_ms is None or d > entry.duration_max_ms:
                    entry.duration_max_ms = d
                entry.duration_sum_ms += d

                # Min/Max fuer VRAM-Peak
                if entry.vram_min_mb is None or v < entry.vram_min_mb:
                    entry.vram_min_mb = v
                if entry.vram_max_mb is None or v > entry.vram_max_mb:
                    entry.vram_max_mb = v

                d_label = _duration_bucket_label(d)
                v_label = _vram_bucket_label(v)
                entry.duration_histogram[d_label] = entry.duration_histogram.get(d_label, 0) + 1
                entry.vram_histogram[v_label] = entry.vram_histogram.get(v_label, 0) + 1
        except Exception as exc:  # pragma: no cover --- Telemetrie darf Task nie kippen
            logger.warning(f"record_task_observation fehlgeschlagen: {exc}")

    def get_telemetry(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Snapshot der Telemetrie. None -> alle Modelle, sonst einzelner Eintrag."""
        with self._telemetry_lock:
            if model_id is not None:
                mid = (model_id or "").strip() or "_unknown"
                entry = self._telemetry.get(mid)
                if entry is None:
                    entry = TelemetryEntry(model_id=mid)
                return entry.to_dict()

            models_snap = {mid: e.to_dict() for mid, e in self._telemetry.items()}
            total_obs = sum(e.count for e in self._telemetry.values())
            return {
                "models": models_snap,
                "summary": {
                    "models_tracked": len(self._telemetry),
                    "observations": total_obs,
                    "duration_buckets_ms": list(DURATION_BUCKETS_MS),
                    "vram_buckets_mb": list(VRAM_BUCKETS_MB),
                },
            }

    def reset_telemetry(self, model_id: Optional[str] = None) -> None:
        """Telemetrie zuruecksetzen --- entweder nur ein Modell oder komplett."""
        with self._telemetry_lock:
            if model_id is None:
                self._telemetry.clear()
            else:
                mid = (model_id or "").strip() or "_unknown"
                self._telemetry.pop(mid, None)



# =========================================================================
# Context Manager for Safe Model Loading
# =========================================================================

class VRAMContext:
    """
    Context manager for safe VRAM allocation.

    Usage:
        manager = VRAMBudgetManager()

        with VRAMContext(manager, "moondream_fp16", "Moondream2", 1800) as ctx:
            if ctx.reserved:
                model = load_model()
                ctx.commit()
            # Model is used here
        # VRAM is automatically released on exit
    """

    def __init__(
        self,
        manager: VRAMBudgetManager,
        model_id: str,
        name: str,
        estimated_vram_mb: int,
        priority: ModelPriority = ModelPriority.MEDIUM,
        force: bool = False
    ):
        self.manager = manager
        self.model_id = model_id
        self.name = name
        self.estimated_vram_mb = estimated_vram_mb
        self.priority = priority
        self.force = force
        self.reserved = False
        self.committed = False
        self._unload_fn: Optional[Callable] = None

    def set_unload_callback(self, fn: Callable):
        """Set function to call on context exit."""
        self._unload_fn = fn

    def commit(self):
        """Mark model as successfully loaded."""
        if self.reserved and not self.committed:
            self.manager.commit(self.model_id)
            self.committed = True

    def __enter__(self):
        # Register and reserve
        self.manager.register_model(
            self.model_id,
            self.name,
            self.estimated_vram_mb,
            self.priority,
            self._unload_fn
        )

        self.reserved = self.manager.reserve(self.model_id, force=self.force)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # On error: cancel reservation
        if exc_type is not None and not self.committed:
            self.manager.cancel_reservation(self.model_id)
        # On success: release is handled by explicit unload
        # (we don't auto-unload on context exit to keep model in memory)
        return False


# =========================================================================
# Global Instance Access
# =========================================================================

def get_vram_manager(monitor=None) -> VRAMBudgetManager:
    """Get the global VRAM Budget Manager instance."""
    return VRAMBudgetManager(monitor=monitor)
