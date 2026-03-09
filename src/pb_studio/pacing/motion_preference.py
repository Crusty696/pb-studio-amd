"""
Motion Preference Calculator
=============================

Berechnet die gewünschte Bewegungsintensität für ein Segment
basierend auf Song-Struktur, Spektral-Analyse und Energy-Kurve.

Portiert von NVIDIA-Version, angepasst für AMD DirectML.

v2-Änderungen (AMD Alignment):
- Spektral-Daten-Format-Normalisierung:
  NV-Format: {"times": [...], "bands": {"sub": [...], ...}, "events": {...}}
  AMD-Format: {"bands": {"sub_bass": {"times": [...], "values": [...]}, ...}}
  → Beide Formate werden automatisch erkannt und unified behandelt.
- _combine_preferences(): NV-Logik portiert (Energy-Kurve differenzierter)
- Debug-Log: Erste 5 Segmente analog zu NV
"""

import logging
from typing import Optional, List, Any

import numpy as np

from .constants import MOTION_PREFERENCES

logger = logging.getLogger(__name__)


def _normalize_spectral_data(spectral_data: dict) -> Optional[dict]:
    """
    Normalisiert spektrale Daten aus verschiedenen Formaten zu einem einheitlichen Format.

    Erkennt automatisch:
    - NV-Format: {"times": [...], "bands": {"sub": [...], "bass": [...], ...}, "events": {...}}
      (flache Arrays pro Band, globale times-Liste)
    - AMD-Format: {"bands": {"sub_bass": {"times": [...], "values": [...]}, ...}}
      (pro-Band-Dict mit eigenen times/values)

    Gibt normalisiertes NV-Format zurück:
    {"times": [...], "bands": {"sub": [...], ...}, "events": {...}}
    """
    if not spectral_data:
        return None

    bands = spectral_data.get("bands", {})
    if not bands:
        return None

    # Format erkennen: Prüfe erstes Band-Element
    first_band = next(iter(bands.values()), None)
    if first_band is None:
        return None

    if isinstance(first_band, dict):
        # AMD-Format: {"sub_bass": {"times": [...], "values": [...]}, ...}
        # → Konvertiere zu NV-Format mit globalen times
        all_times = []
        for band_data in bands.values():
            t = band_data.get("times", [])
            if t:
                all_times = t  # Alle Bänder teilen dieselben times
                break

        if not all_times:
            return None

        # Band-Name-Mapping: AMD -> NV (sub_bass -> sub, etc.)
        name_map = {
            "sub_bass": "sub",
            "sub": "sub",
            "bass": "bass",
            "low_mid": "low_mid",
            "mid": "mid",
            "high_mid": "high_mid",
            "presence": "presence",
            "brilliance": "brilliance",
            "air": "air",
        }

        normalized_bands = {}
        for band_name, band_data in bands.items():
            nv_name = name_map.get(band_name, band_name)
            values = band_data.get("values", [])
            if values:
                normalized_bands[nv_name] = values

        return {
            "times": all_times,
            "bands": normalized_bands,
            "events": spectral_data.get("events", {}),
        }

    elif isinstance(first_band, (list, np.ndarray)):
        # NV-Format bereits — direkt zurückgeben
        return spectral_data

    return None


class MotionPreferenceCalculator:
    """Berechnet Motion-Präferenzen für Video-Clip-Matching."""

    def __init__(self):
        self._debug_counter = 0
        self.spectral_data = None  # Wird von SmartDirector gesetzt

    def reset_counter(self):
        """Resettet den Debug-Counter."""
        self._debug_counter = 0

    def calculate(
        self,
        segment_start: float,
        segment_end: float,
        song_sections: Optional[List] = None,
        energy_curve: Optional[Any] = None,
    ) -> float:
        """
        Berechnet die Motion-Präferenz für ein Segment.

        Kombination: 60% Spektral + 40% Struktur (wenn Spektral vorhanden)
        Sonst: differenzierte Energie/Struktur-Gewichtung (NV-Logik)

        Args:
            segment_start: Startzeit des Segments
            segment_end: Endzeit des Segments
            song_sections: Liste von SongSection-Objekten
            energy_curve: Energy-Kurve (als Array oder Liste)

        Returns:
            Motion-Präferenz (0.0 = statisch, 1.0 = dynamisch)
        """
        segment_mid = (segment_start + segment_end) / 2.0

        # Struktur-basierte Präferenz
        structure_pref = self._calculate_structure_preference(segment_mid, song_sections)

        # Spektral-basierte Präferenz (Format-agnostisch via _normalize_spectral_data)
        spectral_pref = self._calculate_spectral_preference(segment_start, segment_end)

        # Energy-basierte Präferenz (Fallback)
        energy_pref = self._calculate_energy_preference(segment_start, segment_end, energy_curve)

        # Kombination (NV-Logik)
        result = self._combine_preferences(structure_pref, spectral_pref, energy_pref)

        # Debug (erste 5 Segmente, analog NV)
        self._debug_counter += 1
        if self._debug_counter <= 5:
            spectral_info = ""
            if self.spectral_data is not None:
                spectral_info = f", spectral={spectral_pref:.2f}"
            logger.info(
                f"MotionPref #{self._debug_counter}: "
                f"struct={structure_pref:.2f}{spectral_info}, "
                f"energy={energy_pref:.2f} → {result:.2f}"
            )

        return result
    
    def _calculate_structure_preference(
        self,
        time_pos: float,
        song_sections: Optional[List] = None
    ) -> float:
        """Motion basierend auf Song-Struktur."""
        if not song_sections:
            return 0.5  # Neutral
        
        for section in song_sections:
            start = getattr(section, 'start_time', None)
            end = getattr(section, 'end_time', None)
            name = getattr(section, 'name', None)
            
            if start is not None and end is not None and name:
                if start <= time_pos < end:
                    return MOTION_PREFERENCES.get(name, 0.5)
        
        return 0.5
    
    def _calculate_spectral_preference(
        self,
        seg_start: float,
        seg_end: float,
    ) -> float:
        """
        Motion basierend auf 8-Band-Spektral-Analyse.

        Unterstützt beide Formate (AMD + NV) via _normalize_spectral_data().
        Sub-Bass dominant → hohe Motion (Drop)
        High-Freq dominant → mittlere Motion (Build-up)
        Breakdown erkannt → niedrige Motion
        """
        if self.spectral_data is None:
            return 0.5

        try:
            # Format normalisieren (AMD-Dict oder NV-Flat)
            normalized = _normalize_spectral_data(self.spectral_data)
            if normalized is None:
                return 0.5

            times = np.array(normalized.get("times", []))
            if len(times) == 0:
                return 0.5

            start_idx = int(np.searchsorted(times, seg_start))
            end_idx = int(np.searchsorted(times, seg_end))
            start_idx = max(0, min(start_idx, len(times) - 1))
            end_idx = max(start_idx + 1, min(end_idx, len(times)))

            bands = normalized.get("bands", {})

            def _band_mean(name: str) -> float:
                arr = np.array(bands.get(name, []))
                if len(arr) == 0:
                    return 0.5
                return float(np.mean(arr[start_idx:end_idx]))

            def _band_max(name: str) -> float:
                arr = np.array(bands.get(name, []))
                if len(arr) == 0:
                    return 0.5
                return float(np.max(arr[start_idx:end_idx]))

            sub_energy = _band_mean("sub")
            sub_peak = _band_max("sub")
            bass_energy = _band_mean("bass")
            mid_energy = _band_mean("mid")
            presence_energy = _band_mean("presence")
            air_energy = _band_mean("air")

            # Gewichtete Motion (NV-Logik)
            total_energy = sub_energy + bass_energy + mid_energy + presence_energy + air_energy
            if total_energy > 0.1:
                spectral_motion = (
                    sub_energy * 0.9
                    + bass_energy * 0.7
                    + mid_energy * 0.4
                    + presence_energy * 0.8
                    + air_energy * 0.3
                ) / total_energy
            else:
                # Fallback: einfache gewichtete Summe
                spectral_motion = (
                    sub_energy * 0.25 + bass_energy * 0.20 + mid_energy * 0.20
                    + presence_energy * 0.10 + air_energy * 0.05
                )

            # Drop-Boost: Sub-Bass-Peak > 0.8
            if sub_peak > 0.8:
                spectral_motion = min(1.0, spectral_motion + 0.2)

            # Events: Build-up / Breakdown
            events = normalized.get("events", {})
            for buildup in events.get("buildups", []):
                if buildup.get("start", 0) <= seg_end and buildup.get("end", 0) >= seg_start:
                    spectral_motion = 0.4 + (air_energy * 0.3)
                    break
            for breakdown in events.get("breakdowns", []):
                if breakdown.get("start", 0) <= seg_end and breakdown.get("end", 0) >= seg_start:
                    spectral_motion = 0.2
                    break

            return max(0.0, min(1.0, spectral_motion))

        except Exception as e:
            logger.debug(f"Spectral motion preference fehlgeschlagen: {e}")
            return 0.5
    
    def _calculate_energy_preference(
        self,
        seg_start: float,
        seg_end: float,
        energy_curve: Optional[Any] = None
    ) -> float:
        """Motion basierend auf Energy-Kurve."""
        if energy_curve is None:
            return 0.5
        
        try:
            import numpy as np
            curve = np.array(energy_curve)
            if len(curve) == 0:
                return 0.5
            
            start_idx = max(0, int(seg_start))
            end_idx = min(len(curve), int(seg_end) + 1)
            
            if start_idx >= end_idx:
                return 0.5
            
            avg_energy = float(np.mean(curve[start_idx:end_idx]))
            return max(0.0, min(1.0, avg_energy))
            
        except Exception:
            return 0.5
    
    def _combine_preferences(
        self,
        structure: float,
        spectral: float,
        energy: float,
    ) -> float:
        """
        Kombiniert die verschiedenen Motion-Quellen (NV-Logik portiert).

        Mit Spektral: 60% Spektral + 40% Struktur
        Ohne Spektral + mit Energy: differenziert nach Stärke
        Nur Struktur: direkte Rückgabe
        """
        if self.spectral_data is not None:
            # Spektral dominiert
            return max(0.0, min(1.0, spectral * 0.6 + structure * 0.4))
        elif energy != 0.5:
            # Energy-Kurve verfügbar: differenzierte Gewichtung
            if energy > 0.8 or energy < 0.2:
                # Starke Abweichung: Energy dominiert
                return max(0.0, min(1.0, structure * 0.3 + energy * 0.7))
            else:
                # Mittlere Energie: gleichgewichtet
                return max(0.0, min(1.0, structure * 0.5 + energy * 0.5))
        else:
            # Nur Struktur
            return max(0.0, min(1.0, structure))
