# Repair Dependency Hell
Write-Host "Resolving Numpy 2.0 Conflict..." -ForegroundColor Yellow

$python = ".\.venv\Scripts\python.exe"

# 1. Uninstall the "Edge" versions that caused the break
& $python -m pip uninstall -y audio-separator numpy faiss-cpu onnxruntime-directml

# 2. Install the "Stable" core first (Numpy 1.x)
& $python -m pip install "numpy<2.0" 

# 3. Install FAISS (needs numpy<2)
& $python -m pip install faiss-cpu==1.7.4

# 4. Install Audio-Separator (Pinned to verified version compatible with Py3.11 & Numpy 1.x)
& $python -m pip install "audio-separator[dml]==0.17.0"

# 5. Fix up Torch if it got messed up
# Ensure we are on CPU/DirectML track
& $python -m pip install "onnxruntime-directml==1.23.0"

Write-Host "Repair Complete. Please run verify_env.py again." -ForegroundColor Green
