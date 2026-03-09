"""Quick test of waveform loading"""
import sys
from pathlib import Path

# Test librosa
print("[1] Testing librosa import...")
try:
    import librosa
    print(f"   [OK] librosa {librosa.__version__}")
except ImportError as e:
    print(f"   [FAIL] {e}")
    sys.exit(1)

# Test WaveformWidget
print("\n[2] Testing WaveformWidget...")
try:
    from src.pb_studio.ui.widgets.waveform_widget import WaveformWidget
    print("   [OK] Import successful")
except Exception as e:
    print(f"   [FAIL] {e}")
    sys.exit(1)

# Test loading a sample file (if exists)
print("\n[3] Testing audio load...")
test_files = list(Path(".").glob("*.mp3")) + list(Path(".").glob("*.wav"))

if test_files:
    test_file = str(test_files[0])
    print(f"   Found: {test_file}")
    
    try:
        y, sr = librosa.load(test_file, sr=22050, mono=True)
        print(f"   [OK] Loaded: {len(y)} samples, {sr}Hz")
        print(f"   Max amplitude: {max(abs(y)):.4f}")
    except Exception as e:
        print(f"   [FAIL] {e}")
else:
    print("   [SKIP] No test audio files found in project root.")
    print("   Place a .mp3 or .wav file in the project folder to test.")

print("\n--- Waveform Debug Complete ---")
