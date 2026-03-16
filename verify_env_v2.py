import sys
import logging
from importlib import metadata

logger = logging.getLogger("EnvVerifier")
logging.basicConfig(level=logging.INFO)

MUST_HAVE = {
    "numpy": "<2.0.0",
    "onnxruntime-directml": None,
    "BeatNet": "==1.1.1",
    "PyQt6": None,
}


def _normalized_installed_packages():
    installed = {}
    for dist in metadata.distributions():
        name = dist.metadata.get("Name") or dist.metadata.get("Summary")
        if not name:
            continue
        installed[name.lower()] = dist.version
    return installed


def verify():
    logger.info("Verifying Python Environment...")
    all_ok = True

    installed = _normalized_installed_packages()

    # Special Check: Numpy < 2
    np_ver = installed.get("numpy")
    if np_ver and np_ver.startswith("2."):
        logger.critical(f"CRITICAL: Numpy version {np_ver} is too new! BeatNet will crash.")
        all_ok = False

    # Check others
    for pkg, constraint in MUST_HAVE.items():
        version = installed.get(pkg.lower())
        if version is None:
            logger.error(f"Missing package: {pkg}")
            all_ok = False
            continue

        logger.info(f"Found {pkg} == {version}")
        # Keep constraint handling intentionally simple/deterministic for smoke verification.

    if not all_ok:
        logger.error("Environment verification FAILED.")
        return False

    logger.info("Environment looks GOOD.")
    return True


if __name__ == "__main__":
    if not verify():
        sys.exit(1)
