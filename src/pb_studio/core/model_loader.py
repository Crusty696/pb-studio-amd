"""
VRAM-Aware Model Loader for AMD DirectML

This module provides centralized model loading with automatic VRAM management.
All ML models should be loaded through this interface to ensure proper
resource tracking and prevent OOM errors.

DirectML Considerations:
- All sessions use enable_mem_pattern = False (MANDATORY)
- Models are loaded lazily by default
- Automatic eviction when VRAM is full
"""

import logging
import threading
import onnxruntime as ort

_model_loader_init_lock = threading.Lock()
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from pb_studio.core.vram_budget_manager import (
    ModelPriority,
    KNOWN_MODEL_BUDGETS,
    get_vram_manager
)
from pb_studio.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Supported model types."""
    ONNX = "onnx"              # Standard ONNX model
    ONNX_SPLIT = "onnx_split"  # Split encoder/decoder
    PYTORCH_CPU = "pytorch"    # PyTorch CPU-only (no DirectML)


@dataclass
class ModelSpec:
    """Specification for a loadable model."""
    model_id: str
    name: str
    model_type: ModelType
    vram_mb: int
    model_path: str           # Relative to models_dir
    priority: ModelPriority = ModelPriority.MEDIUM

    # For split models
    encoder_path: Optional[str] = None
    decoder_path: Optional[str] = None


# Pre-defined model specifications
MODEL_SPECS = {
    "moondream_fp16": ModelSpec(
        model_id="moondream_fp16",
        name="Moondream2 (FP16)",
        model_type=ModelType.ONNX_SPLIT,
        vram_mb=KNOWN_MODEL_BUDGETS["moondream_fp16"],
        model_path="moondream.onnx",
        encoder_path="moondream_encoder.onnx",
        decoder_path="moondream_decoder.onnx",
        priority=ModelPriority.HIGH
    ),
    "raft_standard": ModelSpec(
        model_id="raft_standard",
        name="RAFT Optical Flow",
        model_type=ModelType.ONNX,
        vram_mb=KNOWN_MODEL_BUDGETS["raft_standard"],
        model_path="raft.onnx",
        priority=ModelPriority.MEDIUM
    ),
    "mdx_net_inst": ModelSpec(
        model_id="mdx_net_inst",
        name="MDX-NET Instrumental",
        model_type=ModelType.ONNX,
        vram_mb=KNOWN_MODEL_BUDGETS["mdx_net_inst"],
        model_path="UVR-MDX-NET-Inst_HQ_3.onnx",
        priority=ModelPriority.MEDIUM
    ),
}


class ModelLoader:
    """
    Centralized model loader with VRAM management.

    Usage:
        loader = ModelLoader()

        # Load a model
        session = loader.load_model("moondream_fp16")

        # Use the model
        result = session.run(...)

        # Unload when done
        loader.unload_model("moondream_fp16")
    """

    _instance = None

    def __new__(cls):
        # R16: Thread-safe singleton — use lock like SystemMonitor does.
        with _model_loader_init_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.config = ConfigManager()
        self.vram_manager = get_vram_manager()

        # Model storage
        self._sessions: Dict[str, Any] = {}
        # Z3 / M-1 (CRITICAL): RLock statt Lock — load_model(force=True) ruft
        # _evict_for_space, das die session_lock erneut acquired. threading.Lock
        # ist non-reentrant → Deadlock im force-reload-Pfad. RLock erlaubt
        # mehrfaches Acquire vom selben Thread (Eviction → Load → Release).
        self._session_lock = threading.RLock()
        self._specs: Dict[str, ModelSpec] = MODEL_SPECS.copy()

        # Paths
        self._models_dir = Path(self.config.get("paths", {}).get("models_dir", "./models"))

        self._initialized = True
        logger.info(f"ModelLoader initialized. Models dir: {self._models_dir}")

    def register_model(self, spec: ModelSpec):
        """Register a custom model specification."""
        self._specs[spec.model_id] = spec
        logger.info(f"Registered model: {spec.name} ({spec.vram_mb}MB)")

    def _create_session_options(self) -> ort.SessionOptions:
        """Create DirectML-compatible session options."""
        opts = ort.SessionOptions()

        # KRITISCH: Beide Memory-Flags MÜSSEN für DirectML deaktiviert sein.
        # enable_mem_pattern=False: Pflicht für DmlExecutionProvider (Graph-Speicher
        #   wird dynamisch, nicht vorab alloziert — DirectML erfordert das).
        # enable_cpu_mem_arena=False: CPU-Arena konkurriert mit DirectML-Allocator
        #   und führt zu Instabilität / OOM. R16/IRON-RULE fix (war True — falsch).
        opts.enable_mem_pattern = False
        opts.enable_cpu_mem_arena = False

        # Optimierungen
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.intra_op_num_threads = 0  # Auto
        opts.inter_op_num_threads = 0

        return opts

    def _get_providers(self) -> list:
        """Get execution providers with DirectML priority."""
        available = ort.get_available_providers()
        providers = []

        if "DmlExecutionProvider" in available:
            providers.append("DmlExecutionProvider")

        providers.append("CPUExecutionProvider")

        return providers

    def can_load(self, model_id: str) -> bool:
        """
        Check if a model can be loaded.

        Args:
            model_id: Model identifier

        Returns:
            True if model can fit in VRAM
        """
        if model_id not in self._specs:
            logger.error(f"Unknown model: {model_id}")
            return False

        spec = self._specs[model_id]

        # Check if already loaded
        if model_id in self._sessions:
            return True

        # Register with VRAM manager if not already
        self.vram_manager.register_model(
            model_id=spec.model_id,
            name=spec.name,
            estimated_vram_mb=spec.vram_mb,
            priority=spec.priority,
            unload_callback=lambda mid=model_id: self._do_unload(mid)
        )

        return self.vram_manager.can_fit(model_id)

    def load_model(
        self,
        model_id: str,
        force: bool = False,
        priority: Optional[ModelPriority] = None
    ) -> Optional[Any]:
        """
        Load a model with VRAM management (thread-safe).

        Args:
            model_id: Model identifier
            force: If True, evict other models to make space
            priority: Override default priority

        Returns:
            ONNX InferenceSession or dict of sessions for split models
        """
        with self._session_lock:
            if model_id not in self._specs:
                logger.error(f"Unknown model: {model_id}")
                return None

            # Already loaded? (check-and-load atomar unter Lock)
            if model_id in self._sessions:
                self.vram_manager.touch_model(model_id)
                return self._sessions[model_id]

            spec = self._specs[model_id]

            # Register with VRAM manager
            self.vram_manager.register_model(
                model_id=spec.model_id,
                name=spec.name,
                estimated_vram_mb=spec.vram_mb,
                priority=priority or spec.priority,
                unload_callback=lambda mid=model_id: self._do_unload(mid)
            )

            # Reserve VRAM
            if not self.vram_manager.reserve(model_id, force=force):
                logger.error(f"Cannot reserve VRAM for {spec.name}")
                return None

            try:
                # Load based on type
                if spec.model_type == ModelType.ONNX:
                    session = self._load_onnx(spec)
                elif spec.model_type == ModelType.ONNX_SPLIT:
                    session = self._load_onnx_split(spec)
                else:
                    logger.error(f"Unsupported model type: {spec.model_type}")
                    self.vram_manager.cancel_reservation(model_id)
                    return None

                if session is None:
                    self.vram_manager.cancel_reservation(model_id)
                    return None

                # Commit VRAM
                self.vram_manager.commit(model_id)
                self._sessions[model_id] = session

                logger.info(f"Loaded model: {spec.name} (Provider: {self._get_active_provider(session)})")
                return session

            except Exception as e:
                logger.error(f"Failed to load {spec.name}: {e}")
                self.vram_manager.cancel_reservation(model_id)
                return None

    def _load_onnx(self, spec: ModelSpec) -> Optional[ort.InferenceSession]:
        """Load a standard ONNX model."""
        model_path = self._models_dir / spec.model_path

        if not model_path.exists():
            logger.error(f"Model file not found: {model_path}")
            return None

        opts = self._create_session_options()
        providers = self._get_providers()

        return ort.InferenceSession(
            str(model_path),
            opts,
            providers=providers
        )

    def _load_onnx_split(self, spec: ModelSpec) -> Optional[Dict[str, ort.InferenceSession]]:
        """Load a split encoder/decoder model."""
        # Try combined first
        combined_path = self._models_dir / spec.model_path
        if combined_path.exists():
            opts = self._create_session_options()
            providers = self._get_providers()

            return {
                "combined": ort.InferenceSession(str(combined_path), opts, providers=providers),
                "is_combined": True
            }

        # Try split
        encoder_path = self._models_dir / spec.encoder_path
        decoder_path = self._models_dir / spec.decoder_path

        if not encoder_path.exists() or not decoder_path.exists():
            logger.error(f"Split model files not found: {encoder_path}, {decoder_path}")
            return None

        opts = self._create_session_options()
        providers = self._get_providers()

        return {
            "encoder": ort.InferenceSession(str(encoder_path), opts, providers=providers),
            "decoder": ort.InferenceSession(str(decoder_path), opts, providers=providers),
            "is_combined": False
        }

    def _get_active_provider(self, session) -> str:
        """Get the active provider for a session."""
        if isinstance(session, dict):
            s = session.get("combined") or session.get("encoder")
            if s:
                return s.get_providers()[0]
        elif hasattr(session, "get_providers"):
            return session.get_providers()[0]
        return "Unknown"

    def unload_model(self, model_id: str) -> bool:
        """
        Unload a model and free VRAM.

        Args:
            model_id: Model identifier

        Returns:
            True if unloaded
        """
        return self._do_unload(model_id)

    def _do_unload(self, model_id: str) -> bool:
        """Internal unload implementation (thread-safe)."""
        with self._session_lock:
            if model_id not in self._sessions:
                return False

            # Delete session(s) — null out references so refcount drops to 0
            session = self._sessions.pop(model_id)

            if isinstance(session, dict):
                for key in list(session.keys()):
                    session[key] = None
            else:
                session = None
        # Lock released — now run gc so C++ ONNX destructor fires and VRAM is
        # actually freed before we update the budget accounting.
        import gc
        gc.collect()

        # Update VRAM budget after memory is actually released
        self.vram_manager.release(model_id)

        logger.info(f"Unloaded model: {model_id}")
        return True

    def get_session(self, model_id: str) -> Optional[Any]:
        """
        Get a loaded model session (thread-safe).

        Loads the model if not already loaded.

        Args:
            model_id: Model identifier

        Returns:
            Session or None
        """
        with self._session_lock:
            if model_id in self._sessions:
                self.vram_manager.touch_model(model_id)
                return self._sessions[model_id]

        # load_model acquires the lock itself
        return self.load_model(model_id)

    def is_loaded(self, model_id: str) -> bool:
        """Check if a model is currently loaded."""
        with self._session_lock:
            return model_id in self._sessions

    def get_stats(self) -> Dict[str, Any]:
        """Get loader statistics."""
        with self._session_lock:
            return {
                "loaded_models": list(self._sessions.keys()),
                "registered_models": list(self._specs.keys()),
                "vram_stats": self.vram_manager.get_stats()
            }

    def unload_all(self):
        """Unload all models."""
        with self._session_lock:
            for model_id in list(self._sessions.keys()):
                # _do_unload acquires lock, but we already hold it — need to call inner logic
                if model_id in self._sessions:
                    session = self._sessions.pop(model_id)
                    if isinstance(session, dict):
                        for key in list(session.keys()):
                            session[key] = None
                    self.vram_manager.release(model_id)

        logger.info("All models unloaded")


# =========================================================================
# Convenience Functions
# =========================================================================

def get_model_loader() -> ModelLoader:
    """Get the singleton ModelLoader instance."""
    return ModelLoader()


def load_model(model_id: str, force: bool = False) -> Optional[Any]:
    """
    Load a model.

    Args:
        model_id: Model identifier
        force: Evict other models if needed

    Returns:
        Model session or None
    """
    return get_model_loader().load_model(model_id, force=force)


def unload_model(model_id: str) -> bool:
    """Unload a model."""
    return get_model_loader().unload_model(model_id)


def get_session(model_id: str) -> Optional[Any]:
    """Get or load a model session."""
    return get_model_loader().get_session(model_id)
