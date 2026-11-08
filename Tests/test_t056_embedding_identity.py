"""T056: preserve legacy data, reject mixing SigLIP preprocessing spaces."""
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

CURRENT = {"embedding_model_name": "siglip_vision", "embedding_model_version": "onnx-dml-v2"}


def test_video_identity_changes_with_preprocessing():
    from pb_studio.video.video_embedder import CURRENT_MODEL_VERSION
    assert CURRENT_MODEL_VERSION == "onnx-dml-v2"


@pytest.mark.parametrize("identity", [{}, {**CURRENT, "embedding_model_version": "onnx-dml-v1"}])
def test_legacy_analysis_is_not_resumable(identity):
    from backend.routers.video_router import _video_stage_data_is_valid
    assert not _video_stage_data_is_valid("embedding", {
        "has_embedding": True, "embedding_dim": 1152, "embedding_samples": 3, **identity,
    })


def test_current_analysis_is_resumable():
    from backend.routers.video_router import _video_stage_data_is_valid
    assert _video_stage_data_is_valid("embedding", {
        "has_embedding": True, "embedding_dim": 1152, "embedding_samples": 3, **CURRENT,
    })


def test_video_search_excludes_legacy_without_starving_current_hits():
    import faiss
    from pb_studio.data.vector_store import VectorStore
    store = object.__new__(VectorStore)
    store.index_name = "video_index"
    store._lock = threading.Lock()
    store.index = faiss.IndexFlatIP(2)
    store.index.add(np.array([[1, 0], [.8, .6], [.6, .8]], dtype=np.float32))
    store.metadata = {0: {"path": "old"}, 1: {"path": "v1", **CURRENT, "embedding_model_version": "onnx-dml-v1"}, 2: {"path": "new", **CURRENT}}
    before = dict(store.metadata)
    assert store.search(np.array([1, 0], dtype=np.float32), k=1) == []
    assert store.search(np.array([1, 0], dtype=np.float32), k=1, query_identity={**CURRENT, "embedding_model_version": "onnx-dml-v1"}) == []
    hits = store.search(np.array([1, 0], dtype=np.float32), k=1, query_identity=CURRENT)
    assert [meta["path"] for meta, _ in hits] == ["new"]
    assert store.metadata == before
    assert store.index.ntotal == 3


def test_neighbor_reconstruction_rejects_unversioned_vector(tmp_path):
    from pb_studio.pacing.clip_selector import ClipSelector
    path = str((tmp_path / "clip.mp4").absolute())
    index = SimpleNamespace(reconstruct=lambda _: pytest.fail("legacy vector read"))
    selector = ClipSelector.__new__(ClipSelector)
    selector.vector_store = SimpleNamespace(metadata={0: {"path": path}}, index=index, tombstoned_ids=set())
    assert selector._embedding_from_vector_store(path) is None


def test_external_similarity_rejects_unknown_query_before_reading_store():
    from pb_studio.pacing.clip_selector import ClipSelector
    selector = ClipSelector.__new__(ClipSelector)
    assert selector.select_by_similarity(np.ones(1152, dtype=np.float32)) == []


@pytest.mark.parametrize("use_store", [False, True])
def test_specialist_rejects_legacy_candidates_even_in_custom_store(use_store):
    from pb_studio.ai.video_specialist import VideoSpecialist, VideoClip
    specialist = VideoSpecialist.__new__(VideoSpecialist)
    specialist.clips = {
        0: VideoClip(0, "old.mp4", 0., 1., np.ones(2, dtype=np.float32)),
        1: VideoClip(1, "new.mp4", 0., 1., np.ones(2, dtype=np.float32), dict(CURRENT)),
    }
    specialist.vector_store = SimpleNamespace(search=lambda *a, **kw: [({"clip_id": 0}, 1.), ({"clip_id": 1, **CURRENT}, .9)]) if use_store else None
    hits = specialist.find_similar_clips(np.ones(2, dtype=np.float32), query_identity=CURRENT)
    assert [clip.clip_id for clip, _ in hits] == [1]


@pytest.mark.parametrize("identity", [{}, CURRENT])
def test_direct_embedding_selection_reports_space_availability(identity):
    from pb_studio.pacing.clip_selector import ClipSelector
    selector = ClipSelector(strategy="semantic")
    selector._get_text_embedding = lambda _: np.array([1., 0.], dtype=np.float32)
    selector.select_clip([{"id": "test", "path": "test.mp4", "video_embedding": [1., 0.], **identity}], trigger_strength=.5, trigger_type="beat")
    strategy = selector._selection_details["selection_path"]
    assert strategy == ("semantic_direct_embedding" if identity else "semantic_fallback_motion")


def test_old_projector_is_rejected_without_overwriting(tmp_path):
    from pb_studio.brain.cross_modal_projector import CrossModalProjector
    path = tmp_path / "weights.npz"
    old = CrossModalProjector(weights_path=path, video_model_version="onnx-dml-v1")
    assert old.save()
    before = path.read_bytes()
    with pytest.raises(RuntimeError, match="identity mismatch"):
        CrossModalProjector(weights_path=path)
    assert path.read_bytes() == before


def test_pacing_gate_rejects_legacy_and_accepts_current():
    from backend.routers.pacing_router import _pacing_stage_payload_is_valid
    payload = {"has_embedding": True, "embedding_dim": 1152, "embedding_samples": 1}
    assert not _pacing_stage_payload_is_valid("video", "embedding", payload)
    assert _pacing_stage_payload_is_valid("video", "embedding", {**payload, **CURRENT})


def test_unversioned_pending_vector_cannot_be_published():
    from backend.routers.video_router import _commit_pending_video_embedding
    with pytest.raises(ValueError, match="identity"):
        _commit_pending_video_embedding({"_pending_embedding": {"meta_info": {}}})


def test_analysis_identity_persisted_and_reloaded(monkeypatch, tmp_path):
    import json
    from backend.app_state import AppState
    from backend.routers.video_router import _persist_video_analysis_outcome
    video = tmp_path / "test.mp4"
    video.write_bytes(b"test-only")
    row = {"id": 101, "file_path": str(video), "duration_sec": 10.,
           "metadata_json": json.dumps({"clip_type": "video", "clip_id": 7, "name": "test"}),
           "ai_data_json": "{}"}

    class Repo:
        def find_by_project_and_path(self, **_):
            return row
        def update_status(self, _id, _status, ai_data):
            row["ai_data_json"] = json.dumps(ai_data)
        def get_by_project(self, project_id):
            return [row]
        def delete_media(self, _):
            pytest.fail("original deletion attempted")

    monkeypatch.setattr("pb_studio.data.repositories.media_repository.MediaRepository", Repo)
    state = AppState(current_project={"db_project_id": 42, "path": str(tmp_path)})
    context = SimpleNamespace(project_id=42)
    result = {"clip_id": 7, "status": "completed", "stage_status": {"embedding": "completed"},
              "has_embedding": True, "embedding_dim": 1152, "embedding_samples": 3, **CURRENT}
    _persist_video_analysis_outcome(state, context, {"path": str(video)}, result)
    assert all(json.loads(row["ai_data_json"])[key] == value for key, value in CURRENT.items())
    reloaded = AppState(current_project={"db_project_id": 42, "path": str(tmp_path)})
    assert reloaded.load_from_db()
    assert all(reloaded.get_video_analysis(7)[key] == value for key, value in CURRENT.items())


def test_backfill_never_relabels_legacy_or_mismatched_sources(monkeypatch, tmp_path):
    import importlib.util
    import sqlite3
    from unittest.mock import Mock
    script = Path(__file__).resolve().parents[1] / "scripts/backfill_brain_embedding_cache.py"
    spec = importlib.util.spec_from_file_location("t056_backfill", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "test.db"
    with sqlite3.connect(path) as conn:
        conn.executescript("CREATE TABLE media(id INTEGER, file_hash TEXT); CREATE TABLE vector_map(faiss_id INTEGER, media_id INTEGER); INSERT INTO media VALUES(1,'legacy'),(2,'wrong'),(3,'current'); INSERT INTO vector_map VALUES(0,1),(1,2),(2,3);")
    index = SimpleNamespace(reconstruct=Mock(return_value=np.ones(1152, dtype=np.float32)))
    store = SimpleNamespace(index=index, tombstoned_ids=set(), metadata={
        0: {"video_hash": "legacy"},
        1: {**CURRENT, "video_hash": "not-the-same-file"},
        2: {**CURRENT, "video_hash": "current"},
    })
    cache = SimpleNamespace(lookup=Mock(return_value=None), store=Mock())
    monkeypatch.setattr("pb_studio.data.vector_store.VectorStore", lambda **_: store)
    monkeypatch.setattr("pb_studio.brain.brain_service.BrainService.get", lambda: SimpleNamespace(brain=SimpleNamespace(cache=cache)))
    assert module.backfill(path, apply=True) == 1
    index.reconstruct.assert_called_once_with(2)
    assert cache.store.call_args.kwargs["model_version"] == "onnx-dml-v2"
    assert cache.store.call_args.kwargs["media_hash"] == "current"
