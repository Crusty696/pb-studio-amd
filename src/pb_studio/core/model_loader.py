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
import weakref
# pyrefly: ignore [missing-import]
import onnxruntime as ort

_model_loader_init_lock = threading.Lock()
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from pb_studio.core.vram_budget_manager import (
    ModelPriority,
    KNOWN_MODEL_BUDGETS,
    get_vram_manager
)
from pb_studio.core.directml_adapter import (
    configure_directml_session_options,
    enforce_directml_session,
    get_directml_provider,
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
    "siglip_vision": ModelSpec(
        model_id="siglip_vision",
        name="SigLIP Vision Encoder",
        model_type=ModelType.ONNX,
        vram_mb=2000,
        model_path="siglip_vision.onnx",
        priority=ModelPriority.MEDIUM
    ),
    "siglip_text": ModelSpec(
        model_id="siglip_text",
        name="SigLIP Text Encoder",
        model_type=ModelType.ONNX,
        vram_mb=500,
        model_path="siglip_text.onnx",
        priority=ModelPriority.MEDIUM
    ),
    "clap_audio": ModelSpec(
        model_id="clap_audio",
        name="CLAP Audio Encoder",
        model_type=ModelType.ONNX,
        vram_mb=400,
        model_path="clap_audio_encoder.onnx",
        priority=ModelPriority.MEDIUM
    ),
    "clap_text": ModelSpec(
        model_id="clap_text",
        name="CLAP Text Encoder",
        model_type=ModelType.ONNX,
        vram_mb=200,
        model_path="clap_text_encoder.onnx",
        priority=ModelPriority.MEDIUM
    ),
    "clap_combined": ModelSpec(
        model_id="clap_combined",
        name="CLAP Combined Encoder",
        model_type=ModelType.ONNX,
        vram_mb=600,
        model_path="clap_combined.onnx",
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
        self._session_owner_callbacks: Dict[
            str,
            list[weakref.WeakMethod],
        ] = {}
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

    def register_session_owner(
        self,
        model_id: str,
        release_callback: Callable[[str], None],
    ) -> None:
        """Register a weak owner callback cleared before a session is evicted."""
        callback_ref = weakref.WeakMethod(release_callback)
        with self._session_lock:
            callbacks = self._session_owner_callbacks.setdefault(model_id, [])
            callbacks[:] = [ref for ref in callbacks if ref() is not None]
            if any(ref() == release_callback for ref in callbacks):
                return
            callbacks.append(callback_ref)

    def _notify_session_owners(self, model_id: str) -> None:
        with self._session_lock:
            callback_refs = list(
                getattr(self, "_session_owner_callbacks", {}).get(model_id, [])
            )
        live_refs: list[weakref.WeakMethod] = []
        for callback_ref in callback_refs:
            callback = callback_ref()
            if callback is None:
                continue
            live_refs.append(callback_ref)
            try:
                callback(model_id)
            except Exception:
                logger.exception("Session-Owner konnte %s nicht freigeben", model_id)
        with self._session_lock:
            if hasattr(self, "_session_owner_callbacks"):
                self._session_owner_callbacks[model_id] = live_refs

    def _create_session_options(self) -> ort.SessionOptions:
        """Create DirectML-compatible session options."""
        opts = configure_directml_session_options(ort.SessionOptions())

        # KRITISCH: Beide Memory-Flags MÜSSEN für DirectML deaktiviert sein.
        # enable_mem_pattern=False: Pflicht für DmlExecutionProvider (Graph-Speicher
        #   wird dynamisch, nicht vorab alloziert — DirectML erfordert das).
        # enable_cpu_mem_arena=False: CPU-Arena konkurriert mit DirectML-Allocator
        #   und führt zu Instabilität / OOM. R16/IRON-RULE fix (war True — falsch).
        # Optimierungen
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.intra_op_num_threads = 0  # Auto
        opts.inter_op_num_threads = 0

        return opts

    def _get_providers(self) -> list:
        """Return the mandatory DirectML execution provider."""
        available = ort.get_available_providers()
        if "DmlExecutionProvider" not in available:
            raise RuntimeError(
                "DmlExecutionProvider is unavailable; CPU ONNX fallback is disabled"
            )

        return [get_directml_provider()]

    @staticmethod
    def _create_onnx_session(
        model_path: Path,
        options: ort.SessionOptions,
        providers: list,
    ) -> ort.InferenceSession:
        return enforce_directml_session(
            ort.InferenceSession(
                str(model_path),
                options,
                providers=providers,
            )
        )

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
        if model_id not in self._specs:
            logger.error(f"Unknown model: {model_id}")
            return None

        spec = self._specs[model_id]

        # 1. Register with VRAM manager (safe without _session_lock)
        self.vram_manager.register_model(
            model_id=spec.model_id,
            name=spec.name,
            estimated_vram_mb=spec.vram_mb,
            priority=priority or spec.priority,
            unload_callback=lambda mid=model_id: self._do_unload(mid)
        )

        # Fast path check: if already loaded, touch and return
        with self._session_lock:
            if model_id in self._sessions:
                self.vram_manager.touch_model(model_id)
                return self._sessions[model_id]

        # 2. Reserve VRAM OUTSIDE of _session_lock
        # This completely avoids circular deadlock since evictions (which need _session_lock)
        # can run without being blocked by this thread holding _session_lock!
        if not self.vram_manager.reserve(model_id, force=force):
            logger.error(f"Cannot reserve VRAM for {spec.name}")
            return None

        # 3. Now acquire _session_lock to actually load the model
        with self._session_lock:
            # Check again inside the lock in case another thread loaded it in the meantime
            if model_id in self._sessions:
                self.vram_manager.commit(model_id)
                return self._sessions[model_id]

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

                # Publish the session only after the reservation was committed.
                if not self.vram_manager.commit(model_id):
                    logger.error(f"VRAM commit failed after loading {spec.name}")
                    session = None
                    import gc
                    gc.collect()
                    self.vram_manager.cancel_reservation(model_id)
                    return None
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

        return self._create_onnx_session(model_path, opts, providers)

    def _load_onnx_split(self, spec: ModelSpec) -> Optional[Dict[str, ort.InferenceSession]]:
        """Load a split encoder/decoder model."""
        # Try combined first
        combined_path = self._models_dir / spec.model_path
        if combined_path.exists():
            opts = self._create_session_options()
            providers = self._get_providers()

            return {
                "combined": self._create_onnx_session(
                    combined_path,
                    opts,
                    providers,
                ),
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
            "encoder": self._create_onnx_session(
                encoder_path,
                opts,
                providers,
            ),
            "decoder": self._create_onnx_session(
                decoder_path,
                opts,
                providers,
            ),
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
        self._notify_session_owners(model_id)
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

        # Update VRAM budget after memory is actually released.
        if not self.vram_manager.release(model_id):
            logger.error(f"VRAM release confirmation failed for model: {model_id}")
            return False

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

    def unload_all(self) -> bool:
        """Unload all models and confirm every budget release."""
        unloaded_ids = []
        with self._session_lock:
            loaded_ids = list(self._sessions.keys())
        for model_id in loaded_ids:
            self._notify_session_owners(model_id)
        with self._session_lock:
            for model_id in list(self._sessions.keys()):
                if model_id in self._sessions:
                    session = self._sessions.pop(model_id)
                    if isinstance(session, dict):
                        for key in list(session.keys()):
                            session[key] = None
                    session = None
                    unloaded_ids.append(model_id)

        import gc
        gc.collect()

        released_all = True
        for model_id in unloaded_ids:
            if not self.vram_manager.release(model_id):
                released_all = False
                logger.error(f"VRAM release confirmation failed for model: {model_id}")

        if released_all:
            logger.info("All models unloaded")
        return released_all


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
