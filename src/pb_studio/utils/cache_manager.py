"""
Cache Manager für PB_studio AMD

Zentralisierte JSON-basierte Cache-Verwaltung mit MD5-Hashing.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CacheManager:
    """Generic JSON cache manager mit MD5-basiertem File-Naming."""

    def __init__(
        self,
        cache_dir: Path,
        prefix: str = "cache",
        ttl_seconds: int | None = None,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.prefix = prefix
        self.ttl_seconds = ttl_seconds

    def _get_cache_path(self, key: str) -> Path:
        hash_str = hashlib.md5(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{self.prefix}_{hash_str}.json"

    def load(self, key: str) -> dict[str, Any] | None:
        cache_file = self._get_cache_path(key)
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if self.ttl_seconds is not None and "_timestamp" in data:
                ts = datetime.fromisoformat(data["_timestamp"])
                age = (datetime.now() - ts).total_seconds()
                if age > self.ttl_seconds:
                    cache_file.unlink()
                    return None
            return data
        except (json.JSONDecodeError, ValueError):
            cache_file.unlink()
            return None

    def save(self, key: str, data: dict[str, Any]) -> None:
        cache_file = self._get_cache_path(key)
        if self.ttl_seconds is not None:
            data = data.copy()
            data["_timestamp"] = datetime.now().isoformat()
        cache_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def exists(self, key: str) -> bool:
        return self.load(key) is not None

    def invalidate(self, key: str) -> bool:
        cache_file = self._get_cache_path(key)
        if cache_file.exists():
            cache_file.unlink()
            return True
        return False

    def clear_all(self) -> int:
        files = list(self.cache_dir.glob(f"{self.prefix}_*.json"))
        for f in files:
            try:
                f.unlink()
            except Exception:
                pass
        return len(files)

    def get_cache_size(self) -> int:
        return sum(f.stat().st_size for f in self.cache_dir.glob(f"{self.prefix}_*.json"))

    def get_cache_info(self) -> dict[str, Any]:
        files = list(self.cache_dir.glob(f"{self.prefix}_*.json"))
        total = sum(f.stat().st_size for f in files)
        return {
            "file_count": len(files),
            "total_size_bytes": total,
            "total_size_mb": round(total / (1024 * 1024), 2),
            "cache_dir": str(self.cache_dir),
            "prefix": self.prefix,
        }
