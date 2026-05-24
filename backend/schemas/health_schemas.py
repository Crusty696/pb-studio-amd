"""Health endpoint schemas (T5b S-H1b: Pydantic-backed /health/vram für NSwag).

Shapes match VRAMBudgetManager.get_stats() + get_telemetry() output exactly
(siehe src/pb_studio/core/vram_budget_manager.py).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Budget side
# ============================================================================

class VramModelEntry(BaseModel):
    """Per-model budget entry as returned by get_stats().models[model_id]."""
    name: str
    vram_mb: float
    is_loaded: bool
    priority: str  # ModelPriority.name (LOW/MEDIUM/HIGH/CRITICAL)


class VramBudgetStats(BaseModel):
    """Output of VRAMBudgetManager.get_stats()."""
    max_vram_mb: float
    usable_vram_mb: float
    reserved_mb: float
    committed_mb: float
    available_mb: float
    loaded_models: int
    reserved_models: int
    models: dict[str, VramModelEntry] = Field(default_factory=dict)


# ============================================================================
# Telemetry side
# ============================================================================

class VramDurationStats(BaseModel):
    """Duration sub-block of TelemetryEntry.to_dict()['duration_ms']."""
    min: Optional[float] = None
    max: Optional[float] = None
    avg: Optional[float] = None
    histogram: dict[str, int] = Field(default_factory=dict)


class VramPeakStats(BaseModel):
    """VRAM-peak sub-block of TelemetryEntry.to_dict()['vram_peak_mb']."""
    min: Optional[float] = None
    max: Optional[float] = None
    histogram: dict[str, int] = Field(default_factory=dict)


class VramTelemetryEntry(BaseModel):
    """Per-model telemetry as returned by TelemetryEntry.to_dict()."""
    model_id: str
    count: int = 0
    success_count: int = 0
    failure_count: int = 0
    duration_ms: VramDurationStats
    vram_peak_mb: VramPeakStats
    last_error: Optional[dict[str, Any]] = None


class VramTelemetrySummary(BaseModel):
    """Aggregate summary block of multi-model get_telemetry()."""
    models_tracked: int = 0
    observations: int = 0
    duration_buckets_ms: list[float] = Field(default_factory=list)
    vram_buckets_mb: list[float] = Field(default_factory=list)


class VramTelemetryMulti(BaseModel):
    """Multi-model variant of get_telemetry() — when model_id is None."""
    models: dict[str, VramTelemetryEntry] = Field(default_factory=dict)
    summary: VramTelemetrySummary


# ============================================================================
# Top-level response
# ============================================================================

class VramHealthResponse(BaseModel):
    """Response for GET /health/vram (no model_id query — multi-model snapshot).

    T5b S-H1b: explicit Pydantic-Schema damit NSwag den DTO benannt
    generieren kann (vorher: inline additionalProperties=true -> opaque).
    """
    status: str = "ok"
    budget: VramBudgetStats
    telemetry: VramTelemetryMulti


class VramHealthSingleResponse(BaseModel):
    """Response for GET /health/vram?model_id=X — single-model view."""
    status: str = "ok"
    budget: VramBudgetStats
    telemetry: VramTelemetryEntry


# ============================================================================
# Dynamic Limit side
# ============================================================================

class VramLimitRequest(BaseModel):
    """Request schema for POST /health/vram/limit."""
    limit_mb: int = Field(..., description="The new maximum VRAM limit in MB.")


class VramLimitResponse(BaseModel):
    """Response schema for POST /health/vram/limit."""
    status: str = "ok"
    limit_mb: int
    usable_vram_mb: float

