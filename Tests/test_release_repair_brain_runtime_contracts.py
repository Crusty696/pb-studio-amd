"""T328 regression/security contracts for Brain, runtime, and public status.

These tests are intentionally authored in T328 and first executed by T332.
"""

from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import re
import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import HTTPException

from pb_studio.brain.bridge_dimensions import (
    BridgeDimensions,
    CandidateFeatures,
)
from pb_studio.brain.feature_adapter import CanonicalFeatureAdapter
from pb_studio.brain.feedback_logger import (
    FeedbackLogger,
    build_credit_assignments,
)
from pb_studio.brain.scorer import BrainScorer
from pb_studio.brain.weight_store import WeightStore
from pb_studio.storage.backup import backup_brain_store
from pb_studio.storage.brain_store import BrainStore
from pb_studio.storage.migration_runner import migrate
from pb_studio.storage.sqlite_init import init_connection


ROOT = Path(__file__).resolve().parents[1]
STATE_MIGRATIONS = (
    ROOT / "src" / "pb_studio" / "storage" / "migrations" / "state"
)
WEIGHT_MIGRATIONS = (
    ROOT / "src" / "pb_studio" / "storage" / "migrations" / "weights"
)


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8-sig")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _state_conn(path: Path) -> sqlite3.Connection:
    migrate(path, STATE_MIGRATIONS)
    conn = sqlite3.connect(
        str(path),
        isolation_level=None,
        check_same_thread=False,
    )
    init_connection(conn)
    conn.execute(
        "INSERT INTO timelines "
        "(id, name, audio_clip_id, created_at, is_current) "
        "VALUES (1, 'repair-contract', 1, '2026-07-29T00:00:00Z', 1)"
    )
    conn.execute(
        "INSERT INTO timeline_cuts "
        "(id, timeline_id, position_idx, clip_id, start_time, end_time) "
        "VALUES (42, 1, 0, 'clip-42', 0.0, 1.0)"
    )
    return conn


def test_canonical_feature_adapter_uses_real_normalized_units_and_status():
    adapter = CanonicalFeatureAdapter(
        audio_analysis={
            "duration_seconds": 100.0,
            "energy_curve": [0.1, 0.4, 0.8, 1.0],
            "spectral_data": {"centroids": [100.0, 200.0, 400.0]},
            "mood_tags": ["Warm", "ENERGETIC", "warm"],
            "analysis_status": "completed",
            "structure_segments": [
                {"start_time": 20.0, "end_time": 40.0, "label": "chorus"},
            ],
        },
        video_analysis_by_clip={
            "clip-a": {
                "avg_motion": 10.0,
                "motion_curve": [0.0, 10.0, 100.0],
                "analysis_status": "completed",
                "mood_tags": ["Energetic", "Live"],
            },
            "clip-b": {
                "avg_motion": 100.0,
                "analysis_status": "partial",
            },
        },
    )

    features = adapter.candidate_features(
        clip_id="clip-a",
        trigger_type="kick",
        trigger_strength=1.4,
        cut_time_sec=30.0,
        cut_duration_sec=2.0,
    )

    assert features.motion_score == pytest.approx(10.0 / 95.5)
    assert features.pace_class_score == features.motion_score
    assert features.trigger_strength == 1.0
    assert features.segment_type == "drop"
    assert features.audio_mood_tags == ["energetic", "warm"]
    assert features.mood_tags == ["energetic", "live"]
    assert features.audio_confidence == 1.0
    assert features.video_confidence == 1.0
    assert features.confidence == 1.0
    assert features.feature_provenance["motion"]["unit"] == "normalized_pool_p95"
    assert adapter.normalized_motion_curve("clip-a") == pytest.approx(
        [0.0, 10.0 / 95.5, 1.0]
    )

    partial = adapter.candidate_features(
        clip_id="clip-b",
        trigger_type="beat",
        trigger_strength=0.5,
        cut_time_sec=0.0,
        cut_duration_sec=1.0,
    )
    assert partial.video_confidence == 0.5
    assert partial.confidence == 0.5


@pytest.mark.parametrize(
    ("audio_embedding", "video_embedding", "expected_status"),
    [
        (None, None, "unavailable"),
        ([1.0, 0.0], None, "partial"),
        ([1.0, 0.0], [1.0, 0.0, 0.0], "partial"),
        ([0.0, 0.0], [1.0, 0.0], "partial"),
        ([float("nan"), 1.0], [1.0, 0.0], "partial"),
    ],
)
def test_semantic_unavailable_or_invalid_is_explicit_not_pseudo_success(
    audio_embedding,
    video_embedding,
    expected_status,
):
    adapter = CanonicalFeatureAdapter(
        audio_analysis={"analysis_status": "completed"},
        video_analysis_by_clip={
            "clip": {"analysis_status": "completed", "avg_motion": 1.0}
        },
    )
    features = adapter.candidate_features(
        clip_id="clip",
        trigger_type="beat",
        trigger_strength=1.0,
        cut_time_sec=0.0,
        cut_duration_sec=1.0,
        audio_embedding=audio_embedding,
        video_embedding=video_embedding,
    )
    scores = BridgeDimensions().compute_all(features)

    assert features.semantic_status == expected_status
    assert features.semantic_reason
    assert "semantic_match_weight" not in scores


def test_semantic_success_requires_valid_equal_dimension_embeddings():
    adapter = CanonicalFeatureAdapter(
        audio_analysis={"analysis_status": "completed"},
        video_analysis_by_clip={
            "clip": {"analysis_status": "completed", "avg_motion": 1.0}
        },
    )
    features = adapter.candidate_features(
        clip_id="clip",
        trigger_type="beat",
        trigger_strength=1.0,
        cut_time_sec=0.0,
        cut_duration_sec=1.0,
        audio_embedding=np.array([1.0, 0.0], dtype=np.float32),
        video_embedding=np.array([1.0, 0.0], dtype=np.float32),
    )
    scores = BridgeDimensions().compute_all(features)

    assert features.semantic_status == "available"
    assert scores["semantic_match_weight"] == pytest.approx(1.0)


def test_brain_scorer_denominator_contains_only_available_axes():
    class UnitWeights:
        @staticmethod
        def get_posterior_mean(_axis: str, _context_keys: list[str]) -> float:
            return 1.0

    features = CandidateFeatures(
        trigger_type="kick",
        trigger_strength=1.0,
        semantic_status="unavailable",
    )
    scored = BrainScorer(
        bridge=BridgeDimensions(),
        weight_store=UnitWeights(),
    ).score(candidate="clip", features=features, context_keys=[""])

    assert "semantic_match_weight" not in scored.brain_scores
    assert len(scored.brain_scores) == 16
    assert scored.final_score == pytest.approx(
        sum(scored.brain_scores.values()) / 16
    )


def test_sparse_credit_updates_only_relevant_axes_and_contexts(tmp_path: Path):
    context_keys = [
        "",
        "section=drop",
        "mood=dark",
        "motion=high",
        "subtrack=main",
        "pace=fast",
    ]
    assignments = build_credit_assignments(
        metadata={
            "bridge_values": {
                "beat_weight": 1.0,
                "min_clip_length": 0.4,
                "motion_match_weight": 0.8,
                "brightness_match_weight": 0.5,
                "semantic_match_weight": 0.9,
                "scene_cut_weight": 0.01,
            },
            "brain_axis_status": {
                "semantic_match_weight": {
                    "status": "unavailable",
                    "reason": "audio_embedding_missing",
                }
            },
        },
        brain_scores={},
        context_keys=context_keys,
    )
    identities = {
        (item["axis"], item["level"], item["key"]): item["credit"]
        for item in assignments
    }

    assert {
        level
        for axis, level, _key in identities
        if axis == "beat_weight"
    } == {0, 1, 4, 5}
    assert {
        level
        for axis, level, _key in identities
        if axis == "min_clip_length"
    } == {0, 1, 5}
    assert {
        level
        for axis, level, _key in identities
        if axis == "motion_match_weight"
    } == {0, 1, 3, 5}
    assert {
        level
        for axis, level, _key in identities
        if axis == "brightness_match_weight"
    } == {0, 2, 3, 5}
    assert not any(axis == "semantic_match_weight" for axis, _, _ in identities)
    assert not any(axis == "scene_cut_weight" for axis, _, _ in identities)
    assert identities[("beat_weight", 0, "")] == 0.25
    assert identities[("motion_match_weight", 3, "motion=high")] == 0.6
    assert identities[("brightness_match_weight", 2, "mood=dark")] == 0.3

    store = BrainStore(tmp_path / "brain")
    state = _state_conn(tmp_path / "state.db")
    try:
        weights = WeightStore(store.weights_conn)
        logger = FeedbackLogger(
            weight_store=weights,
            state_conn=state,
            outbox_path=tmp_path / "feedback-outbox.json",
        )
        updated = logger.log_feedback(
            cut_id=42,
            rating="perfect",
            context_keys=context_keys,
            assignments=assignments,
        )
        rows = store.weights_conn.execute(
            "SELECT axis, context_level, context_key, "
            "positive_count, negative_count FROM axis_weights"
        ).fetchall()

        assert updated == len(assignments)
        assert len(rows) == len(assignments)
        assert {(row[0], row[1], row[2]) for row in rows} == set(identities)
        assert all(row[3] == pytest.approx(2.0 * identities[row[:3]]) for row in rows)
        assert all(row[4] == 0.0 for row in rows)
        assert weights.total_clicks() == 1
        assert state.execute(
            "SELECT COUNT(*) FROM feedback_events"
        ).fetchone()[0] == 1
    finally:
        state.close()
        store.close()


def test_unknown_feedback_cut_fails_closed_before_weight_mutation(
    tmp_path: Path,
    monkeypatch,
):
    from backend.routers import brain_router
    from backend.schemas.brain_schemas import BrainFeedbackRequest

    state = _state_conn(tmp_path / "unknown-state.db")

    class SpyLogger:
        def __init__(self, conn: sqlite3.Connection):
            self.state_conn = conn
            self.called = False

        def log_feedback(self, **_kwargs):
            self.called = True
            raise AssertionError("unknown cut must not mutate weights")

    logger = SpyLogger(state)
    service = SimpleNamespace(state_conn=state, feedback_logger=logger)
    monkeypatch.setattr(brain_router, "get_brain_service", lambda: service)
    try:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                brain_router.feedback(
                    BrainFeedbackRequest(cut_id=999_999, rating="perfect")
                )
            )
        assert exc.value.status_code == 404
        assert logger.called is False
    finally:
        state.close()


def test_weight_v2_migration_has_backup_hash_rehearsal_and_restore(
    tmp_path: Path,
):
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    source = brain_dir / "weights.db"
    conn = sqlite3.connect(str(source), isolation_level=None)
    try:
        conn.execute(
            "CREATE TABLE axis_weights ("
            "axis TEXT NOT NULL, context_level INTEGER NOT NULL, "
            "context_key TEXT NOT NULL, positive_count REAL NOT NULL DEFAULT 0, "
            "negative_count REAL NOT NULL DEFAULT 0, last_updated TEXT NOT NULL, "
            "PRIMARY KEY (axis, context_level, context_key))"
        )
        conn.execute(
            "CREATE INDEX idx_axis_level "
            "ON axis_weights(axis, context_level)"
        )
        conn.execute(
            "INSERT INTO axis_weights VALUES "
            "('kick_weight', 0, '', 6.0, 4.0, '2026-07-29T00:00:00Z')"
        )
        conn.execute("PRAGMA user_version = 1")
    finally:
        conn.close()

    backup_dir = backup_brain_store(
        brain_dir,
        tmp_path / "backups",
        files=("weights.db",),
    )
    backup = backup_dir / "weights.db"
    backup_hash = _sha256(backup)
    assert len(backup_hash) == 64

    rehearsal = tmp_path / "rehearsal.db"
    shutil.copy2(backup, rehearsal)
    assert migrate(rehearsal, WEIGHT_MIGRATIONS) == 2
    rehearsed = sqlite3.connect(str(rehearsal))
    try:
        assert rehearsed.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert rehearsed.execute(
            "SELECT COUNT(*) FROM axis_weights_v1_archive"
        ).fetchone()[0] == 1
        assert rehearsed.execute(
            "SELECT COUNT(*) FROM axis_weights"
        ).fetchone()[0] == 0
        assert rehearsed.execute(
            "SELECT value FROM brain_meta "
            "WHERE key='weight_semantics_version'"
        ).fetchone()[0] == "2"
        assert rehearsed.execute(
            "SELECT value FROM brain_meta WHERE key='feedback_count'"
        ).fetchone()[0] == "0"
    finally:
        rehearsed.close()

    restored = tmp_path / "restored.db"
    shutil.copy2(backup, restored)
    assert _sha256(restored) == backup_hash
    restored_conn = sqlite3.connect(str(restored))
    try:
        assert restored_conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert restored_conn.execute("PRAGMA user_version").fetchone()[0] == 1
        assert restored_conn.execute(
            "SELECT positive_count, negative_count FROM axis_weights"
        ).fetchone() == (6.0, 4.0)
    finally:
        restored_conn.close()


def test_runtime_manifest_hashes_one_canonical_ffmpeg_ffprobe_pair():
    manifest = json.loads(
        (ROOT / "config" / "ffmpeg-runtime.json").read_text(encoding="utf-8")
    )
    stable_bin = (ROOT / manifest["stable_bin"]).resolve()
    ffmpeg = stable_bin / "ffmpeg.exe"
    ffprobe = stable_bin / "ffprobe.exe"

    assert manifest["schema_version"] == 1
    assert ffmpeg.is_file() and ffprobe.is_file()
    assert ffmpeg.parent == ffprobe.parent == stable_bin
    assert _sha256(ffmpeg) == manifest["active"]["ffmpeg_sha256"].upper()
    assert _sha256(ffprobe) == manifest["active"]["ffprobe_sha256"].upper()
    assert manifest["candidate"]["activation_status"] == (
        "pending_t332_hardware_qc"
    )
    for field in ("asset_sha256", "ffmpeg_sha256", "ffprobe_sha256"):
        assert re.fullmatch(r"[0-9A-F]{64}", manifest["active"][field])
        assert re.fullmatch(r"[0-9A-F]{64}", manifest["candidate"][field])


def test_launchers_share_runtime_contract_and_backend_arguments():
    batch_launchers = (
        "AUDIT_FIX_VERIFY.bat",
        "LOW-VRAM-STRESS.bat",
        "SSE-RECOVERY-TEST.bat",
        "_cowork_run.bat",
        "coverage_run_v2.bat",
        "run_audit_tests.bat",
        "run_long_stress.bat",
        "run_quick_tests.bat",
        "start.bat",
        "test.bat",
        "scripts/brain_sync.bat",
        "scripts/qa/sse_visual_review.bat",
        "scripts/qa/stress_4h.bat",
    )
    powershell_launchers = (
        "build.ps1",
        "launch.ps1",
        "run_full_test.ps1",
        "setup_pb_studio.ps1",
        "verify_release_smoke.ps1",
        "scripts/dev/refresh-openapi-snapshot.ps1",
        "scripts/run_lmstudio_smoke.ps1",
    )
    for path in batch_launchers:
        assert "runtime_contract.bat" in _source(path).lower(), path
    for path in powershell_launchers:
        assert "runtime_contract.ps1" in _source(path).lower(), path

    runtime_ps = _source("scripts/runtime_contract.ps1")
    bridge = _source("PBStudio.UI/Services/PythonBridgeService.cs")
    assert "'.venv\\Scripts\\python.exe'" in runtime_ps
    assert "'--host', '127.0.0.1', '--port', '8765'" in runtime_ps
    assert (
        "backend.main:app --host 127.0.0.1 --port {Port}"
        in bridge
    )


def test_legacy_git_mutation_wrappers_are_fail_closed():
    batch_wrappers = (
        "scripts/chat_track_build_and_push.bat",
        "scripts/chat_track_push_only.bat",
        "scripts/push_brain_llm_narrator.bat",
        "scripts/qa/push_to_origin.bat",
        "scripts/recovery/git_recovery_and_commit.bat",
    )
    for path in batch_wrappers:
        source = _source(path).lower()
        assert "retired" in source, path
        assert "exit /b 2" in source, path
        assert "git push " not in source, path
        assert "git reset --hard" not in source, path

    python_wrapper = _source("scripts/chat_track_commit_bypass.py").lower()
    assert "retired" in python_wrapper
    assert "return 2" in python_wrapper
    assert "refs/heads" not in python_wrapper


def test_noncanonical_runtime_overrides_fail_closed_at_each_boundary():
    runtime_ps = _source("scripts/runtime_contract.ps1")
    backend_config = _source("backend/config.py")
    bridge = _source("PBStudio.UI/Services/PythonBridgeService.cs")
    settings = _source("PBStudio.UI/Services/SettingsService.cs")

    for name in (
        "PBSTUDIO_FFMPEG_PATH",
        "PBSTUDIO_FFPROBE_PATH",
        "PBSTUDIO_PYTHON_EXE",
    ):
        assert name in runtime_ps
    assert "selects a non-canonical runtime" in runtime_ps
    assert 'field_validator("ffmpeg_path")' in backend_config
    assert 'field_validator("ffprobe_path")' in backend_config
    assert "requires canonical FFmpeg runtime" in backend_config
    assert "requires canonical FFprobe runtime" in backend_config
    assert "PBSTUDIO_PYTHON_EXE" in bridge
    assert "return null;" in bridge
    assert "Nur die geprüfte Projekt-Runtime ist zulässig." in settings


def test_openapi_csharp_and_python_models_expose_public_repair_contracts():
    from backend.schemas.audio_schemas import (
        AudioAnalysisResult,
        AudioClipInfo,
    )
    from backend.schemas.brain_schemas import BrainFeedbackResponse
    from backend.schemas.pacing_schemas import TimelineEntrySchema
    from backend.schemas.render_schemas import RenderProgress

    expected = {
        "AudioAnalysisResult": {
            "analysis_status",
            "stage_status",
            "stage_errors",
            "chunk_evidence",
            "downbeats",
            "downbeat_provenance",
        },
        "AudioClipInfo": {
            "analysis_status",
            "stage_status",
            "stage_errors",
            "has_audio_embedding",
        },
        "TimelineEntrySchema": {
            "feature_confidence",
            "semantic_status",
            "semantic_reason",
            "trigger_provenance",
            "brain_axis_status",
            "metadata",
        },
        "RenderProgress": {
            "message",
            "queue_job_id",
            "run_id",
            "evidence_path",
            "validation_path",
            "progress_end",
            "validation_status",
        },
        "BrainFeedbackResponse": {"message"},
    }
    model_fields = {
        "AudioAnalysisResult": set(AudioAnalysisResult.model_fields),
        "AudioClipInfo": set(AudioClipInfo.model_fields),
        "TimelineEntrySchema": set(TimelineEntrySchema.model_fields),
        "RenderProgress": set(RenderProgress.model_fields),
        "BrainFeedbackResponse": set(BrainFeedbackResponse.model_fields),
    }
    snapshot = json.loads(_source("PBStudio.UI/openapi.snapshot.json"))
    schemas = snapshot["components"]["schemas"]
    for schema_name, fields in expected.items():
        assert fields <= model_fields[schema_name]
        assert fields <= set(schemas[schema_name]["properties"])

    api_client = _source("PBStudio.UI/Services/ApiClient.cs")
    for field in (
        "AnalysisStatus",
        "StageStatus",
        "StageErrors",
        "HasAudioEmbedding",
        "ChunkEvidence",
        "Downbeats",
        "DownbeatProvenance",
        "FeatureConfidence",
        "SemanticStatus",
        "SemanticReason",
        "TriggerProvenance",
        "BrainAxisStatus",
        "Metadata",
        "Message",
        "QueueJobId",
        "RunId",
        "EvidencePath",
        "ValidationPath",
        "ProgressEnd",
        "ValidationStatus",
    ):
        assert field in api_client


def test_partial_failure_and_evidence_states_remain_visible_and_copyable():
    audio_vm = _source("PBStudio.UI/ViewModels/AudioLibraryViewModel.cs")
    audio_model = _source("PBStudio.UI/Models/AudioClip.cs")
    beat_model = _source("PBStudio.UI/Models/BeatMarkerViewModel.cs")
    timeline_vm = _source("PBStudio.UI/ViewModels/TimelineViewModel.cs")
    sse = _source("PBStudio.UI/Services/SSEClient.cs")
    production_vm = _source("PBStudio.UI/ViewModels/ProductionViewModel.cs")

    assert 'clip.IsAnalyzed = result.AnalysisStatus == "completed";' in audio_vm
    assert 'result.AnalysisStatus == "partial"' in audio_vm
    assert 'AnalysisStatus is "partial" or "failed"' in audio_model
    assert 'BeatType.Equals("downbeat"' in beat_model
    assert 'BeatType.Equals("bar"' in beat_model
    assert "% 4" not in beat_model
    for field in (
        "FeatureConfidence",
        "SemanticStatus",
        "SemanticReason",
        "TriggerProvenance",
        "BrainAxisStatus",
    ):
        assert field in timeline_vm
    for field in (
        "run_id",
        "evidence_path",
        "validation_path",
        "progress_end",
        "validation_status",
    ):
        assert f'"{field}"' in sse
    assert "EvidencePath" in production_vm
    assert "ValidationPath" in production_vm

    copyable_bindings = {
        "PBStudio.UI/Views/AudioLibraryView.xaml": "StatusText",
        "PBStudio.UI/Views/TimelineView.xaml": "SelectedEvidence",
        "PBStudio.UI/Views/ProductionView.xaml": "StatusText",
        "PBStudio.UI/Views/BrainView.xaml": "Status",
    }
    for path, binding in copyable_bindings.items():
        xaml = _source(path)
        pattern = (
            rf"<TextBox[^>]*Text=\"\{{Binding {binding}[^>]*"
            rf"IsReadOnly=\"True\""
        )
        assert re.search(pattern, xaml, re.DOTALL), path


def test_rejected_feedback_detail_flows_from_http_to_visible_ui():
    api_client = _source("PBStudio.UI/Services/ApiClient.cs")
    brain_vm = _source("PBStudio.UI/ViewModels/BrainViewModel.cs")
    brain_view = _source("PBStudio.UI/Views/BrainView.xaml")

    assert "TryReadErrorDetail(raw)" in api_client
    assert 'TryGetProperty("detail"' in api_client
    assert 'new BrainFeedbackResponse("rejected", 0, 0, detail)' in api_client
    rejection = brain_vm.index('if (!resp.Status.Equals("ok"')
    message = brain_vm.index("resp.Message", rejection)
    applied_event = brain_vm.index("BrainFeedbackAppliedMessage", rejection)
    assert rejection < message < applied_event
    assert re.search(
        r'<TextBox[^>]*Text="\{Binding Status[^>]*IsReadOnly="True"',
        brain_view,
        re.DOTALL,
    )


def test_path_writes_use_resolved_containment_guards():
    project_router = _source("backend/routers/project_router.py")
    render_router = _source("backend/routers/render_router.py")

    assert "project_path = (Path(request.path) / request.name).resolve()" in (
        project_router
    )
    assert "project_path = Path(request.path).resolve()" in project_router
    assert project_router.count(
        "if not project_path.is_relative_to(allowed_base):"
    ) >= 2
    assert "output_p_check = Path(request.output_path).resolve()" in render_router
    assert "if not output_p_check.is_relative_to(allowed_render):" in (
        render_router
    )
    assert "output_path = Path(request.output_path).resolve()" in render_router
    assert "if not output_path.is_relative_to(project_root):" in render_router


def test_status_evidence_contract_does_not_expose_secret_fields():
    from backend.schemas.render_schemas import RenderProgress

    payload = RenderProgress(
        task_id="task-safe",
        status="completed",
        percent=100.0,
        current_frame=10,
        total_frames=10,
        run_id="run-safe",
        evidence_path=r"C:\project\result.json",
        validation_path=r"C:\project\validation.json",
        progress_end=True,
        validation_status="validated",
        password="must-be-dropped",
        api_key="must-be-dropped",
        access_token="must-be-dropped",
    ).model_dump()
    forbidden = {
        "password",
        "secret",
        "api_key",
        "authorization",
        "bearer",
        "access_token",
        "refresh_token",
    }
    assert forbidden.isdisjoint(payload)

    tree = ast.parse(_source("backend/routers/render_router.py"))
    published_keys = {
        key.value.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    assert forbidden.isdisjoint(published_keys)
