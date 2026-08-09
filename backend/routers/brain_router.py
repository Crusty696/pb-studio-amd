"""Brain Router (Plan Phase 4 + R-Brain-09) -- 6 Endpoints.

POST /brain/suggest             -- Top-N Cut-Vorschlaege mit brain_scores
POST /brain/feedback            -- 4-Klick-Event verarbeiten
POST /brain/learning_session    -- 15 unsicherste Cuts (Bayes-Varianz)
GET  /brain/stats               -- Diagnostik
POST /brain/reset               -- mit Confirmation
GET  /brain/explain/{cut_id}    -- UX: warum diese Confidence? (R-Brain-09)
"""

from __future__ import annotations

import asyncio
import hmac
import json as _json
import logging
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from ..app_state import (
    AppState,
    ProjectContextChangedError,
    ProjectContextUnavailableError,
    ProjectOperationContext,
    get_app_state,
)
from ..owner_capability import OWNER_CAPABILITY_HEADER, authorize_owner
from ..schemas.brain_schemas import (
    BrainAxisContribution, BrainExplainResponse,
    BrainFeedbackRequest, BrainFeedbackResponse,
    BrainLearningSessionResponse, BrainResetRequest, BrainResetResponse,
    BrainStatsBucket, BrainStatsResponse, BrainSuggestRequest,
    BrainSuggestResponse, BrainSuggestion,
)
from .._brain_singleton import get_brain_service
from pb_studio.brain.brain_service import (
    BrainProjectNotBoundError,
    StaleBrainProjectLeaseError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/brain", tags=["Brain"])

_pending_reset_tokens: dict[str, tuple[float, str]] = {}


def _acquire_project_state_lease(
    svc,
    context: ProjectOperationContext | None = None,
):
    try:
        if context is None:
            return svc.project_state_lease()
        return svc.project_state_lease(
            state_db_path=context.project_root / "state.db",
            project_epoch=context.epoch,
            project_id=context.project_id,
        )
    except BrainProjectNotBoundError as exc:
        raise HTTPException(status_code=409, detail="No project bound") from exc
    except StaleBrainProjectLeaseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _authorize_reset_owner(owner_capability: str | None) -> str:
    return authorize_owner(owner_capability, operation="Brain-Reset")


@router.post("/suggest", response_model=BrainSuggestResponse)
async def suggest(
    req: BrainSuggestRequest,
    state: AppState = Depends(get_app_state),
) -> BrainSuggestResponse:
    """Top-N cuts der aktuellen Timeline mit brain_scores."""
    svc = get_brain_service()
    try:
        async with state.project_operation() as context:
            lease = _acquire_project_state_lease(svc, context)
            try:
                # Video-IDs in "clip_X"-Format wandeln fuer DB-Match
                allowed_clips = (
                    {f"clip_{vid}" for vid in req.video_clip_ids}
                    if req.video_clip_ids else None
                )

                # Alle Cuts der aktuellen Timeline laden, filtern nach Audio-ID
                # und current=1.
                rows = await asyncio.to_thread(
                    lambda: lease.connection.execute(
                        "SELECT id, clip_id, start_time, end_time, "
                        "brain_scores_json, metadata_json FROM timeline_cuts "
                        "WHERE timeline_id IN (SELECT id FROM timelines "
                        "WHERE is_current=1 AND audio_clip_id=?)",
                        (int(req.audio_clip_id),),
                    ).fetchall()
                )

                out: list[BrainSuggestion] = []
                for r in rows:
                    clip_id_str = str(r[1])
                    if allowed_clips and clip_id_str not in allowed_clips:
                        continue

                    scores = _json.loads(r[4]) if r[4] else {}
                    meta = _json.loads(r[5]) if r[5] else {}

                    # Nutze gespeicherten final_score oder berechne Durchschnitt
                    final = meta.get("brain_final_score")
                    if final is None:
                        final = (
                            sum(scores.values()) / len(scores)
                            if scores else 0.0
                        )

                    out.append(BrainSuggestion(
                        cut_id=int(r[0]),
                        clip_id=clip_id_str,
                        start_time=float(r[2]),
                        end_time=float(r[3]),
                        final_score=float(final),
                        brain_scores=scores,
                    ))

                # In Python nach echtem Score absteigend sortieren und limitieren
                out.sort(key=lambda s: s.final_score, reverse=True)
                state.require_project_context_current(context)
                return BrainSuggestResponse(
                    suggestions=out[:int(req.top_n)]
                )
            finally:
                lease.release()
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/feedback", response_model=BrainFeedbackResponse)
async def feedback(
    req: BrainFeedbackRequest,
    state: AppState = Depends(get_app_state),
) -> BrainFeedbackResponse:
    svc = get_brain_service()
    try:
        async with state.project_operation() as context:
            lease = _acquire_project_state_lease(svc, context)
            try:
                feedback_logger = svc.feedback_logger_for_lease(lease)
                from pb_studio.brain.feedback_logger import (
                    FeedbackOperationConflictError,
                    build_credit_assignments,
                )
                from ..dependencies import db_write_lock

                if req.operation_id is not None:
                    async with db_write_lock:
                        try:
                            prior_result = await asyncio.to_thread(
                                lease.run_write,
                                lambda _connection: (
                                    feedback_logger.lookup_feedback_result(
                                        operation_id=req.operation_id,
                                        cut_id=req.cut_id,
                                        rating=req.rating,
                                    )
                                ),
                            )
                        except StaleBrainProjectLeaseError as exc:
                            raise HTTPException(
                                status_code=409,
                                detail=str(exc),
                            ) from exc
                        except FeedbackOperationConflictError as exc:
                            raise HTTPException(
                                status_code=409,
                                detail=str(exc),
                            ) from exc
                    if prior_result is not None:
                        total = await asyncio.to_thread(svc.weights.total_clicks)
                        return BrainFeedbackResponse(
                            status="ok",
                            updated_buckets=prior_result.updated_buckets,
                            total_clicks=total,
                            message="Feedback operation was already applied",
                        )

                row = await asyncio.to_thread(
                    lambda: lease.connection.execute(
                        "SELECT brain_scores_json, metadata_json "
                        "FROM timeline_cuts WHERE id = ?",
                        (int(req.cut_id),),
                    ).fetchone()
                )
                if row is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Cut {req.cut_id} not found",
                    )

                metadata = _json.loads(row[1]) if row[1] else {}
                brain_scores = _json.loads(row[0]) if row[0] else {}
                context_keys = metadata.get("context_keys")
                if not context_keys or not isinstance(context_keys, list):
                    logger.warning(
                        "Cut %d hat keine context_keys in metadata; Feedback wird "
                        "nur in Level-0 gebucht. Pacing muss zuerst mit use_brain=true "
                        "laufen fuer vollen 5-Level Backoff.",
                        req.cut_id,
                    )
                    context_keys = [""]

                assignments = build_credit_assignments(
                    metadata=metadata,
                    brain_scores=brain_scores,
                    context_keys=context_keys,
                )

                def _apply_feedback(_connection):
                    return feedback_logger.log_feedback_result(
                        cut_id=req.cut_id,
                        rating=req.rating,
                        context_keys=context_keys,
                        assignments=assignments,
                        operation_id=req.operation_id,
                    )

                # Z2 / GPU-F4: log_feedback macht SQLite-INSERT + WeightStore-Math
                # (~10-50ms). db_write_lock bleibt der globale Vertrag; der
                # Lease-Guard linearisiert zusaetzlich gegen Projektwechsel.
                async with db_write_lock:
                    try:
                        feedback_result = await asyncio.to_thread(
                            lease.run_write,
                            _apply_feedback,
                        )
                    except StaleBrainProjectLeaseError as exc:
                        raise HTTPException(
                            status_code=409,
                            detail=str(exc),
                        ) from exc
                    except FeedbackOperationConflictError as exc:
                        raise HTTPException(
                            status_code=409,
                            detail=str(exc),
                        ) from exc
                    except ValueError as exc:
                        raise HTTPException(
                            status_code=409,
                            detail=str(exc),
                        ) from exc
                bumps = feedback_result.updated_buckets
                total = await asyncio.to_thread(svc.weights.total_clicks)
                if feedback_result.applied:
                    await _maybe_train_projector(svc, total)
                message = (
                    f"{bumps} evidence-relevant buckets updated"
                    if feedback_result.applied
                    else "Feedback operation was already applied"
                )
                return BrainFeedbackResponse(
                    status="ok",
                    updated_buckets=bumps,
                    total_clicks=total,
                    message=message,
                )
            finally:
                lease.release()
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/learning_session", response_model=BrainLearningSessionResponse)
async def learning_session(
    state: AppState = Depends(get_app_state),
) -> BrainLearningSessionResponse:
    """Top-15 Cuts ranked by Bayes variance (R-Brain-06 stratified)."""
    svc = get_brain_service()

    from pb_studio.brain.smart_sampler import CutForSampling

    try:
        async with state.project_operation() as context:
            lease = _acquire_project_state_lease(svc, context)
            try:
                rows = await asyncio.to_thread(
                    lambda: lease.connection.execute(
                        "SELECT id, clip_id, start_time, end_time, "
                        "brain_scores_json, metadata_json FROM timeline_cuts "
                        "WHERE timeline_id IN "
                        "(SELECT id FROM timelines WHERE is_current=1)"
                    ).fetchall()
                )
                if not rows:
                    state.require_project_context_current(context)
                    return BrainLearningSessionResponse(cuts=[])

                cuts_for_samp: list[CutForSampling] = []
                by_id: dict[int, tuple] = {}
                for r in rows:
                    meta = _json.loads(r[5]) if r[5] else {}
                    ck = meta.get("context_keys") or [""]
                    cuts_for_samp.append(CutForSampling(
                        cut_id=int(r[0]),
                        context_keys=ck,
                    ))
                    by_id[int(r[0])] = r

                # Z2 / GPU-F4: select_uncertain ist CPU-heavy
                # (Bayes-Variance pro Cut).
                selected = await asyncio.to_thread(
                    svc.sampler.select_uncertain,
                    cuts_for_samp,
                    n=15,
                )
                out: list[BrainSuggestion] = []
                for s in selected:
                    r = by_id[s.cut_id]
                    scores = _json.loads(r[4]) if r[4] else {}
                    final = (
                        sum(scores.values()) / len(scores)
                        if scores else 0.0
                    )
                    out.append(BrainSuggestion(
                        cut_id=s.cut_id,
                        clip_id=str(r[1]),
                        start_time=float(r[2]),
                        end_time=float(r[3]),
                        final_score=float(final),
                        brain_scores=scores,
                    ))
                state.require_project_context_current(context)
                return BrainLearningSessionResponse(cuts=out)
            finally:
                lease.release()
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# Audit 2026-08-06 (T3.5): `projector_trainer.run_fit_step` und
# `collect_training_pairs` hatten repo-weit KEINEN Aufrufer ausserhalb der
# eigenen Datei und der Tests. Der CrossModalProjector blieb dadurch dauerhaft
# auf den zufaelligen Johnson-Lindenstrauss-Matrizen aus `_init_random_matrices`
# — die komplette R-Brain-05-Architektur (Rating -> Label -> fit_pairs) war rein
# hypothetisch. Hier ist der fehlende Producer: alle N erfolgreichen Feedbacks
# ein Fit-Schritt.


def _fit_projector_v2(svc) -> dict:
    from pb_studio.brain.cross_modal_projector import (
        WEIGHTS_FILENAME,
        get_default_projector,
    )
    from pb_studio.brain.projector_trainer import (
        ProjectTrainingSource,
        run_v2_fit_step,
    )
    from pb_studio.data.repositories.project_repository import ProjectRepository
    from pb_studio.storage.migration_runner import migrate_project_state

    repo = ProjectRepository()
    catalog_conn = repo.db.get_connection()
    migrations = (
        Path(__file__).resolve().parents[2]
        / "src" / "pb_studio" / "storage" / "migrations" / "state"
    )
    sources: list[ProjectTrainingSource] = []
    opened: list[sqlite3.Connection] = []
    try:
        for project in repo.get_all():
            data = project.get("data") or {}
            project_uuid = project.get("project_uuid") or data.get("project_uuid")
            if not project_uuid:
                raise RuntimeError(f"Project {project['id']} lacks project_uuid")
            media_rows = catalog_conn.execute(
                "SELECT id, file_hash FROM media WHERE project_id=?",
                (int(project["id"]),),
            ).fetchall()
            hashes = {int(row[0]): str(row[1] or "") for row in media_rows}
            project_path = data.get("path")
            if not project_path:
                if media_rows:
                    raise RuntimeError(f"Pathless project {project['id']} owns media")
                sources.append(ProjectTrainingSource(
                    project_uuid=str(project_uuid),
                    state_conn=None,
                    audio_hash_for_clip_id=lambda _clip_id: None,
                    video_hash_for_clip_id=lambda _clip_id: None,
                    status="pathless_empty",
                ))
                continue
            state_path = Path(str(project_path)) / "state.db"
            if not state_path.is_file():
                raise RuntimeError(f"Project {project['id']} state.db is missing")
            migrate_project_state(
                state_path,
                migrations,
                project_uuid=str(project_uuid),
            )
            conn = sqlite3.connect(
                str(state_path), isolation_level=None, check_same_thread=False
            )
            opened.append(conn)

            def _audio_hash(clip_id: int, values=hashes):
                return values.get(int(clip_id)) or None

            def _video_hash(clip_id: str, values=hashes):
                raw = str(clip_id)
                if raw.startswith("clip_"):
                    raw = raw[len("clip_"):]
                try:
                    return values.get(int(raw)) or None
                except (TypeError, ValueError):
                    return None

            sources.append(ProjectTrainingSource(
                project_uuid=str(project_uuid),
                state_conn=conn,
                audio_hash_for_clip_id=_audio_hash,
                video_hash_for_clip_id=_video_hash,
            ))

        weights_path = svc.brain.brain_dir / WEIGHTS_FILENAME
        return run_v2_fit_step(
            get_default_projector(weights_path=weights_path),
            sources=sources,
            embedding_cache=svc.brain.cache,
        )
    finally:
        for conn in opened:
            conn.close()


async def _maybe_train_projector(svc, total_clicks: int) -> None:
    """
    Trainiert den Cross-Modal-Projektor periodisch aus echtem Feedback.

    Best-effort und bewusst nach dem Response-relevanten Teil: ein Fehler hier
    darf ein erfolgreich verbuchtes Feedback niemals zu einem Fehler machen.
    """
    if total_clicks <= 0:
        return

    try:
        result = await asyncio.to_thread(_fit_projector_v2, svc)
        logger.info(
            "Cross-Modal-Projektor nach %d Feedbacks trainiert: %s",
            total_clicks,
            result,
        )
    except Exception as exc:  # noqa: BLE001 - Feedback bleibt gueltig
        logger.warning(
            "Projektor-Training uebersprungen (%s): %r",
            type(exc).__name__,
            exc,
        )


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

    def _read_stats():
        with svc.brain._weights_lock:
            rows = svc.brain.weights_conn.execute(
                "SELECT axis, context_level, context_key, positive_count, "
                "negative_count FROM axis_weights "
                "ORDER BY (positive_count - negative_count) DESC LIMIT 5"
            ).fetchall()
            positive = [_bucket(r) for r in rows]

            rows = svc.brain.weights_conn.execute(
                "SELECT axis, context_level, context_key, positive_count, "
                "negative_count FROM axis_weights "
                "ORDER BY (negative_count - positive_count) DESC LIMIT 5"
            ).fetchall()
            negative = [_bucket(r) for r in rows]

            learned_axes = {
                r[0]
                for r in svc.brain.weights_conn.execute(
                    "SELECT DISTINCT axis FROM axis_weights "
                    "WHERE positive_count + negative_count >= 10"
                ).fetchall()
            }
            # Audit 2026-08-06 (T4.4): Herkunftsangaben mitlesen. Ohne sie
            # sieht der User bei archivierter Historie exakt dasselbe wie bei
            # "noch nie bewertet" — naemlich 0 Klicks.
            meta: dict[str, str] = {}
            try:
                meta = {
                    str(k): str(v)
                    for k, v in svc.brain.weights_conn.execute(
                        "SELECT key, value FROM brain_meta"
                    ).fetchall()
                }
            except sqlite3.Error:
                meta = {}

            archived = 0
            archive_table = meta.get("legacy_archive_table")
            if archive_table:
                try:
                    row = svc.brain.weights_conn.execute(
                        "SELECT COALESCE(SUM(positive_count + negative_count), 0) "
                        f"FROM {archive_table}"  # noqa: S608 - Name aus brain_meta
                    ).fetchone()
                    archived = int(float(row[0])) if row else 0
                except sqlite3.Error:
                    archived = 0

        return (
            positive,
            negative,
            learned_axes,
            svc.weights.total_clicks(),
            meta,
            archived,
        )

    (
        top_pos,
        top_neg,
        learned,
        total_clicks,
        meta,
        archived,
    ) = await asyncio.to_thread(_read_stats)

    from pb_studio.brain.bridge_dimensions import BRIDGE_AXES
    cold_list = [a for a in BRIDGE_AXES if a not in learned]

    return BrainStatsResponse(
        total_clicks=total_clicks,
        cold_start_axes=len(cold_list),
        learned_axes=len(learned),
        top_positive=top_pos,
        top_negative=top_neg,
        cold_start_axes_list=cold_list,
        weight_semantics_version=meta.get("weight_semantics_version"),
        archived_observations=archived,
        migration_reason=meta.get("migration_reason"),
    )


@router.post(
    "/reset",
    response_model=BrainResetResponse,
    responses={
        403: {"description": "Owner-Capability oder Token-Owner ungueltig."},
        503: {"description": "Backend wurde ohne Owner-Capability gestartet."},
    },
    openapi_extra={
        "parameters": [
            {
                "name": OWNER_CAPABILITY_HEADER,
                "in": "header",
                "required": True,
                "schema": {"type": "string"},
                "description": (
                    "Runtime-required launcher capability; confirmation "
                    "tokens are bound to this owner."
                ),
            }
        ]
    },
)
async def reset(
    req: Optional[BrainResetRequest] = None,
    owner_capability: str | None = Header(
        default=None,
        alias=OWNER_CAPABILITY_HEADER,
        include_in_schema=False,
    ),
) -> BrainResetResponse:
    """Owner-bound two-step reset with an expiring, single-use token."""
    owner_id = _authorize_reset_owner(owner_capability)
    now = time.time()
    # Clean expired tokens
    expired = [
        token
        for token, (expires_at, _) in _pending_reset_tokens.items()
        if expires_at < now
    ]
    for t in expired:
        _pending_reset_tokens.pop(t, None)

    svc = get_brain_service()
    if req is None or req.confirmation_token is None:
        token = secrets.token_urlsafe(16)
        _pending_reset_tokens[token] = (now + 300.0, owner_id)
        return BrainResetResponse(status="pending_confirmation",
                                  confirmation_token=token)

    pending = _pending_reset_tokens.get(req.confirmation_token)
    if pending is None:
        raise HTTPException(status_code=400, detail="invalid or expired token")
    _, token_owner_id = pending
    if not hmac.compare_digest(token_owner_id, owner_id):
        raise HTTPException(status_code=403, detail="reset token owner mismatch")

    _pending_reset_tokens.pop(req.confirmation_token, None)
    from ..dependencies import db_write_lock
    import asyncio as _aio
    async with db_write_lock:
        await _aio.to_thread(svc.weights.reset)
    return BrainResetResponse(status="reset_complete")


# ---------- R-Brain-09: /brain/explain/{cut_id} ----------

@router.get("/explain/{cut_id}", response_model=BrainExplainResponse)
async def explain(
    cut_id: int,
    top_n: int = 3,
    narrative: bool = True,
    mode: str = "balance",
    state: AppState = Depends(get_app_state),
) -> BrainExplainResponse:
    """Erklaert die Confidence eines Cuts: Top-/Bottom-N contributing axes
    mit ihrer (bridge_value, posterior, score)-Aufschluesselung.

    Wenn ``narrative=true`` (Default), wird zusaetzlich eine natuerlich-
    sprachliche Erklaerung via LM-Studio-LLM erzeugt. Bei LM-Studio-Fehler
    oder fehlendem Modell bleibt ``narrative`` im Response auf ``None``
    und die strukturierten Felder werden trotzdem geliefert (Iron Rule 10).

    UX: Tooltip beim Hover ueber den Confidence-Balken in der Timeline.
    """
    if top_n < 1 or top_n > 17:
        raise HTTPException(status_code=400, detail="top_n must be 1..17")

    svc = get_brain_service()
    try:
        async with state.project_operation() as context:
            lease = _acquire_project_state_lease(svc, context)
            try:
                row = await asyncio.to_thread(
                    lambda: lease.connection.execute(
                        "SELECT id, clip_id, start_time, end_time, "
                        "segment_type, brain_scores_json, metadata_json "
                        "FROM timeline_cuts WHERE id = ?",
                        (int(cut_id),),
                    ).fetchone()
                )
                if row is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Cut {cut_id} not found",
                    )

                scores: dict[str, float] = (
                    _json.loads(row[5]) if row[5] else {}
                )
                metadata: dict = _json.loads(row[6]) if row[6] else {}
                context_keys: list[str] = (
                    metadata.get("context_keys") or [""]
                )

                # Pro Achse: posterior aus weight_store lesen.
                # Nutzt gespeicherte bridge_values aus den Metadaten, um
                # mathematischen Drift durch spaetere Klicks zu verhindern.
                raw_bridge_values = metadata.get("bridge_values") or {}

                def _read_contributions():
                    contributions: list[BrainAxisContribution] = []
                    cold_axes: list[str] = []
                    for axis, score in scores.items():
                        posterior = float(
                            svc.weights.get_posterior_mean(
                                axis,
                                context_keys,
                            )
                        )

                        if raw_bridge_values:
                            bridge_value = float(
                                raw_bridge_values.get(axis, 0.0)
                            )
                            current_score = bridge_value * posterior
                        else:
                            if posterior > 1e-9:
                                bridge_value = max(
                                    0.0,
                                    min(1.0, float(score) / posterior),
                                )
                            else:
                                bridge_value = 0.0
                            current_score = score

                        n_samples = _n_samples_at_most_specific(
                            svc,
                            axis,
                            context_keys,
                        )
                        if n_samples < 10:
                            cold_axes.append(axis)

                        contributions.append(BrainAxisContribution(
                            axis=axis,
                            bridge_value=round(bridge_value, 6),
                            posterior=round(posterior, 6),
                            score=round(
                                max(
                                    0.0,
                                    min(1.0, float(current_score)),
                                ),
                                6,
                            ),
                            n_samples=n_samples,
                        ))
                    contributions.sort(
                        key=lambda contribution: contribution.score,
                        reverse=True,
                    )
                    top = contributions[:top_n]
                    bottom = (
                        contributions[-top_n:][::-1]
                        if len(contributions) >= top_n else []
                    )
                    return top, bottom, cold_axes

                top_axes, bottom_axes, cold_start = await asyncio.to_thread(
                    _read_contributions,
                )

                final_score = (
                    sum(scores.values()) / len(scores)
                    if scores else 0.0
                )

                # ---- LLM-Narrator (optional) ----
                narrative_text: Optional[str] = None
                if narrative:
                    try:
                        from pb_studio.brain.llm_narrator import (
                            generate_explanation,
                        )
                    except Exception as exc:  # pragma: no cover
                        logger.warning(
                            "LLM-Narrator import fehlgeschlagen: %s",
                            exc,
                        )
                        generate_explanation = None  # type: ignore[assignment]

                    if generate_explanation is not None:
                        try:
                            narrative_text = await generate_explanation(
                                cut_id=int(row[0]),
                                segment_type=(
                                    str(row[4]) if row[4] else None
                                ),
                                top_axes=[
                                    axis.model_dump() for axis in top_axes
                                ],
                                bottom_axes=[
                                    axis.model_dump() for axis in bottom_axes
                                ],
                                cold_start_axes=cold_start,
                                final_score=float(final_score),
                                mode=mode,
                            )
                        except Exception as exc:
                            # Iron Rule 10: kein silent OK -- Warnung + None
                            logger.warning(
                                "LLM-Narrator: unerwarteter Fehler fuer "
                                "cut %s: %s",
                                cut_id,
                                exc,
                            )
                            narrative_text = None

                state.require_project_context_current(context)
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
            finally:
                lease.release()
    except ProjectContextChangedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProjectContextUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
