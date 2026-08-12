"""Canonical local runtime paths for PB Studio."""

from functools import lru_cache
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "config" / "ffmpeg-runtime.json"
APPSETTINGS_PATH = PROJECT_ROOT / "appsettings.json"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True)
class BackendEndpoint:
    scheme: str
    host: str
    port: int

    @property
    def base_url(self) -> str:
        authority = f"[{self.host}]" if self.host == "::1" else self.host
        return f"{self.scheme}://{authority}:{self.port}"


def validate_backend_url(value: str) -> str:
    if not value.startswith("http://"):
        raise RuntimeError("Backend URL scheme must be exactly http")
    parsed = urlparse(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise RuntimeError("Backend URL has an invalid port") from exc
    canonical_host = parsed.hostname
    canonical_authority = (
        f"[{canonical_host}]:{port}"
        if canonical_host == "::1"
        else f"{canonical_host}:{port}"
    )
    if (
        parsed.scheme != "http"
        or canonical_host not in LOOPBACK_HOSTS
        or port is None
        or not 1 <= port <= 65535
        or parsed.netloc != canonical_authority
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError(
            "Backend URL must be an absolute HTTP loopback origin"
        )
    return f"http://{parsed.netloc}"


@lru_cache(maxsize=1)
def backend_endpoint() -> BackendEndpoint:
    try:
        payload = json.loads(APPSETTINGS_PATH.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict) or set(payload) != {"Backend"}:
            raise ValueError("Root settings must contain Backend only")
        backend = payload["Backend"]
        if set(backend) != {"Scheme", "Host", "Port"}:
            raise ValueError("Backend must contain Scheme, Host and Port only")
        scheme = backend["Scheme"]
        host = os.environ.get("PBSTUDIO_HOST", backend["Host"])
        raw_port = os.environ.get("PBSTUDIO_PORT", backend["Port"])
        if isinstance(raw_port, str):
            if not raw_port.isascii() or not raw_port.isdecimal():
                raise ValueError("PBSTUDIO_PORT must be a decimal integer")
            port = int(raw_port)
        else:
            port = raw_port
        if not isinstance(scheme, str) or not isinstance(host, str):
            raise ValueError("Backend.Scheme and Backend.Host must be strings")
        if scheme != "http" or host not in LOOPBACK_HOSTS:
            raise ValueError("Backend Scheme or Host is not canonical")
        if isinstance(port, bool) or not isinstance(port, int):
            raise ValueError("Backend.Port must be an integer")
        endpoint = BackendEndpoint(scheme=scheme, host=host, port=port)
        validate_backend_url(endpoint.base_url)
        return endpoint
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Invalid PB Studio backend contract: {APPSETTINGS_PATH}"
        ) from exc


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
