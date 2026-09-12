"""Pacing Specialist — Database Models."""

from sqlalchemy import Column, Integer, Float, String, Text, DateTime, Boolean, JSON, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship, Session, sessionmaker
from datetime import datetime
import uuid

Base = declarative_base()


class Analysis(Base):
    """Base analysis record (shared ID schema)."""
    __tablename__ = "analyses"
    
    id = Column(String(32), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    file_name = Column(String(256), nullable=False)
    audio_duration_ms = Column(Integer, default=0)
    sample_rate = Column(Integer, default=44100)
    
    # Relationships
    speech_metrics = relationship("SpeechMetrics", back_populates="analysis")
    mood_analysis = relationship("MoodAnalysis", back_populates="analysis") 
    groove_analysis = relationship("GrooveAnalysis", back_populates="analysis")


class SpeechMetrics(Base):
    """Speech pacing metrics for an analysis."""
    __tablename__ = "speech_metrics"
    
    id = Column(Integer, primary_key=True)
    analysis_id = Column(String(32), ForeignKey("analyses.id"), nullable=False)
    
    total_words = Column(Integer, default=0)
    wpm = Column(Float, default=0.0)
    cps = Column(Float, default=0.0)
    avg_pause_ms = Column(Float, default=500.0)
    long_silence_ratio = Column(Float, default=0.0)
    pace_variance = Column(Float, default=1.0)
    score = Column(Integer, default=50)  # 0-100
    
    segments_json = Column(JSON)  # Stored as JSON list
    
    analysis = relationship("Analysis", back_populates="speech_metrics")


class MoodAnalysis(Base):
    """Mood/atmosphere analysis for an audio file."""
    __tablename__ = "mood_analysis"
    
    id = Column(Integer, primary_key=True)
    analysis_id = Column(String(32), ForeignKey("analyses.id"), nullable=False)
    
    dominant_mood_de = Column(String(50))       # German mood name
    dominant_mood_en = Column(String(50))       # English mood name  
    mood_confidence = Column(Float, default=0.5)
    
    energy_level = Column(Float, default=0.5)
    bass_intensity = Column(Float, default=0.5)
    treble_brightness = Column(Float, default=0.5)
    groove_strength = Column(Float, default=0.5)
    
    dynamic_range = Column(String(20))           # narrow/medium/wide
    attack_character = Column(String(20))        # sharp/moderate/soft
    
    track_transition_prob = Column(Float, default=0.0)
    bass_shift_detected = Column(Boolean, default=False)
    
    analysis = relationship("Analysis", back_populates="mood_analysis")


class GrooveAnalysis(Base):
    """Groove/rhythm analysis for an audio file."""
    __tablename__ = "groove_analysis"
    
    id = Column(Integer, primary_key=True)
    analysis_id = Column(String(32), ForeignKey("analyses.id"), nullable=False)
    
    overall_groove_score = Column(Float, default=0.5)
    beat_strength = Column(Float, default=0.5)
    syncopation_level = Column(Float, default=0.3)
    swing_percentage = Column(Float, default=2.0)
    
    snare_position = Column(String(20))          # backbeat/syncopated/constant
    driving_force = Column(Float, default=0.5)
    quality_label_de = Column(Text)              # Human-readable description
    
    analysis = relationship("Analysis", back_populates="groove_analysis")


class TrackTransition(Base):
    """Detected track transitions in a DJ mix."""
    __tablename__ = "track_transitions"
    
    id = Column(Integer, primary_key=True)
    analysis_id = Column(String(32), ForeignKey("analyses.id"), nullable=False)
    
    timestamp_sec = Column(Float, default=0.0)
    transition_type = Column(String(50))         # build_up/drop/fade_out/hard_cut
    confidence = Column(Float, default=0.5)
    
    pre_mood_de = Column(String(50))            # Mood before transition
    post_mood_de = Column(String(50))           # Mood after transition
    energy_change_db = Column(Float, default=0.0)


class BeatAnalysis(Base):
    """Beat/tempo analysis results."""
    __tablename__ = "beat_analysis"
    
    id = Column(Integer, primary_key=True)
    analysis_id = Column(String(32), ForeignKey("analyses.id"), nullable=False)
    
    bpm_global = Column(Float, default=120.0)
    bpm_min = Column(Float, default=60.0)
    bpm_max = Column(Float, default=240.0)
    
    drops_count = Column(Integer, default=0)
    tempo_changes_count = Column(Integer, default=0)
    beat_grid_confidence = Column(Float, default=0.5)
    dominant_genre_hints = Column(JSON, default=list)


class VideoAnalysis(Base):
    """Video pacing analysis results."""
    __tablename__ = "video_analysis"
    
    id = Column(Integer, primary_key=True)
    analysis_id = Column(String(32), ForeignKey("analyses.id"), nullable=False)
    
    total_shots_count = Column(Integer, default=0)
    avg_shot_duration_ms = Column(Float, default=1000.0)
    rhythm_score = Column(Float, default=0.5)
    visual_pacing_score = Column(Integer, default=50)
    
    shot_data_json = Column(JSON)  # Per-shot data stored as JSON


def create_database_uri(db_path: str = "pacing_app.db") -> str:
    """Create SQLAlchemy URI for SQLite database."""
    return f"sqlite:///{db_path}"
