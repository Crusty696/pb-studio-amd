"""Verify SigLIP-2 video embedding works on torch-directml (Plan Phase 2).

Usage:
    python scripts/verify_siglip_directml.py [video_file]

Exits 0 on success.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def _find_test_video() -> Path | None:
    candidates = [
        Path("Tests/data/test_clip.mp4"),
        Path("Tests/data"),
    ]
    for c in candidates:
        if c.is_file():
            return c
        if c.is_dir():
            for ext in ("*.mp4", "*.mov", "*.mkv"):
                hits = list(c.glob(ext))
                if hits:
                    return hits[0]
    return None


def main() -> int:
    sys.path.insert(0, "src")
    from pb_studio.video.video_embedder import EMBED_DIM, get_video_embedder

    video = Path(sys.argv[1]) if len(sys.argv) > 1 else _find_test_video()
    if not video or not video.is_file():
        print("ERROR: Pass a video path or place a sample under Tests/data/")
        return 2

    print(f"Video: {video}")
    embedder = get_video_embedder(prefer_directml=True)

    # 1 dummy scene over the first 5 seconds
    scenes = [(0.0, 5.0)]

    t0 = time.time()
    result = embedder.embed_scenes(video, scenes=scenes, batch_size=1)
    dt = time.time() - t0

    print(f"Device:     {embedder._device}")
    print(f"clip shape: {result.clip_embedding.shape}")
    print(f"scene cnt:  {len(result.scene_embeddings)}")
    print(f"first 4:    {result.clip_embedding[:4]}")
    print(f"elapsed:    {dt:.2f}s")

    if result.clip_embedding.shape != (EMBED_DIM,):
        print("FAIL: embedding shape unexpected")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
