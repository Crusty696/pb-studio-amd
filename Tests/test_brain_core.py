"""Tests für brain-core (Plan Phase 3)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from pb_studio.brain import (
    BRIDGE_AXES,
    BridgeDimensions,
    COLD_START_DEFAULTS,
    ContextResolver,
    CutContext,
    FeedbackLogger,
    BrainScorer,
    WeightStore,
    MIN_CONFIDENT_SAMPLES,
    RATING_MAP,
)
from pb_studio.brain.bridge_dimensions import CandidateFeatures
from pb_studio.storage.brain_store import BrainStore
from pb_studio.storage.migration_runner import migrate
from pb_studio.storage.sqlite_init import init_connection


_STATE_MIG = (
    Path(__file__).resolve().parent.parent
    / "src" / "pb_studio" / "storage" / "migrations" / "state"
)


# ----------------------- helpers -----------------------

def _state_conn(tmp_path: Path) -> sqlite3.Connection:
    p = tmp_path / "state.db"
    migrate(p, _STATE_MIG)
    conn = sqlite3.connect(str(p), isolation_level=None)
    init_connection(conn)
    # minimal cut row so feedback FK is satisfied
    conn.execute(
        "INSERT INTO timelines (id, name, audio_clip_id, created_at, is_current) "
        "VALUES (1, 'tl', 1, '2026-05-06T00:00:00Z', 1)"
    )
    conn.execute(
        "INSERT INTO timeline_cuts (id, timeline_id, position_idx, clip_id, "
        "start_time, end_time) VALUES (42, 1, 0, 'c0', 0.0, 1.0)"
    )
    return conn


# ----------------------- bridge dimensions -----------------------

def test_bridge_axes_count_is_17():
    assert len(BRIDGE_AXES) == 17


def test_bridge_compute_all_returns_all_axes():
    bd = BridgeDimensions()
    feats = CandidateFeatures(
        trigger_type="kick", trigger_strength=0.9, audio_energy=0.8,
        audio_centroid=0.5, motion_score=0.7, scene_distance_sec=0.1,
        brightness=0.6, color_temp=0.2, pace_class_score=0.7,
        cut_duration_sec=2.0,
    )
    out = bd.compute_all(feats)
    assert set(out.keys()) == set(BRIDGE_AXES)
    for v in out.values():
        assert 0.0 <= v <= 1.0


def test_bridge_kick_axis_strong_for_kick_trigger():
    bd = BridgeDimensions()
    f = CandidateFeatures(trigger_type="kick", trigger_strength=1.0)
    out = bd.compute_all(f)
    assert out["kick_weight"] == 1.0
    assert out["snare_weight"] == 0.0


def test_bridge_semantic_match_uses_cosine():
    bd = BridgeDimensions()
    e = np.ones(8, dtype=np.float32)
    f = CandidateFeatures(audio_embedding=e, video_embedding=e)
    out = bd.compute_all(f)
    assert out["semantic_match_weight"] > 0.99


# ----------------------- context resolver -----------------------

def test_context_keys_six_levels():
    ctx = CutContext()
    keys = ctx.context_keys
    assert len(keys) == 6
    assert keys[0] == ""
    assert "section=" in keys[1]
    assert "pace=" in keys[5] and "subpos=" in keys[5]


def test_context_resolver_subtrack_position():
    cr = ContextResolver()
    c = cr.resolve(
        section_type="drop", cut_time_sec=20.0,
        subtrack_start_sec=0.0, subtrack_end_sec=100.0,
        audio_energy=0.5, audio_mood_tags=["dark"],
        video_motion_score=0.7, video_pace_class_value=0.8,
    )
    assert c.section_type == "drop"
    assert c.audio_mood == "dark"
    assert c.subtrack_position == "start"  # 20/100 = 0.2 < 0.25
    assert c.video_pace_class == "fast"


# ----------------------- weight store -----------------------

def test_posterior_cold_start_default(tmp_path: Path):
    store = BrainStore(tmp_path / "brain")
    try:
        ws = WeightStore(store.weights_conn)
        for axis in BRIDGE_AXES:
            pm = ws.get_posterior_mean(axis, [""])
            assert pm == pytest.approx(COLD_START_DEFAULTS[axis])
    finally:
        store.close()


def test_posterior_uses_specific_when_confident(tmp_path: Path):
    store = BrainStore(tmp_path / "brain")
    try:
        ws = WeightStore(store.weights_conn)
        # 100 weak positives at level 0
        for _ in range(100):
            ws.update("kick_weight", 0, "", alpha_delta=1.0, beta_delta=0.0)
        # 15 strong positives at level 1 (drops)
        for _ in range(15):
            ws.update("kick_weight", 1, "section=drop",
                      alpha_delta=2.0, beta_delta=0.0)


        keys = ["", "section=drop"]
        pm = ws.get_posterior_mean("kick_weight", keys)
        # most-specific confident: alpha=30 (15 * 2.0)
        expected = (30.0 + 1) / (30.0 + 0 + 2)
        assert pm == pytest.approx(expected)
    finally:
        store.close()


def test_posterior_falls_back_when_specific_too_few(tmp_path: Path):
    store = BrainStore(tmp_path / "brain")
    try:
        ws = WeightStore(store.weights_conn)
        for _ in range(100):
            ws.update("kick_weight", 0, "", alpha_delta=1.0, beta_delta=0.0)
        # only 3 samples at level 1 (below MIN_CONFIDENT_SAMPLES)
        for _ in range(3):
            ws.update("kick_weight", 1, "section=drop",
                      alpha_delta=0.0, beta_delta=1.0)

        keys = ["", "section=drop"]
        pm = ws.get_posterior_mean("kick_weight", keys)
        expected = (100.0 + 1) / (100.0 + 0 + 2)
        assert pm == pytest.approx(expected)
    finally:
        store.close()


def test_variance_high_when_no_data(tmp_path: Path):
    store = BrainStore(tmp_path / "brain")
    try:
        ws = WeightStore(store.weights_conn)
        v = ws.get_variance("kick_weight", ["", "section=drop"])
        assert v == pytest.approx(0.25)
    finally:
        store.close()


def test_reset_clears_weights(tmp_path: Path):
    store = BrainStore(tmp_path / "brain")
    try:
        ws = WeightStore(store.weights_conn)
        ws.update("kick_weight", 0, "", alpha_delta=5.0, beta_delta=0.0)
        assert ws.get_alpha_beta("kick_weight", 0, "") == (5.0, 0.0)
        ws.reset()
        assert ws.get_alpha_beta("kick_weight", 0, "") is None
    finally:
        store.close()


# ----------------------- feedback logger -----------------------

def test_feedback_perfect_updates_85_buckets(tmp_path: Path):
    store = BrainStore(tmp_path / "brain")
    try:
        ws = WeightStore(store.weights_conn)
        state = _state_conn(tmp_path)
        try:
            fl = FeedbackLogger(weight_store=ws, state_conn=state)
            ctx = CutContext(section_type="drop", audio_mood="dark")
            n = fl.log_feedback(
                cut_id=42, rating="perfect", context_keys=ctx.context_keys
            )
            assert n == 17 * 6
            row = ws.get_alpha_beta("kick_weight", 0, "")
            assert row == (2.0, 0.0)
            row5 = ws.get_alpha_beta(
                "kick_weight", 5, ctx.context_keys[5]
            )
            assert row5 == (2.0, 0.0)

            # raw event was logged
            cnt = state.execute(
                "SELECT COUNT(*) FROM feedback_events"
            ).fetchone()[0]
            assert cnt == 1
        finally:
            state.close()
    finally:
        store.close()


def test_feedback_rating_map():
    assert RATING_MAP["perfect"] == (2.0, 0.0)
    assert RATING_MAP["fits"] == (1.0, 0.0)
    assert RATING_MAP["not_quite"] == (0.0, 1.0)
    assert RATING_MAP["no_match"] == (0.0, 2.0)


def test_feedback_invalid_rating_raises(tmp_path: Path):
    store = BrainStore(tmp_path / "brain")
    try:
        ws = WeightStore(store.weights_conn)
        state = _state_conn(tmp_path)
        try:
            fl = FeedbackLogger(weight_store=ws, state_conn=state)
            with pytest.raises(ValueError):
                fl.log_feedback(cut_id=42, rating="bogus", context_keys=[""])
        finally:
            state.close()
    finally:
        store.close()


def test_feedback_outbox_recovers_without_double_weight_update(tmp_path: Path):
    store = BrainStore(tmp_path / "brain")
    state = _state_conn(tmp_path)
    outbox = tmp_path / "brain" / "feedback_outbox.json"

    def crash_after_weight_commit(stage: str) -> None:
        if stage == "after_weights_commit":
            raise RuntimeError("simulated crash")

    try:
        ws = WeightStore(store.weights_conn)
        logger = FeedbackLogger(
            weight_store=ws,
            state_conn=state,
            outbox_path=outbox,
            fault_injector=crash_after_weight_commit,
        )
        with pytest.raises(RuntimeError, match="simulated crash"):
            logger.log_feedback(
                cut_id=42,
                rating="perfect",
                context_keys=["", "section=drop"],
            )

        assert outbox.is_file()
        assert ws.get_alpha_beta("kick_weight", 0, "") == (2.0, 0.0)
        assert state.execute(
            "SELECT COUNT(*) FROM feedback_events"
        ).fetchone()[0] == 0

        recovered = FeedbackLogger(
            weight_store=ws,
            state_conn=state,
            outbox_path=outbox,
        )
        assert recovered.recover_pending() is True
        assert recovered.recover_pending() is False
        assert ws.get_alpha_beta("kick_weight", 0, "") == (2.0, 0.0)
        assert state.execute(
            "SELECT COUNT(*) FROM feedback_events"
        ).fetchone()[0] == 1
        assert not outbox.exists()
    finally:
        state.close()
        store.close()


def test_feedback_outbox_compensates_when_cut_disappears(tmp_path: Path):
    store = BrainStore(tmp_path / "brain")
    state = _state_conn(tmp_path)
    outbox = tmp_path / "brain" / "feedback_outbox.json"

    def crash_after_weight_commit(stage: str) -> None:
        if stage == "after_weights_commit":
            raise RuntimeError("simulated crash")

    try:
        ws = WeightStore(store.weights_conn)
        logger = FeedbackLogger(
            weight_store=ws,
            state_conn=state,
            outbox_path=outbox,
            fault_injector=crash_after_weight_commit,
        )
        with pytest.raises(RuntimeError, match="simulated crash"):
            logger.log_feedback(
                cut_id=42,
                rating="fits",
                context_keys=[""],
            )
        state.execute("DELETE FROM timeline_cuts WHERE id=42")

        recovered = FeedbackLogger(
            weight_store=ws,
            state_conn=state,
            outbox_path=outbox,
        )
        assert recovered.recover_pending() is True
        assert ws.get_alpha_beta("kick_weight", 0, "") is None
        assert not outbox.exists()
    finally:
        state.close()
        store.close()


# ----------------------- scorer -----------------------

def test_scorer_uses_bridge_and_weights(tmp_path: Path):
    store = BrainStore(tmp_path / "brain")
    try:
        ws = WeightStore(store.weights_conn)
        bd = BridgeDimensions()
        scorer = BrainScorer(bridge=bd, weight_store=ws)

        feats = CandidateFeatures(
            trigger_type="kick", trigger_strength=1.0,
            audio_energy=0.8, motion_score=0.8,
        )
        scored = scorer.score(
            candidate={"id": "x"}, features=feats, context_keys=[""]
        )
        assert set(scored.brain_scores.keys()) == set(BRIDGE_AXES)
        assert 0.0 <= scored.final_score <= 2.0  # axis values 0..1, weights 0..2
    finally:
        store.close()
