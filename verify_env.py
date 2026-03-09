import sys
import importlib

def check_import(name):
    try:
        lib = importlib.import_module(name)
        print(f"[OK] {name} imported. Version: {getattr(lib, '__version__', 'Unknown')}")
        return True
    except ImportError as e:
        print(f"[FAIL] {name} NOT found. {e}")
        return False
    except Exception as e:
        print(f"[FAIL] {name} error. {e}")
        return False

print("--- PB Studio Environment Verification ---")
print(f"Python: {sys.version}")

# 1. Critical ML
check_import("torch")
check_import("torchaudio")
check_import("onnxruntime")

# 2. Transformers Chain
check_import("transformers")
check_import("huggingface_hub")

# 3. Audio/CV
check_import("librosa")
check_import("cv2")
check_import("numpy")

# 4. Hardware
try:
    import clr
    print("[OK] pythonnet imported.")
except:
    print("[FAIL] pythonnet missing.")

print("--- End ---")
