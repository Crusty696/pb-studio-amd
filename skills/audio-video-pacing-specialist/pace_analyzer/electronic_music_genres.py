"""Genre-Spezifischer Elektronische-Musik-Analysemodul — Psytrance bis Techno."""

import json
from dataclasses import dataclass, field
from typing import Optional


# ========================================
# GENRE-BIBLIOTHEK: Alle elektronischen Genres
# ========================================

@dataclass
class GenreProfile:
    """Genre-Spezifisches Profil für elektronische Musik."""
    name_de: str                      # Deutsch
    name_en: str                      # Englisch  
    subgenre_of: Optional[str] = None  # Parent genre
    
    # BPM-Bereich (typisch für das Genre)
    bpm_min: float = 0.0
    bpm_max: float = 0.0
    optimal_bpm: float = 128.0        # Ideal-BPM im Zentrum
    
    # Sound-Charakteristika  
    bass_type: str = ""               # "Sub Bass" / "Bass Drop" / "Kick-Heavy" / "Punchy Kick"
    kick_character: str = ""          # "Hard Kick" / "Four-on-the-floor" / "Off-beat" / "Half-time"
    energy_profile: list[str] = field(default_factory=list)  # ["Build-Up", "Drop", "Breakdown"]
    
    # Strukturelle Merkmale (EDM-Spezialität)
    typical_structure: list[str] = field(default_factory=list)   # Track-Struktur
    common_elements: list[str] = field(default_factory=list)     # Genre-typische Elemente
    
    # Transition-Typen
    transition_patterns: list[str] = field(default_factory=list)  # Wie DJs dieses Genre mischen
    
    def to_dict(self):
        return {
            "name_de": self.name_de,
            "name_en": self.name_en,
            "subgenre_of": self.subgenre_of,
            "bpm_min": round(self.bpm_min, 1),
            "bpm_max": round(self.bpm_max, 1),
            "optimal_bpm": round(self.optimal_bpm, 1),
            "bass_type": self.bass_type,
            "kick_character": self.kick_character,
            "energy_profile": self.energy_profile,
            "typical_structure": self.typical_structure,
            "common_elements": self.common_elements,
            "transition_patterns": self.transition_patterns,
        }


# ==================================================================
# VOLLSTÄNDIGE GENRE-BIBLIOTHEK: Psytrance bis Techno + alle dazwischen
# ==================================================================

GENRES = {
    # --- TRANCE-FAMILIE ---
    "Psytrance": GenreProfile(
        name_de="Psytrance", name_en="Psytrance", subgenre_of="Trance",
        bpm_min=130, bpm_max=154, optimal_bpm=142,
        bass_type="Full Bass Drop", kick_character="Four-on-the-floor + Bass Synth",
        energy_profile=["Build-Up", "Drop (Bass)", "Breakdown", "Drop"],
        typical_structure=[
            "Intro", "Lead Build", "Drops (alternierend)", 
            "Breakdown", "Final Build", "Outro"
        ],
        common_elements=[
            "Hypnotische Bass-Synth Patterns",
            "Psychedelische FX und Risers",
            "Stakkato Lead Melodies",
            "Rolling Basslines (1/32, 1/16)",
            "Atmosphärische Pads"
        ],
        transition_patterns=[
            "Key Change auf Drop-Übergang",
            "BPM-Increase durch 5 BPM Stufen",
            "Melody-Layer-Transition",
            "Energy-Peak-Overlap"
        ]
    ),
    
    "Progressive Trance": GenreProfile(
        name_de="Progressive Trance", name_en="Progressive Trance", subgenre_of="Trance",
        bpm_min=126, bpm_max=138, optimal_bpm=134,
        bass_type="Melodischer Bass", kick_character="Four-on-the-floor + Kick Bass Synchro",
        energy_profile=["Build-Up", "Drop (Bass+Lead)", "Breakdown", "Rising Build"],
        typical_structure=[
            "Progressive Build (Layer für Layer)",
            "Main Drop mit Bass + Lead Melodie",
            "Emotional Breakdown",
            "Crescendo zum Finale"
        ],
        common_elements=[
            "Melodische Progressive Basslines",
            "Atmosphärische Strings und Pads",
            "Vocal Samples (Lyrics)",
            "Risings mit Filter-Opens",
            "Harmonische Progressionen (7-chord)"
        ],
        transition_patterns=[
            "Layer-by-Layer Build-Up",
            "Melody-Transition auf Drop",
            "BPM-Konstant, Energie-Stufung"
        ]
    ),

    "Uplifting Trance": GenreProfile(
        name_de="Uplifting Trance", name_en="Uplifting Trance", subgenre_of="Trance",
        bpm_min=132, bpm_max=150, optimal_bpm=140,
        bass_type="Euphoric Bass Drop", kick_character="Four-on-the-floor + Euphoric Synth",
        energy_profile=["Build-Up", "Drop (Bass+Vocals)", "Breakdown", "Final Build"],
        typical_structure=[
            "Ethereal Intro",
            "Lead Vocal Entry",
            "Main Bass Drop",
            "Emotional Breakdown mit Vocals",
            "Final Euphoric Drop"
        ],
        common_elements=[
            "Vocal Samples (emotional Lyrics)",
            "Euphorische Lead Synths",
            "Atmosphärische Soundscapes",
            "Big Room Drums",
            "Emotionale Harmonien"
        ],
        transition_patterns=[
            "Vocal-Transition auf Drop",
            "Key Change + Bass Change gleichzeitig",
            "Energy-Peak mit Vocal-Climax"
        ]
    ),

    "Hypnotic Trance": GenreProfile(
        name_de="Hypnotic Trance", name_en="Hypnotic Trance", subgenre_of="Trance",
        bpm_min=130, bpm_max=142, optimal_bpm=136,
        bass_type="Rolling Bass Pattern", kick_character="Four-on-the-floor + Roll-Bass Syncro",
        energy_profile=["Steady Build", "Drop (Bass Pattern)", "Breakdown", "Steady Drop"],
        typical_structure=[
            "Hypnotic Intro mit Pads",
            "Repetitive Bass Pattern Entry",
            "Sustained Energy mit Variationen",
            "Brief Breakdown",
            "Return zum Hypnotic Groove"
        ],
        common_elements=[
            "Rollende Bass-Patterns (1/8, 1/16)",
            "Minimalistische Drums",
            "Ethereal Pads und FX",
            "Repetitive Melodische Fragmente",
            "Dreht sich selbst — hypnotischer Groove"
        ],
        transition_patterns=[
            "Pattern-Transition (Bass-Metamorphose)",
            "Minimaler Build-Up (wenige Elemente hinzufügen)",
            "Steady BPM ohne Sprung"
        ]
    ),

    # --- PROGRESSIVE HOUSE / TECH HOUSE ---
    "Progressive House": GenreProfile(
        name_de="Progressive House", name_en="Progressive House", subgenre_of="House",
        bpm_min=124, bpm_max=136, optimal_bpm=128,
        bass_type="Pulsating Bass Drop", kick_character="Four-on-the-floor + Kick Bass Synchro",
        energy_profile=["Build-Up", "Drop (Bass+Lead)", "Breakdown", "Rising Build"],
        typical_structure=[
            "Atmospheric Intro",
            "Progressive Build mit Filter-Opens",
            "Main Drop mit Pulsating Bass",
            "Emotional Breakdown mit Vocals/Melodies",
            "Final Rising Build + Big Drop"
        ],
        common_elements=[
            "Pulsierende Bass-Drops (wässrig, wellenartig)",
            "Atmosphärische Synthesizer und Pads",
            "Vocal Samples (emotionale Fragmente)",
            "Risings mit Filter-Evolution",
            "Harmonische Progressionen"
        ],
        transition_patterns=[
            "Filter-Open Build-Up",
            "Layer-by-Layer Energy-Stufung",
            "Key Change auf Bass-Drop Übergang"
        ]
    ),

    "Tech House": GenreProfile(
        name_de="Tech House", name_en="Tech House", subgenre_of="House",
        bpm_min=118, bpm_max=132, optimal_bpm=124,
        bass_type="Groove Bass + Funky Basslines", kick_character="Four-on-the-floor + Groovy Kick Pattern",
        energy_profile=["Steady Groove", "Build-Up", "Drop (Bass+FX)", "Breakdown", "Groove Return"],
        typical_structure=[
            "Funky Intro mit Drums/Bass",
            "Main Groove (konsistent, mit Variationen)",
            "Brief Breakdown/Filter-Section",
            "Return zum Funky Groove",
            "Final Build + Drop"
        ],
        common_elements=[
            "Groovy Basslines (funky, jazzig, techig)",
            "Minimalistische Drums mit Raumfüllung",
            "Funky Horns und Percussion Samples",
            "Tech-House Kick Pattern",
            "Subtiler Energie-Aufbau"
        ],
        transition_patterns=[
            "Bassline-Transition (funktionaler Wechsel)",
            "Groove-Pattern-Wechsel",
            "Minimal Build-Up mit Percussion-Layer"
        ]
    ),

    "Deep House": GenreProfile(
        name_de="Deep House", name_en="Deep House", subgenre_of="House",
        bpm_min=115, bpm_max=128, optimal_bpm=122,
        bass_type="Warm Bass + Soulful Basslines", kick_character="Four-on-the-floor + Warm Kick",
        energy_profile=["Steady Groove", "Breakdown (Emotional)", "Soft Drop", "Groove Return"],
        typical_structure=[
            "Soulful Intro mit Vocals/Pads",
            "Main Groove mit Soulful Bass",
            "Emotional Breakdown mit Pads/Vocals",
            "Return zum Deep Groove",
            "Final Emotional Build"
        ],
        common_elements=[
            "Soulful/Jazzige Vocal Samples",
            "Warmes, tiefes Bass-Sound",
            "Jazzy Piano und Saxophone",
            "Atmosphärische Pads",
            "Subtiler Groove ohne große Drops"
        ],
        transition_patterns=[
            "Groove-basierter Mix (keine starken Drops)",
            "Bassline-Switching",
            "Vocal-Transition für Stimmungsumstellung"
        ]
    ),

    # --- TECHNO-FAMILIE ---
    "Minimal Techno": GenreProfile(
        name_de="Minimal Techno", name_en="Minimal Techno", subgenre_of="Techno",
        bpm_min=120, bpm_max=135, optimal_bpm=128,
        bass_type="Subtle Bass + Punchy Kick", kick_character="Punchy Kick mit Space",
        energy_profile=["Steady Groove", "Subtle Build", "Drop (Bass+FX)", "Breakdown", "Groove Return"],
        typical_structure=[
            "Minimal Intro (Kick + Space)",
            "Main Groove mit subtilen Variationen",
            "Brief Breakdown/Filter-Section",
            "Return zum Minimal Groove",
            "Final Build mit subtilem Energy-Rise"
        ],
        common_elements=[
            "Extrem minimale Drums (Space zwischen Beats)",
            "Subtile Bass-Variationen",
            "Minimalistische Textur und FX",
            "Raumfüllende Atmosphäre",
            "Wenig Variation, viel Groove-Konsistenz"
        ],
        transition_patterns=[
            "Subtiler Element-Addition/Removal",
            "Space-basierter Mix (viel Atemraum)",
            "Minimal Build-Up mit einem einzigen Element"
        ]
    ),

    "Hard Techno": GenreProfile(
        name_de="Hard Techno", name_en="Hard Techno", subgenre_of="Techno",
        bpm_min=130, bpm_max=152, optimal_bpm=140,
        bass_type="Aggressive Bass + Industrial Bass", kick_character="Hard Kick mit Noise/Impact",
        energy_profile=["Steady Hard Groove", "Build-Up", "Drop (Bass+Noise)", "Breakdown", "Hard Drop"],
        typical_structure=[
            "Industrial Intro mit Noise/FX",
            "Hard Techno Groove Entry",
            "Main Bass Pattern mit Aggressive FX",
            "Brief Breakdown/Filter-Section",
            "Return zum Hard Groove + Final Build"
        ],
        common_elements=[
            "Aggressive, raue Kick-Sounds",
            "Industrial/Bearbeitete Bass-Synths",
            "Noise-Effekte und FX-Landschaften",
            "Dissonante Melodien und Arpeggios",
            "Raumfüllender Industrial Sound"
        ],
        transition_patterns=[
            "Aggressive Build-Up mit Noise-Risers",
            "Bass-Pattern-Switching (harsher/softer)",
            "FX-basierter Transition für Energie-Shift"
        ]
    ),

    "Melodic Techno": GenreProfile(
        name_de="Melodic Techno", name_en="Melodic Techno", subgenre_of="Techno",
        bpm_min=124, bpm_max=135, optimal_bpm=128,
        bass_type="Deep Bass + Atmospheric Bass", kick_character="Four-on-the-floor + Deep Kick",
        energy_profile=["Atmospheric Intro", "Build-Up", "Drop (Bass+Melody)", "Breakdown", "Rising Build"],
        typical_structure=[
            "Atmosphärische Intro mit Pads/Synths",
            "Progressive Build-Up",
            "Main Bass Drop mit Melodischem Hook",
            "Emotional Breakdown mit Vocals/Melodies",
            "Final Rising Build + Big Drop"
        ],
        common_elements=[
            "Atmosphärische Synth-Melodien und Pads",
            "Deep, pulsierender Bass",
            "Vocal Samples (emotionale Fragmente)",
            "Risings mit Filter-Evolution",
            "Melancholische Harmonien"
        ],
        transition_patterns=[
            "Atmospheric Build-Up mit Melody-Layers",
            "Filter-Open Transition auf Drop",
            "Key Change + Bass Evolution gleichzeitig"
        ]
    ),

    # --- DRUM & BASS / JUNGLE ---
    "Drum & Bass": GenreProfile(
        name_de="Drum and Bass", name_en="Drum & Bass", subgenre_of="Breaks",
        bpm_min=165, bpm_max=180, optimal_bpm=174,
        bass_type="Deep Sub Bass + Snare Roll", kick_character="Half-time Kick mit Snare Rolls",
        energy_profile=["Build-Up", "Drop (Bass+Snare)", "Breakdown", "Hard Drop"],
        typical_structure=[
            "Atmospheric Intro mit Pads/Breaks",
            "Main DNB Groove Entry",
            "Heavy Bass Pattern mit Snare Rolls",
            "Emotional Breakdown",
            "Final Hard Drop"
        ],
        common_elements=[
            "Jazzy/Drum'n'Bass Drum Patterns (Breakbeats)",
            "Tiefe Sub-Bass Synths",
            "Snare Rolls und Hi-Hat Fills",
            "Atmosphärische Soundscapes",
            "Liquid oder Neuro Stil-Elemente"
        ],
        transition_patterns=[
            "Breakbeat-basierter Transition",
            "BPM-Konstant (174 BPM), Energy-Stufung",
            "Key Change auf Bass-Drop Übergang"
        ]
    ),

    # --- HARDSTYLE / HARDCORE ---
    "Hardstyle": GenreProfile(
        name_de="Hardstyle", name_en="Hardstyle", subgenre_of="Hardcore",
        bpm_min=150, bpm_max=180, optimal_bpm=160,
        bass_type="Sawtooth Kick + Bass Drop", kick_character="Sawtooth Kick mit Distortion/Noise",
        energy_profile=["Build-Up (Riser)", "Drop (KICK+BASS)", "Breakdown", "Final Build"],
        typical_structure=[
            "Atmospheric Intro mit Pads/Bass FX",
            "Build-Up mit Riser und Filter-Open",
            "MAIN DROP: Kick + Bass Drop gleichzeitig",
            "Emotional Breakdown",
            "Final Big Build + Final Drop"
        ],
        common_elements=[
            "Iconische Sawtooth Kicks (gestampft, verzerrt)",
            "Bass Drops mit Distortion/Noise",
            "Atmosphärische Pads und Bass FX",
            "Risers mit Pitch-Rise-Effekt",
            "Emotionaler Kontrast zwischen Breakdown und Drop"
        ],
        transition_patterns=[
            "Massive Build-Up mit Riser + Filter-Open",
            "Kick+Bass Drop gleichzeitig (der Klassiker)",
            "Key Change auf Bass-Drop Übergang"
        ]
    ),

    # --- BREAKS / IDM ---
    "Breakbeat": GenreProfile(
        name_de="Breakbeat", name_en="Breakbeat", subgenre_of="Jungle/Drum & Bass",
        bpm_min=140, bpm_max=180, optimal_bpm=165,
        bass_type="Groovy Bass + Funky Basslines", kick_character="Breakbeat Pattern + Off-beat Drums",
        energy_profile=["Steady Breaks Groove", "Build-Up", "Drop (Bass+FX)", "Breakdown"],
        typical_structure=[
            "Funky/Breakbeat Intro",
            "Main Groove mit Breakbeats",
            "Brief Breakdown/Filter-Section",
            "Return zum Breakbeat Groove"
        ],
        common_elements=[
            "Jazzy Drum'n'Bass Breaks (Amen, Think, etc.)",
            "Funky Basslines und Horn Samples",
            "Breakbeat Drums mit Space",
            "Atmosphärische Pads",
            "Groovy Groove ohne große Drops"
        ],
        transition_patterns=[
            "Breakbeat-basierter Mix",
            "Bassline-Transition",
            "Groove-Pattern-Wechsel"
        ]
    ),

    # --- ADDITIONALE GENRES ---
    "Ambient": GenreProfile(
        name_de="Ambient", name_en="Ambient", subgenre_of=None,
        bpm_min=60, bpm_max=100, optimal_bpm=85,
        bass_type="Subtle Bass + Atmospheric Bass", kick_character="No Kick (ambient) oder sehr selten",
        energy_profile=["Steady Atmosphere"],
        typical_structure=[
            "Atmospheric Intro",
            "Sustained Pads und Synths",
            "Brief Breakdown/Build-Up (optional)",
            "Return zur Atmosphäre"
        ],
        common_elements=[
            "Atmosphärische Pads und Soundscapes",
            "Minimalistische Textur",
            "Natur-Sounds oder Elektronik-Samples",
            "Subtile Melodien und Harmonien"
        ],
        transition_patterns=["Nahtlose Übergänge", "Pads-Transition"]
    ),

    "Dubstep": GenreProfile(
        name_de="Dubstep", name_en="Dubstep", subgenre_of=None,
        bpm_min=138, bpm_max=150, optimal_bpm=142,
        bass_type="Wobble Bass + Growl Bass", kick_character="Half-time Kick (90 BPM feel)",
        energy_profile=["Steady Groove", "Build-Up", "Drop (Bass Wobble/Growl)", "Breakdown"],
        typical_structure=[
            "Atmospheric Intro mit Dub FX",
            "Main Groove mit Half-time Kick",
            "Wobble Bass Entry",
            "Build-Up mit Riser",
            "Main Drop mit Wobble + Growl Bass"
        ],
        common_elements=[
            "Iconische Wobble-Synths (LFO-moduliert)",
            "Growl Bass und Distorted Bass",
            "Dub-Effekte und FX-Landschaften",
            "Half-time Kick Pattern",
            "Space zwischen Drops"
        ],
        transition_patterns=[
            "Wobble-Bass-Transition",
            "Build-Up mit Riser + Filter-Open",
            "BPM-Konstant, Energy-Stufung"
        ]
    ),

    "Melodic Dubstep": GenreProfile(
        name_de="Melodic Dubstep", name_en="Melodic Dubstep", subgenre_of="Dubstep",
        bpm_min=140, bpm_max=150, optimal_bpm=143,
        bass_type="Emotional Bass + Melodische Wobble", kick_character="Half-time Kick (90 BPM feel)",
        energy_profile=["Atmospheric Intro", "Build-Up", "Drop (Bass+Melody)", "Breakdown"],
        typical_structure=[
            "Emotional Intro mit Pads/Vocals",
            "Progressive Build-Up",
            "Main Drop mit Wobble + Melodie",
            "Emotional Breakdown",
            "Final Rising Build + Big Drop"
        ],
        common_elements=[
            "Atmosphärische Synths und Pads",
            "Emotionale Vocal Samples",
            "Melodische Wobble Bass Lines",
            "Space zwischen Drops für Emotion",
            "Groove-basierter Mix ohne große Sprünge"
        ],
        transition_patterns=[
            "Atmospheric Build-Up mit Melody-Layers",
            "Filter-Open Transition auf Drop",
            "Key Change + Bass Evolution"
        ]
    ),

    # --- TECH FAMILIE (Subgenres) ---
    "Industrial Techno": GenreProfile(
        name_de="Industrial Techno", name_en="Industrial Techno", subgenre_of="Techno",
        bpm_min=125, bpm_max=145, optimal_bpm=130,
        bass_type="Aggressive Bass + Noise Bass", kick_character="Hard Kick mit Industrial FX",
        energy_profile=["Steady Industrial Groove", "Build-Up", "Drop (Bass+Noise)", "Breakdown"],
        typical_structure=[
            "Industrial Intro mit Noise/FX",
            "Main Groove mit Aggressive Drums/Bass",
            "Brief Breakdown/Filter-Section",
            "Return zum Industrial Groove"
        ],
        common_elements=["Aggressive Kicks und Bass", "Noise-Effekte", "Dissonante Melodien"],
        transition_patterns=["Industrial Build-Up mit Noise-Risers"]
    ),

    "Acid Techno": GenreProfile(
        name_de="Acid Techno", name_en="Acid Techno", subgenre_of="Techno",
        bpm_min=125, bpm_max=145, optimal_bpm=130,
        bass_type="Acid Bass (TB-303) + Industrial Bass", kick_character="Hard Kick mit Acid Pattern Syncro",
        energy_profile=["Steady Acid Groove", "Build-Up", "Drop (Acid+Bass)", "Breakdown"],
        typical_structure=[
            "Industrial Intro mit TB-303 Patterns",
            "Main Groove mit Acid Bass + Hard Drums",
            "Brief Breakdown/Filter-Section",
            "Return zum Acid Groove"
        ],
        common_elements=["TB-303 Acid Bass Patterns", "Hard Kicks und Noise FX"],
        transition_patterns=["Acid-Bass-Transition"]
    ),

    # --- SPECIAL FAMILIES ---
    "Footwork": GenreProfile(
        name_de="Footwork", name_en="Footwork", subgenre_of=None,
        bpm_min=140, bpm_max=170, optimal_bpm=160,
        bass_type="Gritty Bass + Funky Drums", kick_character="Fast Breakbeat Pattern + Off-beat Drums",
        energy_profile=["Steady Footwork Groove"],
        typical_structure=["Main Groove mit schnellen Drums"],
        common_elements=["Schnelle Breakbeats (1/16, 1/32)", "Gritty Basslines", "Jazz-Samples und Vocals"],
        transition_patterns=["Drum-Pattern-Wechsel"]
    ),

    # --- SUBGENRES / SPECIALS ---
    "Progressive Psytrance": GenreProfile(
        name_de="Progressive Psytrance", name_en="Progressive Psytrance", subgenre_of="Psytrance",
        bpm_min=130, bpm_max=148, optimal_bpm=139,
        bass_type="Full Bass + Progressive Bass Pattern", kick_character="Four-on-the-floor + Rolling Bass",
        energy_profile=["Build-Up", "Drop (Bass+Pattern)", "Breakdown", "Rising Build"],
        typical_structure=["Progressive Intro", "Main Bass Drop", "Breakdown", "Final Rising Build"],
        common_elements=["Rolling Bass Patterns", "Psychedelische FX", "Stakkato Leads"],
        transition_patterns=["Bass-Pattern-Metamorphose"]
    ),

    # --- TECH-HOUSE SUBGENRES ---
    "Deep Tech": GenreProfile(
        name_de="Deep Tech", name_en="Deep Tech", subgenre_of="Tech House",
        bpm_min=120, bpm_max=135, optimal_bpm=126,
        bass_type="Warm Bass + Deep Basslines", kick_character="Four-on-the-floor + Warm Kick",
        energy_profile=["Steady Deep Groove"],
        typical_structure=["Atmospheric Intro", "Main Deep Groove", "Brief Breakdown", "Return zum Deep Groove"],
        common_elements=["Tiefe, warme Bass-Sounds", "Minimalistische Drums mit Space"],
        transition_patterns=["Bassline-Transition"]
    ),

    # --- KEY CHANGE / TRANSITION TECHNIQUES ---
    "Key Change Patterns": GenreProfile(
        name_de="Key Change Patterns", name_en="Key Change Patterns", subgenre_of=None,
        bpm_min=0, bpm_max=240, optimal_bpm=135,
        bass_type="Variable", kick_character="Variable",
        energy_profile=["Steady Groove"],
        typical_structure=[],
        common_elements=[
            "Key Change auf Drop-Übergang (typisch EDM)",
            "BPM-Konstante mit Energie-Stufung"
        ],
        transition_patterns=[
            "Standard EDM Key Change (+3 oder +4 Halbton)",
            "Modulation während Breakdown",
            "Relative-Key-Wechsel für nahtlosen Übergang"
        ]
    ),

    # --- DJ MIX TECHNIQUES (Electronic Music) ---
    "DJ Mix Techniques": GenreProfile(
        name_de="DJ Mix Techniques", name_en="DJ Mix Techniques", subgenre_of=None,
        bpm_min=120, bpm_max=180, optimal_bpm=135,
        bass_type="Variable", kick_character="Variable",
        energy_profile=["Steady Energy Flow"],
        typical_structure=[],
        common_elements=[
            "BPM-Bridging (nahtlose Geschwindigkeitsanpassung)",
            "Key-Matching (harmonische Kompatibilität)"
        ],
        transition_patterns=[
            "BPM-Increase durch 5 BPM Stufen",
            "Energy-Stufung über mehrere Tracks",
            "Groove-basierter Mix (Tech House, Deep House)",
            "Drop-basierter Mix (Trance, Psytrance)"
        ]
    ),

    # --- BASS-INTENSITY PROFILES ---
    "Bass Profiles": GenreProfile(
        name_de="Bass Intensity Profiles", name_en="Bass Intensity Profiles", subgenre_of=None,
        bpm_min=0, bpm_max=240, optimal_bpm=135,
        bass_type="Variable", kick_character="Variable",
        energy_profile=["Steady"],
        typical_structure=[],
        common_elements=[
            "Sub Bass: 30-60 Hz (tiefster Bass)",
            "Bass Drop: 40-120 Hz (Kick+Bass Syncro)",
            "Wobble Bass: 50-80 Hz + LFO-moduliert",
            "Growl Bass: 40-100 Hz + Distortion"
        ],
        transition_patterns=["Bass-Pattern-Switching"]
    ),

    # --- TRANSITION QUALITY METRICS ---
    "Transition Quality": GenreProfile(
        name_de="Transition Quality Metrics", name_en="Transition Quality Metrics", subgenre_of=None,
        bpm_min=0, bpm_max=240, optimal_bpm=135,
        bass_type="Variable", kick_character="Variable",
        energy_profile=["Steady"],
        typical_structure=[],
        common_elements=[
            "Smoothness: Wie nahtlos der Übergang ist (0-1)",
            "Energy Flow: Energie-Aufbau/Abschwung über Track-Grenze hinweg"
        ],
        transition_patterns=["Nahtloser Übergang"]
    ),

}


# ========================================
# Genre Detection & Classification
# ========================================

def get_genre(name):
    """Get genre by name (German or English)."""
    if name in GENRES:
        return GENRES[name]
    
    # Fuzzy matching (partial)
    for genre_name, profile in GENRES.items():
        if genre_name.lower() in name.lower() or name.lower() in genre_name.lower():
            return profile
    
    return None


def get_all_genre_names():
    """Get all genre names."""
    return list(GENRES.keys())


def get_genres_by_family(family):
    """Get genres belonging to a family (e.g., 'Trance', 'Techno')."""
    result = []
    for name, profile in GENRES.items():
        if profile.subgenre_of == family:
            result.append(name)
    return result


def is_trance_genre(genre_name):
    """Check if genre belongs to Trance family."""
    return get_genres_by_family("Trance")


def is_techno_genre(genre_name):
    """Check if genre belongs to Techno family."""
    return get_genres_by_family("Techno")


def is_house_genre(genre_name):
    """Check if genre belongs to House family."""
    return get_genres_by_family("House")


# ========================================
# BPM Category from Genre (for quick reference)
# ========================================

BPM_CATEGORIES = {
    "ambient": ("slow", 60, 100),
    "deep house": ("mid-slow", 115, 128),
    "tech house": ("mid", 118, 132),
    "progressive house": ("mid", 124, 136),
    "melodic techno": ("mid", 124, 135),
    "minimal techno": ("mid", 120, 135),
    "hard techno": ("mid-fast", 130, 152),
    "industrial techno": ("mid", 125, 145),
    "acid techno": ("mid", 125, 145),
    
    "trance": ("mid-fast", 130, 154),
    "progressive trance": ("mid-fast", 126, 138),
    "uplifting trance": ("fast", 132, 150),
    "hypnotic trance": ("mid-fast", 130, 142),
    
    "psytrance": ("fast", 130, 154),
    "progressive psytrance": ("mid-fast", 130, 148),
    
    "drum and bass": ("fast", 165, 180),
    "breakbeat": ("fast", 140, 180),
    
    "hardstyle": ("very fast", 150, 180),
    "dubstep": ("fast", 138, 150),
    "melodic dubstep": ("fast", 140, 150),
}


def get_bpm_category(genre_name: str) -> dict:
    """Get BPM category for a genre."""
    key = genre_name.lower()
    return BPM_CATEGORIES.get(key, {"category": "unknown", "min": 0, "max": 240})


# ========================================
# Genre-Specific Transition Analysis
# ========================================

class ElectronicMusicTransitionAnalyzer:
    """Specialized transition analysis for electronic music genres."""
    
    def __init__(self):
        self.genres = GENRES
    
    def analyze_transition_quality(
        self, 
        pre_track_genre: str = None,
        post_track_genre: str = None,
        energy_change_db: float = 0.0,
        bass_intensity_diff: float = 0.0,
        key_change_detected: bool = False
    ) -> dict:
        """Analyze transition quality between two electronic tracks."""
        
        pre_genre = get_genre(pre_track_genre) if pre_track_genre else None
        post_genre = get_genre(post_track_genre) if post_track_genre else None
        
        # Genre compatibility check
        compatible = self._check_genre_compatibility(pre_genre, post_genre)
        
        # Energy flow assessment
        energy_flow = self._assess_energy_flow(energy_change_db, bass_intensity_diff)
        
        # Transition type guess based on genres
        transition_type = self._guess_transition_type(pre_genre, post_genre, compatible, energy_flow)
        
        return {
            "pre_track_genre": pre_track_genre or "unknown",
            "post_track_genre": post_track_genre or "unknown",
            "compatible": compatible,
            "energy_change_db": energy_change_db,
            "bass_intensity_diff": bass_intensity_diff,
            "key_change_detected": key_change_detected,
            "transition_type_guess": transition_type,
            "quality_score": self._calculate_quality_score(compatible, energy_flow),
        }
    
    def _check_genre_compatibility(self, pre_genre, post_genre):
        """Check if two genres are DJ-compatible for smooth mixing."""
        if not pre_genre or not post_genre:
            return False
        
        # Same family = always compatible
        if pre_genre.subgenre_of == post_genre.subgenre_of and pre_genre.subgenre_of is not None:
            return True
        
        # Compatible energy ranges (overlap)
        pre_bpm = self._get_bpm_range(pre_genre)
        post_bpm = self._get_bpm_range(post_genre)
        
        bpm_overlap = max(0, min(max(pre_bpm), max(post_bpm)) - max(min(pre_bpm), min(post_bpm)))
        if bpm_overlap > 15:  # Significant overlap
            return True
        
        # Bass type compatibility
        bass_compatible = self._check_bass_compatibility(pre_genre, post_genre)
        
        return bass_compatible
    
    def _get_bpm_range(self, genre):
        """Get BPM range for a genre."""
        if not genre:
            return (100, 160)
        return (genre.bpm_min, genre.bpm_max)
    
    def _check_bass_compatibility(self, pre_genre, post_genre):
        """Check bass type compatibility."""
        bass_types = {
            "Sub Bass": ["Deep Bass", "Atmospheric Bass"],
            "Bass Drop": ["Full Bass Drop", "Euphoric Bass Drop"],
            "Wobble Bass": ["Growl Bass", "Melodische Wobble"],
            "Pulsating Bass": ["Deep Bass", "Warm Bass"],
        }
        
        pre_bass = pre_genre.bass_type.lower() if hasattr(pre_genre, 'bass_type') else ""
        post_bass = post_genre.bass_type.lower() if hasattr(post_genre, 'bass_type') else ""
        
        for base, compatible in bass_types.items():
            if base.lower() in pre_bass and any(c.lower() in post_bass for c in compatible):
                return True
        
        # Generic compatibility check (similar energy profiles)
        pre_energy = set(pre_genre.energy_profile) if hasattr(pre_genre, 'energy_profile') else set()
        post_energy = set(post_genre.energy_profile) if hasattr(post_genre, 'energy_profile') else set()
        
        shared = pre_energy & post_energy
        return len(shared) > 0
    
    def _assess_energy_flow(self, energy_change_db: float, bass_diff: float) -> str:
        """Assess the energy flow between tracks."""
        if abs(energy_change_db) < 3.0 and abs(bass_diff) < 0.15:
            return "smooth"  # Very smooth transition
        elif abs(energy_change_db) < 6.0 and abs(bass_diff) < 0.25:
            return "moderate"  # Moderate — could be smoother
        else:
            return "sharp"  # Sharp jump
    
    def _guess_transition_type(self, pre_genre, post_genre, compatible, energy_flow):
        """Guess the transition type based on genre analysis."""
        if not pre_genre or not post_genre:
            return "unknown"
        
        # Genre-specific transitions
        if pre_genre.subgenre_of and post_genre.subgenre_of == pre_genre.subgenre_of:
            return f"{pre_genre.name_de} family bridge — Key Change + BPM-Bridging"
        
        if energy_flow == "sharp":
            return f"Genre-Switch Transition ({pre_genre.name_de} → {post_genre.name_de}) — Aggressive Energy Shift"
        elif compatible:
            return f"BPM-Bridging Transition ({pre_genre.name_de} → {post_genre.name_de}) — Smooth Groove Flow"
        else:
            return "Style-Transition (Genre-Switch) — Bassline & Pattern Change"
    
    def _calculate_quality_score(self, compatible: bool, energy_flow: str) -> float:
        """Calculate transition quality score (0-100)."""
        base_score = 70.0
        
        if compatible and energy_flow == "smooth":
            return min(95, base_score + 25)
        elif compatible and energy_flow == "moderate":
            return min(85, base_score + 15)
        elif not compatible:
            return max(30, base_score - 40)
        
        return base_score


# ========================================
# Genre-Based Track Structure Analysis
# ========================================

class ElectronicMusicStructureAnalyzer:
    """Analyze electronic music track structure for DJ mixing."""
    
    def __init__(self):
        self.genres = GENRES
    
    def detect_track_structure(self, genre_name: str) -> list[dict]:
        """Detect expected track structure based on genre."""
        genre = get_genre(genre_name) if genre_name else None
        
        if not genre or not genre.typical_structure:
            return [{"section": "unknown", "expected_function": "general"}]
        
        # Map structure sections to DJ mixing functions
        structure = []
        for i, section in enumerate(genre.typical_structure):
            functions = self._map_section_to_function(section)
            structure.append({
                "index": i,
                "section_name_de": f"Abschnitt {i+1}",
                "section_name_en": section,
                "functions": functions,
            })
        
        return structure
    
    def _map_section_to_function(self, section: str) -> list[str]:
        """Map track sections to DJ mixing functions."""
        mapping = {
            "Intro": ["Mixing Point", "DJ Entry"],
            "Drop (Bass)": ["High Energy", "Climax"],
            "Breakdown": ["Emotional Moment", "DJ Transition Point"],
            "Build-Up": ["Energy Rise", "Pre-Drop"],
            "Outro": ["DJ Exit", "Fading Out"],
        }
        
        return mapping.get(section, ["General Section"])
    
    def get_mixing_recommendation(self, genre_name: str) -> list[str]:
        """Get DJ mixing recommendations for a specific electronic music genre."""
        genre = get_genre(genre_name) if genre_name else None
        
        if not genre or not genre.transition_patterns:
            return ["General mixing techniques apply"]
        
        # Add general EDM mixing tips
        recommendations = [
            f"BPM-Bridging zwischen {genre.name_de} Tracks (5 BPM Stufen)",
            "Key-Matching für nahtlose Übergänge"
        ]
        
        for pattern in genre.transition_patterns:
            if "Bass" in pattern or "Drop" in pattern:
                recommendations.append(f"Bass-Intensität auf {pattern.split('—')[0].strip()} achten")
            
        return recommendations


# ========================================
# Genre-Specific Transition Scoring
# ========================================

class ElectronicMusicTransitionScorer:
    """Score electronic music transitions based on genre-specific criteria."""
    
    # Genre-specific transition weights
    GENRE_WEIGHTS = {
        "Trance": {
            "bpm_match": 0.25,
            "key_change": 0.30,
            "energy_flow": 0.25,
            "pattern_similarity": 0.20,
        },
        "Techno": {
            "groove_consistency": 0.40,
            "kick_pattern_match": 0.20,
            "bass_similarity": 0.20,
            "energy_flow": 0.20,
        },
        "Psytrance": {
            "bpm_match": 0.35,
            "pattern_evolution": 0.30,
            "energy_flow": 0.20,
            "key_change": 0.15,
        },
        "Dubstep": {
            "half_time_kick": 0.30,
            "bass_type_match": 0.25,
            "wobble_similarity": 0.20,
            "energy_flow": 0.25,
        },
        "Drum and Bass": {
            "breakbeat_pattern": 0.30,
            "bpm_exact_match": 0.40,
            "energy_flow": 0.15,
            "key_change": 0.15,
        },
        "Hardstyle": {
            "kick_type": 0.25,
            "bass_drop_similarity": 0.30,
            "energy_buildup": 0.25,
            "pattern_evolution": 0.20,
        },
    }
    
    def __init__(self):
        self.genres = GENRES
    
    def score_transition(
        self, 
        pre_track_genre: str,
        post_track_genre: str,
        bpm_difference: float = 5.0,
        key_change_detected: bool = False,
        energy_change_db: float = 3.0,
        bass_intensity_diff: float = 0.1,
    ) -> dict:
        """Score a transition between two electronic music tracks."""
        
        pre_genre = get_genre(pre_track_genre) if pre_track_genre else None
        post_genre = get_genre(post_track_genre) if post_track_genre else None
        
        # Get genre weights for scoring
        weights = self.GENRE_WEIGHTS.get(
            pre_track_genre, 
            {"bpm_match": 0.25, "key_change": 0.15, "energy_flow": 0.25, "pattern_similarity": 0.35}
        )
        
        # Calculate scores per criteria
        bpm_score = self._score_bpm_match(bpm_difference)
        key_score = int(key_change_detected * 100) if key_change_detected else 40
        
        energy_score = self._score_energy_flow(energy_change_db)
        bass_score = self._score_bass_similarity(bass_intensity_diff)
        
        # Weighted total
        total_score = (
            bpm_score * weights["bpm_match"] +
            key_score * weights["key_change"] +
            energy_score * weights["energy_flow"] +
            bass_score * 0.35
        )
        
        return {
            "pre_track_genre": pre_track_genre,
            "post_track_genre": post_track_genre,
            "weighted_score": round(total_score, 1),
            "criteria_scores": {
                "bpm_match": bpm_score,
                "key_change": key_score,
                "energy_flow": energy_score,
                "pattern_similarity/bass": bass_score,
            },
        }
    
    def _score_bpm_match(self, bpm_difference: float) -> int:
        """Score BPM match (0-100)."""
        if abs(bpm_difference) <= 2.5:
            return 95
        elif abs(bpm_difference) <= 5.0:
            return max(70, 95 - (abs(bpm_difference) - 2.5) * 10)
        else:
            return max(30, 70 - (abs(bpm_difference) - 5) * 8)
    
    def _score_energy_flow(self, energy_change_db: float) -> int:
        """Score energy flow smoothness (0-100)."""
        if abs(energy_change_db) <= 3.0:
            return 95
        elif abs(energy_change_db) <= 6.0:
            return max(70, 95 - (abs(energy_change_db) - 3) * 10)
        else:
            return max(40, 70 - (abs(energy_change_db) - 6) * 8)
    
    def _score_bass_similarity(self, bass_diff: float) -> int:
        """Score bass similarity (0-100)."""
        if bass_diff <= 0.15:
            return 95
        elif bass_diff <= 0.30:
            return max(70, 95 - (bass_diff - 0.15) * 80)
        else:
            return max(40, 70 - (bass_diff - 0.3) * 60)


# ========================================
# Genre-Specific BPM Bridging Guide
# ========================================

class ElectronicMusicBPMBridgeGuide:
    """Generate BPM bridging plans for electronic music genres."""
    
    def __init__(self):
        self.genres = GENRES
    
    def generate_bpm_bridge_plan(self, from_genre: str, to_genre: str) -> dict:
        """Generate a step-by-step BPM bridging plan between two genres."""
        
        from_genre_obj = get_genre(from_genre) if from_genre else None
        to_genre_obj = get_genre(to_genre) if to_genre else None
        
        from_bpm = self._get_target_bpm(from_genre, from_genre_obj)
        to_bpm = self._get_target_bpm(to_genre, to_genre_obj)
        
        # Generate bridge steps (5 BPM increments)
        steps = []
        current_bpm = int(from_bpm)
        
        while abs(current_bpm - int(to_bpm)) > 0:
            next_bpm = int(current_bpm) + 5 if to_bpm > from_bpm else int(current_bpm) - 5
            
            steps.append({
                "step": len(steps) + 1,
                "from_bpm": current_bpm,
                "to_bpm": next_bpm,
                "transition_type": self._get_bridge_step_description(from_genre_obj, to_genre_obj, current_bpm, next_bpm),
            })
            
            if next_bpm >= int(to_bpm) or next_bpm <= int(to_bpm):
                break
            
            current_bpm = next_bpm
        
        # Add final step
        steps.append({
            "step": len(steps) + 1,
            "from_bpm": int(current_bpm),
            "to_bpm": int(to_bpm),
            "transition_type": self._get_bridge_step_description(from_genre_obj, to_genre_obj, current_bpm, to_bpm),
        })
        
        return {
            "from_genre": from_genre or "unknown",
            "to_genre": to_genre or "unknown",
            "from_target_bpm": int(from_bpm),
            "to_target_bpm": int(to_bpm),
            "total_steps": len(steps),
            "steps": steps,
        }
    
    def _get_target_bpm(self, genre_name: str, genre_obj) -> float:
        """Get target BPM for a genre."""
        if genre_obj and hasattr(genre_obj, 'optimal_bpm'):
            return genre_obj.optimal_bpm
        
        # Fallback to BPM range center
        bpm_min = 120.0
        bpm_max = 135.0
        if hasattr(genre_obj, 'bpm_min'):
            bpm_min = genre_obj.bpm_min
        if hasattr(genre_obj, 'bpm_max'):
            bpm_max = genre_obj.bpm_max
        
        return (bpm_min + bpm_max) / 2
    
    def _get_bridge_step_description(self, pre_genre, post_genre, from_bpm, to_bpm):
        """Get human-readable description for a bridge step."""
        
        # Genre-specific bridge descriptions
        if pre_genre and post_genre:
            if pre_genre.subgenre_of == post_genre.subgenre_of:
                return f"Same-family BPM-Bridging ({pre_genre.name_de}: {from_bpm} → {to_bpm})"
            elif abs(to_bpm - from_bpm) <= 5:
                return f"BPM-Stufung ({pre_genre.name_de} → {post_genre.name_de}: +{to_bpm - from_bpm:.0f} BPM)"
            else:
                return f"Genre-Switch BPM-Bridge ({from_bpm} → {to_bpm} BPM)"
        
        return f"BPM-Stufung ({from_bpm} → {to_bpm})"


# ========================================
# Convenience Functions for Quick Access
# ========================================

def list_all_genres() -> dict:
    """List all supported electronic music genres with summary."""
    result = {}
    
    families = ["Trance", "Techno", "House", "Psytrance", "Drum & Bass/Jungle/Breaks", 
                "Hardstyle/Hardcore", "Dubstep", "Ambient/Other"]
    
    for family in families:
        genres_in_family = get_genres_by_family(family)
        if genres_in_family:
            result[family] = {
                "genres": [name for name in genres_in_family],
                "bpm_range": f"{min(GENRES[n].bpm_min for n in genres_in_family)}-{max(GENRES[n].bpm_max for n in genres_in_family)}",
            }
    
    # Add standalone genres (no parent)
    standalone = []
    for name, profile in GENRES.items():
        if not profile.subgenre_of:
            standalone.append(name)
    
    if standalone:
        result["Standalone Genres"] = {
            "genres": standalone,
        }
    
    return result


def get_genre_bpm_ranges() -> dict:
    """Get BPM ranges for all genres (quick reference)."""
    result = {}
    
    bpm_data = [
        ("Ambient", 60, 100),
        ("Deep House", 115, 128),
        ("Tech House", 118, 132),
        ("Progressive House", 124, 136),
        ("Melodic Techno", 124, 135),
        ("Minimal Techno", 120, 135),
        ("Hard Techno", 130, 152),
        ("Industrial Techno", 125, 145),
        ("Acid Techno", 125, 145),
        ("Trance", 130, 154),
        ("Progressive Trance", 126, 138),
        ("Uplifting Trance", 132, 150),
        ("Hypnotic Trance", 130, 142),
        ("Psytrance", 130, 154),
        ("Progressive Psytrance", 130, 148),
        ("Drum & Bass", 165, 180),
        ("Breakbeat", 140, 180),
        ("Hardstyle", 150, 180),
        ("Dubstep", 138, 150),
        ("Melodic Dubstep", 140, 150),
    ]
    
    for name, min_bpm, max_bpm in bpm_data:
        result[name] = {"bpm_min": min_bpm, "bpm_max": max_bpm}
    
    return result
