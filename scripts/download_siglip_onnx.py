"""
SigLIP ONNX Model Download and Export Script

Downloads SigLIP model and exports to ONNX for DirectML.

Usage:
    python scripts/download_siglip_onnx.py
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
    """Download and export SigLIP to ONNX."""

    models_dir = Path(__file__).parent.parent / "models"
    models_dir.mkdir(exist_ok=True)

    logger.info("=" * 60)
    logger.info("SigLIP ONNX Export for DirectML")
    logger.info("=" * 60)

    # Check dependencies
    try:
        import torch
        import transformers
        import onnx
        logger.info(f"PyTorch: {torch.__version__}")
        logger.info(f"Transformers: {transformers.__version__}")
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Install: pip install torch transformers onnx")
        return 1

    # Download model
    logger.info("\n1. Downloading SigLIP model from HuggingFace...")
    logger.info("Model: google/siglip-so400m-patch14-384")

    try:
        from transformers import SiglipVisionModel, SiglipProcessor

        processor = SiglipProcessor.from_pretrained("google/siglip-so400m-patch14-384")
        vision_model = SiglipVisionModel.from_pretrained("google/siglip-so400m-patch14-384")

        logger.info("[OK] Model downloaded successfully")

    except Exception as e:
        logger.error(f"Download failed: {e}")
        return 1

    # Save processor/tokenizer
    logger.info("\n2. Saving processor...")
    tokenizer_dir = models_dir / "siglip_tokenizer"
    processor.save_pretrained(str(tokenizer_dir))
    logger.info(f"[OK] Processor saved to {tokenizer_dir}")

    # Export to ONNX
    logger.info("\n3. Exporting Vision Encoder to ONNX...")

    try:
        vision_model.eval()

        # Dummy input (batch, channels, height, width)
        dummy_input = torch.randn(1, 3, 384, 384)

        onnx_path = models_dir / "siglip_vision.onnx"

        # Use legacy exporter to avoid Unicode issues in PyTorch 2.10
        torch.onnx.export(
            vision_model,
            dummy_input,
            str(onnx_path),
            input_names=["pixel_values"],
            output_names=["last_hidden_state", "pooler_output"],
            dynamic_axes={
                "pixel_values": {0: "batch_size"},
                "last_hidden_state": {0: "batch_size"},
                "pooler_output": {0: "batch_size"}
            },
            opset_version=18,
            do_constant_folding=True,
            dynamo=False,
            verbose=False
        )

        logger.info(f"[OK] Vision encoder exported to {onnx_path}")

        # Verify
        import onnx
        model = onnx.load(str(onnx_path))
        onnx.checker.check_model(model)
        logger.info("[OK] ONNX model verification passed")

        # File size
        size_mb = onnx_path.stat().st_size / (1024 * 1024)
        logger.info(f"✓ Model size: {size_mb:.1f} MB")

    except Exception as e:
        logger.error(f"ONNX export failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Test with ONNX Runtime
    logger.info("\n4. Testing with ONNX Runtime DirectML...")

    try:
        import onnxruntime as ort

        sess_options = ort.SessionOptions()
        sess_options.enable_mem_pattern = False  # CRITICAL for DirectML!
        sess_options.enable_cpu_mem_arena = False  # IRON RULE 2: BEIDE Flags Pflicht (AP5.2)

        providers = []
        available = ort.get_available_providers()

        if 'DmlExecutionProvider' in available:
            providers.append('DmlExecutionProvider')
            logger.info("✓ DirectML available")
        providers.append('CPUExecutionProvider')

        session = ort.InferenceSession(
            str(onnx_path),
            sess_options=sess_options,
            providers=providers
        )

        active_provider = session.get_providers()[0]
        logger.info(f"✓ Active provider: {active_provider}")

        # Test inference
        import numpy as np
        test_input = np.random.randn(1, 3, 384, 384).astype(np.float32)
        outputs = session.run(None, {"pixel_values": test_input})

        logger.info(f"✓ Test inference successful")
        logger.info(f"  Output shape: {outputs[1].shape}")  # pooler_output

    except Exception as e:
        logger.warning(f"ONNX Runtime test failed: {e}")
        logger.warning("Model exported but runtime test failed - may still work")

    logger.info("\n" + "=" * 60)
    logger.info("SigLIP ONNX export completed!")
    logger.info("=" * 60)
    logger.info(f"\nFiles created:")
    logger.info(f"  - {models_dir / 'siglip_vision.onnx'}")
    logger.info(f"  - {models_dir / 'siglip_tokenizer/'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
