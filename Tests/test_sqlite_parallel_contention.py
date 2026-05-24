"""Regressionstest zur Verifikation von SQLite Connection-Safety und Lock-Contention unter hoher paralleler Last.

T3.1: Startet 5 parallele Schreib- und 5 parallele Lese-Threads gegen das EmbeddingRepository
und verifiziert, dass dank WAL-Modus und BEGIN IMMEDIATE Transaktionssicherung keine 'database is locked'
Errors auftreten.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import pytest

from pb_studio.storage.embedding_repository import (
    AUDIO_DIM,
    VIDEO_DIM,
    EmbeddingRepository,
)


def test_sqlite_parallel_write_read_contention(tmp_path: Path):
    """Verifiziert die absolute Blockierungsfreiheit des EmbeddingRepository unter Last."""
    db_path = tmp_path / "contention_test.db"
    repo = EmbeddingRepository(db_path)
    
    # Zustandsspeicherung für Threads
    errors: list[Exception] = []
    stop_event = threading.Event()
    
    rng = np.random.default_rng(42)
    dummy_audio_embedding = rng.standard_normal(AUDIO_DIM).astype(np.float32)
    dummy_video_embedding = rng.standard_normal(VIDEO_DIM).astype(np.float32)
    
    # 1. Schreib-Thread
    def writer_target(thread_id: int):
        local_rng = np.random.default_rng(100 + thread_id)
        counter = 0
        while not stop_event.is_set():
            try:
                # Schnelle Schreibvorgänge abwechselnd Audio / Video
                counter += 1
                if counter % 2 == 0:
                    repo.add_audio_unit(
                        parent_id=None,
                        level="window",
                        media_id=thread_id,
                        media_hash=f"hash_w_{thread_id}_{counter}",
                        start_time=float(counter),
                        end_time=float(counter + 1),
                        embedding=dummy_audio_embedding,
                        metadata={"thread": thread_id, "loop": counter},
                    )
                else:
                    repo.add_video_unit(
                        parent_id=None,
                        level="scene",
                        media_id=thread_id,
                        media_hash=f"hash_v_{thread_id}_{counter}",
                        start_time=float(counter),
                        end_time=float(counter + 1),
                        embedding=dummy_video_embedding,
                        motion_score=local_rng.random(),
                        brightness=local_rng.random(),
                        saturation=local_rng.random(),
                        color_temp=local_rng.random(),
                    )
                # Kurze Pause zur Simulation realer Inferenz-Intervalle (10ms)
                time.sleep(0.01)
            except Exception as exc:
                errors.append(exc)
                break

    # 2. Lese-Thread
    def reader_target(thread_id: int):
        while not stop_event.is_set():
            try:
                # Schnelle Suchen und Lesezugriffe
                repo.search_audio(dummy_audio_embedding, level="window", limit=5)
                repo.search_video(dummy_video_embedding, level="scene", limit=5)
                
                # Kurze Pause (10ms)
                time.sleep(0.01)
            except Exception as exc:
                errors.append(exc)
                break

    # 3. Spawne Threads
    threads: list[threading.Thread] = []
    
    # 5 Writer, 5 Reader
    for i in range(5):
        w = threading.Thread(target=writer_target, args=(i,), daemon=True, name=f"stress-writer-{i}")
        r = threading.Thread(target=reader_target, args=(i,), daemon=True, name=f"stress-reader-{i}")
        threads.extend([w, r])
        
    for t in threads:
        t.start()
        
    # 4. Dauerfeuer fuer 2 Sekunden aufrechterhalten
    time.sleep(2.0)
    
    # 5. Stoppen und Cleanup
    stop_event.set()
    for t in threads:
        t.join(timeout=1.0)
        
    repo.close()
    
    # 6. Verifikation: Keine Fehler geworfen!
    if errors:
        for err in errors:
            print(f"[ERROR IN THREAD]: {err}")
        pytest.fail(f"SQLite Parallel-Load fehlgeschlagen: {len(errors)} Thread-Fehler aufgetreten! Erster Fehler: {errors[0]}")
