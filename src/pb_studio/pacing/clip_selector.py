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
from typing import Dict, List, Optional, Tuple

import numpy as np
from pathlib import Path
from dataclasses import dataclass

from .pacing_models import SelectedClip
from .constants import (
    EMBEDDING_CACHE_SIZE,
    MOTION_TOLERANCE,
    BLACKLIST_PERCENTAGE,
    MAX_BLACKLIST_SIZE,
    SMALL_LIBRARY_THRESHOLD,
    SMALL_LIBRARY_MAX_BLACKLIST_PERCENTAGE,
    MIN_SELECTABLE_CLIPS,
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
# THEMATISCHE NARRATIVE CLUSTER & KEYWORDS (Stufe 3)
# =============================================================================

THEMATIC_CLUSTERS: Dict[str, List[int]] = {
    "gothic_demonic": [1, 8, 9, 6],
    "neon_cyber_rave": [0, 10, 11, 12],
    "mystic_nature": [2, 5, 15, 17, 19],
    "ethereal_water": [3, 4, 7, 13, 14, 16, 18]
}

THEMATIC_KEYWORDS: Dict[str, List[str]] = {
    "gothic_demonic": ["gothic", "demon", "devil", "horns", "witch", "monster", "vampire", "dark forest", "ritual", "dark dress"],
    "neon_cyber_rave": ["neon", "cyberpunk", "rave", "bioluminescent", "laser", "futuristic", "synthesizer", "party"],
    "mystic_nature": ["mushrooms", "eerie trees", "enchanted forest", "magic", "moss", "fern", "glowing plants", "mystical forest"],
    "ethereal_water": ["waterfall", "goddess", "dress", "river", "temple", "lake", "floating", "ethereal woman", "angel"]
}

def belongs_to_theme(clip: dict, theme: str) -> bool:
    """Prüft, ob ein Clip-Metadaten-Dict zu einem Thema gehört."""
    # 1. Check if the cluster belongs to the theme
    cluster = clip.get("cluster")
    if cluster is not None:
        try:
            cluster_val = int(cluster)
            if cluster_val in THEMATIC_CLUSTERS[theme]:
                return True
        except (ValueError, TypeError):
            pass
            
    # 2. Check if caption/tags/name has any associated theme keywords
    desc = ""
    if "inhalt" in clip and clip["inhalt"]:
        desc += " " + str(clip["inhalt"]).lower()
    if "description" in clip and clip["description"]:
        desc += " " + str(clip["description"]).lower()
    if "name" in clip and clip["name"]:
        desc += " " + str(clip["name"]).lower()
    if "tags" in clip and clip["tags"]:
        desc += " " + " ".join([str(t).lower() for t in clip["tags"]])

    for kw in THEMATIC_KEYWORDS[theme]:
        if kw in desc:
            return True
    return False


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
        self._blacklist_size = 0

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

        # Plan Phase 4 deep-hook: brain reranker (set externally by PacingService)
        self.brain_reranker = None
        self.brain_context_keys: Optional[list[str]] = None
        self.brain_audio_features: dict = {}
        self.brain_video_features_by_clip: dict = {}
        self.brain_min_confidence: float = 0.0
        self.brain_feature_adapter = None

        # Audit E1 + L-K4: Camelot-Wheel Tonart-Matching.
        # use_key_matching: Master-Switch (vom PacingService gesetzt).
        # audio_key: Tonart des Audio-Tracks (vom AudioAnalyzer KeyDetector).
        # video_keys: {clip_id: video_audio_key} per Clip — vom audio_key_detector
        # via _run_video_analysis erzeugt. Wirkt in _select_by_motion als
        # multiplicativer Score-Bonus (0.3..1.0) auf die Motion-Selektion.
        self.use_key_matching: bool = False
        self.audio_key: Optional[str] = None
        self.video_keys: Dict = {}

        # L-TI-1: Per-call prompt override (set by select_clip), consumed
        # by _select_semantic. None = use TRIGGER_PROMPTS default.
        self._current_prompt_override: Optional[str] = None

        # --- Für Audio-Heuristik (Stufe 2) ---
        self.bass_curve: Optional[np.ndarray] = None
        self.energy_curve: Optional[np.ndarray] = None
        self.duration_seconds: float = 0.0

        # --- Für narrative Stile (Stufe 3) ---
        self.active_theme: Optional[str] = None

        # --- Für Obsidian Storyboard Canvas & Bridges (Stufe 4) ---
        self.bridging_in_to: Optional[dict] = None
        self.bridging_out_of: Optional[dict] = None

    def get_audio_state_at_time(self, time_sec: float) -> str:
        """Erkennt den Audio-Zustand (drop, break, normal) basierend auf der Bass-Kurve."""
        curve = self.bass_curve if self.bass_curve is not None and len(self.bass_curve) > 0 else self.energy_curve
        if curve is None or len(curve) == 0 or self.duration_seconds <= 0:
            return "normal"

        pos = max(0.0, min(1.0, time_sec / self.duration_seconds))
        idx = int(pos * (len(curve) - 1))
        curr_low = float(curve[idx])

        # Past low (ca. 4 Sekunden zurück)
        past_idx = max(0, idx - 4)
        if idx > past_idx:
            past_low = float(np.mean(curve[past_idx:idx]))
        else:
            past_low = curr_low

        # Future low (ca. 4 Sekunden voraus)
        fut_idx = min(len(curve) - 1, idx + 4)
        if fut_idx > idx:
            fut_low = float(np.mean(curve[idx:fut_idx]))
        else:
            fut_low = curr_low

        # Drop: Anstieg im Bass
        idx_2 = max(0, idx - 2)
        is_drop = (curr_low > 0.58 and past_low < 0.35 and (curr_low - float(curve[idx_2]) > 0.25))

        # Break: Ruhige Phase
        is_break = (curr_low < 0.22 and fut_low < 0.22)

        if is_drop:
            return "drop"
        elif is_break:
            return "break"
        return "normal"

    # =========================================================================
    # NV-KOMPATIBLE API: select_clip(), analyze_all_clips(), reset()
    # =========================================================================

    def _adaptive_blacklist_size(self, available_count: int) -> int:
        if available_count <= 1:
            return 0
        percentage = self.blacklist_percentage
        if available_count <= SMALL_LIBRARY_THRESHOLD:
            percentage = min(
                percentage,
                SMALL_LIBRARY_MAX_BLACKLIST_PERCENTAGE,
            )
        requested = int(available_count * percentage)
        selectable_floor = (
            1
            if available_count < MIN_SELECTABLE_CLIPS
            else MIN_SELECTABLE_CLIPS
        )
        return max(
            0,
            min(
                MAX_BLACKLIST_SIZE,
                requested,
                available_count - selectable_floor,
            ),
        )

    def select_clip(
        self,
        available_clips: List[dict],
        trigger_strength: float = 0.5,
        trigger_type: str = "beat",
        # P3.4 vulture-clarification: Compat-Param fuer NV-API, aktuell unused, future routing-hook.
        previous_clip_id: Optional[str] = None,  # noqa: ARG002
        prompt: Optional[str] = None,
        current_time: Optional[float] = None,
        active_theme: Optional[str] = None,
        **_unused,
    ) -> SelectedClip:
        """
        NV-kompatible Methode: Wählt den besten Clip für einen Schnitt.

        Args:
            available_clips: Liste verfügbarer Clips (dict mit id, file_path, etc.)
            trigger_strength: Stärke des Audio-Triggers (0.0-1.0)
            trigger_type: Typ des Triggers (beat, onset, kick, etc.)
            previous_clip_id: ID des vorherigen Clips (für Kontinuität)
            prompt: Optionaler semantischer Override-Prompt (L-TI-1). Wenn gesetzt,
                aktiviert er den FAISS-Semantic-Pfad und ueberschreibt den Default-
                TRIGGER_PROMPTS-Eintrag fuer diesen Cut. None = klassischer Pfad
                (motion/random/round_robin/semantic je nach self.strategy).
            current_time: Optionale aktuelle Zeit im Track in Sekunden (Stufe 2).
            active_theme: Optionales narratives Kapitel-Thema (Stufe 3).
            **_unused: Forward-kompatibler Catch-all fuer kuenftige Kwargs (verhindert
                Wiederholung von L-TI-1 wenn neue Caller weitere optionale Args senden).

        Returns:
            SelectedClip mit dem gewählten Clip
        """
        if not available_clips:
            logger.warning("Keine Clips verfügbar")
            return SelectedClip(clip_id="none", clip_path="", score=0.0)

        # Stufe 3: Aktives Thema sichern
        if active_theme is not None:
            self.active_theme = active_theme

        # L-TI-1: Wenn caller einen expliziten Prompt liefert, semantic Pfad aktivieren.
        # Backward-compat: prompt=None / "" laesst self.strategy unveraendert.
        if prompt:
            self._current_prompt_override = prompt
        else:
            self._current_prompt_override = None

        # Dynamische Blacklist-Größe
        available_ids = {
            str(clip.get("id", ""))
            for clip in available_clips
        }
        self._blacklist_size = self._adaptive_blacklist_size(
            len(available_ids)
        )
        recent_unique: list[str] = []
        seen_recent: set[str] = set()
        for clip_id in reversed(self._recently_used):
            if clip_id in available_ids and clip_id not in seen_recent:
                seen_recent.add(clip_id)
                recent_unique.append(clip_id)
        self._recently_used = deque(reversed(recent_unique))
        while len(self._recently_used) > self._blacklist_size:
            self._recently_used.popleft()

        # Blacklist anwenden
        candidates = [
            clip for clip in available_clips
            if str(clip.get("id", "")) not in self._recently_used
        ]
        if not candidates:
            candidates = available_clips

        # Audio-Zustand für Stufe 2 Audio-Heuristik berechnen
        audio_state = "normal"
        if current_time is not None:
            audio_state = self.get_audio_state_at_time(current_time)

        # Plan Phase 4: brain reranker delegate (deep hook).
        # Wenn reranker + context_keys gesetzt, scoret Brain alle Kandidaten und
        # picked den höchsten — Strategy bleibt als Tiebreak-Fallback.
        if self.brain_reranker is not None and self.brain_context_keys:
            try:
                selected = self._select_via_brain(
                    candidates,
                    trigger_strength,
                    trigger_type,
                    current_time=current_time,
                    cut_duration_sec=float(_unused.get("cut_duration_sec", 1.0)),
                )
                # Blacklist + Roter Faden updates passieren am Funktions-Ende.
            except Exception as e:
                logger.warning(f"Brain reranker failed, fallback strategy: {e}")
                selected = self._fallback_select(
                    candidates, trigger_strength, trigger_type, current_time=current_time, audio_state=audio_state
                )
        else:
            selected = self._fallback_select(
                candidates, trigger_strength, trigger_type, current_time=current_time, audio_state=audio_state
            )

        # Blacklist aktualisieren — R18/MEDIUM-018-3: popleft() is O(1) on deque.
        try:
            self._recently_used.remove(selected.clip_id)
        except ValueError:
            pass
        self._recently_used.append(selected.clip_id)
        if len(self._recently_used) > self._blacklist_size:
            self._recently_used.popleft()

        # Roter Faden: Motion Score merken
        self._last_clip_motion_score = selected.motion_score
        self._last_clip_path = selected.clip_path

        return selected

    def _fallback_select(
        self,
        candidates: List[dict],
        trigger_strength: float,
        trigger_type: str,
        current_time: Optional[float] = None,
        audio_state: str = "normal",
    ) -> "SelectedClip":
        """Original strategy selection — used when no brain reranker available."""
        # L-TI-1: Expliziter Caller-Prompt aktiviert semantic Pfad auch ohne
        # globalen use_semantic-Switch (z.B. pacing_service uebergibt song_mood).
        if self._current_prompt_override or self.use_semantic or self.strategy == "semantic":
            return self._select_semantic(candidates, trigger_strength, trigger_type, current_time=current_time, audio_state=audio_state)
        elif self.strategy == "random":
            return self._select_random(candidates)
        elif self.strategy == "round_robin":
            return self._select_round_robin(candidates)
        else:
            return self._select_by_motion(candidates, trigger_strength, trigger_type, current_time=current_time, audio_state=audio_state)

    def _select_via_brain(
        self,
        candidates: List[dict],
        trigger_strength: float,
        trigger_type: str,
        *,
        current_time: Optional[float] = None,
        cut_duration_sec: float = 1.0,
    ) -> "SelectedClip":
        """Brain reranker scores every candidate, returns highest. Plan Phase 4 deep hook."""
        from pb_studio.brain.feature_adapter import CanonicalFeatureAdapter

        af = self.brain_audio_features or {}
        vf_by_id = self.brain_video_features_by_clip or {}
        adapter = self.brain_feature_adapter or CanonicalFeatureAdapter(
            audio_analysis=af,
            video_analysis_by_clip=vf_by_id,
            fallback_duration=self.duration_seconds,
        )

        rerank_inputs = []
        for clip in candidates:
            cid = str(clip.get("id", ""))
            vf = vf_by_id.get(cid) or vf_by_id.get(f"clip_{cid}") or {}
            feats = adapter.candidate_features(
                clip_id=cid,
                trigger_type=trigger_type,
                trigger_strength=trigger_strength,
                cut_time_sec=float(current_time or 0.0),
                cut_duration_sec=cut_duration_sec,
                audio_embedding=af.get("audio_embedding"),
                video_embedding=vf.get("video_embedding"),
            )
            from pb_studio.brain.reranker import RerankInput
            rerank_inputs.append(RerankInput(candidate=clip, features=feats))

        scored = self.brain_reranker.rerank(
            rerank_inputs,
            context_keys=self.brain_context_keys,
            min_confidence=self.brain_min_confidence,
        )
        if not scored:
            return self._fallback_select(candidates, trigger_strength, trigger_type)

        top = scored[0]
        clip = top.candidate
        clip_path = str(clip.get("file_path", ""))
        clip_id = str(clip.get("id", ""))

        return SelectedClip(
            clip_id=clip_id,
            clip_path=clip_path,
            score=float(top.final_score),
            motion_score=float(top.features.motion_score),
            metadata={
                "brain_scores": top.brain_scores,
                "brain_final_score": float(top.final_score),
                "feature_confidence": float(top.features.confidence),
                "feature_provenance": dict(top.features.feature_provenance),
                "segment_type": top.features.segment_type,
                "semantic_status": top.features.semantic_status,
                "semantic_reason": top.features.semantic_reason,
                "brain_axis_status": {
                    "semantic_match_weight": {
                        "status": top.features.semantic_status,
                        "reason": top.features.semantic_reason,
                    }
                },
            },
        )

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

    def _motion_curve_score(
        self,
        clip_motion_curve,
        clip_duration: float,
        audio_intensity_at_time: float,
    ) -> float:
        """L-M3: Score basierend auf motion-curve mean vs. audio intensity.

        Engine-seitig forwarded pacing_router seit Audit A4 motion_curve in clip_data
        durch — dieser Helper vergleicht den Bewegungs-Mittelwert eines Clips mit der
        aktuellen Audio-Intensität, sodass actionreiche Clips an energiereichen Stellen
        bevorzugt werden.

        Args:
            clip_motion_curve: Liste von Frame-Motion-Werten (typisch 0..50 für RAFT).
            clip_duration: Dauer des Clips in Sekunden (aktuell unbenutzt, behalten
                für künftige zeitlich segmentierte Bewertung).
            audio_intensity_at_time: Audio-Intensität an dieser Position (0..1).

        Returns:
            0.0..1.0 — höher wenn Clip-Motion-Mean zur Audio-Intensität passt.
        """
        if not clip_motion_curve or len(clip_motion_curve) == 0:
            return 0.5  # neutral
        import statistics
        try:
            motion_mean = statistics.fmean(clip_motion_curve)
        except (TypeError, statistics.StatisticsError):
            return 0.5
        # Normiere Motion (typischer max ~30 für action) auf 0..1
        motion_norm = max(0.0, min(1.0, motion_mean / 30.0))
        intensity = max(0.0, min(1.0, audio_intensity_at_time))
        diff = abs(motion_norm - intensity)
        return 1.0 - diff

    def _get_clip_neighbors(self, target_path: str) -> List[str]:
        """Findet die 10 ähnlichsten Clips für einen bestimmten Clip im Vektorraum (Stufe 4)."""
        if not self.vector_store or not target_path:
            return []
        
        # Finde das Embedding des Target-Clips in unserem cache/index
        target_emb = None
        for metadata in self.clip_cache.values():
            if str(Path(metadata.file_path).absolute()) == str(Path(target_path).absolute()):
                target_emb = metadata.embedding
                break
        
        if target_emb is None:
            # Falls kein direktes Metadatenobjekt, suche über textuelle oder strukturelle Übereinstimmung
            return []
            
        try:
            results = self.vector_store.search(target_emb, k=10)
            neighbors = []
            for meta, score in results:
                p = meta.get("path", meta.get("file_path", ""))
                if p:
                    neighbors.append(str(Path(p).absolute()))
            return neighbors
        except Exception:
            return []

    def _select_by_motion(
        self,
        clips: List[dict],
        trigger_strength: float,
        trigger_type: str,
        current_time: Optional[float] = None,
        audio_state: str = "normal",
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
        best_score = -9999.0

        # L-K4: Lazy-Import um Zirkular-Import zu vermeiden.
        _key_score_fn = None
        if self.use_key_matching and self.audio_key:
            try:
                from .advanced_pacing_engine import _key_compatibility_score
                _key_score_fn = _key_compatibility_score
            except Exception:
                _key_score_fn = None

        for clip in clips:
            clip_motion = clip.get("motion_score", 0.5)
            motion_diff = abs(target_motion - clip_motion)
            motion_score = 1.0 - min(motion_diff / (self.motion_tolerance + 0.01), 1.0)

            # L-M3: motion_curve-aware boost. trigger_strength dient als Proxy für
            # die aktuelle Audio-Intensität (energy-curve nicht direkt im Selector
            # verfügbar — bewusst keine position-aware-Logic hardcodet).
            mc = clip.get("motion_curve") if isinstance(clip, dict) else None
            if mc:
                motion_curve_boost = self._motion_curve_score(
                    mc,
                    float(clip.get("duration", 1.0) or 1.0),
                    float(target_motion),
                )
                motion_score = (motion_score + motion_curve_boost) / 2.0

            # Roter Faden: Continuity-Bonus für ähnliche Motion zum letzten Clip
            continuity_bonus = 0.0
            if self._last_clip_path:
                last_motion = self._last_clip_motion_score
                motion_continuity = 1.0 - abs(last_motion - clip_motion)
                continuity_bonus = motion_continuity * self._continuity_weight * 0.5

            total_score = motion_score + continuity_bonus

            # Stufe 2: Audio-Heuristik Scoring-Verstärker
            if audio_state == "break":
                if clip_motion < 0.3:
                    total_score += 0.25
                elif clip_motion < 0.6:
                    total_score += 0.15
                else:
                    total_score -= 0.50
            elif audio_state == "drop":
                if clip_motion >= 0.6:
                    total_score += 0.40

            # Stufe 3: Style-Persistenz / Narrative Kapitel-Themen
            if self.active_theme and belongs_to_theme(clip, self.active_theme):
                total_score += 1000.0

            # Stufe 4: Bridge-Übergänge für manuelle Storyboard-Anker
            if self.bridging_in_to:
                target_path = self.bridging_in_to.get("file_path", self.bridging_in_to.get("path", ""))
                if target_path:
                    neighbors = self._get_clip_neighbors(target_path)
                    current_path = clip.get("file_path", clip.get("path", ""))
                    if current_path and any(str(Path(current_path).absolute()) == str(Path(nb).absolute()) for nb in neighbors):
                        total_score += 400.0

            if self.bridging_out_of:
                target_path = self.bridging_out_of.get("file_path", self.bridging_out_of.get("path", ""))
                if target_path:
                    neighbors = self._get_clip_neighbors(target_path)
                    current_path = clip.get("file_path", clip.get("path", ""))
                    if current_path and any(str(Path(current_path).absolute()) == str(Path(nb).absolute()) for nb in neighbors):
                        total_score += 400.0

            # L-K4: Tonart-Bonus (Camelot-Wheel). Multiplicativer Faktor 0.3..1.0
            # auf die Motion-Selektion. Clips ohne audio_key (None) ergeben 0.5
            # (neutral) — kein Penalty wenn Detection fehlgeschlagen ist.
            if _key_score_fn is not None:
                clip_id = clip.get("id")
                video_key = self.video_keys.get(clip_id) if clip_id is not None else None
                if video_key is None:
                    # Fallback: clip selbst kann audio_key Feld tragen (Test-Pfad).
                    video_key = clip.get("audio_key")
                key_score = _key_score_fn(self.audio_key, video_key)
                total_score *= key_score

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
        current_time: Optional[float] = None,
        audio_state: str = "normal",
    ) -> SelectedClip:
        """
        FAISS-basierte semantische Auswahl.
        Nutzt TRIGGER_PROMPTS für Text→Embedding Query.
        Fallback auf motion-basierte Auswahl wenn FAISS nicht verfügbar.

        L-TI-1: Wenn select_clip einen expliziten prompt-Override geliefert hat,
        wird dieser bevorzugt verwendet (z.B. mood-aware song-prompt aus
        pacing_service). Sonst Default-Trigger-Prompt.
        """
        # Prompt für diesen Trigger-Typ holen (Override-aware)
        prompt = self._current_prompt_override or TRIGGER_PROMPTS.get(
            trigger_type, DEFAULT_PROMPT
        )

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
                    return self._select_by_motion(semantic_candidates, trigger_strength, trigger_type, current_time=current_time, audio_state=audio_state)

        except Exception as e:
            logger.warning(f"Semantische Suche fehlgeschlagen: {e} — Fallback auf Motion")

        return self._select_by_motion(clips, trigger_strength, trigger_type, current_time=current_time, audio_state=audio_state)

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
        Nutzt RAFT ONNX wenn verfügbar, sonst OpenCV-Fallback.
        """
        # 1. Versuche RAFT-basierte Analyse via MotionAnalyzer
        try:
            from ..video.raft import MotionAnalyzer
            analyzer = MotionAnalyzer(lazy_load=True)
            if analyzer.model_path and analyzer.model_path.exists():
                import cv2
                cap = cv2.VideoCapture(str(file_path))
                if cap.isOpened():
                    frames = []
                    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    max_frames = 20
                    step = max(1, total // max_frames)
                    for i in range(0, min(total, max_frames * step), step):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                        ret, frame = cap.read()
                        if not ret:
                            break
                        frames.append(frame)
                    cap.release()

                    if len(frames) >= 2:
                        res = analyzer.analyze_video_segment(frames, stride=1)
                        avg_motion = res.get("avg_motion", 0.0)
                        return min(1.0, max(0.0, float(avg_motion) / 10.0))
        except Exception as e:
            logger.debug(f"RAFT Motion-Analyse fehlgeschlagen für {file_path}: {e}")

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
