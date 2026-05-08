"""
Health Router – Sub-Endpoints fuer System-Telemetrie.

Endpoints:
  GET /health/vram — VRAMBudgetManager-Statistik + Telemetrie-Histogram
                     (Dauer + VRAM-Peak pro model_id).

Hinweis: Die Top-Level-Endpoints `/health` und `/health/heartbeat` werden
weiterhin in backend/main.py inline definiert. Dieses Modul erweitert nur den
`/health` Pfadraum um spezialisierte Sub-Endpoints — kein Konflikt mit den
bestehenden Inline-Routes (FastAPI route table is path-based).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/vram")
async def vram_health(
    model_id: Optional[str] = Query(
        default=None,
        description="Optional: nur Telemetrie fuer einen einzelnen model_id zurueckgeben.",
    ),
) -> dict[str, Any]:
    """
    Liefert eine kombinierte Sicht auf VRAM-Budget + Telemetrie:

      * `budget`    — Live-Stats des VRAMBudgetManager (max/usable/reserved/committed)
      * `telemetry` — Histogram + Min/Max/Avg ueber Dauer und VRAM-Peak pro model_id

    Bei `?model_id=X` wird `telemetry` auf den entsprechenden Eintrag reduziert.
    """
    try:
        from pb_studio.core.vram_budget_manager import get_vram_manager
    except Exception as exc:
        logger.warning(f"VRAM-Manager nicht importierbar: {exc}")
        raise HTTPException(
            status_code=503,
            detail=f"VRAM-Manager nicht verfuegbar: {exc}",
        )

    try:
        manager = get_vram_manager()
        budget_stats = manager.get_stats()
        telemetry = manager.get_telemetry(model_id=model_id)
    except Exception as exc:
        logger.error(f"VRAM-Health-Read fehlgeschlagen: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"VRAM-Health-Read fehlgeschlagen: {exc}",
        )

    return {
        "status": "ok",
        "budget": budget_stats,
        "telemetry": telemetry,
    }
