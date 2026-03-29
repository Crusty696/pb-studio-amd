"""
Clip Selector - Intelligent Video Segment Selection (AMD Edition)

AMD v2: Vollständige NV-Kompatibilität. Führt beide APIs zusammen:
- Neue FAISS-basierte ClipMetadata/ClipSelector-Architektur (behalten)
- NV-kompatible API: LRUCache, TRIGGER_PROMPTS, Blacklist, Roter Faden,
  select_clip(), analyze_all_clips(), reset(), reset_continuity()

Verwendet FAISS statt ChromaDB für Vektor-Suche.
Motion-Analyzer: Nutzt RAFT ONNX wenn verfügbar, sonst Librosa-Fallback.
"""

from __future__ import annotations

import logging
import random
from collections import OrderedDict, deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from dataclasses import dataclass

from .pacing_models import SelectedClip
from .constants import (
    EMBEDDING_CACHE_SIZE,
    MOTION_TOLERANCE,
    BLACKLIST_PERCENTAGE,
    MAX_BLACKLIST_SIZE,
    CONTINUITY_WEIGHT,
)

logger = logging.getLogger(__name__)


# =============================================================================
# LRU CACHE (NV-portiert, verhindert RAM-Explosion bei 400+ Videos)
# =============================================================================

class LRUCache:
    """Simple LRU Cache mit maxsize zur Speicherbegrenzung."""

    def __init__(self, maxsize: int = 100):
        self.maxsize = maxsize
        self._cache: OrderedDict = OrderedDict()

    def get(self, key: str) -> Optional[np.ndarray]:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: np.ndarray) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.maxsize:
                self._cache.popitem(last=False)
            self._cache[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def __len__(self) -> int:
        return len(self._cache)

    def clear(self) -> None:
        self._cache.clear()


# =============================================================================
# TRIGGER -> SEMANTIC QUERY MAPPING (NV-portiert)
# =============================================================================

TRIGGER_PROMPTS: Dict[str, str] = {
    "beat": "energetic rhythmic movement dancing action",
    "kick": "powerful strong impact bass drop explosion",
    "snare": "sharp quick hit dynamic snap punch",
    "hihat": "subtle gentle flowing smooth transition",
    "onset": "sudden change transition new movement",
    "energy": "high intensity exciting fast motion crowd",
    "drop": "massive explosion intense climax peak energy",
    "buildup": "rising tension anticipation growing energy",
    "downbeat": "strong powerful beat impact movement",
    "auto_split": "dynamic movement action visual interest",
}

DEFAULT_PROMPT = "dynamic movement action visual interest"


# =============================================================================
# CLIP METADATA (FAISS-Architektur, AMD-Original)
# =============================================================================

@dataclass
class ClipMetadata:
    """Metadata for a video clip segment."""
    video_id: int
    file_path: str
    start_time: float
    duration: float
    motion_score: float = 0.0
    energy_score: float = 0.0
    tags: List[str] = None
    embedding: Optional[np.ndarray] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


# =============================================================================
# CLIP SELECTOR (Vereinigt NV-API und AMD-FAISS-Architektur)
# =============================================================================

class ClipSelector:
    """
    Wählt Clips basierend auf verschiedenen Kriterien aus.

    Strategien (NV-kompatibel):
    - random: Zufällige Auswahl
    - round_robin: Sequentielle Auswahl
    - motion: Energie-basierte Auswahl (Roter Faden)
    - semantic: FAISS-basierte Ähnlichkeitssuche

    FAISS-Architektur (AMD-Original):
    - add_clip(), select_by_similarity(), select_by_motion()
    - select_by_energy(), select_by_tags(), select_hybrid()
    """

    def __init__(
        self,
        strategy: str = "motion",
        motion_tolerance: float = MOTION_TOLERANCE,
        use_semantic: bool = False,
        blacklist_percentage: float = BLACKLIST_PERCENTAGE,
        vector_store=None,
    ):
        """
        Args:
            strategy: Auswahlstrategie (random, round_robin, motion, semantic)
            motion_tolerance: Toleranz für Motion-Score-Matching
            use_semantic: Aktiviert FAISS-basierte Suche
            blacklist_percentage: Prozentsatz der Clips die geblockt werden (0.0-1.0)
            vector_store: Optionaler FAISS VectorStore (für FAISS-Architektur)
        """
        # --- NV-kompatible Attribute ---
        self.strategy = strategy
        self.motion_tolerance = motion_tolerance
        self.use_semantic = use_semantic
        self.blacklist_percentage = max(0.0, min(1.0, blacklist_percentage))

        # Round-Robin Zustand
        self._rr_index = 0

        # Blacklist für kürzlich verwendete Clips (NV-Roter-Faden)
        # R18/MEDIUM-018-3: Use deque so popleft() is O(1) instead of list.pop(0) O(N).
        self._recently_used: deque = deque()
        self._blacklist_size = 10

        # Roter Faden - Visueller Zusammenhang zwischen Clips
        self._last_clip_motion_score: float = 0.5
        self._last_clip_embedding: Optional[np.ndarray] = None
        self._last_clip_path: Optional[str] = None
        self._continuity_weight: float = CONTINUITY_WEIGHT

        # LRU-Cache (begrenzt, verhindert RAM-Explosion)
        self._embedding_cache: LRUCache = LRUCache(maxsize=EMBEDDING_CACHE_SIZE)

        # Motion-Cache: Clip-Pfad -> motion_score
        self._motion_cache: Dict[str, float] = {}

        # --- FAISS-Architektur (AMD-Original) ---
        self.vector_store = vector_store
        self.clip_cache: Dict[int, ClipMetadata] = {}

    # =========================================================================
    # NV-KOMPATIBLE API: select_clip(), analyze_all_clips(), reset()
    # =========================================================================

    def select_clip(
        self,
        available_clips: List[dict],
        trigger_strength: float = 0.5,
        trigger_type: str = "beat",
        previous_clip_id: Optional[str] = None,
    ) -> SelectedClip:
        """
        NV-kompatible Methode: Wählt den besten Clip für einen Schnitt.

        Args:
            available_clips: Liste verfügbarer Clips (dict mit id, file_path, etc.)
            trigger_strength: Stärke des Audio-Triggers (0.0-1.0)
            trigger_type: Typ des Triggers (beat, onset, kick, etc.)
            previous_clip_id: ID des vorherigen Clips (für Kontinuität)

        Returns:
            SelectedClip mit dem gewählten Clip
        """
        if not available_clips:
            logger.warning("Keine Clips verfügbar")
            return SelectedClip(clip_id="none", clip_path="", score=0.0)

        # Dynamische Blacklist-Größe
        calculated_size = int(len(available_clips) * self.blacklist_percentage)
        self._blacklist_size = max(3, min(MAX_BLACKLIST_SIZE, calculated_size))

        # Blacklist anwenden
        candidates = [
            clip for clip in available_clips
            if str(clip.get("id", "")) not in self._recently_used
        ]
        if not candidates:
            candidates = available_clips

        # Strategie anwenden
        if self.use_semantic or self.strategy == "semantic":
            selected = self._select_semantic(candidates, trigger_strength, trigger_type)
        elif self.strategy == "random":
            selected = self._select_random(candidates)
        elif self.strategy == "round_robin":
            selected = self._select_round_robin(candidates)
        else:  # motion oder default
            selected = self._select_by_motion(candidates, trigger_strength, trigger_type)

        # Blacklist aktualisieren — R18/MEDIUM-018-3: popleft() is O(1) on deque.
        self._recently_used.append(selected.clip_id)
        if len(self._recently_used) > self._blacklist_size:
            self._recently_used.popleft()

        # Roter Faden: Motion Score merken
        self._last_clip_motion_score = selected.motion_score
        self._last_clip_path = selected.clip_path

        return selected

    def reset(self) -> None:
        """NV-kompatibel: Setzt den gesamten Zustand zurück (neue Session)."""
        self._rr_index = 0
        self._recently_used.clear()
        self._last_clip_motion_score = 0.5
        self._last_clip_embedding = None
        self._last_clip_path = None
        logger.debug("ClipSelector: Zustand zurückgesetzt")

    def reset_continuity(self) -> None:
        """NV-kompatibel: Setzt nur den Roter-Faden-Zustand zurück (z.B. bei Sektionswechsel)."""
        self._last_clip_embedding = None
        self._last_clip_motion_score = 0.5
        self._last_clip_path = None
        logger.debug("ClipSelector: Continuity zurückgesetzt")

    def analyze_all_clips(self, clips: List[dict]) -> Dict[str, float]:
        """
        NV-kompatibel: Analysiert Motion-Scores aller Clips (Batch).
        Nutzt RAFT ONNX wenn verfügbar, sonst Librosa-RMS-Fallback.

        Args:
            clips: Liste von Clip-Dicts (mit file_path oder path)

        Returns:
            Dict {file_path: motion_score}
        """
        results: Dict[str, float] = {}

        for clip in clips:
            path = clip.get("file_path", clip.get("path", ""))
            if not path:
                continue

            if path in self._motion_cache:
                results[path] = self._motion_cache[path]
                continue

            score = self._analyze_clip_motion(path)
            self._motion_cache[path] = score
            results[path] = score

        logger.info(f"Motion-Analyse abgeschlossen: {len(results)} Clips")
        return results

    # =========================================================================
    # INTERNE AUSWAHLMETHODEN (NV-portiert)
    # =========================================================================

    def _select_random(self, clips: List[dict]) -> SelectedClip:
        """Zufällige Auswahl."""
        clip = random.choice(clips)
        return SelectedClip(
            clip_id=str(clip.get("id", "unknown")),
            clip_path=clip.get("file_path", clip.get("path", "")),
            score=1.0,
            motion_score=clip.get("motion_score", 0.5),
        )

    def _select_round_robin(self, clips: List[dict]) -> SelectedClip:
        """Sequentielle Auswahl."""
        clip = clips[self._rr_index % len(clips)]
        self._rr_index += 1
        return SelectedClip(
            clip_id=str(clip.get("id", "unknown")),
            clip_path=clip.get("file_path", clip.get("path", "")),
            score=1.0,
            motion_score=clip.get("motion_score", 0.5),
        )

    def _select_by_motion(
        self,
        clips: List[dict],
        trigger_strength: float,
        trigger_type: str,
    ) -> SelectedClip:
        """
        Motion-basierte Auswahl mit Roter-Faden-Continuity.

        Hohe trigger_strength → bevorzuge dynamische Clips.
        Niedrige trigger_strength → bevorzuge ruhige Clips.
        """
        target_motion = trigger_strength

        # Kleine Anpassung basierend auf Trigger-Typ
        if trigger_type in ("kick", "drop"):
            target_motion = min(1.0, trigger_strength * 1.2)
        elif trigger_type in ("breakdown", "hihat"):
            target_motion = max(0.0, trigger_strength * 0.7)

        best_clip = None
        best_score = -1.0

        for clip in clips:
            clip_motion = clip.get("motion_score", 0.5)
            motion_diff = abs(target_motion - clip_motion)
            motion_score = 1.0 - min(motion_diff / (self.motion_tolerance + 0.01), 1.0)

            # Roter Faden: Continuity-Bonus für ähnliche Motion zum letzten Clip
            continuity_bonus = 0.0
            if self._last_clip_path:
                last_motion = self._last_clip_motion_score
                motion_continuity = 1.0 - abs(last_motion - clip_motion)
                continuity_bonus = motion_continuity * self._continuity_weight * 0.5

            total_score = motion_score + continuity_bonus

            if total_score > best_score:
                best_score = total_score
                best_clip = clip

        if best_clip is None:
            best_clip = random.choice(clips)

        return SelectedClip(
            clip_id=str(best_clip.get("id", "unknown")),
            clip_path=best_clip.get("file_path", best_clip.get("path", "")),
            score=best_score,
            motion_score=best_clip.get("motion_score", 0.5),
        )

    def _select_semantic(
        self,
        clips: List[dict],
        trigger_strength: float,
        trigger_type: str,
    ) -> SelectedClip:
        """
        FAISS-basierte semantische Auswahl.
        Nutzt TRIGGER_PROMPTS für Text→Embedding Query.
        Fallback auf motion-basierte Auswahl wenn FAISS nicht verfügbar.
        """
        # Prompt für diesen Trigger-Typ holen
        prompt = TRIGGER_PROMPTS.get(trigger_type, DEFAULT_PROMPT)

        # FAISS-Suche via SigLIP Embedding
        try:
            embedding = self._get_text_embedding(prompt)
            if embedding is not None and self.vector_store is not None:
                results = self.vector_store.search(embedding, k=min(10, len(clips)))

                # Ergebnis-Pfade aus FAISS
                faiss_paths = set()
                for meta, score in results:
                    p = meta.get("path", meta.get("file_path", ""))
                    if p:
                        faiss_paths.add(p)

                # Kandidaten filtern: Nur Clips die in FAISS-Ergebnis sind
                semantic_candidates = [
                    c for c in clips
                    if c.get("file_path", c.get("path", "")) in faiss_paths
                ]

                if semantic_candidates:
                    # Unter semantischen Kandidaten nach Motion wählen
                    return self._select_by_motion(semantic_candidates, trigger_strength, trigger_type)

        except Exception as e:
            logger.warning(f"Semantische Suche fehlgeschlagen: {e} — Fallback auf Motion")

        return self._select_by_motion(clips, trigger_strength, trigger_type)

    def _get_text_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Holt Text-Embedding für Semantic Search.
        Nutzt SigLIP ONNX Model via AMD DirectML.
        Cache verhindert mehrfache Inferenz für gleichen Text.
        """
        cache_key = f"text:{text}"
        cached = self._embedding_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            from ..ai.smart_director import SmartDirector
            # Versuche SigLIP Text-Encoder über SmartDirector
            # (SmartDirector hat bereits ONNX/DirectML initialisiert)
            sd = SmartDirector.get_instance() if hasattr(SmartDirector, "get_instance") else None
            if sd and hasattr(sd, "encode_text"):
                emb = sd.encode_text(text)
                if emb is not None:
                    self._embedding_cache.set(cache_key, emb)
                    return emb
        except Exception:
            pass

        # Fallback: Zufälliges Embedding (degraded mode)
        logger.debug(f"Text-Embedding nicht verfügbar für: '{text}' — degraded mode")
        return None

    def _analyze_clip_motion(self, file_path: str) -> float:
        """
        Analysiert Motion-Score eines Video-Clips.
        Nutzt RAFT ONNX wenn verfügbar, sonst Librosa/OpenCV-Fallback.
        """
        try:
            # Versuche RAFT-basierte Analyse via VideoAnalyzer
            from ..video.raft import RAFTOpticalFlow
            analyzer = RAFTOpticalFlow()
            if hasattr(analyzer, "get_motion_score"):
                score = analyzer.get_motion_score(file_path)
                if score is not None:
                    return float(score)
        except Exception:
            pass

        try:
            # OpenCV-Fallback: Frame-Differenz als Motion-Proxy
            import cv2
            cap = cv2.VideoCapture(str(file_path))
            if not cap.isOpened():
                return 0.5

            scores = []
            prev_frame = None
            frame_count = 0
            max_frames = 20  # Max 20 Frames für Effizienz

            fps = cap.get(cv2.CAP_PROP_FPS) or 25
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            step = max(1, total // max_frames)

            for i in range(0, min(total, max_frames * step), step):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ret, frame = cap.read()
                if not ret:
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if prev_frame is not None:
                    diff = cv2.absdiff(prev_frame, gray)
                    motion = float(np.mean(diff)) / 255.0
                    scores.append(motion)
                prev_frame = gray
                frame_count += 1

            cap.release()
            if scores:
                raw_score = float(np.mean(scores))
                # Normalisierung: Typischer Wertebereich 0.01-0.15 → 0.0-1.0
                return min(1.0, raw_score * 8.0)
        except Exception as e:
            logger.debug(f"OpenCV Motion-Analyse fehlgeschlagen für {file_path}: {e}")

        return 0.5  # Neutral-Fallback

    # =========================================================================
    # FAISS-ARCHITEKTUR (AMD-Original, vollständig erhalten)
    # =========================================================================

    def add_clip(self, clip: ClipMetadata) -> int:
        """Fügt einen Clip zur Auswahl hinzu (FAISS-Architektur)."""
        if clip.embedding is not None and self.vector_store is not None:
            meta_info = {
                "video_id": clip.video_id,
                "file_path": clip.file_path,
                "start_time": clip.start_time,
                "duration": clip.duration,
                "motion_score": clip.motion_score,
                "energy_score": clip.energy_score,
                "tags": clip.tags,
            }
            faiss_id = self.vector_store.add_embedding(clip.embedding, meta_info)
            self.clip_cache[faiss_id] = clip
            return faiss_id
        else:
            clip_id = clip.video_id
            self.clip_cache[clip_id] = clip
            return clip_id

    def select_by_similarity(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        exclude_ids: Optional[List[int]] = None,
    ) -> List[Tuple[ClipMetadata, float]]:
        """FAISS-basierte Ähnlichkeitssuche."""
        if self.vector_store is None or self.vector_store.index.ntotal == 0:
            logger.warning("VectorStore nicht verfügbar — Zufallsauswahl")
            return self._random_selection_meta(k)

        results = self.vector_store.search(query_embedding, k=k * 2)
        selected = []
        exclude_set = set(exclude_ids) if exclude_ids else set()

        for meta, score in results:
            faiss_id = meta.get("video_id", -1)
            if faiss_id in exclude_set:
                continue
            clip = ClipMetadata(
                video_id=meta.get("video_id", -1),
                file_path=meta.get("file_path", ""),
                start_time=meta.get("start_time", 0.0),
                duration=meta.get("duration", 0.0),
                motion_score=meta.get("motion_score", 0.0),
                energy_score=meta.get("energy_score", 0.0),
                tags=meta.get("tags", []),
            )
            selected.append((clip, float(score)))
            if len(selected) >= k:
                break

        return selected

    def select_by_motion(
        self,
        motion_threshold: float,
        operator: str = "greater",
        k: int = 10,
    ) -> List[ClipMetadata]:
        """Filtert Clips nach Motion-Intensität (FAISS-Architektur)."""
        filtered = []
        for clip in self.clip_cache.values():
            if operator == "greater" and clip.motion_score > motion_threshold:
                filtered.append(clip)
            elif operator == "less" and clip.motion_score < motion_threshold:
                filtered.append(clip)
            elif operator == "equal" and abs(clip.motion_score - motion_threshold) < 0.1:
                filtered.append(clip)
        filtered.sort(key=lambda c: c.motion_score, reverse=True)
        return filtered[:k]

    def select_by_energy(
        self,
        energy_level: float,
        tolerance: float = 0.2,
        k: int = 10,
    ) -> List[ClipMetadata]:
        """Wählt Clips nach Energie-Level (FAISS-Architektur)."""
        filtered = []
        for clip in self.clip_cache.values():
            if abs(clip.energy_score - energy_level) <= tolerance:
                filtered.append((clip, abs(clip.energy_score - energy_level)))
        filtered.sort(key=lambda x: x[1])
        return [c for c, _ in filtered[:k]]

    def select_by_tags(
        self,
        required_tags: List[str],
        any_match: bool = False,
        k: int = 10,
    ) -> List[ClipMetadata]:
        """Wählt Clips nach Tags (FAISS-Architektur)."""
        filtered = []
        required_set = set(required_tags)
        for clip in self.clip_cache.values():
            clip_tags = set(clip.tags)
            if any_match:
                if clip_tags & required_set:
                    filtered.append(clip)
            else:
                if required_set.issubset(clip_tags):
                    filtered.append(clip)
        return filtered[:k]

    def select_hybrid(
        self,
        query_embedding: Optional[np.ndarray] = None,
        energy_target: Optional[float] = None,
        motion_threshold: Optional[float] = None,
        required_tags: Optional[List[str]] = None,
        weights: Optional[Dict[str, float]] = None,
        k: int = 5,
    ) -> List[Tuple[ClipMetadata, float]]:
        """Hybrid-Auswahl mit gewichteten Kriterien (FAISS-Architektur)."""
        if weights is None:
            weights = {"similarity": 0.5, "energy": 0.3, "motion": 0.2}

        candidates = list(self.clip_cache.values())

        if required_tags:
            candidates = [c for c in candidates if set(required_tags).issubset(set(c.tags))]
        if motion_threshold is not None:
            candidates = [c for c in candidates if c.motion_score >= motion_threshold]
        if not candidates:
            return []

        scored = []
        for clip in candidates:
            score = 0.0
            if query_embedding is not None and clip.embedding is not None:
                score += self._cosine_similarity(query_embedding, clip.embedding) * weights.get("similarity", 0.0)
            if energy_target is not None:
                score += (1.0 - abs(clip.energy_score - energy_target)) * weights.get("energy", 0.0)
            score += clip.motion_score * weights.get("motion", 0.0)
            scored.append((clip, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Cosine-Similarity zwischen zwei Vektoren."""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def _random_selection_meta(self, k: int) -> List[Tuple[ClipMetadata, float]]:
        """Fallback: Zufällige ClipMetadata-Auswahl."""
        clips = list(self.clip_cache.values())
        if not clips:
            return []
        selected = random.sample(clips, min(k, len(clips)))
        return [(clip, 0.5) for clip in selected]

    def clear_cache(self) -> None:
        """Leert den Clip-Cache (FAISS-Architektur)."""
        self.clip_cache.clear()
        self._motion_cache.clear()
        self._embedding_cache.clear()
        logger.info("Clip-Cache geleert")

    def get_statistics(self) -> Dict[str, object]:
        """Statistiken über den Clip-Pool."""
        if not self.clip_cache:
            return {"total_clips": 0, "avg_motion": 0.0, "avg_energy": 0.0, "unique_tags": []}

        motion_scores = [c.motion_score for c in self.clip_cache.values()]
        energy_scores = [c.energy_score for c in self.clip_cache.values()]
        all_tags: set = set()
        for clip in self.clip_cache.values():
            all_tags.update(clip.tags)

        return {
            "total_clips": len(self.clip_cache),
            "avg_motion": float(np.mean(motion_scores)) if motion_scores else 0.0,
            "avg_energy": float(np.mean(energy_scores)) if energy_scores else 0.0,
            "unique_tags": sorted(list(all_tags)),
            "blacklist_size": len(self._recently_used),
        }
