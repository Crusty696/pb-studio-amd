"""Tests für media_hash util (Plan Phase 1)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pb_studio.core.media_hash import media_hash


def test_media_hash_idempotent(tmp_path: Path):
    f = tmp_path / "a.bin"
    f.write_bytes(os.urandom(1024 * 1024))
    h1 = media_hash(f)
    h2 = media_hash(f)
    assert h1 == h2
    assert len(h1) == 64


def test_media_hash_distinct(tmp_path: Path):
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"hello")
    b.write_bytes(b"world")
    assert media_hash(a) != media_hash(b)


def test_media_hash_chunk_boundary(tmp_path: Path):
    """Verify streaming over multi-chunk file matches one-shot hash."""
    import hashlib

    payload = os.urandom(10 * 1024 * 1024)  # 10 MB > 4 MB chunk
    f = tmp_path / "big.bin"
    f.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()
    assert media_hash(f) == expected


def test_media_hash_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        media_hash(tmp_path / "ghost.bin")
