"""Verify sqlite-vec works for KNN-Search on Windows (Plan Phase 0/2).

Builds an in-memory store, inserts random 768-dim vectors, runs KNN.
Exits 0 on success.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path


def main() -> int:
    sys.path.insert(0, "src")
    import numpy as np

    from pb_studio.storage.embedding_repository import (
        EmbeddingRepository,
        VIDEO_DIM,
    )

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "verify.db"
        repo = EmbeddingRepository(db)
        try:
            rng = np.random.default_rng(0)
            n = 256
            t0 = time.time()
            for i in range(n):
                emb = rng.standard_normal(VIDEO_DIM).astype(np.float32)
                repo.add_video_unit(
                    parent_id=None,
                    level="scene",
                    media_id=i,
                    media_hash=f"{i:032x}",
                    start_time=0.0,
                    end_time=1.0,
                    embedding=emb,
                )
            dt_insert = time.time() - t0

            query = rng.standard_normal(VIDEO_DIM).astype(np.float32)
            t0 = time.time()
            hits = repo.search_video(query, level="scene", limit=10)
            dt_search = time.time() - t0

            print(f"inserted: {n} units in {dt_insert*1000:.1f}ms")
            print(f"knn hits: {len(hits)} in {dt_search*1000:.1f}ms")
            if not hits:
                print("FAIL: empty search result")
                return 1
            print(f"top hit: unit_id={hits[0].unit_id} d={hits[0].distance:.4f}")
            print("OK")
            return 0
        finally:
            repo.close()


if __name__ == "__main__":
    raise SystemExit(main())
