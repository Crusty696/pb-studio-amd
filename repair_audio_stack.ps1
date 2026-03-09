# Repair Audio Stack (Numpy 1.x Alignment)
Write-Host "Aligning Science Stack with Numpy 1.26.4..." -ForegroundColor Yellow

$python = ".\.venv\Scripts\python.exe"

# 1. Uninstall victims of the "Numpy 2.0 Wars"
& $python -m pip uninstall -y scipy matplotlib librosa BeatNet

# 2. Reinstall with strict compatible versions
# Scipy 1.11/1.12 is safe for Numpy 1.26.
& $python -m pip install "numpy==1.26.4" "scipy<1.13.0" "matplotlib<3.9.0"

# 3. Install Librosa (Stable)
& $python -m pip install "librosa==0.10.1"

# 4. Install BeatNet
& $python -m pip install BeatNet

Write-Host "Audio Stack Repaired. Running Verification..." -ForegroundColor Green
& $python test_audio_stack.py
