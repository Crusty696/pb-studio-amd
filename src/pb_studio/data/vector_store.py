import faiss
import numpy as np
import logging
import json
from pathlib import Path
from src.pb_studio.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, index_name="main_index", dimension=None):
        self.config = ConfigManager()
        self.data_dir = Path(self.config.get("paths", {}).get("db_path", "./data")).parent
        self.index_path = self.data_dir / f"{index_name}.faiss"
        self.meta_path = self.data_dir / f"{index_name}_meta.json"
        
        # Dimension: Auto-detect from config or first embedding
        # SigLIP SO400M = 1152, CLIP = 768, smaller models may use 512
        # FIXED: Default changed from 768 to 1152 for SigLIP compatibility
        self.dimension = dimension or self.config.get("vector_store", {}).get("dimension", 1152)
        self.index = None
        self.metadata = {} # Map faiss_id -> dict (media_id, desc, etc)
        
        self._load_index()

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
                            self.metadata = {int(k): v for k, v in raw_meta.items()}
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
        Adds a vector embedding and its metadata.
        Returns the FAISS ID.
        
        FIXED: Auto-initializes index with correct dimension on first embedding.
        """
        # FIXED: Auto-initialize index on first embedding
        if self.index is None or self.index.ntotal == 0:
            detected_dim = embedding.shape[0] if len(embedding.shape) == 1 else embedding.shape[-1]
            if self.dimension != detected_dim:
                logger.warning(
                    f"Dimension mismatch detected. Config: {self.dimension}, "
                    f"Embedding: {detected_dim}. Recreating index with {detected_dim}."
                )
                self.dimension = detected_dim
                self._create_new_index()
        
        # Ensure correct shape
        expected_shape = (self.dimension,)
        if embedding.shape != expected_shape:
             logger.error(f"Embedding dim mismatch. Expected: {expected_shape}, Got: {embedding.shape}")
             return -1
             
        # Normalize for Cosine Similarity
        faiss.normalize_L2(embedding.reshape(1, -1))
        
        self.index.add(embedding.reshape(1, -1))
        faiss_id = self.index.ntotal - 1
        
        self.metadata[faiss_id] = meta_info

        # Auto-save alle 10 Embeddings um Datenverlust bei Crash zu verhindern
        if self.index.ntotal % 10 == 0:
            self.save()

        return faiss_id

    def search(self, query_embedding: np.ndarray, k=5):
        """Returns list of (metadata, score)."""
        if self.index is None or self.index.ntotal == 0:
            return []

        faiss.normalize_L2(query_embedding.reshape(1, -1))
        D, I = self.index.search(query_embedding.reshape(1, -1), k)
        
        results = []
        for i, idx in enumerate(I[0]):
            if idx != -1 and idx in self.metadata:
                score = float(D[0][i])
                meta = self.metadata[idx]
                results.append((meta, score))
        
        return results

    def save(self):
        if self.index:
            faiss.write_index(self.index, str(self.index_path))
            # FIXED: Save metadata as JSON instead of pickle (security)
            try:
                with open(self.meta_path, "w") as f:
                    json.dump(self.metadata, f, indent=2)
                logger.info("FAISS Index saved.")
            except Exception as e:
                logger.error(f"Failed to save metadata: {e}", exc_info=True)
