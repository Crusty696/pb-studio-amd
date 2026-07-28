"""
Stem Separator for AMD GPUs (DirectML Patched)

The standard audio-separator library only auto-detects CUDA (NVIDIA) or MPS (Apple).
This wrapper forces DirectML usage for ONNX Runtime, enabling AMD GPU acceleration.
"""
import importlib.util
import logging
import os
import sys
import threading
import types
from pathlib import Path

try:
    import onnxruntime as ort
except ImportError:  # pragma: no cover - optional dependency in test envs
    class _FallbackSessionOptions:
        def __init__(self):
            self.enable_mem_pattern = False

    class _FallbackOrt:
        SessionOptions = _FallbackSessionOptions

        @staticmethod
        def get_available_providers():
            return ["CPUExecutionProvider"]

    ort = _FallbackOrt()

import torch

from pb_studio.config_manager import ConfigManager

logger = logging.getLogger(__name__)

from pb_studio.core.gpu_lock import gpu_inference_lock

_directml_session_options_patch_lock = threading.RLock()


def _box_iou(box: torch.Tensor, boxes: torch.Tensor) -> torch.Tensor:
    """Compute IoU for NMS in the lightweight torchvision fallback."""
    x1 = torch.maximum(box[0], boxes[:, 0])
    y1 = torch.maximum(box[1], boxes[:, 1])
    x2 = torch.minimum(box[2], boxes[:, 2])
    y2 = torch.minimum(box[3], boxes[:, 3])

    inter_w = torch.clamp(x2 - x1, min=0)
    inter_h = torch.clamp(y2 - y1, min=0)
    inter = inter_w * inter_h

    area_box = torch.clamp(box[2] - box[0], min=0) * torch.clamp(box[3] - box[1], min=0)
    area_boxes = torch.clamp(boxes[:, 2] - boxes[:, 0], min=0) * torch.clamp(boxes[:, 3] - boxes[:, 1], min=0)
    union = area_box + area_boxes - inter

    return torch.where(union > 0, inter / union, torch.zeros_like(union))


def _ensure_torchvision_stub() -> bool:
    """
    Provide a tiny runtime stub for `torchvision.ops` when torchvision is absent.

    audio-separator's ONNX->Torch path imports `onnx2torch`, which imports
    `torchvision.ops` unconditionally even for MDX models that do not use these ops.
    """
    if importlib.util.find_spec("torchvision") is not None:
        return False
    if "torchvision" in sys.modules:
        return False

    ops_module = types.ModuleType("torchvision.ops")

    def box_convert(boxes: torch.Tensor, in_fmt: str, out_fmt: str) -> torch.Tensor:
        if in_fmt == out_fmt:
            return boxes
        if in_fmt == "cxcywh" and out_fmt == "xyxy":
            cx, cy, w, h = boxes.unbind(dim=-1)
            return torch.stack((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), dim=-1)
        if in_fmt == "xyxy" and out_fmt == "cxcywh":
            x1, y1, x2, y2 = boxes.unbind(dim=-1)
            return torch.stack(((x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1), dim=-1)
        raise NotImplementedError(f"torchvision fallback does not support box_convert {in_fmt}->{out_fmt}")

    def nms(boxes: torch.Tensor, scores: torch.Tensor, iou_threshold: float) -> torch.Tensor:
        if boxes.numel() == 0:
            return torch.empty((0,), dtype=torch.long, device=boxes.device)

        order = torch.argsort(scores, descending=True)
        keep = []

        while order.numel() > 0:
            current = order[0]
            keep.append(current)
            if order.numel() == 1:
                break
            remaining = order[1:]
            ious = _box_iou(boxes[current], boxes[remaining])
            order = remaining[ious <= iou_threshold]

        return torch.stack(keep) if keep else torch.empty((0,), dtype=torch.long, device=boxes.device)

    def roi_align(*args, **kwargs):
        raise NotImplementedError("torchvision fallback does not implement roi_align")

    ops_module.box_convert = box_convert
    ops_module.nms = nms
    ops_module.roi_align = roi_align

    tv_module = types.ModuleType("torchvision")
    tv_module.ops = ops_module

    sys.modules["torchvision"] = tv_module
    sys.modules["torchvision.ops"] = ops_module
    logger.warning("torchvision not installed; using minimal fallback for onnx2torch imports")
    return True

def _get_vram_model_id(model_name: str) -> str:
    """Determine the VRAM model budget ID based on filename."""
    name_lower = model_name.lower()
    if "mdxc" in name_lower or "demucs" in name_lower:
        return "mdxc_models"
    elif "voc" in name_lower:
        return "mdx_net_voc"
    else:
        return "mdx_net_inst"


class StemSeparator:
    def __init__(self):
        self.config = ConfigManager()
        self.separator = None
        self._init_engine()

    def _init_engine(self):
        try:
            self._using_torchvision_stub = _ensure_torchvision_stub()
            from audio_separator.separator import Separator
            
            # Get config paths
            model_dir = self.config.get("paths", {}).get("models_dir", "./models")
            output_dir = self.config.get("paths", {}).get("temp_dir", "./temp")
            
            # Create dirs if needed
            os.makedirs(model_dir, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)
            
            # Initialize Separator
            self.separator = Separator(
                model_file_dir=model_dir,
                output_dir=output_dir,
                output_format="WAV"
            )
            
            # === AMD DirectML PATCH ===
            # Override the ONNX execution provider AFTER init
            # This forces DirectML usage for ONNX-based models (MDX, MDXC)
            available_providers = ort.get_available_providers()

            if "DmlExecutionProvider" in available_providers:
                logger.info("AMD DirectML detected. Patching audio-separator for GPU acceleration.")
                self.separator.onnx_execution_provider = ["DmlExecutionProvider"]
                logger.info(f"ONNX Provider set to: {self.separator.onnx_execution_provider}")

                # SessionOptions Patch wird nur während separate() aktiv gehalten
                # (siehe _apply_directml_patch / _restore_directml_patch)
                self._has_directml = True
            else:
                logger.warning(
                    "DirectML not available. ONNX stem models are disabled; "
                    "the intentional PyTorch CPU path for Demucs remains available."
                )
                self._has_directml = False
            # === END PATCH ===
            
            logger.info("StemSeparator initialized (DirectML Patched).")
            
        except ImportError as e:
            logger.error(f"AudioSeparator import failed: {e}")
            self.separator = None
        except Exception as e:
            logger.error(f"StemSeparator init error: {e}")
            self.separator = None

    def _apply_directml_patch(self):
        """Apply SessionOptions monkey-patch for DirectML (scoped)."""
        if not getattr(self, '_has_directml', False):
            return
        _directml_session_options_patch_lock.acquire()
        try:
            original = ort.SessionOptions.__init__
            self._original_session_options_init = original

            def _patched_init(self_opts, *args, **kwargs):
                original(self_opts, *args, **kwargs)
                self_opts.enable_mem_pattern = False
                self_opts.enable_cpu_mem_arena = False  # IRON RULE §2 – beide Flags pflicht

            ort.SessionOptions.__init__ = _patched_init
            self._directml_patch_lock_held = True
            logger.debug("SessionOptions patch applied for DirectML separation")
        except Exception:
            self._original_session_options_init = None
            _directml_session_options_patch_lock.release()
            raise

    def _restore_directml_patch(self):
        """Restore original SessionOptions.__init__ after separation."""
        original = getattr(self, '_original_session_options_init', None)
        lock_held = getattr(self, '_directml_patch_lock_held', False)
        try:
            if original is not None:
                ort.SessionOptions.__init__ = original
                logger.debug("SessionOptions patch restored")
        finally:
            self._original_session_options_init = None
            self._directml_patch_lock_held = False
            if lock_held:
                _directml_session_options_patch_lock.release()

    def unload(self):
        """Release VRAM and reset separator."""
        if self.separator is not None:
            try:
                from pb_studio.core.vram_budget_manager import get_vram_manager
                vram_mgr = get_vram_manager()
                vram_mgr.release("mdx_net_inst")
                vram_mgr.release("mdx_net_voc")
                vram_mgr.release("mdxc_models")
            except Exception as ve:
                logger.warning(f"Failed to release separation budgets during unload: {ve}")

            self.separator = None
            import gc
            gc.collect()
            logger.info("StemSeparator VRAM released")

    def separate(
        self,
        file_path: str,
        model_name: str = "UVR-MDX-NET-Inst_HQ_3.onnx",
        callback=None,
        on_progress=None,
    ):
        """
        Separates audio into stems.

        Args:
            file_path: Path to audio file.
            model_name: Name of the model to use.
            callback: Legacy alias for on_progress (kept for backwards compat).
            on_progress: Optional callable(percent: float) emitting stage progress.
                Stages: 0% init, 10% loading_model, 30% running_inference,
                90% saving_stems, 100% complete. Audit C2 — feeds the
                ``stem_progress`` SSE channel during multi-minute Demucs/MDX runs.
        """
        # Legacy `callback` kept as alias — prefer `on_progress` (Audit C2)
        progress_cb = on_progress if on_progress is not None else callback

        def _emit(pct: float, stage: str = "") -> None:
            if progress_cb is None:
                return
            try:
                progress_cb(float(pct))
            except TypeError:
                # Legacy callback(message, percent) signature support
                try:
                    progress_cb(stage, float(pct))
                except Exception:
                    logger.debug("on_progress callback raised — ignoring", exc_info=True)
            except Exception:
                logger.debug("on_progress callback raised — ignoring", exc_info=True)

        _emit(0.0, "init")

        # Scoped DirectML patch
        self._apply_directml_patch()
        
        # VRAM Budget Manager integration
        vram_reserved = False
        model_id = None
        try:
            from pb_studio.core.vram_budget_manager import get_vram_manager
            vram_mgr = get_vram_manager()
            model_id = _get_vram_model_id(model_name)
            logger.info(f"Reserving VRAM budget for audio separation: {model_id}")
            vram_reserved = vram_mgr.reserve(model_id, force=True)
            if not vram_reserved:
                logger.warning(f"VRAM reserve failed or returned False for {model_id}")
        except Exception as ve:
            logger.warning(f"Failed to integrate with VRAMBudgetManager reserve (proceeding): {ve}")

        try:
            if not self.separator:
                return {"error": "Separator not initialized"}

            if not Path(file_path).exists():
                return {"error": f"File not found: {file_path}"}

            if Path(model_name).suffix.lower() == ".onnx" and not getattr(self, "_has_directml", False):
                return {
                    "error": "DirectML is required for ONNX stem separation; "
                             "CPUExecutionProvider fallback is disabled."
                }

            # Offline-Existenzpruefung fuer das Modell, um Hänger/Timeouts ohne Internet zu vermeiden
            config = getattr(self, "config", None) or ConfigManager()
            model_dir = config.get("paths", {}).get("models_dir", "./models")
            model_path = Path(model_dir) / model_name
            if not model_path.exists():
                return {
                    "error": f"Model file '{model_name}' not found in '{model_dir}'. "
                             "Please run the setup scripts to download models before using PB Studio offline."
                }

            logger.info(f"Loading model: {model_name}")
            _emit(10.0, "loading_model")
            self.separator.load_model(model_name)
            
            if vram_reserved and model_id:
                try:
                    vram_mgr.commit(model_id)
                except Exception as ve:
                    logger.warning(f"Failed to commit VRAM for {model_id}: {ve}")

            logger.info(f"Starting separation for: {file_path}")
            _emit(30.0, "running_inference")
            output_files = self._run_inference(file_path)

            _emit(90.0, "saving_stems")
            logger.info(f"Separation complete. Files: {output_files}")
            _emit(100.0, "complete")
            
            # RAM/VRAM-Cleanup
            import gc
            gc.collect()
            
            return {"stems": output_files}

        except Exception as e:
            logger.error(f"Separation failed: {e}")
            return {"error": str(e)}
        finally:
            self._restore_directml_patch()
            if vram_reserved and model_id:
                try:
                    vram_mgr.release(model_id)
                except Exception as ve:
                    logger.warning(f"Failed to release VRAM for {model_id}: {ve}")

    def _run_inference(self, file_path: str):
        """Internal seam: runs the underlying audio-separator inference call.

        Extracted so tests (and future progress hooks into audio-separator
        internals) can patch a single boundary instead of the whole separate().
        """
        with gpu_inference_lock:
            return self.separator.separate(file_path)

    def list_models(self):
        """Returns available models grouped by type."""
        if not self.separator:
            return {}
        try:
            return self.separator.list_supported_model_files()
        except Exception as e:
            logger.debug(f"Could not list models: {e}")
            return {}
