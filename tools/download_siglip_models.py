"""
SigLIP Model Download and Conversion Script

This script helps download and prepare SigLIP models for PB Studio AMD.

Note: This is a placeholder script. Actual ONNX export requires:
1. PyTorch model conversion
2. ONNX optimization
3. Verification

For now, this script provides instructions and helper functions.
"""

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """Check if required packages are installed."""
    required = [
        "transformers",
        "torch",
        "onnx",
        "onnxruntime"
    ]

    missing = []
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        logger.error(f"Missing packages: {', '.join(missing)}")
        logger.info("Install with: pip install " + " ".join(missing))
        return False

    return True


def download_tokenizer(output_dir: str = "./models/siglip_tokenizer"):
    """Download and save SigLIP tokenizer."""
    try:
        from transformers import AutoTokenizer

        logger.info("Downloading SigLIP tokenizer...")

        tokenizer = AutoTokenizer.from_pretrained("google/siglip-so400m-patch14-384")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        tokenizer.save_pretrained(str(output_path))

        logger.info(f"Tokenizer saved to: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to download tokenizer: {e}")
        return False


def export_to_onnx_instructions():
    """Print instructions for ONNX export."""
    logger.info("""
================================================================================
SigLIP ONNX Export Instructions
================================================================================

The SigLIP model needs to be exported to ONNX format manually.

OPTION 1: Use Optimum Library (Recommended)
-------------------------------------------
from optimum.onnxruntime import ORTModelForImageClassification
from transformers import AutoModel

model = AutoModel.from_pretrained("google/siglip-so400m-patch14-384")

# Export vision encoder
vision_model = model.vision_model
# ... export vision_model to siglip_vision.onnx

# Export text encoder (if available)
text_model = model.text_model
# ... export text_model to siglip_text.onnx


OPTION 2: Manual PyTorch to ONNX Export
---------------------------------------
import torch
import torch.onnx

model = AutoModel.from_pretrained("google/siglip-so400m-patch14-384")
model.eval()

# Create dummy inputs
dummy_image = torch.randn(1, 3, 384, 384)

# Export
torch.onnx.export(
    model.vision_model,
    dummy_image,
    "siglip_vision.onnx",
    input_names=["pixel_values"],
    output_names=["embeddings"],
    dynamic_axes={
        "pixel_values": {0: "batch"},
        "embeddings": {0: "batch"}
    },
    opset_version=14
)


OPTION 3: Use Pre-converted Models
----------------------------------
Search for pre-converted SigLIP ONNX models on:
- HuggingFace Hub (filter by ONNX format)
- ONNX Model Zoo
- Community conversions


REQUIRED FILES:
--------------
models/
├── siglip_vision.onnx      # Vision encoder (REQUIRED)
├── siglip_text.onnx         # Text encoder (optional, for tagging)
└── siglip_tokenizer/        # Tokenizer files (optional)


VERIFICATION:
------------
After placing files in models/ directory, test with:

    python -c "from src.pb_studio.ai import SigLIPWrapper; print(SigLIPWrapper().is_ready)"


DIRECTML COMPATIBILITY:
----------------------
Ensure the exported model:
1. Uses FP32 or FP16 (not BFloat16)
2. Has standard ONNX ops (opset >= 12)
3. No CUDA-specific operations

================================================================================
    """)


def verify_models(models_dir: str = "./models"):
    """Verify that model files exist and are valid."""
    models_path = Path(models_dir)

    required_files = {
        "siglip_vision.onnx": "Vision encoder (required)",
    }

    optional_files = {
        "siglip_text.onnx": "Text encoder (optional)",
        "siglip_tokenizer": "Tokenizer directory (optional)"
    }

    logger.info("Verifying model files...")

    all_good = True

    for filename, description in required_files.items():
        filepath = models_path / filename

        if filepath.exists():
            size_mb = filepath.stat().st_size / (1024 * 1024)
            logger.info(f"✓ {filename} found ({size_mb:.1f} MB) - {description}")
        else:
            logger.error(f"✗ {filename} NOT FOUND - {description}")
            all_good = False

    for filename, description in optional_files.items():
        filepath = models_path / filename

        if filepath.exists():
            if filepath.is_dir():
                logger.info(f"✓ {filename} found - {description}")
            else:
                size_mb = filepath.stat().st_size / (1024 * 1024)
                logger.info(f"✓ {filename} found ({size_mb:.1f} MB) - {description}")
        else:
            logger.warning(f"⚠ {filename} not found - {description}")

    if all_good:
        logger.info("\nAll required models present! Testing model loading...")

        try:
            from src.pb_studio.ai import SigLIPWrapper

            siglip = SigLIPWrapper()

            if siglip.is_ready:
                logger.info("✓ SigLIP models loaded successfully!")
                logger.info(f"  Provider: {siglip.active_provider}")
                logger.info(f"  Embedding dimension: {siglip.embedding_dimension}")
                logger.info(f"  Text encoder available: {siglip.has_text_encoder}")
            else:
                logger.error("✗ Failed to load SigLIP models")
                all_good = False

        except Exception as e:
            logger.error(f"✗ Error testing models: {e}")
            all_good = False

    else:
        logger.error("\nSome required models are missing. Please download them first.")

    return all_good


def main():
    """Main entry point."""
    logger.info("SigLIP Model Download and Verification Tool\n")

    # Check dependencies
    if not check_dependencies():
        logger.error("Please install missing dependencies first.")
        return 1

    # Download tokenizer
    logger.info("\n1. Downloading tokenizer...")
    download_tokenizer()

    # Show export instructions
    logger.info("\n2. ONNX Export Instructions:")
    export_to_onnx_instructions()

    # Verify existing models
    logger.info("\n3. Verifying existing models...")
    if verify_models():
        logger.info("\n✓ Setup complete! SigLIP Video Specialist is ready to use.")
        return 0
    else:
        logger.warning("\n⚠ Setup incomplete. Please follow the instructions above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
