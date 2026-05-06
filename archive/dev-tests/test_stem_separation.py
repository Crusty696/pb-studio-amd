import logging
import sys
from pathlib import Path
from src.pb_studio.utils.logging_setup import setup_logging

setup_logging("test_stem")
logger = logging.getLogger("StemTest")

print("--- Testing Stem Separation (Audio-Separator) ---\n")

# 1. Import Check
print("[1] Checking AudioSeparator import...")
try:
    from audio_separator.separator import Separator
    print("   [OK] Import successful.")
except ImportError as e:
    print(f"   [FAIL] Import error: {e}")
    sys.exit(1)

# 2. ONNX Provider Check
print("\n[2] Checking ONNX Providers...")
try:
    import onnxruntime as ort
    providers = ort.get_available_providers()
    print(f"   Available: {providers}")
    if "DmlExecutionProvider" in providers:
        print("   [OK] DirectML is available (AMD acceleration).")
    else:
        print("   [WARN] DirectML not found, will use CPU.")
except Exception as e:
    print(f"   [FAIL] ONNX check error: {e}")

# 3. Initialize Separator
print("\n[3] Initializing Separator...")
try:
    sep = Separator(output_dir="./temp/stems", output_format="WAV")
    print("   [OK] Separator initialized.")
except Exception as e:
    print(f"   [FAIL] Init error: {e}")
    sys.exit(1)

# 4. List Available Models
print("\n[4] Listing available models...")
try:
    # audio-separator 0.17 might have different API
    # Try common method names
    if hasattr(sep, 'list_models'):
        models = sep.list_models()
        print(f"   Found {len(models)} models.")
        for m in models[:5]:
            print(f"     - {m}")
        if len(models) > 5:
            print(f"     ... and {len(models) - 5} more.")
    else:
        print("   [INFO] list_models() not available in this version.")
        print("   [INFO] Models are loaded on-demand during separation.")
except Exception as e:
    print(f"   [WARN] Could not list models: {e}")

# 5. Test Separation (Optional - requires actual audio file)
print("\n[5] Testing separation...")
test_file = Path("./test_audio.mp3") # User would need to provide this
if test_file.exists():
    try:
        print(f"   Found test file: {test_file}")
        print("   Running separation (this may take a minute and download model)...")
        results = sep.separate(str(test_file))
        print(f"   [OK] Separation complete. Output files: {results}")
    except Exception as e:
        print(f"   [FAIL] Separation error: {e}")
else:
    print("   [SKIP] No test file (test_audio.mp3) found.")
    print("   To test separation, place an audio file named 'test_audio.mp3' in the project root.")

print("\n--- Stem Separation Test Complete ---")
