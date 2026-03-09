"""
CLAP Model Download and ONNX Export Script

Downloads the LAION CLAP model from Hugging Face and converts it to ONNX format
for use with DirectML on AMD GPUs.

Model: laion/clap-htsat-unfused

Requirements:
    pip install transformers torch onnx optimum

Usage:
    python scripts/download_clap_model.py

Output:
    models/clap_audio_encoder.onnx
    models/clap_text_encoder.onnx
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """Check if required packages are installed."""
    required = ["transformers", "torch", "onnx"]
    missing = []

    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        logger.error(f"Missing required packages: {', '.join(missing)}")
        logger.error("Install with: pip install transformers torch onnx optimum")
        return False

    return True


def download_clap_pytorch():
    """
    Download CLAP model from Hugging Face.

    Returns:
        Tuple of (audio_model, text_model, processor) or None on failure
    """
    try:
        from transformers import ClapModel, ClapProcessor

        logger.info("Downloading CLAP model from Hugging Face...")
        logger.info("Model: laion/clap-htsat-unfused")

        # Download model and processor
        model = ClapModel.from_pretrained("laion/clap-htsat-unfused")
        processor = ClapProcessor.from_pretrained("laion/clap-htsat-unfused")

        logger.info("Model downloaded successfully")

        # Extract audio and text encoders
        audio_model = model.audio_model
        text_model = model.text_model

        return audio_model, text_model, processor

    except Exception as e:
        logger.error(f"Failed to download CLAP model: {e}")
        return None


def export_audio_encoder_onnx(audio_model, output_path: Path):
    """
    Export audio encoder to ONNX format.

    Args:
        audio_model: CLAP audio encoder (HTS-AT)
        output_path: Output ONNX file path
    """
    try:
        import torch
        import torch.onnx

        logger.info("Exporting audio encoder to ONNX...")

        # Set model to eval mode
        audio_model.eval()

        # Create dummy mel spectrogram input
        # CLAP expects: [batch_size, 1, n_mels, time_frames]
        # Typical: [1, 1, 64, ~1000 frames for 10 seconds]
        dummy_mel_input = torch.randn(1, 1, 64, 1000)

        # Export to ONNX (use legacy exporter to avoid Unicode issues)
        torch.onnx.export(
            audio_model,
            dummy_mel_input,
            str(output_path),
            input_names=["mel_spectrogram"],
            output_names=["audio_embedding"],
            dynamic_axes={
                "mel_spectrogram": {0: "batch_size", 3: "time_frames"},
                "audio_embedding": {0: "batch_size"}
            },
            opset_version=18,
            do_constant_folding=True,
            dynamo=False,
            verbose=False
        )

        logger.info(f"Audio encoder exported to: {output_path}")
        logger.info(f"File size: {output_path.stat().st_size / (1024*1024):.2f} MB")

        return True

    except Exception as e:
        logger.error(f"Failed to export audio encoder: {e}")
        return False


def export_text_encoder_onnx(text_model, processor, output_path: Path):
    """
    Export text encoder to ONNX format.

    Args:
        text_model: CLAP text encoder (RoBERTa)
        processor: CLAP processor for tokenization
        output_path: Output ONNX file path
    """
    try:
        import torch
        import torch.onnx

        logger.info("Exporting text encoder to ONNX...")

        # Set model to eval mode
        text_model.eval()

        # Create dummy text input
        dummy_texts = ["energetic music", "calm ambient"]
        text_inputs = processor(text=dummy_texts, return_tensors="pt", padding=True)

        # Extract input tensors
        dummy_input_ids = text_inputs["input_ids"]
        dummy_attention_mask = text_inputs["attention_mask"]

        # Export to ONNX (use legacy exporter to avoid Unicode issues)
        torch.onnx.export(
            text_model,
            (dummy_input_ids, dummy_attention_mask),
            str(output_path),
            input_names=["input_ids", "attention_mask"],
            output_names=["text_embedding"],
            dynamic_axes={
                "input_ids": {0: "batch_size", 1: "sequence_length"},
                "attention_mask": {0: "batch_size", 1: "sequence_length"},
                "text_embedding": {0: "batch_size"}
            },
            opset_version=18,
            do_constant_folding=True,
            dynamo=False,
            verbose=False
        )

        logger.info(f"Text encoder exported to: {output_path}")
        logger.info(f"File size: {output_path.stat().st_size / (1024*1024):.2f} MB")

        return True

    except Exception as e:
        logger.error(f"Failed to export text encoder: {e}")
        return False


def verify_onnx_model(onnx_path: Path):
    """
    Verify exported ONNX model.

    Args:
        onnx_path: Path to ONNX file
    """
    try:
        import onnx

        logger.info(f"Verifying ONNX model: {onnx_path.name}")

        # Load and check model
        onnx_model = onnx.load(str(onnx_path))
        onnx.checker.check_model(onnx_model)

        logger.info("✓ Model is valid")

        # Print model info
        logger.info("Model Inputs:")
        for input_tensor in onnx_model.graph.input:
            logger.info(f"  {input_tensor.name}: {input_tensor.type}")

        logger.info("Model Outputs:")
        for output_tensor in onnx_model.graph.output:
            logger.info(f"  {output_tensor.name}: {output_tensor.type}")

        return True

    except Exception as e:
        logger.error(f"Model verification failed: {e}")
        return False


def test_inference(audio_encoder_path: Path, text_encoder_path: Path):
    """
    Test inference with exported ONNX models.

    Args:
        audio_encoder_path: Path to audio encoder ONNX
        text_encoder_path: Path to text encoder ONNX
    """
    try:
        import onnxruntime as ort
        import numpy as np

        logger.info("Testing ONNX inference...")

        # Create session options (DirectML-compatible)
        sess_options = ort.SessionOptions()
        sess_options.enable_mem_pattern = False  # KRITISCH für DirectML!
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        # Use CPU for testing (DirectML might not be available on all systems)
        providers = ['CPUExecutionProvider']

        # Load audio encoder
        audio_session = ort.InferenceSession(
            str(audio_encoder_path),
            sess_options,
            providers=providers
        )

        # Test audio encoding
        dummy_mel = np.random.randn(1, 1, 64, 1000).astype(np.float32)
        audio_outputs = audio_session.run(None, {"mel_spectrogram": dummy_mel})

        logger.info(f"✓ Audio encoder inference successful")
        logger.info(f"  Output shape: {audio_outputs[0].shape}")

        # Load text encoder
        text_session = ort.InferenceSession(
            str(text_encoder_path),
            sess_options,
            providers=providers
        )

        # Test text encoding
        dummy_input_ids = np.array([[101, 2002, 2003, 102]], dtype=np.int64)
        dummy_attention_mask = np.array([[1, 1, 1, 1]], dtype=np.int64)

        text_outputs = text_session.run(
            None,
            {
                "input_ids": dummy_input_ids,
                "attention_mask": dummy_attention_mask
            }
        )

        logger.info(f"✓ Text encoder inference successful")
        logger.info(f"  Output shape: {text_outputs[0].shape}")

        return True

    except Exception as e:
        logger.error(f"Inference test failed: {e}")
        logger.error("Note: This is normal if onnxruntime-directml is not installed")
        return False


def main():
    """Main execution function."""
    logger.info("=" * 60)
    logger.info("CLAP Model Download and ONNX Export")
    logger.info("=" * 60)

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Create models directory
    models_dir = project_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Output directory: {models_dir}")

    # Define output paths
    audio_encoder_path = models_dir / "clap_audio_encoder.onnx"
    text_encoder_path = models_dir / "clap_text_encoder.onnx"

    # Check if models already exist
    if audio_encoder_path.exists() and text_encoder_path.exists():
        logger.warning("ONNX models already exist!")
        response = input("Overwrite? (y/n): ")
        if response.lower() != 'y':
            logger.info("Aborted")
            sys.exit(0)

    # Download PyTorch model
    result = download_clap_pytorch()
    if result is None:
        logger.error("Model download failed")
        sys.exit(1)

    audio_model, text_model, processor = result

    # Export audio encoder
    logger.info("\n" + "=" * 60)
    if not export_audio_encoder_onnx(audio_model, audio_encoder_path):
        logger.error("Audio encoder export failed")
        sys.exit(1)

    # Verify audio encoder
    if not verify_onnx_model(audio_encoder_path):
        logger.warning("Audio encoder verification failed")

    # Export text encoder
    logger.info("\n" + "=" * 60)
    if not export_text_encoder_onnx(text_model, processor, text_encoder_path):
        logger.error("Text encoder export failed")
        sys.exit(1)

    # Verify text encoder
    if not verify_onnx_model(text_encoder_path):
        logger.warning("Text encoder verification failed")

    # Test inference
    logger.info("\n" + "=" * 60)
    test_inference(audio_encoder_path, text_encoder_path)

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Export Complete!")
    logger.info("=" * 60)
    logger.info(f"Audio Encoder: {audio_encoder_path}")
    logger.info(f"Text Encoder: {text_encoder_path}")
    logger.info("\nNext steps:")
    logger.info("1. Test with: python examples/clap_demo.py <audio_file>")
    logger.info("2. Integrate into your application via CLAPAnalyzer")
    logger.info("3. For AMD GPU acceleration, ensure onnxruntime-directml is installed")


if __name__ == "__main__":
    main()
