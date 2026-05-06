"""Brain Router (Plan Phase 4) — 5 Endpoints.

POST /brain/suggest             — Top-N Cut-Vorschläge mit brain_scores
POST /brain/feedback            — 4-Klick-Event verarbeiten
POST /brain/learning_session    — 15 unsicherste Cuts (Bayes-Varianz)
GET  /brain/stats               — Diagnostik
POST /brain/reset               — mit Confirmation
"""

from __future__ import annotations

import logging
import secrets
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..schemas.brain_schemas import (
    BrainFeedbackRequest, BrainFeedbackResponse,
    BrainLearningSessionResponse, BrainResetRequest, BrainResetResponse,
    BrainStatsBucket, BrainStatsResponse, BrainSuggestRequest,
    BrainSuggestResponse, BrainSuggestion,
)
from .._brain_singleton import get_brain_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/brain", tags=["Brain"])

# In-memory reset confirmation tokens (1-step TTL).
_pending_reset_tokens: set[str] = set()


@router.post("/suggest", response_model=BrainSuggestResponse)
async def suggest(req: BrainSuggestRequest) -> BrainSuggestResponse:
    """Sub-set of /pacing/generate — Brain-Reranker only.

    Currently returns the cuts of the latest timeline filtered to the
    requested clip ids. Full pacing-engine integration läuft über
    /pacing/generate?use_brain=true (Plan Phase 4 Verifikation).
    """
    svc = get_brain_service()
    if svc.state_conn is None:
        raise HTTPException(status_code=409, detail="No project bound")

    rows = svc.state_conn.execute(
        "SELECT id, clip_id, start_time, end_time, brain_scores_json "
        "FROM timeline_cuts WHERE timeline_id IN "
        "(SELECT id FROM timelines WHERE is_current=1) "
        "ORDER BY position_idx LIMIT ?",
        (int(req.top_n),),
    ).fetchall()

    out: list[BrainSuggestion] = []
    import json as _json
    for r in rows:
        scores = _json.loads(r[4]) if r[4] else {}
        final = (
            sum(scores.values()) / len(scores)
            if scores else 0.0
        )
        out.append(BrainSuggestion(
            cut_id=int(r[0]),
            clip_id=str(r[1]),
            start_time=float(r[2]),
            end_time=float(r[3]),
            final_score=float(final),
            brain_scores=scores,
        ))
    return BrainSuggestResponse(suggestions=out)


@router.post("/feedback", response_model=BrainFeedbackResponse)
async def feedback(req: BrainFeedbackRequest) -> BrainFeedbackResponse:
    svc = get_brain_service()
    if svc.state_conn is None:
        raise HTTPException(status_code=409, detail="No project bound")

    row = svc.state_conn.execute(
        "SELECT brain_scores_json, metadata_json FROM timeline_cuts WHERE id = ?",
        (int(req.cut_id),),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Cut {req.cut_id} not found")

    import json as _json
    metadata = _json.loads(row[1]) if row[1] else {}
    context_keys = metadata.get("context_keys")
    if not context_keys or not isinstance(context_keys, list):
        # Cold-start: fall back to global-only key
        context_keys = [""]

    bumps = svc.feedback_logger.log_feedback(
        cut_id=req.cut_id,
        rating=req.rating,
        context_keys=context_keys,
    )
    return BrainFeedbackResponse(
        status="ok",
        updated_buckets=bumps,
        total_clicks=svc.weights.total_clicks(),
    )


@router.post("/learning_session", response_model=BrainLearningSessionResponse)
async def learning_session() -> BrainLearningSessionResponse:
    """Returns top-15 cuts ranked by Bayes variance."""
    svc = get_brain_service()
    if svc.state_conn is None:
        raise HTTPException(status_code=409, detail="No project bound")

    import json as _json
    from pb_studio.brain.smart_sampler import CutForSampling

    rows = svc.state_conn.execute(
        "SELECT id, clip_id, start_time, end_time, brain_scores_json, "
        "metadata_json FROM timeline_cuts WHERE timeline_id IN "
        "(SELECT id FROM timelines WHERE is_current=1)"
    ).fetchall()
    if not rows:
        return BrainLearningSessionResponse(cuts=[])

    cuts_for_samp: list[CutForSampling] = []
    by_id: dict[int, tuple] = {}
    for r in rows:
        meta = _json.loads(r[5]) if r[5] else {}
        ck = meta.get("context_keys") or [""]
        cuts_for_samp.append(CutForSampling(cut_id=int(r[0]), context_keys=ck))
        by_id[int(r[0])] = r

    selected = svc.sampler.select_uncertain(cuts_for_samp, n=15)
    out: list[BrainSuggestion] = []
    for s in selected:
        r = by_id[s.cut_id]
        scores = _json.loads(r[4]) if r[4] else {}
        final = sum(scores.values()) / len(scores) if scores else 0.0
        out.append(BrainSuggestion(
            cut_id=s.cut_id, clip_id=str(r[1]),
            start_time=float(r[2]), end_time=float(r[3]),
            final_score=float(final), brain_scores=scores,
        ))
    return BrainLearningSessionResponse(cuts=out)


@router.get("/stats", response_model=BrainStatsResponse)
async def stats() -> BrainStatsResponse:
    svc = get_brain_service()

    rows = svc.brain.weights_conn.execute(
        "SELECT axis, context_level, context_key, positive_count, "
        "negative_count FROM axis_weights "
        "ORDER BY (positive_count - negative_count) DESC LIMIT 5"
    ).fetchall()
    top_pos = [
        BrainStatsBucket(
            axis=r[0], context_level=int(r[1]), context_key=r[2],
            positive_count=float(r[3]), negative_count=float(r[4]),
            posterior=(float(r[3]) + 1) / (float(r[3]) + float(r[4]) + 2),
        )
        for r in rows
    ]

    rows = svc.brain.weights_conn.execute(
        "SELECT axis, context_level, context_key, positive_count, "
        "negative_count FROM axis_weights "
        "ORDER BY (negative_count - positive_count) DESC LIMIT 5"
    ).fetchall()
    top_neg = [
        BrainStatsBucket(
            axis=r[0], context_level=int(r[1]), context_key=r[2],
            positive_count=float(r[3]), negative_count=float(r[4]),
            posterior=(float(r[3]) + 1) / (float(r[3]) + float(r[4]) + 2),
        )
        for r in rows
    ]

    from pb_studio.brain.bridge_dimensions import BRIDGE_AXES
    learned = set()
    for r in svc.brain.weights_conn.execute(
        "SELECT DISTINCT axis FROM axis_weights "
        "WHERE positive_count + negative_count >= 10"
    ).fetchall():
        learned.add(r[0])
    cold = len([a for a in BRIDGE_AXES if a not in learned])

    return BrainStatsResponse(
        total_clicks=svc.weights.total_clicks(),
        cold_start_axes=cold,
        learned_axes=len(learned),
        top_positive=top_pos,
        top_negative=top_neg,
    )


@router.post("/reset", response_model=BrainResetResponse)
async def reset(req: Optional[BrainResetRequest] = None) -> BrainResetResponse:
    """Two-step confirmation reset: 1st call returns token, 2nd call with token resets."""
    svc = get_brain_service()
    if req is None or req.confirmation_token is None:
        token = secrets.token_urlsafe(16)
        _pending_reset_tokens.add(token)
        return BrainResetResponse(status="pending_confirmation",
                                  confirmation_token=token)

    if req.confirmation_token not in _pending_reset_tokens:
        raise HTTPException(status_code=400, detail="invalid or expired token")

    _pending_reset_tokens.discard(req.confirmation_token)
    svc.weights.reset()
    return BrainResetResponse(status="reset_complete")
