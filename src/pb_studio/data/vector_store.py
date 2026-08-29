import atexit
import faiss
import numpy as np
import logging
import json
import math
import os
import pickle
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional
from pb_studio.config_manager import ConfigManager
from pb_studio.storage.recovery_barrier import (
    RecoveryBusyError,
    recovery_write_operation,
)

logger = logging.getLogger(__name__)

_vs_lock = threading.Lock()
# L-VIDEO-1 / L-STATE-3 Sub-Fix: atexit darf NUR EINMAL pro Prozess registriert
# werden. __new__ erlaubt index_name-Wechsel (= neue Instanz) und __init__ wuerde
# bei jedem Wechsel atexit.register erneut aufrufen — die atexit-Liste waechst
# unbegrenzt und triggert bei Shutdown N save-Calls. Module-Level Flag verhindert
# das. Cleanup arbeitet weiter korrekt weil der Handler self._save_on_exit ueber
# das aktuelle cls._instance referenziert.
_atexit_registered: bool = False


class _RestrictedMetadataUnpickler(pickle.Unpickler):
    """Legacy metadata may contain data only; global object loading is forbidden."""

    def find_class(self, module: str, name: str):
        raise pickle.UnpicklingError(
            f"Legacy metadata may not load global {module}.{name}"
        )


def _validate_legacy_metadata(value, *, _seen: set[int] | None = None):
    """Accept only ``dict[int, dict[str, JSON-value]]`` legacy metadata."""
    if type(value) is not dict:
        raise ValueError("Legacy metadata muss ein dict sein")

    seen = _seen if _seen is not None else set()
    result: dict[int, dict] = {}
    for key, metadata in value.items():
        if type(key) is not int or type(metadata) is not dict:
            raise ValueError("Legacy metadata muss dict[int, dict] sein")
        result[key] = _validate_legacy_json_value(metadata, seen=seen)
    return result


def _validate_legacy_json_value(value, *, seen: set[int]):
    """Copy a JSON-compatible value while rejecting cycles and custom objects."""
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Legacy metadata darf nur endliche Zahlen enthalten")
        return value

    if type(value) in (str, int, bool, type(None)):
        return value

    if type(value) is list:
        value_id = id(value)
        if value_id in seen:
            raise ValueError("Legacy metadata darf keine zyklischen Listen enthalten")
        seen.add(value_id)
        try:
            return [_validate_legacy_json_value(item, seen=seen) for item in value]
        finally:
            seen.remove(value_id)

    if type(value) is dict:
        value_id = id(value)
        if value_id in seen:
            raise ValueError("Legacy metadata darf keine zyklischen dicts enthalten")
        seen.add(value_id)
        try:
            result: dict[str, object] = {}
            for key, item in value.items():
                if type(key) is not str:
                    raise ValueError("Legacy metadata dict keys muessen strings sein")
                result[key] = _validate_legacy_json_value(item, seen=seen)
            return result
        finally:
            seen.remove(value_id)

    raise ValueError(
        f"Legacy metadata enthaelt nicht-JSON Typ: {type(value).__name__}"
    )


class VectorStore:
    _instance: "VectorStore | None" = None
    _instance_index_name: str | None = None

    def __new__(cls, index_name: str = "main_index", dimension=None):
        with _vs_lock:
            current = cls._instance
            needs_new = (
                current is None
                or cls._instance_index_name != index_name
                or getattr(current, "_closed", False)
            )
            if needs_new:
                if current is not None and not getattr(current, "_closed", False):
                    current.close()
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
                cls._instance_index_name = index_name
            return cls._instance

    def __init__(self, index_name: str = "main_index", dimension=None):
        if getattr(self, '_initialized', False):
            return
        self._initialized = True

        self.config = ConfigManager()
        self.data_dir = Path(self.config.get("paths", {}).get("db_path", "./data")).parent
        self.index_path = self.data_dir / f"{index_name}.faiss"
        self.meta_path = self.data_dir / f"{index_name}_meta.json"
        self.tombstone_path = self.data_dir / f"{index_name}_tombstones.json"
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()

        # BUGFIX C1: single coalescing background writer instead of a fresh
        # daemon thread + full faiss.clone_index() per add_embedding. The old
        # design spawned unbounded threads (thousands on a bulk import), each
        # pinning its own full-index clone in RAM and racing to write the SAME
        # file with no ordering guarantee -> an early/stale snapshot could win
        # and, on a crash after import, most embeddings were lost on next start.
        # Now: add/tombstone only mark dirty + notify; ONE writer thread clones
        # the current state under _lock and writes it atomically, debounced, so
        # bursts coalesce and the on-disk file always reflects the newest state.
        self._save_debounce_sec = 2.0
        self._save_dirty = False
        self._save_generation = 0
        self._save_cv = threading.Condition()
        self._writer_stop = False
        self._closed = False
        self._writer_thread = threading.Thread(
            target=self._writer_loop, name=f"vs-writer-{index_name}", daemon=True
        )

        # Dimension: Auto-detect from config or first embedding
        # SigLIP SO400M = 1152, CLIP = 768, smaller models may use 512
        # FIXED: Default changed from 768 to 1152 for SigLIP compatibility
        self.dimension = dimension or self.config.get("vector_store", {}).get("dimension", 1152)
        self.index = None
        self.metadata = {} # Map faiss_id -> dict (media_id, desc, etc)

        # Y6 / L-STATE-2: Tombstone-Set fuer "weggeloeschte" FAISS-IDs.
        # FAISS IndexFlatIP hat keine Remove-Operation — wir filtern Hits in search()
        # gegen diese Liste. Wird via mark_tombstoned() von delete_audio/video_clip
        # gepflegt (cascade-driven aus vector_map).
        self._tombstoned_ids: set[int] = set()

        self._load_index()
        # BUGFIX C1: start the single coalescing writer after the index is loaded.
        self._writer_thread.start()
        # L-VIDEO-1 Sub-Fix: nur einmal registrieren, auch bei Index-Name-Wechsel.
        global _atexit_registered
        if not _atexit_registered:
            atexit.register(VectorStore._save_active_on_exit)
            _atexit_registered = True

    @staticmethod
    def _save_active_on_exit(
        _faiss_ref=faiss,
        _json_ref=json,
        _os_ref=os,
        _logger_ref=logger,
        _path_ref=Path
    ) -> None:
        """L-VIDEO-1 Sub-Fix: atexit-Handler greift auf aktuell aktive Instanz zu.
        Verhindert dass N alte Instanzen ihre toten Indizes ueberschreiben.
        Hält starke Referenzen auf Module zur Shutdown-Sicherheit (T-DATA-01)."""
        inst = VectorStore._instance
        if inst is not None and not getattr(inst, "_closed", False):
            try:
                inst._stop_writer()
                inst._save_on_exit(
                    faiss_mod=_faiss_ref,
                    json_mod=_json_ref,
                    os_mod=_os_ref,
                    logger_mod=_logger_ref,
                    path_class=_path_ref
                )
                inst._closed = True
            except Exception:
                # atexit darf niemals werfen — "nicht werfen" ist aber nicht
                # dasselbe wie "nicht melden": ohne Log und Dirty-Marker gehen
                # alle seit dem letzten Write ergaenzten Embeddings spurlos
                # verloren.
                _logger_ref.critical(
                    "FAISS-Abschluss-Save beim Prozessende fehlgeschlagen — "
                    "seit dem letzten Write ergaenzte Embeddings sind verloren",
                    exc_info=True,
                )
                inst._mark_dirty("atexit save failed")

    def _snapshot_targets(self) -> tuple[Path, Path, Path]:
        return (
            Path(self.index_path),
            Path(self.meta_path),
            Path(self.tombstone_path),
        )

    def _snapshot_journal_path(self) -> Path:
        return Path(str(self.index_path) + ".txn.json")

    def _recover_incomplete_snapshot(
        self,
        *,
        os_mod=os,
        shutil_mod=shutil,
        path_class=Path,
    ) -> bool:
        """Restore the previous three-file generation when a journal exists."""
        journal_path = self._snapshot_journal_path()
        if not journal_path.exists():
            return False

        targets = self._snapshot_targets()
        logger.warning(
            "Incomplete FAISS snapshot transaction detected; restoring backups"
        )

        for target in targets:
            backup = path_class(str(target) + ".bak")
            restore_temp = path_class(str(target) + ".restore")
            if backup.exists():
                shutil_mod.copy2(backup, restore_temp)
                os_mod.replace(str(restore_temp), str(target))
            else:
                target.unlink(missing_ok=True)

        for target in targets:
            path_class(str(target) + ".tmp").unlink(missing_ok=True)
        journal_path.unlink(missing_ok=True)
        for target in targets:
            path_class(str(target) + ".bak").unlink(missing_ok=True)

        logger.info("Previous FAISS snapshot generation restored")
        return True

    def _commit_snapshot_files(
        self,
        temp_paths,
        *,
        json_mod=json,
        os_mod=os,
        shutil_mod=shutil,
        path_class=Path,
    ) -> None:
        """Publish index, metadata and tombstones as one recoverable generation."""
        targets = self._snapshot_targets()
        temp_paths = tuple(path_class(path) for path in temp_paths)
        if len(temp_paths) != len(targets):
            raise ValueError("FAISS snapshot commit requires exactly three files")

        self._recover_incomplete_snapshot(
            os_mod=os_mod,
            shutil_mod=shutil_mod,
            path_class=path_class,
        )

        journal_path = self._snapshot_journal_path()
        journal_temp = path_class(str(journal_path) + ".tmp")
        backups = tuple(path_class(str(target) + ".bak") for target in targets)

        for backup in backups:
            backup.unlink(missing_ok=True)

        had_original = []
        for target, backup in zip(targets, backups):
            exists = target.exists()
            had_original.append(exists)
            if exists:
                shutil_mod.copy2(target, backup)

        try:
            with journal_temp.open("w", encoding="utf-8") as handle:
                json_mod.dump(
                    {
                        "version": 1,
                        "targets": [str(path) for path in targets],
                        "had_original": had_original,
                    },
                    handle,
                )
                handle.flush()
                os_mod.fsync(handle.fileno())
            os_mod.replace(str(journal_temp), str(journal_path))

            for temp_path, target in zip(temp_paths, targets):
                os_mod.replace(str(temp_path), str(target))

            journal_path.unlink()
        except Exception:
            if journal_path.exists():
                self._recover_incomplete_snapshot(
                    os_mod=os_mod,
                    shutil_mod=shutil_mod,
                    path_class=path_class,
                )
            raise
        finally:
            journal_temp.unlink(missing_ok=True)

        for backup in backups:
            backup.unlink(missing_ok=True)


    def _load_index(self):
        self._recover_incomplete_snapshot()
        if self.index_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                # FIXED: Update dimension from loaded index
                if self.index:
                    self.dimension = self.index.d
                
                # FIXED: Load metadata from JSON (or migrate from legacy pickle)
                if self.meta_path.exists():
                    try:
                        with open(self.meta_path, "r") as f:
                            raw_meta = json.load(f)
                            # JSON konvertiert int-Keys zu Strings - zurueck konvertieren
                            self.metadata = {}
                            for k, v in raw_meta.items():
                                try:
                                    self.metadata[int(k)] = v
                                except (ValueError, TypeError):
                                    logger.warning(f"Skipping invalid FAISS metadata key: {k}")
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to load metadata from {self.meta_path}, starting fresh")
                        self.metadata = {}
                else:
                    # Check for legacy .pkl file
                    legacy_path = self.meta_path.with_suffix(".pkl")
                    if legacy_path.exists():
                        logger.info("Migrating legacy metadata from pickle to JSON...")
                        try:
                            self._migrate_legacy_metadata(legacy_path)
                        except Exception as e:
                            logger.error(f"Failed to migrate legacy pickle: {e}")
                            self.metadata = {}

                # B-7 FIX: Tombstones laden
                if getattr(self, "tombstone_path", None) and self.tombstone_path.exists():
                    try:
                        with open(self.tombstone_path, "r") as f:
                            self._tombstoned_ids = set(json.load(f))
                    except Exception as e:
                        logger.warning(f"Failed to load tombstones: {e}")

                logger.info(f"FAISS Index loaded. Size: {self.index.ntotal}, Dim: {self.dimension}")
            except Exception as e:
                logger.error(f"Failed to load FAISS index: {e}. Creating new.")
                self._create_new_index()
        else:
            self._create_new_index()

    def _migrate_legacy_metadata(self, legacy_path: Path) -> None:
        """Migrate primitive-only legacy metadata through atomic snapshot save."""
        with legacy_path.open("rb") as handle:
            legacy_metadata = _RestrictedMetadataUnpickler(handle).load()

        self.metadata = _validate_legacy_metadata(legacy_metadata)
        # ``_write_snapshot`` reports a failed atomic publish; ``save`` logs
        # and swallows write errors, so it cannot safely guard the rename.
        if self.index is None or not self._write_snapshot(
            faiss.clone_index(self.index),
            self.metadata.copy(),
            list(self._tombstoned_ids),
        ):
            raise OSError("Legacy metadata snapshot konnte nicht publiziert werden")
        legacy_path.replace(legacy_path.with_suffix(".pkl.bak"))

    def _create_new_index(self):
         # IndexFlatIP = Inner Product (Cos Sim) + Flat (Exact Search)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = {}
        logger.info(f"Created new FAISS index (Dim: {self.dimension})")

    @recovery_write_operation("vector")
    def add_embedding(self, embedding: np.ndarray, meta_info: dict) -> int:
        """
        Adds a vector embedding and its metadata (thread-safe).
        Returns the FAISS ID.
        Raises ValueError on dimension mismatch with existing non-empty index.
        """
        with self._lock:
            self._ensure_open()
            # Flatten 2D arrays (batch of 1) zu 1D
            if len(embedding.shape) == 2 and embedding.shape[0] == 1:
                embedding = embedding.flatten()

            # Auto-initialize index on first embedding
            if self.index is None or self.index.ntotal == 0:
                detected_dim = embedding.shape[0] if len(embedding.shape) == 1 else embedding.shape[-1]
                if self.dimension != detected_dim:
                    logger.warning(
                        f"Dimension mismatch detected. Config: {self.dimension}, "
                        f"Embedding: {detected_dim}. Recreating empty index with {detected_dim}."
                    )
                    self.dimension = detected_dim
                    self._create_new_index()
            else:
                # Non-empty index: dimension mismatch is an error
                detected_dim = embedding.shape[0] if len(embedding.shape) == 1 else embedding.shape[-1]
                if self.dimension != detected_dim:
                    raise ValueError(
                        f"Embedding dimension {detected_dim} does not match existing index "
                        f"dimension {self.dimension}. Cannot silently recreate index with "
                        f"{self.index.ntotal} existing entries."
                    )

            # Ensure correct shape
            expected_shape = (self.dimension,)
            if embedding.shape != expected_shape:
                raise ValueError(f"Embedding dim mismatch. Expected: {expected_shape}, Got: {embedding.shape}")

            # BUG-072 FIX: Copy array before in-place normalization to avoid mutating caller data
            emb_copy = embedding.copy().reshape(1, -1)
            faiss.normalize_L2(emb_copy)

            self.index.add(emb_copy)
            faiss_id = self.index.ntotal - 1

            self.metadata[faiss_id] = meta_info

            # BUGFIX C1: mark dirty + notify the coalescing writer (no per-add
            # clone, no per-add thread). Persistence still happens promptly and
            # off the calling thread, but bursts collapse to one write.
            self._request_save()

            return faiss_id

    @recovery_write_operation("vector")
    def add_embedding_with_media_link(
        self,
        embedding: np.ndarray,
        meta_info: dict,
        *,
        media_id: int | None,
        segment_start: float = 0.0,
        segment_end: float = 0.0,
        description: str = "",
    ) -> int:
        """Y6 / L-STATE-2: Wie add_embedding(), aber legt zusaetzlich vector_map-Row an.

        vector_map ist FK-CASCADE-Anker fuer FAISS-Cleanup beim Media-Delete.
        Ohne diesen Eintrag entstehen aktive Orphan-Hits. Deshalb ist der
        relationale Link verpflichtend; ein Linkfehler rollt den neuen letzten
        Vektor zurueck oder tombstoniert ihn bei konkurrierenden Adds.
        """
        if media_id is None:
            raise ValueError("media_id ist für verlinkte FAISS-Embeddings erforderlich")

        faiss_id = self.add_embedding(embedding, meta_info)
        try:
            from pb_studio.data.database_core import DatabaseCore
            db = DatabaseCore()
            with db.transaction(immediate=True) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO vector_map "
                    "(faiss_id, media_id, segment_start, segment_end, description) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (faiss_id, media_id, segment_start, segment_end, description),
                )
        except Exception:
            with self._lock:
                rolled_back = False
                if self.index is not None and self.index.ntotal - 1 == faiss_id:
                    try:
                        removed = self.index.remove_ids(
                            np.asarray([faiss_id], dtype=np.int64)
                        )
                        rolled_back = int(removed) == 1
                    except Exception:
                        rolled_back = False
                if rolled_back:
                    self.metadata.pop(faiss_id, None)
                else:
                    if not hasattr(self, "_tombstoned_ids"):
                        self._tombstoned_ids = set()
                    self._tombstoned_ids.add(faiss_id)
                self._request_save()
            logger.error(
                "vector_map-Insert fehlgeschlagen; FAISS-ID %s wurde %s",
                faiss_id,
                "zurueckgerollt" if rolled_back else "tombstoniert",
                exc_info=True,
            )
            raise
        return faiss_id

    @recovery_write_operation("vector")
    def mark_tombstoned(self, faiss_ids) -> None:
        """Y6 / L-STATE-2: Markiert FAISS-IDs als "weggeloescht" — werden in
        search() ausgefiltert. Wird von delete_audio_clip/delete_video_clip
        gerufen mit den IDs aus vector_map.media_id-Cascade."""
        with self._lock:
            self._ensure_open()
            if not hasattr(self, "_tombstoned_ids"):
                self._tombstoned_ids = set()
            for fid in faiss_ids:
                try:
                    self._tombstoned_ids.add(int(fid))
                except (TypeError, ValueError):
                    pass
            
            # Trigger clean_tombstones bei signifikantem Tombstone-Bloat
            # Bedingung: min. 100 Tombstones und min. 20% des Indexes tombstoniert
            total = self.index.ntotal if self.index else 0
            if len(self._tombstoned_ids) >= 100 and len(self._tombstoned_ids) / max(1, total) >= 0.2:
                self._clean_tombstones_unlocked()
            else:
                # B-7 FIX / BUGFIX C1: Zustand nach Tombstoning speichern (coalesced).
                self._request_save()

    @recovery_write_operation("vector")
    def clean_tombstones(self) -> None:
        """Physische Bereinigung des FAISS-Indexes (Re-Indexing) mit Thread-Sicherung."""
        with self._lock:
            self._ensure_open()
            self._clean_tombstones_unlocked()

    def _clean_tombstones_unlocked(self) -> None:
        """
        Interne, nicht thread-sichere Methode zur Bereinigung (ruft self._lock nicht auf).
        Erstellt einen neuen FAISS-Index und schliesst alle markierten IDs dauerhaft aus.
        """
        tombstones = getattr(self, "_tombstoned_ids", set())
        if not tombstones or self.index is None or self.index.ntotal == 0:
            return

        logger.info(f"Physisches Re-Indexing gestartet. Tombstones zu entfernen: {len(tombstones)}")
        
        try:
            # Neuen Index erstellen (IndexFlatIP)
            new_index = faiss.IndexFlatIP(self.dimension)
            new_metadata = {}
            
            # SQLite-Verbindung herstellen
            from pb_studio.data.database_core import DatabaseCore
            db = DatabaseCore()
            updates = []
            
            new_id = 0
            for old_id in range(self.index.ntotal):
                if old_id in tombstones:
                     continue
                
                # Vektor aus altem Index rekonstruieren
                vec = np.zeros(self.dimension, dtype=np.float32)
                self.index.reconstruct(old_id, vec)
                vec_2d = vec.reshape(1, -1)
                new_index.add(vec_2d)
                
                # Metadaten übertragen
                if old_id in self.metadata:
                    new_metadata[new_id] = self.metadata[old_id]
                
                # IDs aufsteigend sammeln
                if new_id != old_id:
                    updates.append((new_id, old_id))
                
                new_id += 1
            
            # SQLite vector_map synchronisieren in einer Transaktion (aufsteigend nach new_id)
            if updates:
                with db.transaction(immediate=True) as conn:
                    for new_fid, old_fid in updates:
                        conn.execute(
                            "UPDATE vector_map SET faiss_id = ? WHERE faiss_id = ?",
                            (new_fid, old_fid)
                        )
                logger.info(f"vector_map erfolgreich mit {len(updates)} ID-Updates synchronisiert.")
            
            self.index = new_index
            self.metadata = new_metadata
            self._tombstoned_ids.clear()
            
            logger.info(f"Re-Indexing beendet. Neue Index-Groesse: {self.index.ntotal}")
            
            # Im Hintergrund speichern (BUGFIX C1: coalesced writer)
            self._request_save()
        except Exception as e:
            logger.error(f"Fehler bei clean_tombstones: {e}", exc_info=True)

    def search(self, query_embedding: np.ndarray, k=5, nprobe: Optional[int] = None):
        """Returns list of (metadata, score). Thread-safe."""
        with self._lock:
            self._ensure_open()
            if self.index is None or self.index.ntotal == 0:
                return []

            # BUG-078 FIX: nprobe handling for IVF indexes
            if hasattr(self.index, 'nprobe'):
                self.index.nprobe = nprobe if nprobe is not None else 1

            # BUG-101 FIX: Copy query_embedding before in-place normalization
            q_copy = query_embedding.copy().reshape(1, -1)
            faiss.normalize_L2(q_copy)
            tombstoned = getattr(self, "_tombstoned_ids", set())
            search_k = min(int(self.index.ntotal), max(int(k), int(k) + len(tombstoned)))
            D, I = self.index.search(q_copy, search_k)

            results = []
            for i, idx in enumerate(I[0]):
                # Y6 / L-STATE-2: Tombstoned IDs (vector_map-cascade-removed)
                # ausfiltern — sonst liefert FAISS Hits zu geloeschten Clips.
                if idx != -1 and idx in self.metadata and int(idx) not in tombstoned:
                    score = float(D[0][i])
                    meta = self.metadata[idx]
                    results.append((meta, score))
                    if len(results) >= k:
                        break

            return results

    @recovery_write_operation("vector")
    def save(self):
        """Thread-safe save."""
        with self._lock:
            self._ensure_open()
            self._save_unlocked()

    def _ensure_open(self) -> None:
        if getattr(self, "_closed", False):
            raise RuntimeError("VectorStore ist bereits geschlossen")

    def _stop_writer(self) -> None:
        writer = getattr(self, "_writer_thread", None)
        save_cv = getattr(self, "_save_cv", None)
        if writer is None or save_cv is None:
            return

        with save_cv:
            self._writer_stop = True
            save_cv.notify_all()

        if writer.is_alive() and writer is not threading.current_thread():
            writer.join()

    def close(self) -> None:
        """Stop the coalescing writer and persist the final index state."""
        lock = getattr(self, "_lock", None)
        if lock is None:
            self._closed = True
            return

        with lock:
            if getattr(self, "_closed", False):
                return
            self._closed = True

        self._stop_writer()
        self._save_on_exit()

    def _save_unlocked(
        self,
        force: bool = False,
        faiss_mod=faiss,
        json_mod=json,
        os_mod=os,
        logger_mod=logger,
        path_class=Path
    ):
        """Save index and metadata atomically (caller must hold lock)."""
        write_lock = getattr(self, "_write_lock", None)
        if write_lock is None:
            write_lock = threading.Lock()
            try:
                self._write_lock = write_lock
            except Exception:
                pass

        # Non-blocking lock acquisition to prevent main thread blocking, unless force=True
        acquired = write_lock.acquire(blocking=force)
        if not acquired:
            logger_mod.info("Asynchroner Speichervorgang läuft bereits. Überspringe synchrones Speichern zur Performance-Optimierung.")
            return

        try:
            if self.index and getattr(self, "index_path", None) is not None:
                # Atomic save: write to temp files, then rename
                try:
                    # Save FAISS index to temp file first
                    temp_index = str(self.index_path) + ".tmp"
                    faiss_mod.write_index(self.index, temp_index)

                    # Save metadata to temp file
                    temp_meta = str(self.meta_path) + ".tmp"
                    with open(temp_meta, "w") as f:
                        json_mod.dump(self.metadata, f, indent=2, allow_nan=False)

                    # B-7 FIX: Save tombstones
                    temp_tomb = str(self.tombstone_path) + ".tmp"
                    with open(temp_tomb, "w") as f:
                        json_mod.dump(
                            list(self._tombstoned_ids),
                            f,
                            allow_nan=False,
                        )

                    self._commit_snapshot_files(
                        [temp_index, temp_meta, temp_tomb],
                        json_mod=json_mod,
                        os_mod=os_mod,
                        path_class=path_class,
                    )
                    logger_mod.info("FAISS Index saved.")
                except Exception as e:
                    logger_mod.error(f"Failed to save FAISS index/metadata: {e}", exc_info=True)
                    # Cleanup temp files
                    for tmp in [str(self.index_path) + ".tmp", str(self.meta_path) + ".tmp", str(self.tombstone_path) + ".tmp"]:
                        try:
                            path_class(tmp).unlink(missing_ok=True)
                        except Exception:
                            pass
        finally:
            write_lock.release()

    def _request_save(self) -> None:
        """BUGFIX C1: mark state dirty and wake the single coalescing writer.
        Cheap and safe to call while holding self._lock — it only touches the
        writer condition, and the writer never holds that condition while
        acquiring self._lock, so there is no lock-ordering deadlock."""
        with self._save_cv:
            self._save_generation += 1
            self._save_dirty = True
            self._save_cv.notify()

    def _writer_loop(self) -> None:
        """BUGFIX C1: single background writer. Waits for a dirty signal,
        debounces to coalesce bursts, then clones the CURRENT state under
        _lock and writes it atomically. Because it always snapshots the newest
        state, 'latest wins' is inherent and stale snapshots never overwrite
        newer data."""
        while True:
            with self._save_cv:
                while not self._save_dirty and not self._writer_stop:
                    self._save_cv.wait(timeout=30.0)
                if self._writer_stop and not self._save_dirty:
                    return
                generation = self._save_generation

            # Debounce: let a burst of adds accumulate into one write.
            if self._save_debounce_sec > 0:
                time.sleep(self._save_debounce_sec)

            # Snapshot current state under the index lock (one clone per write,
            # not one per add).
            try:
                with self._lock:
                    snap_index = faiss.clone_index(self.index) if self.index else None
                    snap_meta = self.metadata.copy()
                    snap_tomb = list(getattr(self, "_tombstoned_ids", set()))
            except Exception as e:
                logger.error(f"VectorStore writer snapshot failed: {e}", exc_info=True)
                if self._writer_stop:
                    return
                continue

            try:
                persisted = self._write_snapshot(snap_index, snap_meta, snap_tomb)
            except RecoveryBusyError:
                persisted = False
            with self._save_cv:
                if persisted and generation == self._save_generation:
                    self._save_dirty = False
                if self._writer_stop and (persisted or not self._save_dirty):
                    return

    @recovery_write_operation("vector")
    def _write_snapshot(self, cloned_index, cloned_metadata, cloned_tombstones) -> bool:
        """Atomically persist a snapshot (temp file + os.replace). Serialized
        against the synchronous save() via _write_lock."""
        if cloned_index is None or getattr(self, "index_path", None) is None:
            return True
        with self._write_lock:
            try:
                temp_index = str(self.index_path) + ".tmp"
                faiss.write_index(cloned_index, temp_index)

                temp_meta = str(self.meta_path) + ".tmp"
                with open(temp_meta, "w") as f:
                    json.dump(cloned_metadata, f, indent=2, allow_nan=False)

                temp_tomb = str(self.tombstone_path) + ".tmp"
                with open(temp_tomb, "w") as f:
                    json.dump(cloned_tombstones, f, allow_nan=False)

                self._commit_snapshot_files(
                    [temp_index, temp_meta, temp_tomb],
                )
                logger.debug("FAISS Index saved (coalesced writer).")
                return True
            except Exception as e:
                logger.error(f"Failed to save FAISS index/metadata: {e}", exc_info=True)
                for tmp in [str(self.index_path) + ".tmp", str(self.meta_path) + ".tmp", str(self.tombstone_path) + ".tmp"]:
                    try:
                        Path(tmp).unlink(missing_ok=True)
                    except Exception:
                        pass
                return False

    def _save_on_exit(
        self,
        faiss_mod=faiss,
        json_mod=json,
        os_mod=os,
        logger_mod=logger,
        path_class=Path
    ):
        """atexit-Handler: stellt sicher dass beim Prozessende gespeichert wird."""
        try:
            with self._lock:
                self._save_unlocked(
                    force=True,
                    faiss_mod=faiss_mod,
                    json_mod=json_mod,
                    os_mod=os_mod,
                    logger_mod=logger_mod,
                    path_class=path_class
                )
        except Exception:
            # Letzter Persistenzpunkt. Ohne Log und Dirty-Marker fehlen beim
            # naechsten Start Clips im semantischen Index und der Zeitpunkt des
            # Verlusts ist nicht rekonstruierbar. Darf trotzdem nicht werfen,
            # der Aufrufer ist der Shutdown-Pfad.
            logger_mod.critical(
                "Finaler FAISS-Save fehlgeschlagen — seit dem letzten Write "
                "ergaenzte Embeddings sind verloren",
                exc_info=True,
            )
            self._mark_dirty("final save failed", path_class=path_class)

    def _mark_dirty(self, reason: str, path_class=Path) -> None:
        """Persistierter Marker neben der Indexdatei nach verlorenem Save.

        Wird bewusst NICHT von einem spaeteren erfolgreichen Save entfernt: die
        verlorenen Embeddings lagen nur im RAM, ein neuer Write holt sie nicht
        zurueck. Der Marker bleibt, bis er beim Nachanalysieren aufgeraeumt wird.
        Wirft nie — alle Aufrufer sind Shutdown-Pfade."""
        try:
            marker = path_class(str(self.index_path) + ".dirty")
            marker.write_text(
                f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {reason}\n",
                encoding="utf-8",
            )
        except Exception:
            logger.critical(
                "FAISS-Dirty-Marker konnte nicht geschrieben werden (%s) — "
                "der Verlust bleibt unsichtbar",
                reason,
                exc_info=True,
            )
