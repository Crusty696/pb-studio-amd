#!/usr/bin/env python3
"""
PB Studio AMD Edition - Status Check

Comprehensive check of all components:
- Python environment
- DirectML availability
- AMF encoder support
- Required models
- Module imports
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, "src")

def print_header(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_status(name, ok, detail=""):
    status = "[OK]  " if ok else "[FAIL]"
    detail_str = f" - {detail}" if detail else ""
    print(f"  {status} {name}{detail_str}")

def check_python():
    print_header("Python Environment")

    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    # Python 3.10 or 3.11 required
    ok = version.major == 3 and version.minor in [10, 11]
    print_status("Python Version", ok, version_str)

    if not ok:
        print("    WARNING: Python 3.10 or 3.11 required (BeatNet compatibility)")

    return ok

def check_packages():
    print_header("Critical Packages")

    all_ok = True

    # numpy < 2.0
    try:
        import numpy as np
        version = np.__version__
        ok = int(version.split('.')[0]) < 2
        print_status("numpy", ok, f"{version} (must be < 2.0)")
        all_ok = all_ok and ok
    except ImportError:
        print_status("numpy", False, "NOT INSTALLED")
        all_ok = False

    # onnxruntime-directml
    try:
        import onnxruntime as ort
        version = ort.__version__
        providers = ort.get_available_providers()
        dml = "DmlExecutionProvider" in providers
        print_status("onnxruntime-directml", True, version)
        print_status("DirectML Provider", dml, "AMD GPU acceleration")
        all_ok = all_ok and dml
    except ImportError:
        print_status("onnxruntime-directml", False, "NOT INSTALLED")
        all_ok = False

    # PyQt6
    try:
        from PyQt6.QtCore import QT_VERSION_STR
        print_status("PyQt6", True, QT_VERSION_STR)
    except ImportError:
        print_status("PyQt6", False, "NOT INSTALLED")
        all_ok = False

    # BeatNet
    try:
        from BeatNet.BeatNet import BeatNet
        print_status("BeatNet", True, "1.1.1")
    except ImportError as e:
        print_status("BeatNet", False, str(e)[:40])
        all_ok = False

    return all_ok

def check_amf():
    print_header("AMD AMF Encoder")

    try:
        from pb_studio.video.encoder_utils import get_encoder_info
        info = get_encoder_info()

        print_status("AMF Available", info["amf_available"])
        if info["amf_available"]:
            for codec in ["h264_amf", "hevc_amf", "av1_amf"]:
                if codec in info.get("available_encoders", []):
                    print_status(f"  {codec}", True)
        else:
            print("    Software fallback will be used (libx264/libx265)")

        return True  # Not critical - fallback exists
    except Exception as e:
        print_status("AMF Check", False, str(e)[:40])
        return False

def check_models():
    print_header("ONNX Models")

    models_dir = Path("models")

    models = {
        "Moondream": ["moondream.onnx", "moondream_encoder.onnx"],
        "RAFT": ["raft.onnx"],
        "UVR MDX": ["UVR-MDX-NET-Inst_HQ_3.onnx"]
    }

    all_ok = True
    for name, files in models.items():
        found = any((models_dir / f).exists() for f in files)
        print_status(name, found, "Found" if found else "Missing")
        if name == "UVR MDX":
            all_ok = all_ok and found  # Only UVR is required

    return all_ok

def check_modules():
    print_header("PB Studio Modules")

    modules = [
        "pb_studio.config_manager",
        "pb_studio.core.vram_arbiter",
        "pb_studio.audio.analyzer",
        "pb_studio.audio.separator",
        "pb_studio.video.moondream",
        "pb_studio.video.raft",
        "pb_studio.video.engine",
        "pb_studio.data.vector_store",
        "pb_studio.services.analysis_service",
        "pb_studio.services.generation_service",
    ]

    all_ok = True
    for mod in modules:
        try:
            __import__(mod)
            print_status(mod.split('.')[-1], True)
        except Exception as e:
            print_status(mod.split('.')[-1], False, str(e)[:30])
            all_ok = False

    return all_ok

def main():
    print()
    print("  PB Studio AMD Premium Edition - Status Check")
    print("  =============================================")

    results = []
    results.append(("Python", check_python()))
    results.append(("Packages", check_packages()))
    results.append(("AMF", check_amf()))
    results.append(("Models", check_models()))
    results.append(("Modules", check_modules()))

    print_header("Summary")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    for name, ok in results:
        print_status(name, ok)

    print()
    if passed == total:
        print("  STATUS: READY TO RUN")
        print("  Start with: python run_ui.py")
    else:
        print(f"  STATUS: {total - passed} issue(s) found")
        print("  Fix the issues above before running.")

    print()
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
