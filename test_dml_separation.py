import logging
import sys
from pathlib import Path
from src.pb_studio.utils.logging_setup import setup_logging

setup_logging("test_dml_stem")
logger = logging.getLogger("DMLStemTest")

print("--- Testing DirectML Stem Separation (Patched) ---\n")

# 1. Import our patched separator
print("[1] Importing patched StemSeparator...")
try:
    from src.pb_studio.audio.separator import StemSeparator
    print("   [OK] Import successful.")
except ImportError as e:
    print(f"   [FAIL] Import error: {e}")
    sys.exit(1)

# 2. Initialize (this applies the DirectML patch)
print("\n[2] Initializing StemSeparator (DirectML Patch)...")
try:
    sep = StemSeparator()
    if sep.separator:
        provider = sep.separator.onnx_execution_provider
        print(f"   [OK] Initialized. ONNX Provider: {provider}")
        
        if provider and "DmlExecutionProvider" in provider:
            print("   *** AMD DirectML ACCELERATION ENABLED ***")
        else:
            print("   [WARN] DirectML not in provider list.")
    else:
        print("   [FAIL] Separator is None.")
except Exception as e:
    print(f"   [FAIL] Init error: {e}")
    sys.exit(1)

# 3. Test separation (optional - requires actual audio file)
print("\n[3] Testing separation...")
test_file = Path("./test_audio.mp3")
if test_file.exists():
    try:
        print(f"   Found test file: {test_file}")
        print("   Running separation with MDX model (DirectML accelerated)...")
        print("   This will download the model on first run (~100MB)...")
        results = sep.separate(str(test_file))
        if "error" in results:
            print(f"   [FAIL] {results['error']}")
        else:
            print(f"   [OK] Separation complete!")
            for stem in results.get("stems", []):
                print(f"      - {stem}")
    except Exception as e:
        print(f"   [FAIL] Separation error: {e}")
else:
    print("   [SKIP] No test file (test_audio.mp3) found.")
    print("   To test separation, place an audio file named 'test_audio.mp3' in project root.")

print("\n--- DirectML Stem Separation Test Complete ---")
