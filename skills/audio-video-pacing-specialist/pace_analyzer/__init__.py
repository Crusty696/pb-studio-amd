"""Pace Analyzer — Core Library for Audio/Video Pacing Analysis."""

from .speech_pace import SpeechPaceAnalyzer, PaceSegment
from .beat_detector import BeatDetector, DetectedBeat
from .pacing_models import PacingScore, PacingReport, PacingOptimizer, OptimizationSuggestion
from .mood_detector import MoodDetector, EDMGenreMood, EDM_MOOD_PROFILES
from .groove_detector import GrooveDetector, GrooveFeature, GrooveResult, describe_groove_to_user

# Genre-specific library for electronic music (Psytrance → Techno)
try:
    from .electronic_music_genres import GENRES, get_genre, BPM_CATEGORIES
except ImportError:
    GENRES = {}
    get_genre = lambda name: None
    BPM_CATEGORIES = {}

__all__ = [
    # Speech
    "SpeechPaceAnalyzer", "PaceSegment",
    # Beat
    "BeatDetector", "DetectedBeat", 
    # Models & Optimizer
    "PacingScore", "PacingReport", "PacingOptimizer", "OptimizationSuggestion",
    # Mood
    "MoodDetector", "EDMGenreMood", "EDM_MOOD_PROFILES",
    # Groove
    "GrooveDetector", "GrooveFeature", "GrooveResult", "describe_groove_to_user",
    # Genre library (electronic music)
    "GENRES", "get_genre", "BPM_CATEGORIES",
]
