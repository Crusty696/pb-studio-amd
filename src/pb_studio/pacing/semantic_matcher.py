"""
Semantic Matcher
================

Die "Intelligenz" der Schnitt-Logik.
Wählt den besten Video-Clip/Szene für eine gegebene Query (Embedding) aus.

Features:
- Semantische Suche via FAISS VectorStore (SigLIP 1152-dim)
- Visual Variety: Bestraft Wiederholungen von Szenen UND Videos
- Duration-Aware: Findet Segmente, die lang genug sind
- Continuity (Roter Faden): Bevorzugt visuell ähnliche Folgeszenen

Portiert von NVIDIA-Version.
AMD-Anpassung: FAISS VectorStore statt ChromaDB.
"""

import logging
import numpy as np
from typing import List, Dict, Optional, Set
from collections import deque

from .constants import (
    VARIETY_HISTORY_SIZE,
    MAX_SCENE_HISTORY,
    MAX_SCENE_REUSES,
    SCENE_RECYCLE_INTERVAL,
    VISUAL_SIMILARITY_THRESHOLD,
    VISUAL_PENALTY_FACTOR,
)

logger = logging.getLogger(__name__)


class SemanticMatcher:
    """Semantische Clip-Suche mit Variety, Continuity und Motion-Matching."""
    
    def __init__(self, history_size: int = VARIETY_HISTORY_SIZE,
                 max_scene_history: int = MAX_SCENE_HISTORY):
        """
        Args:
            history_size: Wie viele der letzten Videos sollen gemerkt werden?
            max_scene_history: Maximale Anzahl getrackter Scene-IDs
        """
        # VectorStore wird lazy geladen
        self._vector_store = None
        
        # History für Visual Variety
        self.used_videos_history: deque = deque(maxlen=history_size)
        self._max_scene_history = max_scene_history
        self.used_scene_ids: Set[str] = set()
        
        # Intelligente Scene-Recycling
        self.scene_reuse_counter: Dict[str, int] = {}
        self.max_scene_reuses = MAX_SCENE_REUSES
        self.recycle_after_segments = SCENE_RECYCLE_INTERVAL
        self.segments_processed = 0
        
        # Continuity (Roter Faden)
        self.last_embedding: Optional[np.ndarray] = None
        self.continuity_weight = 0.35
    
    @property
    def vector_store(self):
        """Lazy-Load des FAISS VectorStore."""
        if self._vector_store is None:
            try:
                from ..data.vector_store import VectorStore
                self._vector_store = VectorStore(index_name="main_index")
                logger.info(f"FAISS VectorStore geladen (Dim: {self._vector_store.dimension})")
            except Exception as e:
                logger.error(f"VectorStore konnte nicht geladen werden: {e}")
        return self._vector_store
    
    def _query_vector_store(self, query_embedding: np.ndarray, n_results: int = 60) -> List[Dict]:
        """
        Sucht im FAISS VectorStore nach ähnlichen Clips.
        
        Konvertiert das FAISS-Ergebnis in das von SemanticMatcher erwartete Format.
        """
        vs = self.vector_store
        if vs is None:
            return []
        
        try:
            results = vs.search(query_embedding, k=n_results)
            
            candidates = []
            for meta, score in results:
                candidates.append({
                    "id": meta.get("scene_id", meta.get("id", "")),
                    "score": score,
                    "metadata": {
                        "path": meta.get("path", meta.get("file_path", "")),
                        "scene_id": meta.get("scene_id", meta.get("id", "")),
                        "duration": meta.get("duration", 0.0),
                        "start_time": meta.get("start_time", 0.0),
                        "caption": meta.get("caption", ""),
                        "motion_score": meta.get("motion_score", 0.5),
                    }
                })
            
            return candidates
            
        except Exception as e:
            logger.error(f"VectorStore-Suche fehlgeschlagen: {e}")
            return []
    
    def find_best_match(
        self,
        query_embedding: np.ndarray,
        min_duration: float = 2.0,
        n_candidates: int = 60,
        variety_weight: float = 1.0,
        preferred_motion: Optional[float] = None
    ) -> Optional[Dict]:
        """
        Findet die beste Szene für das gegebene Stimmung-Embedding.
        
        Args:
            query_embedding: SigLIP Embedding (1152-dim)
            min_duration: Mindestlänge der Szene
            n_candidates: Anzahl der Kandidaten aus DB
            variety_weight: Faktor für Wiederholungs-Strafe
            preferred_motion: Gewünschte Bewegung (0.0=statisch, 1.0=dynamisch)
        """
        candidates = self._query_vector_store(query_embedding, n_candidates)
        
        if not candidates:
            return None
        
        best_candidate = None
        best_score = -1.0
        
        # Fallback: Längsten Clip tracken
        longest_short_candidate = None
        longest_short_duration = 0.0
        
        for cand in candidates:
            meta = cand.get("metadata", {})
            video_path = meta.get("path", "")
            scene_id = str(meta.get("scene_id", cand.get("id")))
            duration = meta.get("duration", 0.0)
            
            # --- Hard Constraints ---
            if duration < min_duration:
                if duration > longest_short_duration:
                    usage_count = self.scene_reuse_counter.get(scene_id, 0)
                    if usage_count < self.max_scene_reuses:
                        longest_short_candidate = cand
                        longest_short_duration = duration
                continue
            
            # Scene-Wiederverwendung
            usage_count = self.scene_reuse_counter.get(scene_id, 0)
            if usage_count >= self.max_scene_reuses:
                continue
            
            # --- Scoring ---
            similarity = cand.get("score", 0.5)
            score = similarity
            
            # Motion-Score Matching (50% Gewicht)
            motion_weight = 0.50
            if preferred_motion is not None:
                clip_motion_score = meta.get("motion_score", 0.5)
                motion_diff = abs(preferred_motion - clip_motion_score)
                motion_match = 1.0 - (motion_diff ** 1.5)
                
                # Bonus für exakte Matches
                if preferred_motion > 0.7 and clip_motion_score > 0.7:
                    motion_match += 0.15
                elif preferred_motion < 0.3 and clip_motion_score < 0.3:
                    motion_match += 0.10
                
                motion_match = max(0.0, min(1.0, motion_match))
                score = similarity * (1.0 - motion_weight) + motion_match * motion_weight
            
            # Continuity (Roter Faden)
            if self.last_embedding is not None:
                try:
                    candidate_embedding = self._get_candidate_embedding(cand)
                    if candidate_embedding is not None:
                        continuity_sim = self._cosine_similarity(self.last_embedding, candidate_embedding)
                        score += continuity_sim * self.continuity_weight
                except Exception:
                    pass
            
            # Variety Penalty (Video-Level)
            if video_path in self.used_videos_history:
                try:
                    history_list = list(reversed(self.used_videos_history))
                    recent_index = history_list.index(video_path)
                    penalty = (0.5 / (recent_index + 1)) * variety_weight
                    score -= penalty
                except ValueError:
                    pass
            
            # Visual Similarity Penalty
            if self.last_embedding is not None and variety_weight > 0.5:
                try:
                    candidate_embedding = self._get_candidate_embedding(cand)
                    if candidate_embedding is not None:
                        visual_sim = self._cosine_similarity(self.last_embedding, candidate_embedding)
                        if visual_sim > VISUAL_SIMILARITY_THRESHOLD:
                            visual_penalty = (visual_sim - VISUAL_SIMILARITY_THRESHOLD) * VISUAL_PENALTY_FACTOR * variety_weight
                            score -= visual_penalty
                except Exception:
                    pass
            
            if score > best_score:
                best_score = score
                best_candidate = cand
        
        # History & State Update
        if best_candidate and best_score > 0.05:
            meta = best_candidate["metadata"]
            self._record_usage(meta.get("path", ""), str(meta.get("scene_id", "")))
            
            try:
                current_embedding = self._get_candidate_embedding(best_candidate)
                if current_embedding is not None:
                    self.last_embedding = current_embedding
            except Exception:
                pass
            
            return best_candidate
        
        # Fallback
        if longest_short_candidate is not None and longest_short_duration > 0.3:
            logger.warning(
                f"Kein Clip mit min_duration={min_duration:.1f}s gefunden. "
                f"Fallback: Längster ({longest_short_duration:.1f}s)"
            )
            meta = longest_short_candidate["metadata"]
            self._record_usage(meta.get("path", ""), str(meta.get("scene_id", "")))
            
            try:
                current_embedding = self._get_candidate_embedding(longest_short_candidate)
                if current_embedding is not None:
                    self.last_embedding = current_embedding
            except Exception:
                pass
            
            return longest_short_candidate
        
        return None
    
    def _record_usage(self, video_path: str, scene_id: str):
        """Merkt sich die Nutzung zur Vermeidung von Loops."""
        if video_path:
            self.used_videos_history.append(video_path)
        if scene_id:
            current_count = self.scene_reuse_counter.get(scene_id, 0)
            self.scene_reuse_counter[scene_id] = current_count + 1
            
            self.used_scene_ids.add(scene_id)
            
            if len(self.used_scene_ids) > self._max_scene_history:
                excess = len(self.used_scene_ids) - self._max_scene_history
                scene_list = list(self.used_scene_ids)
                for old_id in scene_list[:excess]:
                    self.used_scene_ids.discard(old_id)
        
        self.segments_processed += 1
        
        if self.segments_processed % self.recycle_after_segments == 0:
            self._reset_scene_blocks()
            logger.info(f"Scene-Block Reset nach {self.segments_processed} Segmenten")
    
    def _reset_scene_blocks(self):
        """Resettet Scene-Sperren für Recycling."""
        self.used_scene_ids.clear()
        for scene_id in list(self.scene_reuse_counter.keys()):
            self.scene_reuse_counter[scene_id] = max(0, self.scene_reuse_counter[scene_id] - 1)
        self.scene_reuse_counter = {k: v for k, v in self.scene_reuse_counter.items() if v > 0}
    
    def reset_history(self) -> None:
        """Löscht das Gedächtnis (für neue Session)."""
        self.used_videos_history.clear()
        self.used_scene_ids.clear()
        self.last_embedding = None
        self.scene_reuse_counter.clear()
        self.segments_processed = 0
        logger.debug("SemanticMatcher History resetted")
    
    def find_alternatives(self, query_embedding: np.ndarray, count: int = 5) -> List[Dict]:
        """Findet alternative Clips ohne History-Penalty."""
        candidates = self._query_vector_store(query_embedding, count * 2)
        return candidates[:count]
    
    def _get_candidate_embedding(self, candidate: Dict) -> Optional[np.ndarray]:
        """
        Holt das SigLIP-Embedding für einen Kandidaten aus FAISS.

        Nutzt IndexFlatIP.reconstruct() um das Original-Embedding zurückzuholen.
        IndexFlatIP speichert alle Vektoren und unterstützt reconstruct() direkt.

        Cache-Strategie: scene_id → embedding (verhindert mehrfache FAISS-Anfragen).
        """
        meta = candidate.get("metadata", {})
        scene_id = str(meta.get("scene_id", candidate.get("id", "")))

        # 1. Internes Cache prüfen (scene_id → embedding)
        if hasattr(self, "_embedding_cache") and scene_id in self._embedding_cache:
            return self._embedding_cache[scene_id]

        if not hasattr(self, "_embedding_cache"):
            self._embedding_cache: Dict[str, np.ndarray] = {}

        # 2. FAISS reconstruct() nutzen
        vs = self.vector_store
        if vs is None:
            return None

        try:
            faiss_index = vs.index
            if faiss_index is None or faiss_index.ntotal == 0:
                return None

            # FAISS-interne ID aus Metadata holen
            # Die interne ID entspricht dem Index beim Einfügen (0-basiert)
            # Wir suchen die ID über die Metadata-Map des VectorStore
            faiss_id = None

            if hasattr(vs, "metadata"):
                # Inverted Index Cache to avoid O(N) lookup over all metadata items
                current_metadata_len = len(vs.metadata)

                # Check if cache is missing or if the vector store length has changed.
                # For a more robust cache, we also store the id() of vs to ensure we don't
                # use a cache from a different vector store instance.
                if (getattr(self, "_vs_metadata_len", -1) != current_metadata_len or
                    getattr(self, "_vs_instance_id", -1) != id(vs)):

                    new_cache = {}
                    # We iterate backwards so that the *first* occurrence in the original order
                    # overwrites any later occurrences, preserving the original `break` behavior.
                    for fid, fmeta in reversed(list(vs.metadata.items())):
                        s_id = str(fmeta.get("scene_id", ""))
                        m_id = str(fmeta.get("id", ""))

                        # In the original code, empty strings were allowed to match
                        new_cache[s_id] = int(fid)
                        new_cache[m_id] = int(fid)

                    self._inverted_metadata_cache = new_cache
                    self._vs_metadata_len = current_metadata_len
                    self._vs_instance_id = id(vs)

                faiss_id = self._inverted_metadata_cache.get(scene_id)

            if faiss_id is None:
                return None

            # IndexFlatIP.reconstruct() ist O(1) - sehr schnell
            embedding = np.zeros(faiss_index.d, dtype=np.float32)
            faiss_index.reconstruct(faiss_id, embedding)

            if np.linalg.norm(embedding) < 1e-8:
                return None

            # Cache speichern (begrenzt auf 5000 Einträge)
            if len(self._embedding_cache) < 5000:
                self._embedding_cache[scene_id] = embedding

            return embedding

        except Exception as e:
            logger.debug(f"FAISS reconstruct() fehlgeschlagen für scene_id={scene_id}: {e}")
            return None
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Berechnet Cosine-Similarity zwischen zwei Vektoren."""
        try:
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return float(np.dot(vec1, vec2) / (norm1 * norm2))
        except Exception:
            return 0.0
