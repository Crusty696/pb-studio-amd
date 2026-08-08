"""Canonical local runtime paths for PB Studio."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "config" / "ffmpeg-runtime.json"


@lru_cache(maxsize=1)
def _manifest() -> dict:
    with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("schema_version") != 1:
        raise RuntimeError(
            f"Unsupported FFmpeg runtime manifest: {MANIFEST_PATH}"
        )
    return manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


@lru_cache(maxsize=1)
def verified_ffmpeg_pair() -> tuple[Path, Path]:
    manifest = _manifest()
    stable_bin = PROJECT_ROOT / manifest["stable_bin"]
    ffmpeg = stable_bin / "ffmpeg.exe"
    ffprobe = stable_bin / "ffprobe.exe"
    expected = {
        ffmpeg: manifest["active"]["ffmpeg_sha256"].upper(),
        ffprobe: manifest["active"]["ffprobe_sha256"].upper(),
    }
    for path, expected_hash in expected.items():
        if not path.is_file():
            raise RuntimeError(f"Canonical runtime missing: {path}")
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"Canonical runtime hash mismatch for {path.name}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
    return ffmpeg.resolve(), ffprobe.resolve()


def ffmpeg_path() -> Path:
    return verified_ffmpeg_pair()[0]


def ffprobe_path() -> Path:
    return verified_ffmpeg_pair()[1]
