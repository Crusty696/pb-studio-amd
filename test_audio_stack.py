import sys
import logging
from src.pb_studio.utils.logging_setup import setup_logging

setup_logging("test_audio")
logger = logging.getLogger("AudioVerifier")

print("--- Testing Audio Engine Stack ---")

# 1. BeatNet Check
print("\n[1] Checking BeatNet...")
try:
    # Try the standard import (BeatNet library, BeatNet class)
    # Usually it is 'from BeatNet.BeatNet import BeatNet'
    try:
        from BeatNet.BeatNet import BeatNet
    except ImportError:
        # Fallback if structure is different
        from BeatNet import BeatNet

    # Initialize with offline mode
    # use 'madmom' or 'DBN' model. 'DBN' is default.
    estimator = BeatNet(1, mode='offline', inference_model='DBN', plot=[], thread=False)
    print("   [OK] BeatNet initialized.")
except ImportError as e:
    print(f"   [FAIL] BeatNet Import Error: {e}")
except Exception as e:
    print(f"   [FAIL] BeatNet Init Error: {e}")

# 2. Audio Separator Check
print("\n[2] Checking AudioSeparator [DML]...")
try:
    from audio_separator.separator import Separator
    import onnxruntime as ort
    
    print(f"   ONNX Providers Available: {ort.get_available_providers()}")
    
    # Initialize
    sep = Separator()
    print("   [OK] Separator initialized.")
    
except ImportError as e:
    print(f"   [FAIL] audio_separator/onnxruntime not installed: {e}")
except Exception as e:
    print(f"   [FAIL] Separator Init Error: {e}")

print("\n--- Audio Stack Verification Complete ---")
