"""
Backfill des Brain-EmbeddingCache aus dem bestehenden FAISS-Video-Index.

Audit 2026-08-05 (C-3)
----------------------
``EmbeddingCache.store()`` hatte im gesamten Produktivcode keinen Aufrufer.
Empirisch: ``media_embedding_index`` = 0 Zeilen, ``brain/embeddings/`` = 0
Dateien, seit Anlage am 2026-05-31.

Die SigLIP-Vektoren existieren aber laengst — sie liegen im FAISS-Index
``video_index`` und sind ueber ``vector_map`` an ``media.id`` gebunden. Der
Brain-Post-Processor sucht dagegen ueber ``media_hash``. Genau diese
Store-Domain-Divergenz ist der Grund, warum ``semantic_match_weight`` in 0 von
2576 Cuts vorkam.

Dieses Skript schliesst die Luecke ohne eine einzige Neuanalyse:
    vector_map(faiss_id, media_id) -> media.file_hash
    FAISS.reconstruct(faiss_id)    -> 1152-D Vektor
    EmbeddingCache.store(media_hash=file_hash, media_type="video", ...)

Der laufende Fix in ``video_router._store_video_embedding_in_brain_cache``
sorgt dafuer, dass kuenftige Analysen direkt beide Stores fuellen.

Aufruf:
    $env:PYTHONPATH = (Join-Path (Get-Location) "src")
    .\.venv\Scripts\python.exe scripts\backfill_brain_embedding_cache.py --dry-run
    .\.venv\Scripts\python.exe scripts\backfill_brain_embedding_cache.py --apply
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "data" / "pb_studio.db"


def backfill(db_path: Path, apply: bool) -> int:
    sys.path.insert(0, str(REPO_ROOT / "src"))

    import numpy as np

    from pb_studio.brain.brain_service import BrainService
    from pb_studio.data.vector_store import VectorStore
    from pb_studio.video import video_embedder

    store = VectorStore(index_name="video_index")
    index = store.index
    tombstoned = set(getattr(store, "tombstoned_ids", set()) or set())

    connection = sqlite3.connect(db_path)
    rows = connection.execute(
        "SELECT vm.faiss_id, m.file_hash "
        "FROM vector_map vm JOIN media m ON m.id = vm.media_id "
        "WHERE m.file_hash IS NOT NULL AND m.file_hash != ''"
    ).fetchall()
    connection.close()

    cache = getattr(BrainService.get().brain, "cache", None)
    if cache is None:
        print("Brain-Cache nicht verfuegbar — Abbruch.", file=sys.stderr)
        return 0

    total = len(rows)
    skipped_tombstone = 0
    already = 0
    written = 0
    failed = 0
    seen_hashes: set[str] = set()

    for faiss_id, file_hash in rows:
        faiss_id = int(faiss_id)
        media_hash = str(file_hash)

        if faiss_id in tombstoned:
            skipped_tombstone += 1
            continue
        # Ein Hash braucht genau einen Cache-Eintrag; mehrere Projekte teilen
        # sich denselben Dateiinhalt.
        if media_hash in seen_hashes:
            continue
        seen_hashes.add(media_hash)

        existing = cache.lookup(
            media_hash,
            video_embedder.CURRENT_MODEL_NAME,
            video_embedder.CURRENT_MODEL_VERSION,
        )
        if existing is not None:
            already += 1
            continue

        try:
            vector = np.asarray(index.reconstruct(faiss_id), dtype=np.float32)
        except Exception as exc:  # noqa: BLE001 - defekte IDs ueberspringen
            failed += 1
            print(f"  reconstruct({faiss_id}) fehlgeschlagen: {exc}")
            continue

        if vector.size != video_embedder.EMBED_DIM:
            failed += 1
            continue

        if apply:
            try:
                cache.store(
                    media_hash=media_hash,
                    media_type="video",
                    embedding=vector,
                    model_name=video_embedder.CURRENT_MODEL_NAME,
                    model_version=video_embedder.CURRENT_MODEL_VERSION,
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"  store({media_hash[:12]}...) fehlgeschlagen: {exc}")
                continue
        written += 1

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"[{mode}] vector_map-Eintraege mit Hash: {total}")
    print(f"[{mode}] Tombstones uebersprungen:      {skipped_tombstone}")
    print(f"[{mode}] bereits im Cache:              {already}")
    print(f"[{mode}] geschrieben / schreibbar:      {written}")
    print(f"[{mode}] fehlgeschlagen:                {failed}")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True)
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"DB nicht gefunden: {args.db}", file=sys.stderr)
        return 2

    backfill(args.db, apply=bool(args.apply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
