"""
Stem Separator for AMD GPUs (DirectML Patched)

The standard audio-separator library only auto-detects CUDA (NVIDIA) or MPS (Apple).
This wrapper forces DirectML usage for ONNX Runtime, enabling AMD GPU acceleration.
"""
import importlib.util
import logging
import os
import sys
import types
from pathlib import Path

import onnxruntime as ort
import torch

from pb_studio.config_manager import ConfigManager

logger = logging.getLogger(__name__)


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
                self.separator.onnx_execution_provider = ["DmlExecutionProvider", "CPUExecutionProvider"]
                logger.info(f"ONNX Provider set to: {self.separator.onnx_execution_provider}")

                # SessionOptions Patch wird nur während separate() aktiv gehalten
                # (siehe _apply_directml_patch / _restore_directml_patch)
                self._has_directml = True
            else:
                logger.warning("DirectML not available. Running in CPU mode.")
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
        self._original_session_options_init = ort.SessionOptions.__init__
        def _patched_init(self_opts, *args, **kwargs):
            self._original_session_options_init(self_opts, *args, **kwargs)
            self_opts.enable_mem_pattern = False
        ort.SessionOptions.__init__ = _patched_init
        logger.debug("SessionOptions patch applied for DirectML separation")

    def _restore_directml_patch(self):
        """Restore original SessionOptions.__init__ after separation."""
        original = getattr(self, '_original_session_options_init', None)
        if original is not None:
            ort.SessionOptions.__init__ = original
            self._original_session_options_init = None
            logger.debug("SessionOptions patch restored")

    def separate(self, file_path: str, model_name: str = "UVR-MDX-NET-Inst_HQ_3.onnx"):
        """
        Separates audio into stems.

        Args:
            file_path: Path to audio file.
            model_name: Name of the model to use.
                       ONNX models (MDX): Get DirectML acceleration.
                       PyTorch models (Demucs): Run on CPU (PyTorch has no DML).

        Returns:
            dict with 'stems' list or 'error' string.
        """
        if not self.separator:
            return {"error": "Separator not initialized"}

        if not Path(file_path).exists():
            return {"error": f"File not found: {file_path}"}

        # Scoped DirectML patch: nur während Separation aktiv
        self._apply_directml_patch()
        try:
            logger.info(f"Loading model: {model_name}")
            self.separator.load_model(model_name)

            logger.info(f"Starting separation for: {file_path}")
            logger.info(f"Using ONNX Provider: {self.separator.onnx_execution_provider}")

            output_files = self.separator.separate(file_path)

            logger.info(f"Separation complete. Files: {output_files}")
            return {"stems": output_files}

        except Exception as e:
            logger.error(f"Separation failed: {e}")
            return {"error": str(e)}
        finally:
            self._restore_directml_patch()

    def list_models(self):
        """Returns available models grouped by type."""
        if not self.separator:
            return {}
        try:
            return self.separator.list_supported_model_files()
        except Exception as e:
            logger.debug(f"Could not list models: {e}")
            return {}
