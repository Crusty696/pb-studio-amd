"""
Anchor Manager
==============

Verwaltet Audio-Video-Anchors für Few-Shot Learning basiertes Matching.

Anchors sind User-definierte Verknüpfungen zwischen Audio-Bereichen
und Video-Beispielen. Das System lernt daraus Präferenzen für
ähnliche Audio-Passagen.

Portiert von NVIDIA-Version.
AMD-Anpassung: JSON-Persistenz statt DB-CRUD (AMD hat keine Anchor-DB-Tabelle).
"""

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass

import numpy as np

from .constants import AUDIO_FEATURE_DIM, EMBEDDING_DIM

logger = logging.getLogger(__name__)


@dataclass
class AnchorData:
    """
    In-Memory Repräsentation eines Anchors für schnelles Matching.
    Enthält vorberechnete numpy Arrays statt JSON-Strings.
    """
    id: int
    audio_start: float
    audio_end: float
    audio_features: np.ndarray  # (20,) float32
    video_path: str
    video_embedding: np.ndarray  # (1152,) float32
    label: str


class AnchorManager:
    """
    Verwaltet Anchors für ein Projekt.
    
    AMD-Version: Persistenz via JSON-Dateien im Projektordner.
    Lädt Anchors in den RAM für schnelles Matching.
    """
    
    def __init__(self, project_id: Optional[int] = None, data_dir: Optional[str] = None):
        """
        Args:
            project_id: Projekt-ID
            data_dir: Verzeichnis für Anchor-JSON-Dateien
        """
        self.project_id = project_id
        self._anchors: List[AnchorData] = []
        self._audio_matrix: Optional[np.ndarray] = None
        self._video_matrix: Optional[np.ndarray] = None
        self._next_id = 1
        
        # Persistenz-Pfad
        if data_dir:
            self._data_dir = Path(data_dir)
        else:
            self._data_dir = Path("./data/anchors")
        
        if project_id is not None:
            self.load_anchors()
    
    def _get_anchor_file(self) -> Path:
        """Gibt den Pfad zur Anchor-JSON-Datei zurück."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        return self._data_dir / f"anchors_project_{self.project_id}.json"
    
    def set_project(self, project_id: int) -> None:
        """Setzt das aktive Projekt und lädt dessen Anchors."""
        self.project_id = project_id
        self.load_anchors()
    
    def load_anchors(self) -> int:
        """
        Lädt alle Anchors des Projekts aus JSON in den RAM.
        
        Returns:
            Anzahl der geladenen Anchors
        """
        if self.project_id is None:
            logger.warning("Kein Projekt gesetzt, kann Anchors nicht laden")
            return 0
        
        self._anchors.clear()
        self._next_id = 1
        
        anchor_file = self._get_anchor_file()
        if not anchor_file.exists():
            self._build_matrices()
            return 0
        
        try:
            with open(anchor_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for entry in data.get("anchors", []):
                try:
                    audio_features = np.array(entry["audio_features"], dtype=np.float32)
                    video_embedding = np.array(entry["video_embedding"], dtype=np.float32)
                    
                    if len(audio_features) != AUDIO_FEATURE_DIM:
                        logger.warning(f"Anchor {entry['id']}: Ungültige Audio-Features, überspringe")
                        continue
                    if len(video_embedding) != EMBEDDING_DIM:
                        logger.warning(f"Anchor {entry['id']}: Ungültiges Video-Embedding, überspringe")
                        continue
                    
                    self._anchors.append(AnchorData(
                        id=entry["id"],
                        audio_start=entry["audio_start"],
                        audio_end=entry["audio_end"],
                        audio_features=audio_features,
                        video_path=entry["video_path"],
                        video_embedding=video_embedding,
                        label=entry.get("label", "")
                    ))
                    
                    self._next_id = max(self._next_id, entry["id"] + 1)
                    
                except Exception as e:
                    logger.error(f"Fehler beim Laden von Anchor {entry.get('id', '?')}: {e}")
            
        except Exception as e:
            logger.error(f"Anchor-Datei konnte nicht geladen werden: {e}")
        
        self._build_matrices()
        logger.info(f"AnchorManager: {len(self._anchors)} Anchors geladen für Projekt {self.project_id}")
        return len(self._anchors)
    
    def _save_anchors(self) -> bool:
        """Speichert alle Anchors als JSON."""
        if self.project_id is None:
            return False
        
        try:
            entries = []
            for a in self._anchors:
                entries.append({
                    "id": a.id,
                    "audio_start": a.audio_start,
                    "audio_end": a.audio_end,
                    "audio_features": a.audio_features.tolist(),
                    "video_path": a.video_path,
                    "video_embedding": a.video_embedding.tolist(),
                    "label": a.label,
                })
            
            data = {
                "project_id": self.project_id,
                "count": len(entries),
                "anchors": entries
            }
            
            anchor_file = self._get_anchor_file()
            # Review-Fix MEDIUM (2026-07-09): eindeutiger Temp-Name via mkstemp
            # (fixer .tmp-Name clobberte bei parallelen Saves) + fsync
            # (Atomicity ohne Durability: Crash konnte leere Datei promoten)
            # + Retry bei PermissionError (Windows: os.replace schlaegt fehl,
            # wenn ein Reader die Ziel-Datei gerade offen hat).
            fd, tmp_name = tempfile.mkstemp(
                dir=str(anchor_file.parent),
                prefix=anchor_file.name + ".",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                last_err: Optional[Exception] = None
                for attempt in range(3):
                    try:
                        os.replace(tmp_name, anchor_file)
                        break
                    except PermissionError as e:
                        last_err = e
                        time.sleep(0.1 * (attempt + 1))
                else:
                    raise last_err  # type: ignore[misc]
            except Exception:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise

            return True
        except Exception as e:
            logger.error(f"Anchor-Save fehlgeschlagen: {e}")
            return False
    
    def _build_matrices(self) -> None:
        """Baut numpy Matrizen für Batch-Similarity-Berechnung."""
        if not self._anchors:
            self._audio_matrix = None
            self._video_matrix = None
            return
        
        self._audio_matrix = np.stack([a.audio_features for a in self._anchors])
        self._video_matrix = np.stack([a.video_embedding for a in self._anchors])
        
        # Normalisieren für Cosine Similarity
        audio_norms = np.linalg.norm(self._audio_matrix, axis=1, keepdims=True)
        audio_norms[audio_norms == 0] = 1e-10
        self._audio_matrix = self._audio_matrix / audio_norms
        
        video_norms = np.linalg.norm(self._video_matrix, axis=1, keepdims=True)
        video_norms[video_norms == 0] = 1e-10
        self._video_matrix = self._video_matrix / video_norms
    
    @property
    def count(self) -> int:
        return len(self._anchors)
    
    @property
    def has_anchors(self) -> bool:
        return len(self._anchors) > 0
    
    def get_all_anchors(self) -> List[AnchorData]:
        return self._anchors.copy()
    
    def add_anchor(
        self,
        audio_start: float,
        audio_end: float,
        video_path: str,
        audio_features: np.ndarray,
        video_embedding: np.ndarray,
        label: str = ""
    ) -> Optional[int]:
        """Erstellt einen neuen Anchor und speichert ihn."""
        if self.project_id is None:
            logger.error("Kein Projekt gesetzt")
            return None
        
        if len(audio_features) != AUDIO_FEATURE_DIM:
            logger.error(f"Audio-Features müssen {AUDIO_FEATURE_DIM}-dim sein")
            return None
        if len(video_embedding) != EMBEDDING_DIM:
            logger.error(f"Video-Embedding muss {EMBEDDING_DIM}-dim sein")
            return None
        
        anchor_id = self._next_id
        self._next_id += 1
        
        self._anchors.append(AnchorData(
            id=anchor_id,
            audio_start=audio_start,
            audio_end=audio_end,
            audio_features=np.array(audio_features, dtype=np.float32),
            video_path=video_path,
            video_embedding=np.array(video_embedding, dtype=np.float32),
            label=label
        ))
        
        self._build_matrices()
        if not self._save_anchors():
            logger.error("Anchor-Save fehlgeschlagen — Anchor %s ist NICHT persistiert (project_id=%s)", anchor_id, self.project_id)

        logger.info(f"Anchor hinzugefügt: {audio_start:.1f}-{audio_end:.1f}s -> {Path(video_path).name}")
        return anchor_id
    
    def remove_anchor(self, anchor_id: int) -> bool:
        """Löscht einen Anchor."""
        before = len(self._anchors)
        self._anchors = [a for a in self._anchors if a.id != anchor_id]
        
        if len(self._anchors) < before:
            self._build_matrices()
            if not self._save_anchors():
                logger.error("Anchor-Save fehlgeschlagen — Loeschung von Anchor %s ist NICHT persistiert (project_id=%s)", anchor_id, self.project_id)
            return True
        return False
    
    def clear_all(self) -> int:
        """Löscht alle Anchors des Projekts."""
        count = len(self._anchors)
        self._anchors.clear()
        self._audio_matrix = None
        self._video_matrix = None
        if not self._save_anchors():
            logger.error("Anchor-Save fehlgeschlagen — clear_all ist NICHT persistiert (project_id=%s)", self.project_id)
        return count
    
    def find_best_anchor(
        self,
        audio_features: np.ndarray,
        min_similarity: float = 0.5
    ) -> Optional[Tuple[AnchorData, float]]:
        """Findet den Anchor mit den ähnlichsten Audio-Features."""
        if not self.has_anchors or self._audio_matrix is None:
            return None
        
        query = np.array(audio_features, dtype=np.float32).flatten()
        if len(query) != AUDIO_FEATURE_DIM:
            logger.warning(f"Query hat falsche Dimension: {len(query)} != {AUDIO_FEATURE_DIM}")
            return None
        
        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm
        
        similarities = self._audio_matrix @ query
        best_idx = np.argmax(similarities)
        best_sim = float(similarities[best_idx])
        
        if best_sim < min_similarity:
            return None
        
        return (self._anchors[best_idx], best_sim)
    
    def find_top_k_anchors(
        self,
        audio_features: np.ndarray,
        k: int = 3,
        min_similarity: float = 0.3
    ) -> List[Tuple[AnchorData, float]]:
        """Findet die k ähnlichsten Anchors."""
        if not self.has_anchors or self._audio_matrix is None:
            return []
        
        query = np.array(audio_features, dtype=np.float32).flatten()
        if len(query) != AUDIO_FEATURE_DIM:
            return []
        
        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm
        
        similarities = self._audio_matrix @ query
        top_indices = np.argsort(similarities)[::-1][:k]
        
        results = []
        for idx in top_indices:
            sim = float(similarities[idx])
            if sim >= min_similarity:
                results.append((self._anchors[idx], sim))
        
        return results
    
    def get_blended_video_embedding(
        self,
        audio_features: np.ndarray,
        top_k: int = 3,
        min_similarity: float = 0.3
    ) -> Optional[np.ndarray]:
        """Berechnet ein gewichtetes Video-Embedding aus den ähnlichsten Anchors."""
        matches = self.find_top_k_anchors(audio_features, k=top_k, min_similarity=min_similarity)
        
        if not matches:
            return None
        
        total_weight = sum(sim for _, sim in matches)
        if total_weight <= 0:
            total_weight = 1.0
        
        blended = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        for anchor, sim in matches:
            weight = sim / total_weight
            blended += anchor.video_embedding * weight
        
        norm = np.linalg.norm(blended)
        if norm > 0:
            blended = blended / norm
        
        return blended
    
    def get_stats(self) -> Dict[str, Any]:
        """Gibt Statistiken über die Anchors zurück."""
        if not self._anchors:
            return {"count": 0, "total_duration": 0.0, "labels": {}, "avg_duration": 0.0}
        
        durations = [a.audio_end - a.audio_start for a in self._anchors]
        labels = {}
        for a in self._anchors:
            label = a.label or "unlabeled"
            labels[label] = labels.get(label, 0) + 1
        
        return {
            "count": len(self._anchors),
            "total_duration": sum(durations),
            "avg_duration": sum(durations) / len(durations),
            "labels": labels,
            "project_id": self.project_id
        }


# Singleton-Instanz
_anchor_manager: Optional[AnchorManager] = None


def get_anchor_manager() -> AnchorManager:
    """Gibt die globale AnchorManager-Instanz zurück."""
    global _anchor_manager
    if _anchor_manager is None:
        _anchor_manager = AnchorManager()
    return _anchor_manager


def reset_anchor_manager() -> None:
    """Resettet die globale AnchorManager-Instanz."""
    global _anchor_manager
    _anchor_manager = None
