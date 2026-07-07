"""
Moondream2 Vision-Language Model - ONNX Export for DirectML

Exports Moondream2 vision encoder to ONNX.
Note: Full VLM export is complex, we export the vision encoder for embeddings.
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
    """Export Moondream vision encoder to ONNX."""

    models_dir = Path(__file__).parent.parent / "models"
    models_dir.mkdir(exist_ok=True)

    logger.info("=" * 60)
    logger.info("Moondream2 Vision Encoder - ONNX Export")
    logger.info("=" * 60)

    # Check dependencies
    try:
        import torch
        import transformers
        logger.info(f"PyTorch: {torch.__version__}")
        logger.info(f"Transformers: {transformers.__version__}")
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        return 1

    # Load Moondream
    logger.info("\n1. Loading Moondream2 model...")
    logger.info("   This may take a few minutes (downloading ~2GB)...")

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        # Load model with trust_remote_code (required for Moondream)
        model = AutoModelForCausalLM.from_pretrained(
            "vikhyatk/moondream2",
            trust_remote_code=True,
            torch_dtype=torch.float32  # FP32 for ONNX export
        )

        tokenizer = AutoTokenizer.from_pretrained(
            "vikhyatk/moondream2",
            trust_remote_code=True
        )

        model.eval()
        logger.info("[OK] Moondream2 loaded successfully")

    except Exception as e:
        logger.error(f"Failed to load Moondream: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Save tokenizer
    logger.info("\n2. Saving tokenizer...")
    tokenizer_dir = models_dir / "moondream_tokenizer"
    tokenizer.save_pretrained(str(tokenizer_dir))
    logger.info(f"[OK] Tokenizer saved to {tokenizer_dir}")

    # Extract and export vision encoder
    logger.info("\n3. Extracting vision encoder...")

    try:
        # Moondream has a vision_encoder attribute
        if hasattr(model, 'vision_encoder'):
            vision_encoder = model.vision_encoder
            logger.info("[OK] Vision encoder extracted")
        elif hasattr(model, 'model') and hasattr(model.model, 'vision_encoder'):
            vision_encoder = model.model.vision_encoder
            logger.info("[OK] Vision encoder extracted from model.model")
        else:
            # Try to find vision component
            logger.warning("Standard vision_encoder not found, trying alternatives...")

            # List available attributes
            attrs = [a for a in dir(model) if not a.startswith('_')]
            logger.info(f"Available attributes: {attrs[:20]}...")

            # Moondream2 specific: check for encode_image method
            if hasattr(model, 'encode_image'):
                logger.info("[OK] Found encode_image method - using wrapper")

                class VisionEncoderWrapper(torch.nn.Module):
                    def __init__(self, moondream_model):
                        super().__init__()
                        self.model = moondream_model

                    def forward(self, pixel_values):
                        # Use Moondream's encode_image
                        return self.model.encode_image(pixel_values)

                vision_encoder = VisionEncoderWrapper(model)
            else:
                logger.error("Could not find vision encoder component")
                logger.info("Moondream architecture may have changed. Skipping ONNX export.")
                logger.info("The model is still usable via PyTorch directly.")
                return 1

    except Exception as e:
        logger.error(f"Failed to extract vision encoder: {e}")
        return 1

    # Export to ONNX
    logger.info("\n4. Exporting to ONNX...")

    try:
        vision_encoder.eval()

        # Moondream expects 384x384 images (or 378x378 in some versions)
        dummy_input = torch.randn(1, 3, 384, 384)

        onnx_path = models_dir / "moondream_vision.onnx"

        torch.onnx.export(
            vision_encoder,
            dummy_input,
            str(onnx_path),
            input_names=["pixel_values"],
            output_names=["image_features"],
            dynamic_axes={
                "pixel_values": {0: "batch_size"},
                "image_features": {0: "batch_size"}
            },
            opset_version=18,
            do_constant_folding=True,
            dynamo=False,
            verbose=False
        )

        logger.info(f"[OK] Vision encoder exported to {onnx_path}")

        size_mb = onnx_path.stat().st_size / (1024 * 1024)
        logger.info(f"[OK] Model size: {size_mb:.1f} MB")

    except Exception as e:
        logger.error(f"ONNX export failed: {e}")
        import traceback
        traceback.print_exc()

        logger.info("\n--- Alternative: Save PyTorch model for later ---")
        try:
            torch.save(model.state_dict(), models_dir / "moondream_pytorch.pt")
            logger.info("[OK] PyTorch weights saved as fallback")
        except:
            pass

        return 1

    # Verify ONNX
    logger.info("\n5. Verifying ONNX model...")

    try:
        import onnx
        onnx_model = onnx.load(str(onnx_path))
        onnx.checker.check_model(onnx_model)
        logger.info("[OK] ONNX verification passed")
    except Exception as e:
        logger.warning(f"Verification warning: {e}")

    # Test with DirectML
    logger.info("\n6. Testing with DirectML...")

    try:
        import onnxruntime as ort
        import numpy as np

        sess_options = ort.SessionOptions()
        sess_options.enable_mem_pattern = False
        sess_options.enable_cpu_mem_arena = False  # IRON RULE 2: BEIDE Flags Pflicht (AP5.2)

        providers = []
        if 'DmlExecutionProvider' in ort.get_available_providers():
            providers.append('DmlExecutionProvider')
            logger.info("[OK] DirectML available")
        providers.append('CPUExecutionProvider')

        session = ort.InferenceSession(
            str(onnx_path),
            sess_options=sess_options,
            providers=providers
        )

        logger.info(f"[OK] Provider: {session.get_providers()[0]}")

        # Test inference
        test_input = np.random.randn(1, 3, 384, 384).astype(np.float32)
        outputs = session.run(None, {"pixel_values": test_input})

        logger.info(f"[OK] Test successful, output shape: {outputs[0].shape}")

    except Exception as e:
        logger.warning(f"DirectML test failed: {e}")

    logger.info("\n" + "=" * 60)
    logger.info("Moondream ONNX export completed!")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
