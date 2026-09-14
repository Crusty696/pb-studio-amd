
"""Mood & Emotional-Stimmungs-Erkennung für elektronische Musik (Psytrance bis Techno).

Detects mood, emotional valence, energy, groove-feel, bass-intensity und
Flanngfarbe (Timbre-Charakteristik) — inklusive Track-Änderungserkennung bei DJ-Mixes.

Architektur:
    1. Genre-Kontext liefert Stimmungsexpektation (EDM_MOOD_PROFILES)
    2. Audio-Features werden extrahiert (RMS, Spektrum, Frequenzband-Energie)
    3. Mood wird klassifiziert basierend auf Genre + Features
    4. Track-Änderungen werden durch Energie-Sprünge und Spektrums-Shift erkannt
"""

import json
from dataclasses import dataclass, field
from typing import Optional


# ============================================================================
# EDM MOOD PROFILES — Genre-spezifische Stimmungsexpektationen
# ============================================================================
#
# Jedes Genre hat ein Profil mit:
#   - expected_moods: Was wird typischerweise gefühlt (z.B. Psytrance = Hypnotisch, Energisch)
#   - valence_target: Emotionaler Ton (0=sehr negativ, 1=sehr positiv/euphorisch)
#   - arousal_target: Energie-Aktivierung (0=schlafend, 1=euforisch/überdreht)
#   - bass_intensity_target: Bass-Stärke im Profil (0=mehr Melodie, 1=reine Bass-Wucht)
#   - groove_quality_target: Wie "groovy" das Genre ist
#   - energy_profile: Energie-Verlauf über den Track (Intro → Drop → Breakdown → Outro)
#   - emotional_keywords: Deutsche Stimmungswörter die zum Genre passen


EDM_MOOD_PROFILES = {

    # --- TRANCE-FAMILIE ---

    "Psytrance": {
        "expected_moods": ["Hypnotisch", "Energisch", "Psychedelisch", "Aufregend"],
        "valence_target": 0.7,          # Positiv — euphorische Psyche
        "arousal_target": 0.85,         # Hoch-Arousal — energiegeladen
        "bass_intensity_target": 0.95,  # Dominanter Full-Bass-Drop
        "groove_quality_target": 0.85,  # Starke Hypnotic-Loop-Grooves
        "energy_profile": [0.3, 0.6, 0.95, 1.0],  # Intro → Build → Drop → Peak
        "emotional_keywords": ["hypnotisch", "energisch", "psychedelisch", "euforisch",
                                "aufregend", "kreativ", "verrückt"],
    },

    "Progressive Trance": {
        "expected_moods": ["Melodisch", "Euphorisch", "Emotional", "Aufbauend"],
        "valence_target": 0.85,         # Sehr positiv — emotional/euphorisch
        "arousal_target": 0.75,         # Hoch aber kontrolliert
        "bass_intensity_target": 0.7,   # Bass + Melodie im Gleichgewicht
        "groove_quality_target": 0.8,   # Progressive Grooves mit Evolution
        "energy_profile": [0.2, 0.45, 0.9, 1.0],  # Steilerer Aufbau als Psytrance
        "emotional_keywords": ["melodisch", "euphorisch", "emotional", "aufbauend",
                                "traumhaft", "erhaben"],
    },

    "Uplifting Trance": {
        "expected_moods": ["Euphorisch", "Erhaben", "Emotional", "Inspizierend"],
        "valence_target": 0.95,         # Maximale Positivität — die Euphorie-Disco des EDM
        "arousal_target": 0.8,          # Hoch-Arousal mit emotionaler Tiefe
        "bass_intensity_target": 0.75,  # Bass-Drop + Vocal-Melodie
        "groove_quality_target": 0.75,  # Big-Room-Grooves
        "energy_profile": [0.25, 0.4, 0.95, 1.0],
        "emotional_keywords": ["euphorisch", "erhaben", "inspizierend", "traumhaft",
                                "glücklich", "aufwärts"],
    },

    "Hypnotic Trance": {
        "expected_moods": ["Hypnotisch", "Ruhig", "Fokusiert", "Hintergrund"],
        "valence_target": 0.6,          # Neutral-positiv — entspannt aber aufmerksamt
        "arousal_target": 0.5,          # Mittel-Arousal — nicht überreizend
        "bass_intensity_target": 0.85,  # Rolling Bass Patterns sind dominierend
        "groove_quality_target": 0.95,  # Sehr hoher Groove-Score für hypnotische Loops
        "energy_profile": [0.4, 0.65, 0.7, 0.6],  # Steady — keine extremen Peaks
        "emotional_keywords": ["hypnotisch", "ruhig", "fokusiert", "meditativ",
                                "konsistent", "gleichmäßig"],
    },

    # --- PROGRESSIVE HOUSE / TECH HOUSE ---

    "Progressive House": {
        "expected_moods": ["Pulsierend", "Melodisch", "Euphorisch", "Wellenartig"],
        "valence_target": 0.8,          # Positiv — euphorische Drops
        "arousal_target": 0.75,         # Hoch aber fließend wie Wasser
        "bass_intensity_target": 0.8,   # Pulsating Bass-Drops dominant
        "groove_quality_target": 0.8,   # Progressive Grooves mit Filter-Evolution
        "energy_profile": [0.3, 0.5, 0.9, 1.0],
        "emotional_keywords": ["pulsierend", "melodisch", "euphorisch", "wellenartig",
                                "fließend"],
    },

    "Tech House": {
        "expected_moods": ["Funktional", "Groovy", "Tief", "Raumfüllend"],
        "valence_target": 0.55,         # Neutral — funky/techig ohne große Emotion
        "arousal_target": 0.6,          # Mittel-Arousal — konstanter Groove-Flow
        "bass_intensity_target": 0.75,  # Funky Basslines + Sub-Bass
        "groove_quality_target": 0.95,  # Sehr hoher Groove-Score
        "energy_profile": [0.6, 0.7, 0.75, 0.7],   # Steady — kaum Peaks/Tals
        "emotional_keywords": ["funktional", "groovy", "tief", "jazzig",
                                "technisch", "raumfüllend"],
    },

    "Deep House": {
        "expected_moods": ["Soulful", "Warm", "Tief", "Emotional", "Jazzy"],
        "valence_target": 0.75,         # Positiv-Neutral — warm/emotional
        "arousal_target": 0.45,         # Niedrig-Arousal — entspannt/soulful
        "bass_intensity_target": 0.7,   # Warm Bass + Soulful Basslines
        "groove_quality_target": 0.9,   # Sehr hoher Groove-Score für Deep-House-Loops
        "energy_profile": [0.45, 0.6, 0.55, 0.5],  # Sehr steady, kaum Peaks
        "emotional_keywords": ["soulful", "warm", "tief", "jazzy", "emotional",
                                "entspannt"],
    },

    # --- TECHNO-FAMILIE ---

    "Minimal Techno": {
        "expected_moods": ["Fokusiert", "Raumfüllend", "Subtil", "Industrial"],
        "valence_target": 0.45,         # Neutral-leicht-negativ — industrial/funkional
        "arousal_target": 0.65,         # Mittel-Arousal — konzentriert
        "bass_intensity_target": 0.85,  # Subtle Bass + Punchy Kick dominant
        "groove_quality_target": 0.9,   # Sehr hoher Groove-Score durch Space und Konsistenz
        "energy_profile": [0.35, 0.5, 0.6, 0.5],   # Steady Industrial Groove
        "emotional_keywords": ["fokusiert", "raumfüllend", "subtil", "industrial",
                                "konzentriert", "minimal"],
    },

    "Hard Techno": {
        "expected_moods": ["Aggressiv", "Industrial", "Rau", "Dissonant"],
        "valence_target": 0.25,         # Leicht-negativ — aggressive/industrial Stimmung
        "arousal_target": 0.95,         # Extrem-hoch-Arousal — Wut/Energie-Explosion
        "bass_intensity_target": 0.95,  # Aggressive Bass + Industrial Bass dominant
        "groove_quality_target": 0.8,   # Groove durch Härte/Aggression
        "energy_profile": [0.3, 0.6, 0.95, 1.0],
        "emotional_keywords": ["aggressiv", "industrial", "rau", "dissonant",
                                "hässlich", "wütend"],
    },

    "Melodic Techno": {
        "expected_moods": ["Emotional", "Atmosphärisch", "Traurig", "Euphorisch"],
        "valence_target": 0.6,          # Neutral — melancholisch aber mit Hoffnung
        "arousal_target": 0.7,          # Hoch-Arousal durch atmosphärische Melodien
        "bass_intensity_target": 0.8,   # Deep Bass + Atmospheric Bass dominant
        "groove_quality_target": 0.85,  # Groovy aber atmosphärisch
        "energy_profile": [0.3, 0.5, 0.9, 1.0],
        "emotional_keywords": ["emotional", "atmosphärisch", "traurig", "euphorisch",
                                "melancholisch"],
    },

    # --- DRUM & BASS / JUNGLE ---

    "Drum and Bass": {
        "expected_moods": ["Schnell", "Aggressiv", "Complex", "Snare-Heavy"],
        "valence_target": 0.5,          # Neutral — komplexe/energetische Stimmung
        "arousal_target": 0.9,          # Extrem-hoch-Arousal durch schnelle Drums + Bass
        "bass_intensity_target": 0.95,  # Deep Sub Bass + Snare Rolls dominant
        "groove_quality_target": 0.8,   # Groovy aber komplex
        "energy_profile": [0.4, 0.7, 1.0, 1.0],
        "emotional_keywords": ["schnell", "aggressiv", "complex", "snare-heavy"],
    },

    "Breakbeat": {
        "expected_moods": ["Funktional", "Groovy", "Jazzy", "Loose"],
        "valence_target": 0.55,         # Neutral-positiv — funky/loose Stimmung
        "arousal_target": 0.65,         # Mittel-Arousal durch schnelle Breaks
        "bass_intensity_target": 0.7,   # Groovy Bass + Funky Basslines
        "groove_quality_target": 0.9,   # Sehr hoher Groove-Score für funky Drums
        "energy_profile": [0.5, 0.6, 0.7, 0.6],
        "emotional_keywords": ["funktional", "groovy", "jazzy", "loose"],
    },

    # --- HARDSTYLE / HARDCORE ---

    "Hardstyle": {
        "expected_moods": ["Explosiv", "Stompig", "Emotional", "Kraftvoll"],
        "valence_target": 0.6,          # Positiv — emotionaler Kontrast zwischen Breakdown und Drop
        "arousal_target": 0.95,         # Extrem-hoch-Arousal durch massive Drops
        "bass_intensity_target": 0.95,  # Sawtooth Kick + Bass Drop dominant
        "groove_quality_target": 0.75,  # Groovy aber extrem kraftvoll
        "energy_profile": [0.3, 0.6, 1.0, 1.0],  # Steilerer Build-Up als andere Genres
        "emotional_keywords": ["explosiv", "stompig", "emotional", "kraftvoll"],
    },

    # --- DUBSTEP ---

    "Dubstep": {
        "expected_moods": ["Wobble", "Growl", "Dark", "Aggressiv"],
        "valence_target": 0.35,         # Negativ — dunkle/aggressive Stimmung
        "arousal_target": 0.8,          # Hoch-Arousal durch Wobble/Growl Bass Drops
        "bass_intensity_target": 1.0,   # Maximale Bass-Intensität — der Hauptcharakter
        "groove_quality_target": 0.75,  # Groovy aber dunkel/aggressiv
        "energy_profile": [0.35, 0.55, 1.0, 1.0],
        "emotional_keywords": ["wobble", "growl", "dark", "aggressiv"],
    },

    "Melodic Dubstep": {
        "expected_moods": ["Emotional", "Euphorisch", "Wobble-melodisch", "Space"],
        "valence_target": 0.75,         # Positiv — emotionale/vocal-laden Stimmung
        "arousal_target": 0.8,          # Hoch-Arousal durch emotionale Wobble Drops
        "bass_intensity_target": 0.9,   # Emotional Bass + Melodische Wobble dominant
        "groove_quality_target": 0.8,   # Groovy mit emotionaler Tiefe
        "energy_profile": [0.3, 0.55, 1.0, 1.0],
        "emotional_keywords": ["emotional", "euphorisch", "wobble-melodisch"],
    },

    # --- ADDITIONALE GENRES ---

    "Ambient": {
        "expected_moods": ["Ruhig", "Atmosphärisch", "Schlafend", "Immersiv"],
        "valence_target": 0.65,         # Positiv — entspannt/immersiv
        "arousal_target": 0.25,         # Extrem-niedrig-Arousal — beruhigend
        "bass_intensity_target": 0.3,   # Minimaler Bass — Atmosphäre ist Hauptelement
        "groove_quality_target": 0.4,   # Kein Groove im EDM-Sinne — eher Flow
        "energy_profile": [0.4, 0.5, 0.5, 0.4],  # Sehr steady/ruhig
        "emotional_keywords": ["ruhig", "atmosphärisch", "schlafend", "immersiv"],
    },

    "Footwork": {
        "expected_moods": ["Schnell", "Funktional", "Aggressiv", "Breakbeat"],
        "valence_target": 0.4,          # Neutral-negativ — aggressive/schnelle Stimmung
        "arousal_target": 0.95,         # Extrem-hoch-Arousal durch schnelle Breakbeats
        "bass_intensity_target": 0.7,   # Gritty Bass + Funky Drums
        "groove_quality_target": 0.85,  # Groovy aber schnell/aggressiv
        "energy_profile": [0.6, 0.75, 0.8, 0.7],
        "emotional_keywords": ["schnell", "funktional", "aggressiv"],
    },

    # --- SUBGENRES / SPECIALS ---

    "Progressive Psytrance": {
        "expected_moods": ["Hypnotisch", "Melodisch", "Energisch", "Psychedelisch"],
        "valence_target": 0.75,         # Positiv — euphorische Hypnose
        "arousal_target": 0.8,          # Hoch-Arousal — energiegeladen
        "bass_intensity_target": 0.9,   # Full Bass + Progressive Bass Pattern dominant
        "groove_quality_target": 0.9,   # Sehr hoher Groove-Score für hypnotische Loops
        "energy_profile": [0.35, 0.6, 0.85, 1.0],
        "emotional_keywords": ["hypnotisch", "melodisch", "energisch"],
    },

    "Deep Tech": {
        "expected_moods": ["Tief", "Funktional", "Warm", "Minimal"],
        "valence_target": 0.5,          # Neutral — warm/funkional
        "arousal_target": 0.55,         # Mittel-Arousal — konzentriert
        "bass_intensity_target": 0.85,  # Tiefe, warme Bass-Sounds dominant
        "groove_quality_target": 0.9,   # Sehr hoher Groove-Score
        "energy_profile": [0.4, 0.6, 0.7, 0.6],
        "emotional_keywords": ["tief", "funktional", "warm"],
    },

    # --- DJ MIX TECHNIQUES / KEY CHANGE PATTERNS ---

    "DJ Mix Techniques": {
        "expected_moods": ["Fließend", "BPM-Bridging", "Konsistent", "Energie-Flow"],
        "valence_target": 0.6,          # Positiv — fließender Energie-Flow
        "arousal_target": 0.7,          # Hoch-Arousal durch steigende BPM-Stufen
        "bass_intensity_target": 0.75,  # Variable Bass-Intensität je nach Genre-Mix
        "groove_quality_target": 0.85,  # Groovy aber konsistent über den Mix
        "energy_profile": [0.4, 0.6, 0.8, 1.0],   # Steigender Energie-Flow durch DJ-Mix
        "emotional_keywords": ["fließend", "bpm-bridging", "konsistent"],
    },

    # --- BASS INTENSITY PROFILES (Meta-Genre) ---

    "Bass Profiles": {
        "expected_moods": ["Sub Bass", "Wobble Bass", "Growl Bass", "Full Bass"],
        "valence_target": 0.5,          # Neutral — bass-focused Stimmung
        "arousal_target": 0.75,         # Hoch-Arousal durch Bass-Intensität
        "bass_intensity_target": 1.0,   # Maximale Bass-Intensität
        "groove_quality_target": 0.8,   # Groovy aber bass-dominiert
        "energy_profile": [0.4, 0.65, 0.9, 1.0],
        "emotional_keywords": ["sub-bass", "wobble", "growl"],
    },

}


# ============================================================================
# MOOD CLASSIFICATION DATA STRUCTURES
# ============================================================================


@dataclass
class SpectralBandEnergy:
    """Energie in Frequenzbändern (für Bass-Intensität/Timbre-Analyse)."""
    sub_bass_30_60hz: float = 0.5       # Sub-Bass Energie (30-60 Hz)
    bass_60_120hz: float = 0.4          # Bass Energie (60-120 Hz)
    low_mid_120_500hz: float = 0.3      # Low-Mid Energie (120-500 Hz)
    mid_500_2khz: float = 0.4           # Mittelbereich (500-2 kHz)
    high_2k_8khz: float = 0.3          # High-Freq Energie (2-8 kHz)
    very_high_8k_plus: float = 0.1      # Sehr hohe Frequenzen (>8 kHz)

    @property
    def sub_bash_30_60hz(self) -> float:
        """Alias for typo tolerance."""
        return self.sub_bass_30_60hz


@dataclass  
class TimbreProfile:
    """Flanngfarbe / Timbre-Charakteristik des Signals."""
    brightness: float = 0.5             # Hochfrequenzanteil (0=dark, 1=bright)
    warmth: float = 0.5                 # Tiefenergieanteil (0=kalt, 1=warm)
    density: float = 0.5                # Gesamtdichte des Signals
    harmonic_richness: float = 0.5      # Harmonische Komplexität
    saturation_level: float = 0.3       # Sättigung/Verzerrung


@dataclass
class EDMGenreMood:
    """Erkannte Stimmung eines EDM-Schnippets basierend auf Genre + Features."""

    genre_name: str = ""                # Erkennendes Genre (oder "unknown")

    # Stimmungswerte
    mood_label_de: str = ""             # Deutsche Stimmungsbezeichnung
    mood_label_en: str = ""             # Englische Stimmung
    confidence_score: float = 0.5       # 0-1, wie sicher die Erkennung ist

    # Emotionale Dimensionen (Valence-Arousal-Dominance)
    valence: float = 0.5                # Emotionaler Ton: 0=negativ, 1=positiv
    arousal: float = 0.5                # Energie/Aktivierung: 0=schlafend, 1=euforisch
    dominance: float = 0.5              # Kontrollgefühl: 0=submissiv, 1=kontrolliert

    # Bass-Intensität und Groove
    bass_intensity: float = 0.5         # 0=mehr Melodie, 1=reine Bass-Wucht
    groove_score: float = 0.5           # 0=kein Groove, 1=maximaler Groove
    kick_strength: float = 0.5          # Kick-Stärke (0=leise, 1=extrem)

    # Spektrale Charakteristika
    spectral_profile: Optional[SpectralBandEnergy] = None
    timbre_profile: Optional[TimbreProfile] = None

    # Energie-Verlauf (für Track-Änderungserkennung)
    energy_level: float = 0.5           # 0=leise, 1=laut/energetisch
    build_up_detected: bool = False     # Wird ein Build-Up erkannt?
    drop_detected: bool = False         # Ist es ein Drop?
    breakdown_detected: bool = False    # Ist es ein Breakdown?

    # Transition-Erkennung
    track_change_detected: bool = False # Hat sich der Track geändert?
    transition_type: str = ""           # "smooth", "harsh", "key-change", "bpm-shift"
    new_genre_suggested: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "genre_name": self.genre_name,
            "mood_label_de": self.mood_label_de,
            "mood_label_en": self.mood_label_en,
            "confidence_score": round(self.confidence_score, 3),
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "dominance": round(self.dominance, 3),
            "bass_intensity": round(self.bass_intensity, 3),
            "groove_score": round(self.groove_score, 3),
            "kick_strength": round(self.kick_strength, 3),
            "energy_level": round(self.energy_level, 3),
            "build_up_detected": self.build_up_detected,
            "drop_detected": self.drop_detected,
            "breakdown_detected": self.breakdown_detected,
            "track_change_detected": self.track_change_detected,
            "transition_type": self.transition_type,
            "new_genre_suggested": self.new_genre_suggested,
        }


@dataclass  
class TrackChangeEvent:
    """Ereignis: Ein neuer Track wurde erkannt in einem DJ-Mix."""

    timestamp_ms: int = 0               # Zeitpunkt der Änderung (ms)
    previous_genre: str = ""            # Genre vor der Änderung
    current_genre: str = ""             # Neues Genre nach der Änderung

    energy_jump_db: float = 3.0         # Energie-Sprung in dB
    bpm_shift_expected: Optional[float] = None  # Erwarteter BPM-Shift

    transition_quality: str = "unknown" # "smooth", "moderate", "sharp"

    def to_dict(self) -> dict:
        return {
            "timestamp_ms": self.timestamp_ms,
            "previous_genre": self.previous_genre,
            "current_genre": self.current_genre,
            "energy_jump_db": round(self.energy_jump_db, 1),
            "bpm_shift_expected": self.bpm_shift_expected,
            "transition_quality": self.transition_quality,
        }


# ============================================================================
# MOOD DETECTOR — Genre-spezifische EDM Stimmungserkennung
# ============================================================================

class MoodDetector:
    """
    Detects mood, emotional valence, bass-intensity und Timbre-Charakteristik
    für elektronische Musik (Psytrance bis Techno).

    Core Features erkannt:
        1. Genre-spezifische Stimmungserwartung (EDM_MOOD_PROFILES)
        2. Bass-Intensität (Sub-Bass, Wobble, Growl, Full Bass Drop)
        3. Timbre/Flanngfarbe (Brightness, Warmth, Density, Harmonic Richness)
        4. Energie-Verlauf und Track-Änderungen in DJ-Mixes
        5. Groove-Qualität je nach Genre

    Usage:
        detector = MoodDetector()

        # Einzelne Analyse
        result = detector.analyze_audio(
            spectral_bands=[0.8, 0.6, 0.4, 0.5, 0.3, 0.1],
            rms_energy=0.75,
            genre_name="Psytrance"
        )

        # DJ-Mix Analyse mit Track-Änderungserkennung
        mix_results = detector.analyze_dj_mix(
            track_data=[...],
            spectral_history=[...]
        )
    """

    def __init__(self):
        self.mood_profiles: dict = EDM_MOOD_PROFILES

    # ========================================================================
    # AUDIO-FEATURE EXTRACTION (Simulation von DSP-Analyse)
    # ========================================================================

    def extract_spectral_bands(self, spectral_data: list[float]) -> SpectralBandEnergy:
        """Extrahiert Frequenzband-Energie aus Spektrum-Daten."""

        if len(spectral_data) < 6:
            return SpectralBandEnergy()

        # Normalisierung (0-1)
        max_val = max(spectral_data) + 1e-6
        normalized = [v / max_val for v in spectral_data]

        if len(normalized) == 6:
            sub_bass = normalized[0]
            bass = normalized[1]
            low_mid = normalized[2]
            mid = normalized[3]
            high = normalized[4]
            very_high = normalized[5]
        else:
            n = len(normalized)
            sub_bass = sum(normalized[:max(1, int(n * 0.15))]) / max(1, int(n * 0.15))
            bass = sum(normalized[max(1, int(n * 0.15)):max(2, int(n * 0.35))]) / max(1, max(2, int(n * 0.35)) - max(1, int(n * 0.15)))
            low_mid = sum(normalized[max(2, int(n * 0.35)):max(3, int(n * 0.55))]) / max(1, max(3, int(n * 0.55)) - max(2, int(n * 0.35)))
            mid = sum(normalized[max(3, int(n * 0.55)):max(4, int(n * 0.75))]) / max(1, max(4, int(n * 0.75)) - max(3, int(n * 0.55)))
            high = sum(normalized[max(4, int(n * 0.75)):max(5, int(n * 0.9))]) / max(1, max(5, int(n * 0.9)) - max(4, int(n * 0.75)))
            very_high = sum(normalized[max(5, int(n * 0.9)):]) / max(1, len(normalized) - max(5, int(n * 0.9)))

        return SpectralBandEnergy(
            sub_bass_30_60hz=round(float(sub_bass), 3),
            bass_60_120hz=round(float(bass), 3),
            low_mid_120_500hz=round(float(low_mid), 3),
            mid_500_2khz=round(float(mid), 3),
            high_2k_8khz=round(float(high), 3),
            very_high_8k_plus=round(float(very_high), 3),
        )

    def compute_timbre(self, spectral_bands: SpectralBandEnergy) -> TimbreProfile:
        """Berechnet Timbre/Flanngfarbe aus Frequenzband-Energie."""

        # Brightness = High-Freq Anteil
        total = (spectral_bands.sub_bass_30_60hz + spectral_bands.bass_60_120hz +
                 spectral_bands.low_mid_120_500hz + spectral_bands.mid_500_2khz +
                 spectral_bands.high_2k_8khz) + 1e-6

        brightness = (spectral_bands.high_2k_8khz + spectral_bands.very_high_8k_plus) / total
        warmth = (spectral_bands.sub_bass_30_60hz + spectral_bands.bass_60_120hz) / total

        # Density = Gesamtdichte
        density = sum([
            spectral_bands.sub_bass_30_60hz,
            spectral_bands.bass_60_120hz,
            spectral_bands.low_mid_120_500hz,
            spectral_bands.mid_500_2khz,
        ]) / 4.0

        # Harmonic richness = Mittelbereich + Sub-Bass Balance
        harmonic_richness = (spectral_bands.mid_500_2khz + spectral_bands.sub_bass_30_60hz) / 2.0

        # Saturation = wie "verzerrt" der Klang ist (High-Freq Boost als Proxy)
        saturation_level = brightness * 0.7 + density * 0.3

        return TimbreProfile(
            brightness=round(brightness, 3),
            warmth=round(warmth, 3),
            density=round(density, 3),
            harmonic_richness=round(harmonic_richness, 3),
            saturation_level=round(saturation_level, 3),
        )

    # ========================================================================
    # MOOD DETECTION (Genre-spezifisch)
    # ========================================================================

    def get_edm_genre_mood_profile(self, genre_name: str) -> dict:
        """Gibt das Stimmung-Profil für ein Genre zurück."""
        key = genre_name.lower().strip()

        if key in self.mood_profiles:
            return self.mood_profiles[key]

        # Fuzzy Match (Teil-Übereinstimmung, z.B. "progressive" -> "Progressive Trance")
        best_match = None
        best_score = 0.0

        for profile_key, _ in self.mood_profiles.items():
            if genre_name.lower() == profile_key:
                return self.mood_profiles[profile_key]

            name_lower = profile_key.lower().replace(" ", "").replace("-", "")
            input_lower = key.replace(" ", "").replace("-", "")

            # Teil-Übereinstimmung prüfen
            if len(name_lower) > 0 and len(input_lower) > 0:
                overlap = sum(1 for c in name_lower if c in input_lower or c == " ")
                max_len = max(len(name_lower), len(input_lower))
                score = overlap / max_len

                if score > best_score:
                    best_score = score
                    best_match = profile_key

        return self.mood_profiles.get(best_match, self.mood_profiles.get("Ambient", {}))

    def get_genre_expected_moods(self, genre_name: str) -> dict:
        """Gibt die erwarteten Stimmungen für ein Genre zurück."""
        profile = self.get_edm_genre_mood_profile(genre_name)
        return {
            "genre": genre_name,
            "expected_moods_de": profile["expected_moods"],
            "valence_target": profile["valence_target"],
            "arousal_target": profile["arousal_target"],
            "bass_intensity_target": profile["bass_intensity_target"],
            "groove_quality_target": profile["groove_quality_target"],
        }

    def get_genre_expected_bpm(self, genre_name: str) -> dict:
        """Gibt die BPM-Erwartung für ein Genre zurück."""
        # BPM-Categories aus der Genre-Bibliothek holen (über import)
        bpm_ranges = {
            "Ambient": (60, 100), "Deep House": (115, 128), "Tech House": (118, 132),
            "Progressive House": (124, 136), "Melodic Techno": (124, 135),
            "Minimal Techno": (120, 135), "Hard Techno": (130, 152),
            "Industrial Techno": (125, 145), "Acid Techno": (125, 145),
            "Trance": (130, 154), "Progressive Trance": (126, 138),
            "Uplifting Trance": (132, 150), "Hypnotic Trance": (130, 142),
            "Psytrance": (130, 154), "Progressive Psytrance": (130, 148),
            "Drum and Bass": (165, 180), "Breakbeat": (140, 180),
            "Hardstyle": (150, 180), "Dubstep": (138, 150),
            "Melodic Dubstep": (140, 150), "Footwork": (140, 170),
        }

        bpm_map = {k.lower(): v for k, v in bpm_ranges.items()}
        range_a = bpm_map.get(genre_name.lower().strip(), (120, 135))
        profile = self.get_edm_genre_mood_profile(genre_name)
        return {
            "genre": genre_name,
            "bpm_range_info": {"min": range_a[0], "max": range_a[1], "optimal": (range_a[0]+range_a[1])/2},
            "energy_rise_expected": profile.get("energy_profile", []),
        }

    def analyze_audio(self, spectral_bands: list[float], rms_energy: float = 0.5,
                      genre_name: str = None) -> EDMGenreMood:
        """
        Analysiert ein Audio-Segment und ermittelt die Stimmung.

        Args:
            spectral_bands: Normalisierte Spektralband-Energie (6+ Werte).
                           Index-Beispiel: [sub_30hz, bass_60hz, low_mid_120hz, mid_500hz, high_2k_hz, very_high_8k+]
            rms_energy: Overall RMS Energie (0-1), Proxy für Lautstärke/Energie.
            genre_name: Erkennendes Genre (wird aus Spektrum + Profil abgeleitet).

        Returns:
            EDMGenreMood mit Stimmungswerten und Genre-Kontext.
        """

        # Spectral-Band-Energie extrahieren
        spectral = self.extract_spectral_bands(spectral_bands)
        timbre = self.compute_timbre(spectral)

        # Genre-Profile laden
        mood_profile = self.get_edm_genre_mood_profile(genre_name or "Unknown")

        # --- MOOD CALCULATION ---
        genre_mood = EDMGenreMood()
        genre_mood.genre_name = genre_name or "unknown"

        # Valence: Genre-Valence + Spektraler Einfluss
        spectral_valence = self._spectral_to_valence(spectral)
        mood_profile_valence = mood_profile["valence_target"]

        # Gewichtung: Genre-Profile (60%) + Spektrum-Analyse (40%)
        genre_mood.valence = round(
            0.6 * mood_profile_valence + 0.4 * spectral_valence, 3
        )

        # Arousal: Genre-Arousal + RMS-Energie + Bass-Intensität
        spectral_arousal = self._spectral_to_arousal(spectral)
        rms_factor = min(1.0, max(0.0, (rms_energy - 0.3) * 4))

        genre_mood.arousal = round(
            0.5 * mood_profile["arousal_target"] +
            0.3 * spectral_arousal +
            0.2 * rms_factor, 3
        )

        # Dominance: Wie kontrolliert/aggressiv der Klang ist
        genre_mood.dominance = round(
            self._compute_dominance(spectral, timbre), 3
        )

        # --- BASS INTENSITY DETECTION ---
        genre_mood.bass_intensity = self._detect_bass_intensity(spectral, mood_profile)

        # --- GROOVE SCORE ---
        genre_mood.groove_score = self._estimate_groove(spectral, mood_profile)

        # --- KICK STÄRKE ---
        genre_mood.kick_strength = self._estimate_kick_strength(spectral, rms_energy)

        # --- ENERGIE-LEVEL ---
        genre_mood.energy_level = rms_energy

        # --- EVENT DETECTION (Build-Up / Drop / Breakdown) ---
        genre_mood.build_up_detected = self._detect_build_up(rms_energy, mood_profile)
        genre_mood.drop_detected = self._detect_drop(rms_energy, spectral, mood_profile)
        genre_mood.breakdown_detected = self._detect_breakdown(rms_energy, spectral, mood_profile)

        # --- SPECTRAL & TIMBRE PROFILE ---
        genre_mood.spectral_profile = spectral
        genre_mood.timbre_profile = timbre

        # --- MOOD LABEL ---
        genre_mood.mood_label_de = self._get_mood_label(mood_profile, spectral, rms_energy)

        # --- CONFIDENCE SCORE ---
        genre_mood.confidence_score = self._compute_confidence(
            mood_profile_valence, spectral_valence,
            mood_profile["arousal_target"], spectral_arousal,
            genre_name is not None
        )

        return genre_mood

    def analyze_dj_mix(self, track_segments: list[dict],
                       spectral_history: Optional[list[list[float]]] = None) -> dict:
        """
        Analysiert einen kompletten DJ-Mix und erkennt Track-Änderungen.

        Args:
            track_segments: Liste von Segment-Daten mit Genre und Energie.
                           Jeder Entry: {"genre": str, "rms_energy": float, "timestamp_ms": int}
            spectral_history: (Optional) Historische Spektrum-Daten für Transition-Erkennung.

        Returns:
            Dict mit Mix-Analyse inklusive Track-Änderungsereignissen.
        """

        track_changes = []
        previous_genre = None
        energy_baseline = 0.5

        for i, seg in enumerate(track_segments):
            # Energie-Baseline berechnen (Durchschnitt der letzten Segmente)
            recent_energy = [s["rms_energy"] for s in track_segments[max(0,i-10):i]]
            if len(recent_energy) > 0:
                energy_baseline = sum(recent_energy) / len(recent_energy)

            # Transition-Erkennung
            prev_genre = previous_genre or seg.get("genre", "unknown")
            current_rms = seg["rms_energy"]

            # Track-Änderung erkennen (Energie-Sprung > 3dB + Genre-Wechsel)
            if i > 0:
                energy_diff_db = (current_rms - energy_baseline) * 20  # dB Proxy

                if abs(energy_diff_db) > 3.0 and prev_genre != seg.get("genre", "unknown"):
                    transition_quality = self._classify_transition_quality(
                        energy_diff_db, prev_genre, seg.get("genre")
                    )

                    event = TrackChangeEvent(
                        timestamp_ms=seg.get("timestamp_ms", i * 60000),
                        previous_genre=prev_genre,
                        current_genre=seg.get("genre", "unknown"),
                        energy_jump_db=round(abs(energy_diff_db), 1),
                        transition_quality=transition_quality,
                    )

                    track_changes.append(event)

            # Mood-Analyse pro Segment
            mood = self.analyze_audio(
                spectral_bands=[0.5, 0.6, 0.4, 0.5, 0.3, 0.1],  # Default Spektrum
                rms_energy=seg.get("rms_energy", 0.5),
                genre_name=seg.get("genre"),
            )

            seg["mood"] = mood
            previous_genre = seg.get("genre")

        return {
            "total_segments": len(track_segments),
            "track_changes_detected": len(track_changes),
            "track_change_events": [tc.to_dict() for tc in track_changes],
            "segments_with_mood": [s["mood"].to_dict() if s.get("mood") else None
                                   for s in track_segments],
        }

    # ========================================================================
    # INTERNAL MOOD CALCULATION HELPERS
    # ========================================================================

    @staticmethod
    def _spectral_to_valence(spectral: SpectralBandEnergy) -> float:
        """Spektrale Energie → Valence-Mapping (positiver Klang)."""

        warm_signal = (spectral.sub_bass_30_60hz + spectral.bass_60_120hz) / 2.0
        harshness = spectral.high_2k_8khz * 0.7 + spectral.very_high_8k_plus * 0.3

        valence_from_spectrum = (warm_signal - harshness) / 2.0 + 0.5
        return max(0.0, min(1.0, round(valence_from_spectrum, 3)))

    @staticmethod
    def _spectral_to_arousal(spectral: SpectralBandEnergy) -> float:
        """Spektrale Energie → Arousal-Mapping (Energie/Aktivierung)."""

        energy_from_bass = spectral.sub_bass_30_60hz * 0.5 + spectral.bass_60_120hz * 0.4
        high_energy_signal = spectral.high_2k_8khz + spectral.very_high_8k_plus

        overall_arousal = energy_from_bass * 0.6 + high_energy_signal * 0.4
        return max(0.0, min(1.0, round(overall_arousal, 3)))

    @staticmethod
    def _compute_dominance(spectral: SpectralBandEnergy, timbre: TimbreProfile) -> float:
        """Berechnet Dominanz aus Spektralprofil und Timbre."""

        dark_factor = spectral.sub_bass_30_60hz + spectral.bass_60_120hz
        bright_factor = timbre.brightness

        dominance = (dark_factor * 0.7 + timbre.density - bright_factor) / 2.0
        return max(0.0, min(1.0, round(dominance, 3)))

    def _detect_bass_intensity(self, spectral: SpectralBandEnergy, mood_profile: dict | None = None) -> float:
        """Detektiert Bass-Intensität basierend auf Frequenzband-Energie."""

        sub_bass_dominance = (spectral.sub_bass_30_60hz * 0.7 + spectral.bass_60_120hz * 0.3)
        high_penalty = min(0.3, spectral.high_2k_8khz * 0.3)
        raw_bass = max(0.0, min(1.0, sub_bass_dominance - high_penalty))

        if mood_profile and "bass_intensity_target" in mood_profile:
            target = mood_profile["bass_intensity_target"]
            bass_intensity = 0.55 * raw_bass + 0.45 * target
        else:
            bass_intensity = raw_bass

        return round(max(0.0, min(1.0, bass_intensity)), 3)

    def _estimate_groove(self, spectral: SpectralBandEnergy, mood_profile: dict) -> float:
        """Schätzt Groove-Score basierend auf Spektrum und Genre-Profil."""

        genre_groove = mood_profile["groove_quality_target"]
        bass_pattern_score = spectral.sub_bass_30_60hz * 0.7 + spectral.bass_60_120hz * 0.5
        low_noise_factor = 1 - (spectral.high_2k_8khz + spectral.very_high_8k_plus) / 2.0

        groove = genre_groove * 0.5 + bass_pattern_score * 0.3 + low_noise_factor * 0.2
        return round(max(0.0, min(1.0, groove)), 3)

    def _estimate_kick_strength(self, spectral: SpectralBandEnergy, rms_energy: float) -> float:
        """Schätzt Kick-Stärke."""

        kick_dominance = (spectral.sub_bass_30_60hz * 0.7 + spectral.bass_60_120hz * 0.5) / 2.0
        rms_factor = min(1.0, rms_energy)

        kick_strength = kick_dominance * (0.7 + 0.3 * rms_factor)
        return round(max(0.0, min(1.0, kick_strength)), 3)

    def _detect_build_up(self, rms_energy: float, mood_profile: dict) -> bool:
        """Detektiert Build-Up (steigende Energie)."""

        energy_profile = mood_profile.get("energy_profile", [0.3, 0.5, 0.7, 1.0])
        if len(energy_profile) >= 2:
            slope = (energy_profile[-1] - energy_profile[0]) / max(len(energy_profile), 1)
            return rms_energy > 0.7 and slope > 0.3
        return False

    def _detect_drop(self, rms_energy: float, spectral: SpectralBandEnergy, mood_profile: dict) -> bool:
        """Detektiert Bass-Drop."""

        sub_bass_dominance = (spectral.sub_bass_30_60hz + spectral.bass_60_120hz) / 2.0
        drop_likelihood = rms_energy * sub_bass_dominance * mood_profile.get("bass_intensity_target", 0.5)

        return drop_likelihood > 0.6

    def _detect_breakdown(self, rms_energy: float, spectral: SpectralBandEnergy, mood_profile: dict) -> bool:
        """Detektiert Breakdown (Energie-Reduktion)."""

        sub_bass_dominance = (spectral.sub_bass_30_60hz + spectral.bass_60_120hz) / 2.0
        breakdown_likelihood = (1 - rms_energy) * (1 - sub_bass_dominance) * mood_profile.get("bass_intensity_target", 0.5)

        return breakdown_likelihood > 0.3

    def _get_mood_label(self, mood_profile: dict, spectral: SpectralBandEnergy,
                        rms_energy: float) -> str:
        """Generiert einen deutschen Stimmungs-Label."""

        expected_moods = mood_profile["expected_moods"]

        sub_bass_level = (spectral.sub_bass_30_60hz + spectral.bass_60_120hz) / 2.0

        if rms_energy > 0.8 and sub_bass_level > 0.7:
            return expected_moods[0] if len(expected_moods) > 0 else "Energisch"
        elif rms_energy < 0.4 and sub_bass_level < 0.5:
            return expected_moods[2] if len(expected_moods) > 2 else "Ruhig"
        elif rms_energy > 0.8 and sub_bass_level < 0.5:
            return expected_moods[0] if len(expected_moods) > 0 else "Melodisch"
        elif rms_energy < 0.4 and sub_bass_level > 0.7:
            return expected_moods[2] if len(expected_moods) > 2 else "Dunkel"

        return expected_moods[0] if expected_moods else "Neutral"

    def _compute_confidence(self, profile_valence: float, spectral_valence: float,
                            profile_arousal: float, spectral_arousal: float,
                            has_genre_context: bool) -> float:
        """Berechnet Confidence-Score der Mood-Erkennung."""

        valence_agreement = 1.0 - abs(profile_valence - spectral_valence) / 2.0
        arousal_agreement = 1.0 - abs(profile_arousal - spectral_arousal) / 2.0

        base_confidence = (valence_agreement + arousal_agreement) / 2.0
        genre_bonus = 0.15 if has_genre_context else 0.0

        return round(min(1.0, max(0.3, base_confidence + genre_bonus)), 3)

    def _classify_transition_quality(self, energy_diff_db: float,
                                     previous_genre: str, current_genre: str) -> str:
        """Klassifiziert die Qualität einer Track-Übergang."""

        if self._genres_compatible(previous_genre, current_genre):
            return "smooth"  # Kompatibel = smooth

        if abs(energy_diff_db) < 3.0:
            return "moderate"   # Kleiner Sprung = moderate
        else:
            return "sharp"      # Größerer Sprung = sharp

    @staticmethod
    def _genres_compatible(genre_a: str, genre_b: str) -> bool:
        """Prüft ob zwei Genres DJ-kompatibel sind."""

        if not genre_a or not genre_b:
            return False

        ga = str(genre_a).strip().lower()
        gb = str(genre_b).strip().lower()

        if ga == gb:
            return True

        # Common family words (Trance, Techno, House, Dubstep)
        for root in ["trance", "techno", "house", "dubstep", "breakbeat"]:
            if root in ga and root in gb:
                return True

        compatible_pairs = [
            ("trance", "psytrance"),
            ("trance", "progressive trance"),
            ("psytrance", "progressive trance"),
            ("psytrance", "progressive psytrance"),
            ("techno", "minimal techno"),
            ("techno", "hard techno"),
            ("techno", "melodic techno"),
            ("house", "deep house"),
            ("house", "tech house"),
            ("house", "progressive house"),
            ("dubstep", "melodic dubstep"),
        ]

        for f1, f2 in compatible_pairs:
            if (ga == f1 and gb == f2) or (ga == f2 and gb == f1):
                return True

        # BPM-Overlap-Prüfung
        bpm_data = {
            "ambient": (60, 100), "deep house": (115, 128), "tech house": (118, 132),
            "progressive house": (124, 136), "melodic techno": (124, 135),
            "minimal techno": (120, 135), "hard techno": (130, 152),
            "industrial techno": (125, 145), "acid techno": (125, 145),
            "trance": (130, 154), "progressive trance": (126, 138),
            "uplifting trance": (132, 150), "hypnotic trance": (130, 142),
            "psytrance": (130, 154), "progressive psytrance": (130, 148),
            "drum and bass": (165, 180), "breakbeat": (140, 180),
            "hardstyle": (150, 180), "dubstep": (138, 150),
            "melodic dubstep": (140, 150), "footwork": (140, 170),
        }

        range_a = bpm_data.get(ga, (120, 135))
        range_b = bpm_data.get(gb, (120, 135))

        overlap = max(0, min(range_a[1], range_b[1]) - max(range_a[0], range_b[0]))
        return overlap >= 8

