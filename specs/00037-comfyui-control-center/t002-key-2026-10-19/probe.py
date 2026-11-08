"""Bounded, read-only T002 CPU key probe for the selected 30-second excerpts."""
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUN = ROOT / "scratch" / ("t002-key-" + time.strftime("%Y%m%d-%H%M%S"))
RUN.mkdir(parents=True, exist_ok=False)
REAL_APPDATA = Path(os.environ["APPDATA"])
REAL_LOCALAPPDATA = Path(os.environ["LOCALAPPDATA"])
for name in ("APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "NUMBA_CACHE_DIR"):
    path = RUN / name
    path.mkdir()
    os.environ[name] = str(path)
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
sys.path.insert(0, str(ROOT / "src"))

import librosa
import numpy as np


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


manifest = json.loads((OUT.parent / "reference-manifest.json").read_text(encoding="utf-8"))
sources = [item for item in manifest["sources"] if item["source_id"] in {"A01", "A02", "A03"}]
if len(sources) != 3:
    raise RuntimeError("three selected audio sources required")
protected = [ROOT / "config.json", ROOT / "data/pb_studio.db",
             ROOT / "data/pb_studio.db-wal", ROOT / "data/pb_studio.db-shm",
             REAL_LOCALAPPDATA / "PB_Studio/recovery-control/v1/RUNTIME_DIRTY"]
protected += list((REAL_APPDATA / "PB_Studio/brain").glob("*.db*"))
protected += [Path(item["absolute_path"]) for item in sources]


def snapshot():
    return {str(path): digest(path) if path.is_file() else None for path in protected}


before = snapshot()
for item in sources:
    if before[item["absolute_path"]] != item["sha256"]:
        raise RuntimeError(f"source manifest drift: {item['source_id']}")

module_path = ROOT / "src/pb_studio/audio/key_detector.py"
spec = importlib.util.spec_from_file_location("t002_key_detector", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
messages = []


class WarningCapture(logging.Handler):
    def emit(self, record):
        messages.append({"level": record.levelname, "message": record.getMessage()})


handler = WarningCapture()
handler.setLevel(logging.WARNING)
module.logger.addHandler(handler)
result = {"scope": "CPU key module, source seconds 60-90; no GUI or musical truth",
          "run_directory": str(RUN), "code_sha256": digest(module_path),
          "versions": {"python": sys.version, "numpy": np.__version__,
                       "librosa": librosa.__version__},
          "protection_before": before, "sources": []}
deadline = time.monotonic() + 300
try:
    for item in sources:
        if time.monotonic() >= deadline:
            raise TimeoutError("overall probe budget exhausted")
        decoded = subprocess.run(
            [str(ROOT / "tools/ffmpeg/bin/ffmpeg.exe"), "-v", "error", "-nostdin",
             "-threads", "2", "-ss", "60", "-i", item["absolute_path"], "-t", "30",
             "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "22050", "-f", "f32le", "pipe:1"],
            check=True, capture_output=True, timeout=min(90, max(1, deadline - time.monotonic())))
        y = np.frombuffer(decoded.stdout, dtype="<f4").copy()
        if len(y) != 30 * 22050 or not np.isfinite(y).all():
            raise RuntimeError(f"invalid decoded excerpt: {item['source_id']}")
        detector = module.KeyDetector()
        started = time.perf_counter()
        first = detector.detect_key(y, 22050)
        second = detector.detect_key(y, 22050)
        chroma_mean = np.mean(librosa.feature.chroma_cqt(
            y=y, sr=22050, hop_length=detector.hop_length), axis=1)
        from_chroma = detector.detect_key_from_chroma(chroma_mean)
        duration = time.perf_counter() - started
        if (time.monotonic() > deadline or first == "Unknown" or
                first != second or first != from_chroma or messages):
            raise RuntimeError(f"key contract mismatch: {item['source_id']}")
        result["sources"].append({"id": item["source_id"], "source_sha256": item["sha256"],
                                  "source_window": [60, 90], "samples": len(y),
                                  "first": first, "second": second,
                                  "from_same_chroma": from_chroma,
                                  "analysis_seconds": duration})
        print(item["source_id"], first, round(duration, 2), flush=True)
    result["technical_status"] = "PASS"
except Exception as error:
    result["technical_status"] = "FAIL"
    result["error"] = repr(error)
    raise
finally:
    result["warnings"] = messages
    result["protection_after"] = snapshot()
    result["protected_files_unchanged"] = before == result["protection_after"]
    (OUT / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False),
                                     encoding="utf-8")
if not result["protected_files_unchanged"]:
    raise RuntimeError("protected file changed")
