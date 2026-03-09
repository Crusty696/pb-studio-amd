"""Projekt-bezogene Schemas."""

from pydantic import BaseModel, Field
from typing import Optional
from pathlib import Path


class ProjectCreate(BaseModel):
    """Request: Neues Projekt erstellen."""
    name: str = Field(..., min_length=1, max_length=200)
    path: str = Field(..., description="Zielverzeichnis für das Projekt")


class ProjectOpen(BaseModel):
    """Request: Bestehendes Projekt öffnen."""
    path: str = Field(..., description="Pfad zur Projektdatei oder zum Projektordner")


class ProjectInfo(BaseModel):
    """Response: Projekt-Informationen."""
    name: str
    path: str
    audio_count: int = 0
    video_count: int = 0
    has_timeline: bool = False
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
