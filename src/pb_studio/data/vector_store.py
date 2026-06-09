import atexit
import faiss
import numpy as np
import logging
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional
from pb_studio.config_manager import ConfigManager

logger = logging.getLogger(__name__)

_vs_lock = threading.Lock()
# L-VIDEO-1 / L-STATE-3 Sub-Fix: atexit darf NUR EINMAL pro Prozess registriert
# werden. __new__ erlaubt index_name-Wechsel (= neue Instanz) und __init__ wuerde
# bei jedem Wechsel atexit.register erneut aufrufen — die atexit-Liste waechst
# unbegrenzt und triggert bei Shutdown N save-Calls. Module-Level Flag verhindert
# das. Cleanup arbeitet weiter korrekt weil der Handler self._save_on_exit ueber
# das aktuelle cls._instance referenziert.
_atexit_registered: bool = False


class VectorStore:
    _instance: "VectorStore | None" = None
    _instance_index_name: str | None = None

    def __new__(cls, index_name: str = "main_index", dimension=None):
        with _vs_lock:
            if cls._instance is None or cls._instance_index_name != index_name:
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
        if inst is not None:
            try:
                inst._save_on_exit(
                    faiss_mod=_faiss_ref,
                    json_mod=_json_ref,
                    os_mod=_os_ref,
                    logger_mod=_logger_ref,
                    path_class=_path_ref
                )
            except Exception:
                # atexit darf niemals werfen
                pass


    def _load_index(self):
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
                        import pickle
                        logger.info("Migrating legacy metadata from pickle to JSON...")
                        try:
                            with open(legacy_path, "rb") as f:
                                self.metadata = pickle.load(f)
                            # Save immediately as JSON
                            self.save()
                            # Optional: Rename/Backup legacy
                            legacy_path.rename(legacy_path.with_suffix(".pkl.bak"))
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

    def _create_new_index(self):
         # IndexFlatIP = Inner Product (Cos Sim) + Flat (Exact Search)
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = {}
        logger.info(f"Created new FAISS index (Dim: {self.dimension})")

    def add_embedding(self, embedding: np.ndarray, meta_info: dict) -> int:
        """
        Adds a vector embedding and its metadata (thread-safe).
        Returns the FAISS ID.
        Raises ValueError on dimension mismatch with existing non-empty index.
        """
        with self._lock:
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

            # Immer nach jedem Embedding im Hintergrund speichern — verhindert Datenverlust bei Absturz
            # und blockiert parallele Suchanfragen nicht.
            try:
                cloned_index = faiss.clone_index(self.index) if self.index else None
                cloned_metadata = self.metadata.copy()
                cloned_tombstones = list(getattr(self, "_tombstoned_ids", set()))
                self._save_background(cloned_index, cloned_metadata, cloned_tombstones)
            except Exception as e:
                logger.error(f"Failed to trigger background save in add_embedding: {e}")

            return faiss_id

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
        Ohne diesen Eintrag wachsen FAISS-Files unbegrenzt (Orphan-Hits).
        Best-effort: vector_map-Insert-Failure schluckt nur Logging, embedding
        wird trotzdem hinzugefuegt (vector_map ist Cleanup-Optimierung).
        """
        faiss_id = self.add_embedding(embedding, meta_info)
        if media_id is not None:
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
            except Exception as e:
                logger.warning(
                    "vector_map-Insert fehlgeschlagen (FAISS bleibt orphan-faehig): %s", e
                )
        return faiss_id

    def mark_tombstoned(self, faiss_ids) -> None:
        """Y6 / L-STATE-2: Markiert FAISS-IDs als "weggeloescht" — werden in
        search() ausgefiltert. Wird von delete_audio_clip/delete_video_clip
        gerufen mit den IDs aus vector_map.media_id-Cascade."""
        with self._lock:
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
                # B-7 FIX: Zustand nach Tombstoning im Hintergrund speichern
                try:
                    cloned_index = faiss.clone_index(self.index) if self.index else None
                    cloned_metadata = self.metadata.copy()
                    cloned_tombstones = list(self._tombstoned_ids)
                    self._save_background(cloned_index, cloned_metadata, cloned_tombstones)
                except Exception as e:
                    logger.error(f"Failed to trigger background save in mark_tombstoned: {e}")

    def clean_tombstones(self) -> None:
        """Physische Bereinigung des FAISS-Indexes (Re-Indexing) mit Thread-Sicherung."""
        with self._lock:
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
                
                new_id += 1
            
            self.index = new_index
            self.metadata = new_metadata
            self._tombstoned_ids.clear()
            
            logger.info(f"Re-Indexing beendet. Neue Index-Groesse: {self.index.ntotal}")
            
            # Im Hintergrund speichern
            cloned_index = faiss.clone_index(self.index) if self.index else None
            cloned_metadata = self.metadata.copy()
            cloned_tombstones = []
            self._save_background(cloned_index, cloned_metadata, cloned_tombstones)
        except Exception as e:
            logger.error(f"Fehler bei clean_tombstones: {e}", exc_info=True)

    def search(self, query_embedding: np.ndarray, k=5, nprobe: Optional[int] = None):
        """Returns list of (metadata, score). Thread-safe."""
        with self._lock:
            if self.index is None or self.index.ntotal == 0:
                return []

            # BUG-078 FIX: nprobe handling for IVF indexes
            if hasattr(self.index, 'nprobe'):
                self.index.nprobe = nprobe if nprobe is not None else 1

            # BUG-101 FIX: Copy query_embedding before in-place normalization
            q_copy = query_embedding.copy().reshape(1, -1)
            faiss.normalize_L2(q_copy)
            D, I = self.index.search(q_copy, k)

            results = []
            tombstoned = getattr(self, "_tombstoned_ids", set())
            for i, idx in enumerate(I[0]):
                # Y6 / L-STATE-2: Tombstoned IDs (vector_map-cascade-removed)
                # ausfiltern — sonst liefert FAISS Hits zu geloeschten Clips.
                if idx != -1 and idx in self.metadata and int(idx) not in tombstoned:
                    score = float(D[0][i])
                    meta = self.metadata[idx]
                    results.append((meta, score))

            return results

    def save(self):
        """Thread-safe save."""
        with self._lock:
            self._save_unlocked()

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
                        json_mod.dump(self.metadata, f, indent=2)

                    # B-7 FIX: Save tombstones
                    temp_tomb = str(self.tombstone_path) + ".tmp"
                    with open(temp_tomb, "w") as f:
                        json_mod.dump(list(self._tombstoned_ids), f)

                    # BUG-102 FIX: Atomic replace
                    os_mod.replace(temp_index, str(self.index_path))
                    os_mod.replace(temp_meta, str(self.meta_path))
                    os_mod.replace(temp_tomb, str(self.tombstone_path))
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

    def _save_background(self, cloned_index, cloned_metadata, cloned_tombstones):
        """Asynchronously save cloned index and metadata in a daemon thread."""
        write_lock = getattr(self, "_write_lock", None)
        if write_lock is None:
            write_lock = threading.Lock()
            try:
                self._write_lock = write_lock
            except Exception:
                pass

        def do_save():
            with write_lock:
                if cloned_index and getattr(self, "index_path", None) is not None:
                    try:
                        temp_index = str(self.index_path) + ".tmp"
                        faiss.write_index(cloned_index, temp_index)

                        temp_meta = str(self.meta_path) + ".tmp"
                        with open(temp_meta, "w") as f:
                            json.dump(cloned_metadata, f, indent=2)

                        temp_tomb = str(self.tombstone_path) + ".tmp"
                        with open(temp_tomb, "w") as f:
                            json.dump(cloned_tombstones, f)

                        import os
                        os.replace(temp_index, str(self.index_path))
                        os.replace(temp_meta, str(self.meta_path))
                        os.replace(temp_tomb, str(self.tombstone_path))
                        logger.info("FAISS Index saved in background successfully.")
                    except Exception as e:
                        logger.error(f"Failed to save FAISS index/metadata in background: {e}", exc_info=True)
                        for tmp in [str(self.index_path) + ".tmp", str(self.meta_path) + ".tmp", str(self.tombstone_path) + ".tmp"]:
                            try:
                                Path(tmp).unlink(missing_ok=True)
                            except Exception:
                                pass
        t = threading.Thread(target=do_save, daemon=True)
        t.start()

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
            pass
