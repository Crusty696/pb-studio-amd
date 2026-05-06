"""Install missing dependencies for model downloads."""
import subprocess
import sys

deps = ["sentencepiece"]

for dep in deps:
    print(f"Installing {dep}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
    print(f"✓ {dep} installed")

print("\nChecking PyTorch version...")
import torch
print(f"PyTorch: {torch.__version__}")

if torch.__version__ < "2.6":
    print("⚠️ PyTorch < 2.6 - CLAP download may fail")
    print("Run: pip install torch>=2.6 (if needed)")
else:
    print("✓ PyTorch version OK")
