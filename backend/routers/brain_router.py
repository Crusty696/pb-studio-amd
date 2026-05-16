"""Brain Router (Plan Phase 4 + R-Brain-09) -- 6 Endpoints.

POST /brain/suggest             -- Top-N Cut-Vorschlaege mit brain_scores
POST /brain/feedback            -- 4-Klick-Event verarbeiten
POST /brain/learning_session    -- 15 unsicherste Cuts (Bayes-Varianz)
GET  /brain/stats               -- Diagnostik
POST /brain/reset               -- mit Confirmation
GET  /brain/explain/{cut_id}    -- UX: warum diese Confidence? (R-Brain-09)
"""

from __future__ import annotations

import json as _json
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..schemas.brain_schemas import (
    BrainAxisContribution, BrainExplainResponse,
    BrainFeedbackRequest, BrainFeedbackResponse,
    BrainLearningSessionResponse, BrainResetRequest, BrainResetResponse,
    BrainStatsBucket, BrainStatsResponse, BrainSuggestRequest,
    BrainSuggestResponse, BrainSuggestion,
)
from .._brain_singleton import get_brain_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/brain", tags=["Brain"])

_pending_reset_tokens: set[str] = set()


@router.post("/suggest", response_model=BrainSuggestResponse)
async def suggest(req: BrainSuggestRequest) -> BrainSuggestResponse:
    """Top-N cuts der aktuellen Timeline mit brain_scores."""
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
    for r in rows:
        scores = _json.loads(r[4]) if r[4] else {}
        final = sum(scores.values()) / len(scores) if scores else 0.0
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

    metadata = _json.loads(row[1]) if row[1] else {}
    context_keys = metadata.get("context_keys")
    if not context_keys or not isinstance(context_keys, list):
        logger.warning(
            "Cut %d hat keine context_keys in metadata; Feedback wird nur in Level-0 "
            "gebucht. Pacing muss zuerst mit use_brain=true laufen fuer vollen 5-Level "
            "Backoff.", req.cut_id
        )
        context_keys = [""]

    # Z2 / GPU-F4: log_feedback macht SQLite-INSERT + WeightStore-Math (~10-50ms).
    # asyncio.to_thread haelt den Event-Loop frei fuer parallele SSE-Streams.
    import asyncio as _aio
    bumps = await _aio.to_thread(
        svc.feedback_logger.log_feedback,
        cut_id=req.cut_id,
        rating=req.rating,
        context_keys=context_keys,
    )
    total = await _aio.to_thread(svc.weights.total_clicks)
    return BrainFeedbackResponse(
        status="ok",
        updated_buckets=bumps,
        total_clicks=total,
    )


@router.post("/learning_session", response_model=BrainLearningSessionResponse)
async def learning_session() -> BrainLearningSessionResponse:
    """Top-15 Cuts ranked by Bayes variance (R-Brain-06 stratified)."""
    svc = get_brain_service()
    if svc.state_conn is None:
        raise HTTPException(status_code=409, detail="No project bound")

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

    # Z2 / GPU-F4: select_uncertain ist CPU-heavy (Bayes-Variance pro Cut).
    import asyncio as _aio
    selected = await _aio.to_thread(svc.sampler.select_uncertain, cuts_for_samp, n=15)
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

    def _bucket(r) -> BrainStatsBucket:
        # Beta-Bernoulli mit Laplace-Prior (alpha0=beta0=1).
        a = float(r[3]) + 1.0
        b = float(r[4]) + 1.0
        n = a + b
        posterior = a / n
        # Var(Beta(a,b)) = a*b / ((a+b)^2 * (a+b+1)).
        variance = (a * b) / (n * n * (n + 1.0))
        return BrainStatsBucket(
            axis=r[0],
            context_level=int(r[1]),
            context_key=r[2],
            positive_count=float(r[3]),
            negative_count=float(r[4]),
            posterior=posterior,
            posterior_variance=variance,
        )

    rows = svc.brain.weights_conn.execute(
        "SELECT axis, context_level, context_key, positive_count, "
        "negative_count FROM axis_weights "
        "ORDER BY (positive_count - negative_count) DESC LIMIT 5"
    ).fetchall()
    top_pos = [_bucket(r) for r in rows]

    rows = svc.brain.weights_conn.execute(
        "SELECT axis, context_level, context_key, positive_count, "
        "negative_count FROM axis_weights "
        "ORDER BY (negative_count - positive_count) DESC LIMIT 5"
    ).fetchall()
    top_neg = [_bucket(r) for r in rows]

    from pb_studio.brain.bridge_dimensions import BRIDGE_AXES
    learned = set()
    for r in svc.brain.weights_conn.execute(
        "SELECT DISTINCT axis FROM axis_weights "
        "WHERE positive_count + negative_count >= 10"
    ).fetchall():
        learned.add(r[0])
    cold_list = [a for a in BRIDGE_AXES if a not in learned]

    return BrainStatsResponse(
        total_clicks=svc.weights.total_clicks(),
        cold_start_axes=len(cold_list),
        learned_axes=len(learned),
        top_positive=top_pos,
        top_negative=top_neg,
        cold_start_axes_list=cold_list,
    )


@router.post("/reset", response_model=BrainResetResponse)
async def reset(req: Optional[BrainResetRequest] = None) -> BrainResetResponse:
    """Two-step confirmation reset: 1st call returns token, 2nd resets."""
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


# ---------- R-Brain-09: /brain/explain/{cut_id} ----------

@router.get("/explain/{cut_id}", response_model=BrainExplainResponse)
async def explain(
    cut_id: int,
    top_n: int = 3,
    narrative: bool = True,
    mode: str = "balance",
) -> BrainExplainResponse:
    """Erklaert die Confidence eines Cuts: Top-/Bottom-N contributing axes
    mit ihrer (bridge_value, posterior, score)-Aufschluesselung.

    Wenn ``narrative=true`` (Default), wird zusaetzlich eine natuerlich-
    sprachliche Erklaerung via Ollama-LLM erzeugt. Bei Ollama-Fehler oder
    fehlendem Modell bleibt ``narrative`` im Response auf ``None`` und die
    strukturierten Felder werden trotzdem geliefert (Iron Rule 10).

    UX: Tooltip beim Hover ueber den Confidence-Balken in der Timeline.
    """
    if top_n < 1 or top_n > 17:
        raise HTTPException(status_code=400, detail="top_n must be 1..17")

    svc = get_brain_service()
    if svc.state_conn is None:
        raise HTTPException(status_code=409, detail="No project bound")

    row = svc.state_conn.execute(
        "SELECT id, clip_id, start_time, end_time, segment_type, "
        "brain_scores_json, metadata_json "
        "FROM timeline_cuts WHERE id = ?",
        (int(cut_id),),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Cut {cut_id} not found")

    scores: dict[str, float] = _json.loads(row[5]) if row[5] else {}
    metadata: dict = _json.loads(row[6]) if row[6] else {}
    context_keys: list[str] = metadata.get("context_keys") or [""]

    # Pro Achse: posterior aus weight_store rekonstruieren.
    # score (gespeichert) = bridge_value * posterior, daher
    # bridge_value = score / posterior (mit safe-divide).
    contributions: list[BrainAxisContribution] = []
    cold_start: list[str] = []

    for axis, score in scores.items():
        posterior = float(svc.weights.get_posterior_mean(axis, context_keys))
        # rekonstruiere bridge_value
        if posterior > 1e-9:
            bridge_value = max(0.0, min(1.0, float(score) / posterior))
        else:
            bridge_value = 0.0
        n_samples = _n_samples_at_most_specific(svc, axis, context_keys)
        if n_samples < 10:
            cold_start.append(axis)
        contributions.append(BrainAxisContribution(
            axis=axis,
            bridge_value=round(bridge_value, 6),
            posterior=round(posterior, 6),
            score=round(max(0.0, min(1.0, float(score))), 6),
            n_samples=n_samples,
        ))

    contributions.sort(key=lambda c: c.score, reverse=True)
    top_axes = contributions[:top_n]
    bottom_axes = contributions[-top_n:][::-1] if len(contributions) >= top_n else []

    final_score = (
        sum(scores.values()) / len(scores) if scores else 0.0
    )

    # ---- LLM-Narrator (optional) ----
    narrative_text: Optional[str] = None
    if narrative:
        try:
            from pb_studio.brain.llm_narrator import generate_explanation
        except Exception as exc:  # pragma: no cover - defensive Import-Guard
            logger.warning("LLM-Narrator import fehlgeschlagen: %s", exc)
            generate_explanation = None  # type: ignore[assignment]

        if generate_explanation is not None:
            try:
                narrative_text = await generate_explanation(
                    cut_id=int(row[0]),
                    segment_type=str(row[4]) if row[4] else None,
                    top_axes=[a.model_dump() for a in top_axes],
                    bottom_axes=[a.model_dump() for a in bottom_axes],
                    cold_start_axes=cold_start,
                    final_score=float(final_score),
                    mode=mode,
                )
            except Exception as exc:
                # Iron Rule 10: kein silent OK -- Log-Warnung + None
                logger.warning(
                    "LLM-Narrator: unerwarteter Fehler fuer cut %s: %s",
                    cut_id,
                    exc,
                )
                narrative_text = None

    return BrainExplainResponse(
        cut_id=int(row[0]),
        clip_id=str(row[1]),
        start_time=float(row[2]),
        end_time=float(row[3]),
        segment_type=str(row[4]) if row[4] else None,
        final_score=round(float(final_score), 6),
        context_keys=context_keys,
        top_axes=top_axes,
        bottom_axes=bottom_axes,
        cold_start_axes=cold_start,
        narrative=narrative_text,
    )


def _n_samples_at_most_specific(svc, axis: str, context_keys: list[str]) -> int:
    """Wie viele Klicks sind in den spezifischsten verfuegbaren Bucket fuer
    (axis, context) geflossen? Spiegelt WeightStore.get_posterior_mean Backoff.
    """
    for level in range(len(context_keys) - 1, -1, -1):
        row = svc.weights.get_alpha_beta(axis, level, context_keys[level])
        if row is None:
            continue
        alpha, beta = row
        return int(round(alpha + beta))
    return 0
