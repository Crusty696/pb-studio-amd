"""Brain-Endpoint Schemas (Plan Phase 4)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class BrainScoreEntry(BaseModel):
    """Sub-Score für eine Achse."""
    axis: str
    score: float
    weight: float


class BrainSuggestRequest(BaseModel):
    audio_clip_id: int
    video_clip_ids: list[int] = []
    top_n: int = Field(20, ge=1, le=200)


class BrainSuggestion(BaseModel):
    cut_id: Optional[int] = None
    clip_id: str
    start_time: float
    end_time: float
    final_score: float
    brain_scores: dict[str, float] = {}


class BrainSuggestResponse(BaseModel):
    suggestions: list[BrainSuggestion] = []


class BrainFeedbackRequest(BaseModel):
    cut_id: int
    rating: str = Field(..., pattern="^(perfect|fits|not_quite|no_match)$")


class BrainFeedbackResponse(BaseModel):
    status: str
    updated_buckets: int
    total_clicks: int


class BrainLearningSessionResponse(BaseModel):
    cuts: list[BrainSuggestion] = []


class BrainStatsBucket(BaseModel):
    axis: str
    context_level: int
    context_key: str
    positive_count: float
    negative_count: float
    posterior: float


class BrainStatsResponse(BaseModel):
    total_clicks: int
    cold_start_axes: int
    learned_axes: int
    top_positive: list[BrainStatsBucket] = []
    top_negative: list[BrainStatsBucket] = []


class BrainResetRequest(BaseModel):
    confirmation_token: Optional[str] = None


class BrainResetResponse(BaseModel):
    status: str
    confirmation_token: Optional[str] = None
