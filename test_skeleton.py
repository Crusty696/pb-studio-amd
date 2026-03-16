import os
import sys

PROJECT = r"C:\Users\david\Dokumente\Pb_studio_AMD_version"
sys.path.insert(0, os.path.join(PROJECT, "src"))

from pb_studio.config_manager import ConfigManager
from pb_studio.core.crash_handler import CrashHandler
from pb_studio.utils.logging_setup import setup_logging

print("Testing Skeleton...")

# 1. Test Crash Handler
ch = CrashHandler()
print("[OK] CrashHandler initialized.")

# 2. Test Logging
log = setup_logging("test_run")
log.info("Test Log Message")
print("[OK] Logging initialized.")

# 3. Test Config
cfg = ConfigManager()
print(f"[OK] Config Loaded. App Name: {cfg.get('app_name')}")
print(f"    LHM Path: {cfg.lhm_path}")

print("--- Skeleton Verification Complete ---")
