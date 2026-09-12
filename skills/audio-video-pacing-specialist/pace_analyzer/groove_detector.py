"""Groove & Rhythmus-Erkennung — Percussive Patterns, Syncopation, Groove Feel."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class GrooveFeature:
    """A single rhythmic feature detected in the audio."""
    name: str = ""          # "kick_pattern", "snare_position", etc.
    strength: float = 0.5   # 0-1 detection confidence
    periodicity_ms: Optional[float] = None  # Expected period in ms
    syncopation_level: float = 0.0    # How off-grid the rhythm is


@dataclass  
class GrooveResult:
    """Complete groove analysis for a section."""
    overall_groove_score: float = 0.5     # 0-1, how "groovy" it feels
    bpm_category: str = "mid-fast"        # slow / mid-fast / mid / fast / very-fast
    beat_strength: float = 0.5            # How strong the beat is (driving force)
    syncopation_level: float = 0.3        # Syncopation intensity (off-beat emphasis)
    swing_percentage: float = 2.0         # Swing/Rubato amount (%)
    
    # Rhythmic features detected
    kick_pattern_detected: bool = False
    kick_period_ms: Optional[float] = None
    
    snare_position: str = "backbeat"      # backbeat / off-beat / constant
    hihat_pattern: str = "steady"         # steady / open_close / roll
    
    groove_quality_label: str = ""        # Human-readable quality label
    
    # Groove characteristics
    driving_force: float = 0.5            # How much it pushes forward
    rhythmic_complexity: float = 0.3      # Complexity of rhythm pattern (0=steady, 1=complex)
    
    def to_dict(self):
        return {
            "overall_groove_score": round(self.overall_groove_score, 3),
            "bpm_category": self.bpm_category,
            "beat_strength": round(self.beat_strength, 3),
            "syncopation_level": round(self.syncopation_level, 3),
            "swing_percentage": round(self.swing_percentage, 1),
            "kick_pattern_detected": self.kick_pattern_detected,
            "snare_position": self.snare_position,
            "hihat_pattern": self.hihat_pattern,
            "driving_force": round(self.driving_force, 3),
            "rhythmic_complexity": round(self.rhythmic_complexity, 3),
            "groove_quality_label": self.groove_quality_label,
        }


class GrooveDetector:
    """
    Detects groove patterns and rhythmic characteristics.
    
    Core concepts detected:
    - Kick/Snare/Hihat placement (backbeat vs syncopated)
    - Swing/Rubato amount (how much off-grid the rhythm is)
    - Syncopation level (emphasis on weak beats)
    - Driving force (forward momentum of the rhythm)
    """
    
    def __init__(self):
        self.result: Optional[GrooveResult] = None
    
    def analyze_rms_envelope(self, rms_frames: list[float], sample_rate: int) -> GrooveResult:
        """Estimate groove from RMS energy envelope periodicity."""
        import numpy as np
        
        n = len(rms_frames)
        if n < 20:
            self.result = self._create_default_groove()
            return self.result

        rms_arr = np.array(rms_frames, dtype=np.float64) - np.mean(rms_frames)
        rms_norm = rms_arr / (np.std(rms_arr) + 1e-6) if np.std(rms_arr) > 0 else np.zeros(n)
        
        # Detect beat periodicity at common BPM intervals
        best_period_ms = None
        best_correlation = 0.3
        
        for target_bpm in range(70, 200, 5):
            period_samples = int(sample_rate * 60.0 / target_bpm)
            
            if period_samples >= n // 4:
                continue
            
            # Autocorrelation at expected beat interval
            ac_vals = []
            for start_idx in range(0, n - period_samples, max(period_samples // 3, 1)):
                window2 = rms_norm[start_idx + period_samples:start_idx + 2 * period_samples]
                
                if len(window2) > 5:
                    cross_corr = np.dot(rms_norm[start_idx:start_idx+period_samples], window2) / (
                        max(np.std(rms_norm[max(0,start_idx):start_idx+period_samples]), 0.001) * 
                        max(np.std(window2), 0.001))
                    ac_vals.append(max(-1, min(1, cross_corr)))
            
            avg_ac = sum(ac_vals) / max(len(ac_vals), 3) if ac_vals else 0
            
            if avg_ac > best_correlation:
                best_correlation = avg_ac
                best_period_ms = period_samples * 1000.0 / max(1, sample_rate)
        
        # Derive groove characteristics from periodicity analysis
        self._populate_groove_from_rms(best_correlation, best_period_ms, rms_arr, sample_rate)
        
        return self.result
    
    def _populate_groove_from_rms(self, correlation: float, period_ms: int | None, 
                                    rms_arr: list[float] | Any, sample_rate: int):
        """Fill groove result from RMS analysis."""
        if hasattr(rms_arr, "tolist"):
            rms_arr = rms_arr.tolist()
        elif not isinstance(rms_arr, list):
            rms_arr = list(rms_arr) if rms_arr is not None else []
        n = len(rms_arr)
        
        # Beat strength from correlation quality
        beat_strength = min(1.0, max(0.3, (correlation + 0.5) * 2))
        
        # Groove score combines multiple factors
        groove_score = self._estimate_groove_from_correlation(correlation)
        
        # Syncopation: check if energy peaks are regularly distributed or clustered
        sync_level = self._estimate_syncopation(rms_arr, period_ms, sample_rate)
        
        # Swing: compare even vs odd beat intensities
        swing = self._estimate_swing(rms_arr, period_ms)
        
        # Driving force from overall energy trend
        driving_force = self._estimate_driving_force(rms_arr)
        
        # Rhythmic complexity from envelope variation
        complexity = self._estimate_complexity(rms_arr)
        
        # BPM category
        bpm_cat = "mid-fast" if period_ms and 300 < period_ms < 1200 else (
            "slow" if period_ms and period_ms > 1200 else ("fast" if period_ms and period_ms < 300 else "mid")
        )
        
        # Classify snare position based on periodicity pattern
        snare_pos = self._classify_snare_position(rms_arr, period_ms)
        
        # Hi-hat pattern from high-frequency energy (approximation via RMS fine structure)
        hihat_pattern = self._classify_hihat_pattern(rms_arr, sample_rate)
        
        # Human-readable quality label
        groove_label = self._describe_groove_quality(beat_strength, sync_level, swing, bpm_cat)
        
        self.result = GrooveResult(
            overall_groove_score=groove_score,
            bpm_category=bpm_cat,
            beat_strength=round(beat_strength, 3),
            syncopation_level=min(1.0, max(0.0, sync_level)),
            swing_percentage=max(0.0, min(25.0, swing * 100)),
            kick_pattern_detected=True if correlation > 0.4 else False,
            snare_position=snare_pos,
            hihat_pattern=hihat_pattern,
            driving_force=round(driving_force, 3),
            rhythmic_complexity=min(1.0, complexity),
            groove_quality_label=groove_label,
        )
    
    @staticmethod
    def _estimate_groove_from_correlation(correlation: float) -> float:
        """Map autocorrelation to a perceived groove score."""
        # High correlation + consistent period = strong groove
        if correlation > 0.7:
            return 0.9 + (correlation - 0.7) * 5  # Up to ~1.4 -> capped at 1.0
        elif correlation > 0.5:
            return 0.6 + (correlation - 0.5) * 4   # Medium groove
        else:
            return 0.3 + correlation                 # Weak groove
    
    @staticmethod
    def _estimate_syncopation(rms_arr: list[float], period_ms: int | None, sample_rate: int) -> float:
        """Estimate syncopation level (emphasis on weak beats)."""
        if not rms_arr or len(rms_arr) < 30:
            return 0.2
        
        n = len(rms_arr)
        if period_ms is None:
            return 0.4  # Default mid when no periodicity found
        
        # Compare strong beats (even multiples of period) vs weak beats
        energy_on_beats = []
        energy_between_beats = []
        
        window_samples = int(sample_rate * 60.0 / max(1, sample_rate))  # ~1 beat window
        for i in range(0, n - period_ms, min(period_ms // 2, 5)):
            segment = rms_arr[i:i+window_samples]
            if len(segment) > 3:
                energy_on_beats.append(max(segment))
        
        # Check mid-period positions (weak beats)
        for i in range(0, n - period_ms * 2 // 2, min(period_ms // 4, 5)):
            segment = rms_arr[i:i+window_samples]
            if len(segment) > 3:
                energy_between_beats.append(max(segment))
        
        # Syncopation = how much the mid-period beats are emphasized relative to on-beat
        avg_on = max(sum(energy_on_beats) / max(len(energy_on_beats), 1), 0.01) if energy_on_beats else 0.3
        avg_between = max(sum(energy_between_beats) / max(len(energy_between_beats), 1), 0.01) if energy_between_beats else 0.2
        
        if avg_on < 0.1 or avg_between > avg_on * 1.5:
            return 0.8  # Strong syncopation (weak beats are emphasized!)
        elif avg_between > avg_on * 0.9:
            return 0.6  # Moderate syncopation
        else:
            return max(0.2, 1.0 - ((avg_on - avg_between) / avg_on)) if avg_on > 0 else 0.3
    
    @staticmethod
    def _estimate_swing(rms_arr: list[float], period_ms: int | None) -> float:
        """Estimate swing/rubato amount."""
        if not rms_arr or len(rms_arr) < 50:
            return 2.0  # Default moderate
        
        n = len(rms_arr)
        if period_ms is None:
            return 3.0
        
        # Compare consecutive beat positions for timing variation
        energies = []
        step = max(period_ms // 4, 1)
        for i in range(0, min(n - period_ms, n), step):
            seg = rms_arr[i:i+period_ms]
            if len(seg) > 5:
                energies.append(sum(seg) / len(seg))
        
        if len(energies) < 4:
            return 2.0
        
        # Check for alternating strong-weak pattern (swing)
        even_avg = sum(energies[i] for i in range(0, len(energies), 2)) / max(len(energies)//2, 1)
        odd_avg = sum(energies[i] for i in range(1, len(energies), 2)) / max((len(energies)-1)//2, 1)
        
        swing_ratio = abs(even_avg - odd_avg) / max(max(even_avg, odd_avg, 0.001), 0.001)
        return min(25.0, swing_ratio * 50 + 2.0)  # Map to percentage
    
    @staticmethod
    def _estimate_driving_force(rms_arr: list[float]) -> float:
        """Estimate how much the rhythm pushes forward."""
        if not rms_arr or len(rms_arr) < 10:
            return 0.5
        
        n = len(rms_arr)
        
        # Driving force: sustained energy at regular intervals
        window_size = max(5, n // 20)
        energies_per_beat = [max(sum(rms_arr[i:i+window_size]) / window_size, 0.01) 
                            for i in range(0, n - window_size, max(window_size, n // 4))]
        
        if not energies_per_beat:
            return 0.5
        
        # High minimum energy = consistent driving force
        min_energy = min(energies_per_beat)
        avg_energy = sum(energies_per_beat) / len(energies_per_beat)
        
        consistency = min_energy / max(avg_energy, 0.01)
        return min(1.0, (consistency + 0.5)) * 0.6 + 0.4
    
    @staticmethod  
    def _estimate_complexity(rms_arr: list[float]) -> float:
        """Estimate rhythmic complexity from envelope variation."""
        if not rms_arr or len(rms_arr) < 20:
            return 0.5
        
        n = len(rms_arr)
        
        # Coefficient of variation in energy levels
        mean_energy = sum(rms_arr) / n
        std_energy = (sum((x - mean_energy)**2 for x in rms_arr) / n) ** 0.5
        
        cv = std_energy / max(mean_energy, 0.01)
        return min(1.0, cv * 3 + 0.3)
    
    @staticmethod
    def _classify_snare_position(rms_arr: list[float], period_ms: int | None) -> str:
        """Classify snare position (backbeat vs syncopated)."""
        if not rms_arr or len(rms_arr) < 50:
            return "unknown"
        
        n = len(rms_arr)
        if period_ms is None:
            return "unknown"
        
        # Check if there's a secondary peak at mid-period (snare on beat 2 and 4)
        quarter_period = period_ms // 4
        
        main_peaks = []
        mid_peaks = []
        
        for i in range(0, n - period_ms, max(period_ms // 8, 1)):
            seg = rms_arr[i:i+period_ms]
            if len(seg) > 5:
                peak_val = max(seg)
                peak_pos = seg.index(max(seg))
                
                main_peaks.append(peak_pos % int(n / (n // quarter_period)) if quarter_period else 0)
                
                # Check if there's energy at the midpoint of each beat cycle
                mid_seg = rms_arr[i + period_ms // 2:i + period_ms]
                if len(mid_seg) > 3:
                    mid_val = max(mid_seg) / max(max(seg), 0.01)
                    mid_peaks.append(mid_val)
        
        avg_mid_peak = sum(mid_peaks) / max(len(mid_peaks), 3) if mid_peaks else 0
        
        # Strong snare position when mid-period energy is significant
        if avg_mid_peak > 0.4:
            return "backbeat"  # Snare on beats 2 and 4
        elif avg_mid_peak > 0.2:
            return "syncopated"
        else:
            return "constant"
    
    @staticmethod
    def _classify_hihat_pattern(rms_arr: list[float], sample_rate: int) -> str:
        """Approximate hi-hat pattern classification."""
        if not rms_arr or len(rms_arr) < 50:
            return "steady"
        
        # High-frequency energy variation indicates hihat activity
        n = len(rms_arr)
        window = max(10, n // 20)
        
        high_energy_windows = []
        for i in range(0, n - window, window):
            seg = rms_arr[i:i+window]
            if len(seg) > 5:
                variance = (sum((x - sum(seg)/len(seg))**2 for x in seg) / len(seg)) ** 0.5
                high_energy_windows.append(variance)
        
        if not high_energy_windows:
            return "steady"
        
        avg_hihat = sum(high_energy_windows) / len(high_energy_windows)
        
        # Check for open/close alternation pattern (high variance = hihat rolls)
        max_hihat = max(high_energy_windows)
        if max_hihat > 0 and min(high_energy_windows) < max_hihat * 0.3:
            return "open_close"
        elif avg_hihat < sum(rms_arr) / len(rms_arr) * 0.5:
            return "steady"
        else:
            return "roll"
    
    @staticmethod
    def _describe_groove_quality(beat_strength: float, sync_level: float, 
                                   swing_pct: float, bpm_cat: str) -> str:
        """Generate human-readable groove quality description."""
        
        descriptions = {
            ("strong", "high", "moderate"): "Starker 4/4 Groove mit klarem Snare-Backbeat. Klassische Dance-Musik-Fühlung.",
            ("strong", "low", "low"): "Sehr treibender Beat, direkt und kraftvoll. Kein Syncopation — straight forward.",
            ("strong", "medium", "high"): "Treiberischer Beat mit deutlicher Swing-Charakteristik. Jazz-HipHop-Fusion-Groove.",
            ("moderate", "high", "any"): "Organischer Groove mit viel Leben und Bewegung. Organic/Jazz-Feeling.",
            ("weak", "any", "any"): "Geringer Beat — eher atmosphärisch als rhythmisch treibend.",
        }
        
        strength = "strong" if beat_strength > 0.7 else ("moderate" if beat_strength > 0.4 else "weak")
        sync = "high" if sync_level > 0.5 else ("medium" if sync_level > 0.3 else "low")
        
        key = (strength, sync, swing_pct)
        for k in descriptions:
            if k[0] == strength and (k[1] == "any" or k[2] == "any"):
                return descriptions[k]
        
        # Fallback description based on BPM category
        bpm_desc = {
            "slow": "Langsamer, ruhiger Groove mit viel Raum. Ambient oder Downtempo.",
            "mid-fast": "Klassischer 4/4 Dance-Groove mit starkem Beat.",
            "fast": "Schneller, energiegeladener Groove. House oder Techno-Tempo.",
        }
        
        return bpm_desc.get(bpm_cat, "Mittelmäßiger Groove ohne starke rhythmische Merkmale.")


def describe_groove_to_user(groove_result: GrooveResult) -> str:
    """Generate a human-readable groove analysis for user communication."""
    if not groove_result or not groove_result.groove_quality_label:
        return "Keine Groove-Analyse verfügbar."
    
    lines = [f"**Groove-Bewertung: {groove_result.overall_groove_score:.0%}**\n"]
    lines.append(f"Tempo-Kategorie: {groove_result.bpm_category}\n")
    lines.append(f"**Qualitätsbeschreibung:** {groove_result.groove_quality_label}")
    
    if groove_result.beat_strength > 0.7:
        lines.append("\n🥁 **Beat-Stärke: Stark** — Der Rhythmus treibt den Track kraftvoll voran.")
    elif groove_result.beat_strength > 0.4:
        lines.append(f"\n🥁 **Beat-Stärke: {groove_result.beat_strength:.0%}** — Moderate Treibkraft, guter Flow.")
    else:
        lines.append(f"\n🥁 **Beat-Stärke: {groove_result.beat_strength:.0%}** — Geringe Treibkraft, eher atmosphärisch.")
    
    if groove_result.syncopation_level > 0.5:
        lines.append(f"🎵 **Syncopation: {groove_result.syncopation_level:.0%}** — Deutliche Off-Beat-Erwähnung, lebendiger Groove.")
    elif groove_result.syncopation_level > 0.3:
        lines.append(f"🎵 **Syncopation: {groove_result.syncopation_level:.0%}** — Moderate rhythmische Variation.")
    
    if groove_result.swing_percentage > 5:
        lines.append(f"💃 **Swing: {groove_result.swing_percentage:.0f}%** — Deutlicher Swing/Beat, organisches Feeling.")
    
    if groove_result.driving_force > 0.7:
        lines.append("\n⚡ **Treibkraft: Stark** — Der Beat drängt nach vorne, ideal für Video-Cuts.")
    elif groove_result.driving_force > 0.4:
        lines.append(f"\n⚡ **Treibkraft: {groove_result.driving_force:.0%}** — Moderater Drive, angenehmer Flow.")
    
    return "\n".join(lines)
