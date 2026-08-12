"""Regression test: GET /video/clips must not crash with TypeError after
analyze_video has persisted is_analyzed/avg_motion/peak_motion/motion_category/
embedding_*/has_embedding into the in-memory video clip dict.

Root cause (commit 9909d4a): list_clips constructs VideoClipInfo(**c_payload,
is_analyzed=..., avg_motion=..., ...). The 8 fields written by analyze_video
overlap with the explicit kwargs → "multiple values for keyword". The fix uses
an _explicit_kwargs set to strip those fields from c_payload before the **expand.

This test guards against drift: if a new field is added to the explicit-kwarg
list in list_clips but is missed in the _explicit_kwargs filter, the test fails.
"""

from fastapi.testclient import TestClient

from pb_studio.core.stage_receipts import (
    create_stage_receipt,
    receipt_to_dict,
    transition_stage_receipt,
)


def _make_app_with_state():
    from backend.main import app
    from backend.app_state import get_app_state

    state = get_app_state()
    state.reset()
    return app, state


def _seed_analyzed_video_clip(state, clip_id=1):
    """Persist a clip dict that already contains every field analyze_video sets."""
    state.set_video_clip(clip_id, {
        "id": clip_id,
        "name": "regression",
        "path": "/tmp/regression.mp4",
        "duration_seconds": 10.0,
        "width": 720,
        "height": 480,
        "fps": 30.0,
        "codec": "h264",
        "thumbnail_available": True,
        "tags": [],
        "video_hash": "abc" * 21 + "x",
        # 8 fields written by analyze_video into in-memory clip:
        "is_analyzed": True,
        "avg_motion": 12.5,
        "peak_motion": 99.0,
        "motion_category": "high",
        "embedding_dim": 1152,
        "embedding_samples": 4,
        "has_embedding": True,
        "tag_source": "lmstudio:qwen3-vl-8b",
    })


def test_list_clips_no_typeerror_after_analyze_persists_all_fields():
    """list_clips must accept clips where every explicit-kwarg field is also in the dict."""
    app, state = _make_app_with_state()
    _seed_analyzed_video_clip(state, clip_id=1)

    client = TestClient(app)
    resp = client.get("/video/clips")
    assert resp.status_code == 200, f"erwartet 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1
    clip = body[0]
    # Verify fields survive the round-trip (not stripped, not duplicated)
    assert clip["id"] == 1
    assert clip["name"] == "regression"
    assert clip["video_hash"] is not None
    # avg_motion / peak_motion / motion_category come from analysis_cache;
    # the in-memory clip dict path is independent. list_clips merges
    # avg_motion via analysis_snap, not via the clip dict, so a missing
    # analysis cache entry means the response value is None — that's OK.


def test_explicit_kwargs_filter_covers_all_documented_fields():
    """Hard-fail if list_clips' _explicit_kwargs set ever drifts away from the
    8 fields known to be set by analyze_video into the clip dict.

    This guards the maintenance contract: when a new field gets added to either
    set_video_clip OR list_clips' explicit kwargs, the _explicit_kwargs filter
    MUST be updated to include it.
    """
    import re
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "backend" / "routers" / "video_router.py"
    text = src.read_text(encoding="utf-8")

    # Locate _explicit_kwargs set definition
    m = re.search(r"_explicit_kwargs\s*=\s*\{([^}]+)\}", text)
    assert m, "_explicit_kwargs set must exist in video_router.list_clips"
    field_block = m.group(1)
    found = set(re.findall(r'"([a-z_]+)"', field_block))

    expected = {
        "video_hash",
        "is_analyzed",
        "avg_motion",
        "peak_motion",
        "motion_category",
        "embedding_dim",
        "embedding_samples",
        "has_embedding",
        "tag_source",
        "analysis_status",
        "stage_status",
        "stage_errors",
        "stage_receipts",
        "tags",
    }
    missing = expected - found
    extra = found - expected
    assert not missing, f"_explicit_kwargs missing fields: {missing}"
    assert not extra, f"_explicit_kwargs has unexpected fields: {extra} — update test if intentional"


def test_list_clips_uses_analysis_snapshot_as_single_tag_and_status_truth():
    """Reloaded analysis truth must win over stale clip-card fields."""
    app, state = _make_app_with_state()
    _seed_analyzed_video_clip(state, clip_id=7)
    state.update_video_clip(
        7,
        tags=["stale"],
        tag_source="stale-provider",
        analysis_status="completed",
        stage_status={},
        stage_errors={},
        stage_receipts={},
    )

    receipt = create_stage_receipt(
        "captions",
        requested=True,
        input_identity={"media": "video-sha"},
        config_identity={"stage": "captions"},
    )
    receipt = transition_stage_receipt(receipt, "running")
    captions_artifact = {
        "tags": ["neon", "club"],
        "tag_source": "lmstudio:qwen-vl",
    }
    receipt = transition_stage_receipt(
        receipt,
        "completed",
        artifact_ref="ai_data_json.stage_artifacts.captions",
        artifact=captions_artifact,
    )
    state.set_video_analysis(7, {
        "analysis_status": "partial",
        "tags": captions_artifact["tags"],
        "tag_source": captions_artifact["tag_source"],
        "stage_status": {"captions": "completed", "motion": "failed"},
        "stage_errors": {"motion": "raft unavailable"},
        "stage_receipts": {"captions": receipt_to_dict(receipt)},
    })

    response = TestClient(app).get("/video/clips")

    assert response.status_code == 200, response.text
    clip = response.json()[0]
    assert clip["tags"] == ["neon", "club"]
    assert clip["tag_source"] == "lmstudio:qwen-vl"
    assert clip["analysis_status"] == "partial"
    assert clip["stage_status"] == {
        "captions": "completed",
        "motion": "failed",
    }
    assert clip["stage_errors"] == {"motion": "raft unavailable"}
    assert clip["stage_receipts"]["captions"]["status"] == "completed"


def test_wpf_apply_analysis_result_immediately_applies_tag_truth():
    """Task 6 keeps typed receipts raw, but applies legacy UI truth immediately."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "PBStudio.UI"
        / "ViewModels"
        / "VideoLibraryViewModel.cs"
    ).read_text(encoding="utf-8")
    method = source.split("private bool ApplyAnalysisResult(", 1)[1].split(
        "private void CancelActiveAnalysis()", 1
    )[0]

    assert "clip.Tags = result.Tags.ToList();" in method
    assert "clip.TagSource = result.TagSource;" in method
    assert "clip.AnalysisStatus = result.Status;" in method
    assert "clip.StageErrors = result.StageErrors;" in method
    assert "OnPropertyChanged(nameof(SelectedClip));" in method
