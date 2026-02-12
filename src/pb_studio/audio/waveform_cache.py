"""
Waveform Cache with LRU Eviction

Caches pre-computed 3-band waveforms to avoid redundant processing.
Implements Least Recently Used (LRU) eviction policy with file hash verification.
"""
import logging
import hashlib
import threading
import time
from typing import Dict, Optional
from pathlib import Path
from collections import OrderedDict
import numpy as np

logger = logging.getLogger(__name__)


class WaveformCache:
    """
    LRU Cache for 3-band waveform data.

    Caches waveform analysis results to avoid re-processing the same files.
    Uses file hash to detect changes and invalidate stale entries.
    """

    def __init__(self, max_size: int = 50, use_file_hash: bool = True):
        """
        Initialize WaveformCache.

        Args:
            max_size: Maximum number of cached waveforms (default 50)
            use_file_hash: Verify file integrity with hash (default True)
        """
        self.max_size = max_size
        self.use_file_hash = use_file_hash

        # OrderedDict maintains insertion order for LRU
        self.cache: OrderedDict[str, Dict] = OrderedDict()

        # Thread-Safety Lock (OrderedDict ist nicht thread-safe)
        self._lock = threading.Lock()

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0

        logger.info(f"WaveformCache initialized: max_size={max_size}, hash={use_file_hash}")

    def get(self, audio_path: str) -> Optional[Dict[str, np.ndarray]]:
        """
        Get cached waveform for audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            Cached waveform dict or None if not found/invalid
        """
        # Convert to absolute path for consistency
        abs_path = str(Path(audio_path).resolve())

        with self._lock:
            # Check if in cache
            if abs_path not in self.cache:
                self.misses += 1
                logger.debug(f"Cache MISS: {Path(audio_path).name}")
                return None

            # Retrieve cached entry
            entry = self.cache[abs_path]

            # Verify file hasn't changed (if hash is enabled)
            if self.use_file_hash:
                current_hash = self._compute_hash(abs_path)
                if current_hash != entry['hash']:
                    # File changed - invalidate cache
                    logger.info(f"Cache INVALID (file changed): {Path(audio_path).name}")
                    del self.cache[abs_path]
                    self.misses += 1
                    return None

            # Cache HIT - move to end (most recently used)
            self.cache.move_to_end(abs_path)
            self.hits += 1

            logger.debug(f"Cache HIT: {Path(audio_path).name}")
            return entry['waveform']

    def put(self, audio_path: str, waveform: Dict[str, np.ndarray]):
        """
        Cache waveform data for audio file.

        Args:
            audio_path: Path to audio file
            waveform: 3-band waveform dict with 'low', 'mid', 'high' keys
        """
        # Convert to absolute path
        abs_path = str(Path(audio_path).resolve())

        # Compute file hash
        file_hash = self._compute_hash(abs_path) if self.use_file_hash else None

        # Create cache entry
        entry = {
            'waveform': waveform,
            'hash': file_hash,
            'timestamp': time.time(),
            'size': self._estimate_size(waveform)
        }

        with self._lock:
            # Check if already exists (update case)
            if abs_path in self.cache:
                # Remove old entry
                del self.cache[abs_path]

            # Add to cache (at end = most recent)
            self.cache[abs_path] = entry

            # Enforce size limit with LRU eviction
            while len(self.cache) > self.max_size:
                # Pop first item (least recently used)
                evicted_path, evicted_entry = self.cache.popitem(last=False)
                self.evictions += 1
                logger.debug(f"Cache EVICT (LRU): {Path(evicted_path).name}")

        logger.debug(f"Cache PUT: {Path(audio_path).name} ({entry['size']} bytes)")

    def _compute_hash(self, file_path: str) -> str:
        """
        Compute SHA-256 hash of first 1MB of file + file size.

        Fast hash that detects file changes without reading entire file.

        Args:
            file_path: Path to file

        Returns:
            Hex string of SHA-256 hash
        """
        try:
            hasher = hashlib.sha256()

            # Dateigroesse als Praeambel einbeziehen (verhindert Kollisionen
            # bei Dateien mit gleichem Anfang aber verschiedenem Ende)
            file_size = Path(file_path).stat().st_size
            hasher.update(str(file_size).encode())

            with open(file_path, 'rb') as f:
                # Read first 1MB (sufficient for change detection)
                chunk = f.read(1024 * 1024)
                hasher.update(chunk)

            return hasher.hexdigest()

        except Exception as e:
            logger.warning(f"Hash computation failed: {e}")
            # Fallback to file size + mtime
            path = Path(file_path)
            return f"{path.stat().st_size}_{path.stat().st_mtime}"

    def _estimate_size(self, waveform: Dict[str, np.ndarray]) -> int:
        """
        Estimate memory size of waveform data in bytes.

        Args:
            waveform: Waveform dict

        Returns:
            Estimated size in bytes
        """
        total_bytes = 0
        for band_name, data in waveform.items():
            if isinstance(data, np.ndarray):
                total_bytes += data.nbytes
        return total_bytes

    def clear(self):
        """Clear all cached entries."""
        with self._lock:
            self.cache.clear()
        logger.info("Cache cleared")

    def remove(self, audio_path: str) -> bool:
        """
        Remove specific entry from cache.

        Args:
            audio_path: Path to audio file

        Returns:
            True if removed, False if not found
        """
        abs_path = str(Path(audio_path).resolve())

        with self._lock:
            if abs_path in self.cache:
                del self.cache[abs_path]
                logger.debug(f"Cache REMOVE: {Path(audio_path).name}")
                return True

        return False

    def get_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with hit rate, size, evictions, etc.
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0.0

        total_size = sum(entry['size'] for entry in self.cache.values())

        return {
            'hits': self.hits,
            'misses': self.misses,
            'evictions': self.evictions,
            'hit_rate': hit_rate,
            'size': len(self.cache),
            'max_size': self.max_size,
            'total_bytes': total_size
        }

    def print_stats(self):
        """Print cache statistics to logger."""
        stats = self.get_stats()
        logger.info(
            f"Cache Stats: {stats['hits']} hits, {stats['misses']} misses, "
            f"{stats['hit_rate']:.1f}% hit rate, {stats['size']}/{stats['max_size']} entries, "
            f"{stats['evictions']} evictions, {stats['total_bytes'] / (1024*1024):.2f} MB"
        )

    def get_entry_info(self, audio_path: str) -> Optional[Dict]:
        """
        Get metadata about cached entry.

        Args:
            audio_path: Path to audio file

        Returns:
            Dict with timestamp, size, hash or None if not cached
        """
        abs_path = str(Path(audio_path).resolve())

        if abs_path not in self.cache:
            return None

        entry = self.cache[abs_path]
        return {
            'timestamp': entry['timestamp'],
            'size_bytes': entry['size'],
            'hash': entry['hash'],
            'age_seconds': time.time() - entry['timestamp']
        }

    def __len__(self) -> int:
        """Return number of cached entries."""
        return len(self.cache)

    def __contains__(self, audio_path: str) -> bool:
        """Check if path is in cache."""
        abs_path = str(Path(audio_path).resolve())
        return abs_path in self.cache
