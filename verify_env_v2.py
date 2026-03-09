import sys
import pkg_resources
import logging
import subprocess

logger = logging.getLogger("EnvVerifier")
logging.basicConfig(level=logging.INFO)

MUST_HAVE = {
    "numpy": "<2.0.0",
    "onnxruntime-directml": None,
    "BeatNet": "==1.1.1",
    "PyQt6": None
}

def verify():
    logger.info("Verifying Python Environment...")
    all_ok = True
    
    installed = {pkg.key: pkg.version for pkg in pkg_resources.working_set}
    
    # Special Check: Numpy < 2
    np_ver = installed.get("numpy")
    if np_ver:
        if np_ver.startswith("2."):
            logger.critical(f"CRITICAL: Numpy version {np_ver} is too new! BeatNet will crash.")
            all_ok = False
            # Auto-Fix attempt?
            # subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy<2.0", "--force-reinstall"])
    
    # Check others
    for pkg, constraint in MUST_HAVE.items():
        if pkg.lower() not in installed:
             logger.error(f"Missing package: {pkg}")
             all_ok = False
        else:
            ver = installed[pkg.lower()]
            logger.info(f"Found {pkg} == {ver}")
            # (Simple constraint logic skipped for brevity, focused on existence + numpy check)

    if not all_ok:
        logger.error("Environment verification FAILED.")
        return False
        
    logger.info("Environment looks GOOD.")
    return True

if __name__ == "__main__":
    if not verify():
        sys.exit(1)
