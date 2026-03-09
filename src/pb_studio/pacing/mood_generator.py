"""
Mood Generator
==============

Generiert energy-basierte Mood-Texte für semantisches Clip-Matching.
Variiert den Base-Mood basierend auf Song-Struktur und Energy-Kurve.

Portiert von NVIDIA-Version, angepasst für AMD DirectML.
"""

import logging
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

# Mood-Texte basierend auf Song-Struktur
STRUCTURE_MOODS = {
    "intro": "calm atmospheric opening scene, slow establishing shot",
    "verse": "moderate energy, natural movement, storytelling",
    "chorus": "high energy, dynamic movement, vibrant colors",
    "drop": "intense explosive energy, rapid movement, strobe lights, crowd",
    "breakdown": "calm peaceful, slow motion, ambient, dreamy",
    "buildup": "rising tension, increasing speed, anticipation",
    "bridge": "transitional, changing mood, reflective",
    "outro": "fading energy, slow ending, peaceful closing",
    # DJ-Mix Phasen
    "high_energy": "maximum energy, fast cuts, intense visuals, crowd jumping",
    "rising": "building energy, accelerating, growing intensity",
    "falling": "decreasing energy, slowing down, calming",
    "low_energy": "minimal movement, ambient, slow, peaceful",
    "plateau": "steady energy, consistent rhythm, balanced",
}

# Energy-Level zu Mood-Modifier
ENERGY_MOODS = {
    (0.0, 0.2): "very calm, slow, peaceful, ambient",
    (0.2, 0.4): "gentle, moderate, relaxed",
    (0.4, 0.6): "medium energy, balanced, rhythmic",
    (0.6, 0.8): "energetic, dynamic, fast movement",
    (0.8, 1.0): "maximum energy, explosive, intense, rapid",
}


class MoodGenerator:
    """Generiert kontextabhängige Mood-Beschreibungen für Clip-Matching."""
    
    def __init__(self):
        self._debug_counter = 0
        self.spectral_data = None  # Wird von SmartDirector gesetzt
    
    def reset_counter(self):
        """Resettet den Debug-Counter."""
        self._debug_counter = 0
    
    def generate(
        self,
        base_mood: str,
        segment_start: float,
        segment_end: float,
        energy_curve: Optional[Any] = None,
        song_sections: Optional[List] = None,
    ) -> str:
        """
        Generiert einen Mood-Text für ein Segment.
        
        Kombiniert: base_mood + section_mood + energy_mood + spectral_mood
        
        Args:
            base_mood: Basis-Mood vom User
            segment_start: Startzeit des Segments
            segment_end: Endzeit des Segments
            energy_curve: Energy-Kurve (numpy array oder Liste)
            song_sections: Liste von SongSection-Objekten
            
        Returns:
            Kombinierter Mood-Text
        """
        parts = [base_mood]
        segment_mid = (segment_start + segment_end) / 2.0
        
        # 1. Song-Struktur Mood
        section_mood = self._get_section_mood(segment_mid, song_sections)
        if section_mood:
            parts.append(section_mood)
        
        # 2. Energy-basierter Mood
        energy_mood = self._get_energy_mood(segment_start, segment_end, energy_curve)
        if energy_mood:
            parts.append(energy_mood)
        
        # 3. Spektral-basierter Mood (wenn verfügbar)
        spectral_mood = self._get_spectral_mood(segment_start, segment_end)
        if spectral_mood:
            parts.append(spectral_mood)
        
        # Debug-Log für erste Segmente
        self._debug_counter += 1
        if self._debug_counter <= 3:
            logger.debug(f"MoodGenerator: '{', '.join(parts)}'")
        
        return ", ".join(parts)
    
    def _get_section_mood(
        self,
        time_pos: float,
        song_sections: Optional[List] = None
    ) -> Optional[str]:
        """Bestimmt Mood basierend auf Song-Abschnitt."""
        if not song_sections:
            return None
        
        for section in song_sections:
            start = getattr(section, 'start_time', None)
            end = getattr(section, 'end_time', None)
            name = getattr(section, 'name', None)
            
            if start is not None and end is not None and name:
                if start <= time_pos < end:
                    return STRUCTURE_MOODS.get(name, None)
        
        return None
    
    def _get_energy_mood(
        self,
        seg_start: float,
        seg_end: float,
        energy_curve: Optional[Any] = None
    ) -> Optional[str]:
        """Bestimmt Mood basierend auf Energy-Kurve."""
        if energy_curve is None:
            return None
        
        try:
            import numpy as np
            
            # Energy-Kurve ist typischerweise ein Array mit Werten pro Zeiteinheit
            curve = np.array(energy_curve)
            if len(curve) == 0:
                return None
            
            # Zeitfenster extrahieren
            total_duration = len(curve)  # Annahme: 1 Wert pro Sekunde
            start_idx = max(0, int(seg_start))
            end_idx = min(total_duration, int(seg_end) + 1)
            
            if start_idx >= end_idx:
                return None
            
            # Durchschnittliche Energy im Segment
            avg_energy = float(np.mean(curve[start_idx:end_idx]))
            avg_energy = max(0.0, min(1.0, avg_energy))
            
            # Passenden Mood finden
            for (low, high), mood_text in ENERGY_MOODS.items():
                if low <= avg_energy < high:
                    return mood_text
            
            # Fallback für energy == 1.0
            return "maximum energy, explosive, intense, rapid"
            
        except Exception as e:
            logger.debug(f"Energy-Mood Berechnung fehlgeschlagen: {e}")
            return None
    
    def _get_spectral_mood(
        self,
        seg_start: float,
        seg_end: float
    ) -> Optional[str]:
        """Bestimmt Mood basierend auf Spektral-Daten (wenn verfügbar)."""
        if self.spectral_data is None:
            return None
        
        try:
            events = self.spectral_data.get("events", {})
            seg_mid = (seg_start + seg_end) / 2.0
            
            # Prüfe ob Drop im Segment
            for drop in events.get("drops", []):
                if seg_start - 1 <= drop.get("time", -1) <= seg_end + 1:
                    return "bass drop, explosive energy, maximum impact"
            
            # Prüfe ob Buildup im Segment
            for buildup in events.get("buildups", []):
                if buildup.get("start", 0) <= seg_end and buildup.get("end", 0) >= seg_start:
                    return "rising tension, building anticipation, increasing frequency"
            
            # Prüfe ob Breakdown im Segment
            for breakdown in events.get("breakdowns", []):
                if breakdown.get("start", 0) <= seg_end and breakdown.get("end", 0) >= seg_start:
                    return "atmospheric breakdown, ambient, ethereal"
            
            return None
            
        except Exception as e:
            logger.debug(f"Spectral-Mood Berechnung fehlgeschlagen: {e}")
            return None
