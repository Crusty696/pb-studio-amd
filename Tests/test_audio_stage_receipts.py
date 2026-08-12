from __future__ import annotations

import asyncio
import importlib
from contextlib import asynccontextmanager, contextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException


PROJECT_UUID = "0e736c32-948c-4323-b9ba-0f9d50fa193f"
MEDIA_SHA256 = "a" * 64


class _ReceiptState:
    def __init__(self, clip: dict, analysis: dict | None = None) -> None:
        self.clip = clip
        self.analysis = dict(analysis or {})
        self.persisted_history: list[dict] = []
        self.timeline: list[tuple[str, object]] = []
        self._project_reads = 0
        self._current_project = {
            "db_project_id": 17,
            "path": str(SimpleNamespace()),
            "project_uuid": PROJECT_UUID,
        }
        self.context = SimpleNamespace(project_id=17, epoch=9)
        self.operation_active = False

    @property
    def current_project(self):
        self._project_reads += 1
        if self._project_reads > 1:
            raise AssertionError("active project identity was read more than once")
        return self._current_project

    @asynccontextmanager
    async def project_operation(self):
        self.operation_active = True
        try:
            yield self.context
        finally:
            self.operation_active = False

    @contextmanager
    def project_commit(self, _context):
        yield

    def is_project_context_current(self, _context) -> bool:
        return True

    def get_audio_clip(self, clip_id: int):
        return self.clip if clip_id == self.clip["id"] else None

    def get_audio_analysis(self, clip_id: int):
        return self.analysis if clip_id == self.clip["id"] else None

    def update_audio_analysis(self, **kwargs) -> None:
        snapshot = dict(kwargs)
        self.persisted_history.append(snapshot)
        self.timeline.append(("persist", snapshot))
        for source, target in (
            ("analysis_status", "_analysis_status"),
            ("stage_status", "_stage_status"),
            ("stage_errors", "_stage_errors"),
            ("stage_receipts", "_stage_receipts"),
        ):
            if source in kwargs:
                self.analysis[target] = kwargs[source]


def _clip(path) -> dict:
    return {
        "id": 7,
        "name": "receipt",
        "path": str(path),
        "duration_seconds": 30.0,
        "audio_hash": MEDIA_SHA256,
        "is_analyzed": False,
    }


def _beats_payload(clip_id: int = 7, bpm: float = 128.0) -> dict:
    return {
        "clip_id": clip_id,
        "duration_seconds": 30.0,
        "bpm": bpm,
        "beat_count": 1,
        "beats": [{"time": 1.0, "strength": 1.0, "beat_type": "beat"}],
        "energy_curve": [0.5],
        "downbeats": [],
        "downbeat_provenance": {"status": "unavailable"},
        "onset_times": [1.0],
        "kick_times": [1.0],
        "snare_times": [],
        "hihat_times": [],
        "structure_segments": [],
        "spectral_data": None,
        "key": None,
        "_analysis_status": "completed",
        "_stage_status": {
            "beats": "completed",
            "structure": "skipped",
            "spectral": "skipped",
            "key": "skipped",
        },
        "_stage_errors": {},
    }


def _beats_only_request():
    from backend.schemas.audio_schemas import AudioAnalyzeRequest

    return AudioAnalyzeRequest(
        clip_id=7,
        detect_beats=True,
        detect_structure=False,
        spectral_analysis=False,
        detect_key=False,
    )


def _bound_completed_beats_receipt(audio_router, cache: dict):
    from pb_studio.core.stage_receipts import (
        build_config_fingerprint,
        build_input_fingerprint,
        create_stage_receipt,
        transition_stage_receipt,
    )

    request = _beats_only_request()
    request_flags = {
        field: bool(getattr(request, field))
        for field in audio_router._AUDIO_STAGE_REQUEST_FIELDS.values()
    }
    request_flags["force"] = bool(request.force)
    pending = create_stage_receipt(
        "beats",
        requested=True,
        input_fingerprint=build_input_fingerprint(
            project_uuid=PROJECT_UUID,
            catalog_project_id=17,
            project_epoch=9,
            clip_id=7,
            media_sha256=MEDIA_SHA256,
            stage_input_identity={"stage_id": "beats", "source_paths": {}},
        ),
        config_fingerprint=build_config_fingerprint(
            stage_request_flags=request_flags,
            effective_config_identity=audio_router._AUDIO_STAGE_CONFIG_IDENTITIES[
                "beats"
            ],
        ),
    )
    return transition_stage_receipt(
        transition_stage_receipt(pending, "running"),
        "completed",
        artifact_ref="ai_data_json.beats_json",
        artifact=cache["beats"],
    )


def _install_quiet_dependencies(monkeypatch, audio_router, state) -> None:
    async def capture_event(name, payload):
        state.timeline.append(("event", (name, dict(payload))))

    async def no_log(*_args, **_kwargs):
        return None

    monkeypatch.setattr(audio_router, "publish_event", capture_event)
    monkeypatch.setattr(audio_router, "publish_log", no_log)
    monkeypatch.setattr(
        audio_router,
        "_store_audio_embedding_in_brain_cache",
        no_log,
    )


def test_receipt_running_is_persisted_before_worker_and_first_sse(
    monkeypatch,
    tmp_path,
) -> None:
    audio_router = importlib.import_module("backend.routers.audio_router")
    audio = tmp_path / "running.wav"
    audio.write_bytes(b"audio")
    state = _ReceiptState(_clip(audio))
    _install_quiet_dependencies(monkeypatch, audio_router, state)

    def run_analysis(*args, **kwargs):
        receipts = state.persisted_history[-1]["stage_receipts"]
        assert receipts["beats"]["status"] == "running"
        assert all(
            receipts[name]["status"] == "skipped"
            for name in ("structure", "spectral", "key")
        )
        return _beats_payload()

    monkeypatch.setattr(audio_router, "_run_audio_analysis", run_analysis)

    response = asyncio.run(audio_router.analyze_audio(_beats_only_request(), state))

    first_persist = next(i for i, row in enumerate(state.timeline) if row[0] == "persist")
    first_event = next(i for i, row in enumerate(state.timeline) if row[0] == "event")
    assert first_persist < first_event
    assert response.stage_receipts["beats"].status == "completed"
    assert response.stage_receipts["beats"].artifact_valid is True
    correlation_ids = {
        receipt.correlation_id for receipt in response.stage_receipts.values()
    }
    assert len(correlation_ids) == 1
    UUID(correlation_ids.pop())
    assert state._project_reads == 1
    assert all(row["project_id"] == 17 for row in state.persisted_history)


def test_terminal_receipts_are_persisted_before_terminal_sse(
    monkeypatch,
    tmp_path,
) -> None:
    audio_router = importlib.import_module("backend.routers.audio_router")
    audio = tmp_path / "terminal.wav"
    audio.write_bytes(b"audio")
    state = _ReceiptState(_clip(audio))
    _install_quiet_dependencies(monkeypatch, audio_router, state)
    monkeypatch.setattr(audio_router, "_run_audio_analysis", lambda *_a, **_k: _beats_payload())

    asyncio.run(audio_router.analyze_audio(_beats_only_request(), state))

    terminal_event_index = max(
        index
        for index, row in enumerate(state.timeline)
        if row[0] == "event" and row[1][1].get("percent") == 100
    )
    terminal_persist_index = max(
        index
        for index, row in enumerate(state.timeline)
        if row[0] == "persist"
        and row[1]["stage_receipts"]["beats"]["status"] == "completed"
    )
    assert terminal_persist_index < terminal_event_index
    terminal_event = state.timeline[terminal_event_index][1][1]
    assert terminal_event["correlation_id"]
    assert terminal_event["stage_receipts"]["beats"]["artifact_valid"] is True


def test_missing_file_persists_failed_requested_receipt_before_error_sse(
    monkeypatch,
    tmp_path,
) -> None:
    audio_router = importlib.import_module("backend.routers.audio_router")
    state = _ReceiptState(_clip(tmp_path / "missing.wav"))
    _install_quiet_dependencies(monkeypatch, audio_router, state)

    with pytest.raises(HTTPException) as caught:
        asyncio.run(audio_router.analyze_audio(_beats_only_request(), state))

    assert caught.value.status_code == 422
    assert state.persisted_history[-1]["stage_receipts"]["beats"]["status"] == "failed"
    assert state.persisted_history[-1]["stage_receipts"]["beats"]["error_code"] == "media_missing"
    assert state.timeline[0][0] == "persist"
    error_event = [row[1][1] for row in state.timeline if row[0] == "event"][-1]
    assert error_event["status"] == "failed"
    assert error_event["stage_receipts"]["beats"]["status"] == "failed"


def test_global_worker_failure_persists_all_affected_receipts_before_sse(
    monkeypatch,
    tmp_path,
) -> None:
    audio_router = importlib.import_module("backend.routers.audio_router")
    audio = tmp_path / "worker.wav"
    audio.write_bytes(b"audio")
    state = _ReceiptState(_clip(audio))
    _install_quiet_dependencies(monkeypatch, audio_router, state)

    def fail_worker(*_args, **_kwargs):
        raise RuntimeError("worker exploded")

    monkeypatch.setattr(audio_router, "_run_audio_analysis", fail_worker)

    with pytest.raises(HTTPException) as caught:
        asyncio.run(audio_router.analyze_audio(_beats_only_request(), state))

    assert caught.value.status_code == 500
    failed = state.persisted_history[-1]
    assert failed["analysis_status"] == "failed"
    assert failed["stage_receipts"]["beats"]["status"] == "failed"
    assert failed["stage_receipts"]["beats"]["error_code"] == "analysis_worker_failed"
    final_event_index = max(i for i, row in enumerate(state.timeline) if row[0] == "event")
    assert state.timeline[final_event_index - 1][0] == "persist"


def test_retry_reuses_valid_completed_receipt_artifact_hash(
    monkeypatch,
    tmp_path,
) -> None:
    from backend.schemas.audio_schemas import AudioAnalyzeRequest
    from pb_studio.core.stage_receipts import (
        create_stage_receipt,
        receipt_to_dict,
        transition_stage_receipt,
    )

    audio_router = importlib.import_module("backend.routers.audio_router")
    audio = tmp_path / "retry.wav"
    audio.write_bytes(b"audio")
    cache = _beats_payload()
    completed = _bound_completed_beats_receipt(audio_router, cache)
    cache["_stage_receipts"] = {"beats": receipt_to_dict(completed)}
    state = _ReceiptState(_clip(audio), cache)
    _install_quiet_dependencies(monkeypatch, audio_router, state)

    def must_not_recompute(*_args, **_kwargs):
        raise AssertionError("valid completed stage was recomputed")

    monkeypatch.setattr(audio_router, "_run_audio_analysis", must_not_recompute)

    response = asyncio.run(audio_router.analyze_audio(_beats_only_request(), state))

    assert response.stage_receipts["beats"].artifact_sha256 == completed.artifact_sha256
    assert response.bpm == 128.0


@pytest.mark.parametrize("corruption", ["hash", "ref"])
def test_retry_recomputes_v1_receipt_with_stale_artifact_binding(
    monkeypatch,
    tmp_path,
    corruption,
) -> None:
    from pb_studio.core.stage_receipts import (
        create_stage_receipt,
        receipt_to_dict,
        transition_stage_receipt,
    )

    audio_router = importlib.import_module("backend.routers.audio_router")
    audio = tmp_path / f"stale-{corruption}.wav"
    audio.write_bytes(b"audio")
    cache = _beats_payload()
    completed = _bound_completed_beats_receipt(audio_router, cache)
    serialized = receipt_to_dict(completed)
    if corruption == "hash":
        serialized["artifact_sha256"] = "b" * 64
    else:
        serialized["artifact_ref"] = "ai_data_json.energy_curve"
    cache["_stage_receipts"] = {"beats": serialized}
    state = _ReceiptState(_clip(audio), cache)
    _install_quiet_dependencies(monkeypatch, audio_router, state)
    planned_requests = []

    def run_analysis(_path, _clip_id, planned, *_args, **_kwargs):
        planned_requests.append(planned)
        return _beats_payload(bpm=130.0)

    monkeypatch.setattr(audio_router, "_run_audio_analysis", run_analysis)

    response = asyncio.run(audio_router.analyze_audio(_beats_only_request(), state))

    assert planned_requests[0].detect_beats is True
    assert response.bpm == 130.0
    assert response.stage_receipts["beats"].artifact_ref == "ai_data_json.beats_json"
    assert response.stage_receipts["beats"].artifact_sha256 != "b" * 64


@pytest.mark.parametrize(
    ("fingerprint_field", "mismatched_value"),
    [
        ("input_fingerprint", "b" * 64),
        ("config_fingerprint", "c" * 64),
    ],
)
def test_retry_recomputes_v1_receipt_with_stale_fingerprint_binding(
    monkeypatch,
    tmp_path,
    fingerprint_field,
    mismatched_value,
) -> None:
    from pb_studio.core.stage_receipts import receipt_to_dict

    audio_router = importlib.import_module("backend.routers.audio_router")
    audio = tmp_path / f"stale-{fingerprint_field}.wav"
    audio.write_bytes(b"audio")
    cache = _beats_payload()
    completed = _bound_completed_beats_receipt(audio_router, cache)
    expected_fingerprint = getattr(completed, fingerprint_field)
    serialized = receipt_to_dict(completed)
    serialized[fingerprint_field] = mismatched_value
    cache["_stage_receipts"] = {"beats": serialized}
    state = _ReceiptState(_clip(audio), cache)
    _install_quiet_dependencies(monkeypatch, audio_router, state)
    planned_requests = []

    def run_analysis(_path, _clip_id, planned, *_args, **_kwargs):
        planned_requests.append(planned)
        return _beats_payload(bpm=132.0)

    monkeypatch.setattr(audio_router, "_run_audio_analysis", run_analysis)

    response = asyncio.run(audio_router.analyze_audio(_beats_only_request(), state))

    assert planned_requests[0].detect_beats is True
    assert response.bpm == 132.0
    assert (
        getattr(response.stage_receipts["beats"], fingerprint_field)
        == expected_fingerprint
    )
    assert (
        getattr(response.stage_receipts["beats"], fingerprint_field)
        != mismatched_value
    )


def test_optional_embedding_runs_after_final_commit_and_cannot_change_receipts(
    monkeypatch,
    tmp_path,
) -> None:
    audio_router = importlib.import_module("backend.routers.audio_router")
    audio = tmp_path / "embedding-order.wav"
    audio.write_bytes(b"audio")
    state = _ReceiptState(_clip(audio))
    _install_quiet_dependencies(monkeypatch, audio_router, state)
    monkeypatch.setattr(
        audio_router,
        "_run_audio_analysis",
        lambda *_args, **_kwargs: _beats_payload(),
    )

    async def record_embedding(**_kwargs):
        final_write = state.persisted_history[-1]
        assert final_write["stage_receipts"]["beats"]["status"] == "completed"
        state.timeline.append(("embedding", None))

    monkeypatch.setattr(
        audio_router,
        "_store_audio_embedding_in_brain_cache",
        record_embedding,
    )

    response = asyncio.run(audio_router.analyze_audio(_beats_only_request(), state))

    final_completed_persist = max(
        index
        for index, row in enumerate(state.timeline)
        if row[0] == "persist"
        and row[1]["stage_receipts"]["beats"]["status"] == "completed"
    )
    embedding_index = next(
        index for index, row in enumerate(state.timeline) if row[0] == "embedding"
    )
    terminal_sse = max(
        index
        for index, row in enumerate(state.timeline)
        if row[0] == "event" and row[1][1].get("percent") == 100
    )
    assert final_completed_persist < terminal_sse < embedding_index
    assert response.analysis_status == "completed"
    assert response.stage_receipts["beats"].status == "completed"


def test_force_beats_only_preserves_unrequested_durable_truth_and_scope(
    monkeypatch,
    tmp_path,
) -> None:
    from backend.schemas.audio_schemas import AudioAnalyzeRequest
    from pb_studio.core.stage_receipts import (
        create_stage_receipt,
        receipt_to_dict,
        transition_stage_receipt,
    )

    audio_router = importlib.import_module("backend.routers.audio_router")
    audio = tmp_path / "request-scope.wav"
    audio.write_bytes(b"audio")
    cache = _beats_payload()
    cache["structure_segments"] = [
        {"start_time": 0.0, "end_time": 30.0, "label": "verse"}
    ]
    structure = transition_stage_receipt(
        transition_stage_receipt(
            create_stage_receipt("structure", requested=True),
            "running",
        ),
        "completed",
        artifact_ref="ai_data_json.structure_segments",
        artifact=cache["structure_segments"],
    )
    failed_key = transition_stage_receipt(
        transition_stage_receipt(
            create_stage_receipt("key", requested=True),
            "running",
        ),
        "failed",
        error_code="legacy_key_failure",
        error_message="preserve this exact error",
    )
    original_structure = receipt_to_dict(structure)
    original_key = receipt_to_dict(failed_key)
    cache["_stage_receipts"] = {
        "structure": original_structure,
        "key": original_key,
    }
    cache["_stage_status"] = {
        "structure": "completed",
        "key": "failed",
    }
    cache["_stage_errors"] = {"key": "preserve this exact error"}
    state = _ReceiptState(_clip(audio), cache)
    _install_quiet_dependencies(monkeypatch, audio_router, state)
    monkeypatch.setattr(
        audio_router,
        "_run_audio_analysis",
        lambda *_args, **_kwargs: _beats_payload(bpm=131.0),
    )

    response = asyncio.run(
        audio_router.analyze_audio(
            AudioAnalyzeRequest(
                clip_id=7,
                detect_beats=True,
                detect_structure=False,
                spectral_analysis=False,
                detect_key=False,
                force=True,
            ),
            state,
        )
    )

    final = state.persisted_history[-1]
    assert final["stage_receipts"]["structure"] == original_structure
    assert final["stage_receipts"]["key"] == original_key
    assert final["stage_status"]["structure"] == "completed"
    assert final["stage_status"]["key"] == "failed"
    assert final["stage_errors"]["key"] == "preserve this exact error"
    assert response.analysis_status == "completed"


def test_project_switch_cancellation_during_bound_embedding_keeps_completed_boundary(
    monkeypatch,
    tmp_path,
) -> None:
    audio_router = importlib.import_module("backend.routers.audio_router")
    audio = tmp_path / "embedding-cancel.wav"
    audio.write_bytes(b"audio")
    state = _ReceiptState(_clip(audio))
    _install_quiet_dependencies(monkeypatch, audio_router, state)
    monkeypatch.setattr(
        audio_router,
        "_run_audio_analysis",
        lambda *_args, **_kwargs: _beats_payload(),
    )
    embedding_started = asyncio.Event()

    async def blocking_embedding(**_kwargs):
        assert state.operation_active is True
        state.timeline.append(("embedding", None))
        embedding_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            state.timeline.append(("embedding-cancelled", None))
            raise
        state.timeline.append(("cache-store", None))

    monkeypatch.setattr(
        audio_router,
        "_store_audio_embedding_in_brain_cache",
        blocking_embedding,
    )
    async def scenario():
        task = asyncio.create_task(
            audio_router.analyze_audio(_beats_only_request(), state)
        )
        await asyncio.wait_for(embedding_started.wait(), timeout=2.0)
        state.is_project_context_current = lambda _context: False
        state.timeline.append(("project-switch", None))
        task.cancel()
        return await task

    response = asyncio.run(scenario())

    assert state.persisted_history[-1]["analysis_status"] == "completed"
    assert response.analysis_status == "completed"
    statuses = [
        row[1][1].get("status")
        for row in state.timeline
        if row[0] == "event"
    ]
    assert "completed" in statuses
    assert "interrupted" not in statuses
    assert any(row[0] == "embedding-cancelled" for row in state.timeline)
    assert not any(row[0] == "cache-store" for row in state.timeline)


def test_missing_file_replaces_requested_cached_completion_with_fresh_failure(
    monkeypatch,
    tmp_path,
) -> None:
    from backend.schemas.audio_schemas import AudioAnalyzeRequest
    from pb_studio.core.stage_receipts import (
        create_stage_receipt,
        receipt_to_dict,
        transition_stage_receipt,
    )

    audio_router = importlib.import_module("backend.routers.audio_router")
    missing = tmp_path / "removed-after-cache.wav"
    cache = _beats_payload()
    cache["structure_segments"] = [
        {"start_time": 0.0, "end_time": 30.0, "label": "verse"}
    ]
    cache["key"] = "C major"
    completed_beats = transition_stage_receipt(
        transition_stage_receipt(
            create_stage_receipt("beats", requested=True),
            "running",
        ),
        "completed",
        artifact_ref="ai_data_json.beats_json",
        artifact=cache["beats"],
    )
    completed_structure = transition_stage_receipt(
        transition_stage_receipt(
            create_stage_receipt("structure", requested=True),
            "running",
        ),
        "completed",
        artifact_ref="ai_data_json.structure_segments",
        artifact=cache["structure_segments"],
    )
    completed_key = transition_stage_receipt(
        transition_stage_receipt(
            create_stage_receipt("key", requested=True),
            "running",
        ),
        "completed",
        artifact_ref="audio_clips.key",
        artifact=cache["key"],
    )
    original_beats = receipt_to_dict(completed_beats)
    original_structure = receipt_to_dict(completed_structure)
    original_key = receipt_to_dict(completed_key)
    cache["_stage_receipts"] = {
        "beats": original_beats,
        "structure": original_structure,
        "key": original_key,
    }
    cache["_stage_status"] = {
        "beats": "completed",
        "structure": "completed",
        "key": "completed",
    }
    state = _ReceiptState(_clip(missing), cache)
    _install_quiet_dependencies(monkeypatch, audio_router, state)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            audio_router.analyze_audio(
                AudioAnalyzeRequest(
                    clip_id=7,
                    detect_beats=True,
                    detect_structure=True,
                    spectral_analysis=False,
                    detect_key=False,
                ),
                state,
            )
        )

    assert exc_info.value.status_code == 422
    final = state.persisted_history[-1]
    assert final["analysis_status"] == "failed"
    assert final["stage_receipts"]["beats"]["status"] == "failed"
    assert final["stage_receipts"]["beats"]["error_code"] == "media_missing"
    assert final["stage_receipts"]["beats"] != original_beats
    assert final["stage_receipts"]["structure"]["status"] == "failed"
    assert final["stage_receipts"]["structure"]["error_code"] == "media_missing"
    assert final["stage_receipts"]["structure"] != original_structure
    assert final["stage_receipts"]["key"] == original_key
    terminal = [row[1][1] for row in state.timeline if row[0] == "event"][-1]
    assert terminal["status"] == "failed"
    assert terminal["stage_receipts"]["beats"]["status"] == "failed"


def test_late_global_failure_uses_persisted_partial_status_for_sse(
    monkeypatch,
    tmp_path,
) -> None:
    from backend.schemas.audio_schemas import AudioAnalyzeRequest

    audio_router = importlib.import_module("backend.routers.audio_router")
    audio = tmp_path / "late-global-failure.wav"
    audio.write_bytes(b"audio")
    state = _ReceiptState(_clip(audio))
    _install_quiet_dependencies(monkeypatch, audio_router, state)

    def fail_after_beats(
        _path,
        clip_id,
        _request,
        _stems,
        _loop,
        on_stage_checkpoint=None,
    ):
        on_stage_checkpoint("beats", _beats_payload(clip_id))
        raise RuntimeError("late global failure")

    monkeypatch.setattr(audio_router, "_run_audio_analysis", fail_after_beats)

    with pytest.raises(HTTPException):
        asyncio.run(
            audio_router.analyze_audio(
                AudioAnalyzeRequest(
                    clip_id=7,
                    detect_beats=True,
                    detect_structure=True,
                    spectral_analysis=False,
                    detect_key=False,
                ),
                state,
            )
        )

    final = state.persisted_history[-1]
    assert final["analysis_status"] == "partial"
    assert final["stage_receipts"]["beats"]["status"] == "completed"
    assert final["stage_receipts"]["structure"]["status"] == "failed"
    terminal = [row[1][1] for row in state.timeline if row[0] == "event"][-1]
    assert terminal["status"] == "partial"
