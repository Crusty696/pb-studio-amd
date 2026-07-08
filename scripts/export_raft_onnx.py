"""
RAFT Optical Flow - ONNX Export for DirectML

Downloads RAFT model and exports to ONNX format.
"""

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Export RAFT to ONNX."""

    models_dir = Path(__file__).parent.parent / "models"
    models_dir.mkdir(exist_ok=True)

    logger.info("=" * 60)
    logger.info("RAFT Optical Flow - ONNX Export for DirectML")
    logger.info("=" * 60)

    # Check dependencies
    try:
        import torch
        import torchvision
        logger.info(f"PyTorch: {torch.__version__}")
        logger.info(f"TorchVision: {torchvision.__version__}")
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        return 1

    # Use TorchVision's RAFT implementation
    logger.info("\n1. Loading RAFT model from TorchVision...")

    try:
        from torchvision.models.optical_flow import raft_small, Raft_Small_Weights

        # Load pretrained RAFT-Small (smaller, faster, good for real-time)
        weights = Raft_Small_Weights.DEFAULT
        model = raft_small(weights=weights)
        model.eval()

        logger.info("[OK] RAFT-Small loaded successfully")
        logger.info(f"    Input size: 520x960 recommended")

    except Exception as e:
        logger.error(f"Failed to load RAFT: {e}")

        # Fallback: Try RAFT-Large
        logger.info("Trying RAFT-Large as fallback...")
        try:
            from torchvision.models.optical_flow import raft_large, Raft_Large_Weights
            weights = Raft_Large_Weights.DEFAULT
            model = raft_large(weights=weights)
            model.eval()
            logger.info("[OK] RAFT-Large loaded")
        except Exception as e2:
            logger.error(f"RAFT-Large also failed: {e2}")
            return 1

    # Export to ONNX
    logger.info("\n2. Exporting to ONNX...")

    try:
        import torch

        # Dummy inputs (batch, channels, height, width)
        # Using smaller resolution for faster inference
        dummy_img1 = torch.randn(1, 3, 256, 448)
        dummy_img2 = torch.randn(1, 3, 256, 448)

        onnx_path = models_dir / "raft_small.onnx"

        # RAFT returns a list of flow predictions (multi-scale)
        # We need to wrap it for ONNX export
        class RAFTWrapper(torch.nn.Module):
            def __init__(self, raft_model):
                super().__init__()
                self.raft = raft_model

            def forward(self, img1, img2):
                # RAFT returns list of flow predictions, take the last (finest)
                flow_predictions = self.raft(img1, img2)
                return flow_predictions[-1]  # Final flow prediction

        wrapped_model = RAFTWrapper(model)
        wrapped_model.eval()

        torch.onnx.export(
            wrapped_model,
            (dummy_img1, dummy_img2),
            str(onnx_path),
            input_names=["image1", "image2"],
            output_names=["optical_flow"],
            dynamic_axes={
                "image1": {0: "batch", 2: "height", 3: "width"},
                "image2": {0: "batch", 2: "height", 3: "width"},
                "optical_flow": {0: "batch", 2: "height", 3: "width"}
            },
            opset_version=18,
            do_constant_folding=True,
            dynamo=False,
            verbose=False
        )

        logger.info(f"[OK] RAFT exported to {onnx_path}")

        # File size
        size_mb = onnx_path.stat().st_size / (1024 * 1024)
        logger.info(f"[OK] Model size: {size_mb:.1f} MB")

    except Exception as e:
        logger.error(f"ONNX export failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Verify with ONNX
    logger.info("\n3. Verifying ONNX model...")

    try:
        import onnx
        model = onnx.load(str(onnx_path))
        onnx.checker.check_model(model)
        logger.info("[OK] ONNX verification passed")
    except Exception as e:
        logger.warning(f"ONNX verification warning: {e}")

    # Test with DirectML
    logger.info("\n4. Testing with ONNX Runtime DirectML...")

    try:
        import onnxruntime as ort
        import numpy as np

        sess_options = ort.SessionOptions()
        sess_options.enable_mem_pattern = False  # CRITICAL for DirectML
        sess_options.enable_cpu_mem_arena = False  # IRON RULE 2: BEIDE Flags Pflicht (AP5.2)

        providers = []
        available = ort.get_available_providers()

        if 'DmlExecutionProvider' in available:
            providers.append('DmlExecutionProvider')
            logger.info("[OK] DirectML available")
        providers.append('CPUExecutionProvider')

        session = ort.InferenceSession(
            str(onnx_path),
            sess_options=sess_options,
            providers=providers
        )

        active = session.get_providers()[0]
        logger.info(f"[OK] Active provider: {active}")

        # Test inference
        test_img1 = np.random.randn(1, 3, 256, 448).astype(np.float32)
        test_img2 = np.random.randn(1, 3, 256, 448).astype(np.float32)

        outputs = session.run(None, {"image1": test_img1, "image2": test_img2})

        logger.info(f"[OK] Test inference successful")
        logger.info(f"    Flow output shape: {outputs[0].shape}")

    except Exception as e:
        logger.warning(f"DirectML test failed: {e}")
        logger.warning("Model exported but runtime test failed")

    logger.info("\n" + "=" * 60)
    logger.info("RAFT ONNX export completed!")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
