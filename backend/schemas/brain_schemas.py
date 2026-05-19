"""Brain-Endpoint Schemas (Plan Phase 4 + R-Brain-09)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class BrainScoreEntry(BaseModel):
    """Sub-Score fuer eine Achse."""
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
    posterior_variance: float = Field(
        0.0,
        description="Bayes-Varianz des Beta-Posterior: alpha*beta / "
                    "((alpha+beta)^2 * (alpha+beta+1)). SmartSampler nutzt das "
                    "fuer die 'unsicherste-Cuts'-Selektion.",
    )


class BrainStatsResponse(BaseModel):
    total_clicks: int
    cold_start_axes: int
    learned_axes: int
    top_positive: list[BrainStatsBucket] = []
    top_negative: list[BrainStatsBucket] = []
    cold_start_axes_list: list[str] = Field(
        default_factory=list,
        description="Achsen aus BRIDGE_AXES, die noch nicht gelernt sind "
                    "(positive_count + negative_count < 10). UX-Anzeige im "
                    "HIRN-Tab fuers Brain-Coaching.",
    )


class BrainResetRequest(BaseModel):
    confirmation_token: Optional[str] = None


class BrainResetResponse(BaseModel):
    status: str
    confirmation_token: Optional[str] = None


# R-Brain-09: explain endpoint
class BrainAxisContribution(BaseModel):
    """Pro-Achse-Aufschluesselung: bridge_value (raw) * posterior (gelerntes
    Gewicht) = score. Sortiert absteigend nach score in /brain/explain.

    bridge_value/posterior haben keine harte Obergrenze, weil einige Cold-Start
    Defaults (z.B. kick_weight=1.2, max_clip_length=8.0) ausserhalb 0..1 liegen.
    score wird im Endpoint auf 0..1 geclippt.
    """
    axis: str
    bridge_value: float = Field(..., ge=0.0)
    posterior: float = Field(..., ge=0.0)
    score: float = Field(..., ge=0.0, le=1.0)
    n_samples: int = Field(
        0, ge=0,
        description="Klicks die in diese (axis, context)-Kombination geflossen "
                    "sind, am spezifischsten verfuegbaren Bucket-Level.",
    )


class BrainExplainResponse(BaseModel):
    """Antwort fuer GET /brain/explain/{cut_id}.

    UX: Tooltip beim Hover ueber den Confidence-Balken in der Timeline.
    """
    cut_id: int
    clip_id: str
    start_time: float
    end_time: float
    segment_type: Optional[str] = None
    final_score: float
    context_keys: list[str] = []
    top_axes: list[BrainAxisContribution] = []
    bottom_axes: list[BrainAxisContribution] = []
    cold_start_axes: list[str] = Field(
        default_factory=list,
        description="Achsen ohne genug Samples (< 10) -- Confidence kommt vom Default.",
    )
    narrative: Optional[str] = Field(
        default=None,
        description="Natuerlichsprachige Erklaerung (1-3 Saetze, DE) vom LLM-"
                    "Narrator. None wenn LM Studio nicht verfuegbar, kein "
                    "passendes Modell oder explizit per ?narrative=false "
                    "abgeschaltet. Augmentiert die strukturierten Achsen-"
                    "Daten, ersetzt sie nicht.",
    )
