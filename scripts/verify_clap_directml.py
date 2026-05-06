"""Verify CLAP audio embedding works on torch-directml (Plan Phase 2).

Usage:
    python scripts/verify_clap_directml.py [audio_file]

Exits 0 on success, prints embedding shape + first 4 elements.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def _find_test_audio() -> Path | None:
    candidates = [
        Path("Tests/data/test_mix.mp3"),
        Path("Tests/data/sample.wav"),
        Path("Tests/data"),
    ]
    for c in candidates:
        if c.is_file():
            return c
        if c.is_dir():
            for ext in ("*.mp3", "*.wav", "*.flac"):
                hits = list(c.glob(ext))
                if hits:
                    return hits[0]
    return None


def main() -> int:
    sys.path.insert(0, "src")
    from pb_studio.audio.audio_embedder import (
        EMBED_DIM,
        get_audio_embedder,
    )

    audio = Path(sys.argv[1]) if len(sys.argv) > 1 else _find_test_audio()
    if not audio or not audio.is_file():
        print("ERROR: Pass an audio path or place a sample under Tests/data/")
        return 2

    print(f"Audio: {audio}")
    embedder = get_audio_embedder(prefer_directml=True)

    t0 = time.time()
    result = embedder.embed_audio(audio)
    dt = time.time() - t0

    print(f"Device:     {embedder._device}")
    print(f"mix shape:  {result.mix_embedding.shape}")
    print(f"window cnt: {len(result.window_embeddings)}")
    print(f"first 4:    {result.mix_embedding[:4]}")
    print(f"elapsed:    {dt:.2f}s")

    if result.mix_embedding.shape != (EMBED_DIM,):
        print("FAIL: embedding shape unexpected")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
