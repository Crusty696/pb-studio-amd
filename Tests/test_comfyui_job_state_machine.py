"""T010 pure state contract; no DB, network, backend or ComfyUI runtime."""
from dataclasses import replace
from uuid import uuid4

import pytest

from pb_studio.jobs.models import (
    ProjectIdentity, ProductionBatch, LogicalJobSnapshot, AttemptIdentity, ArtifactReceipt,
    AttemptReceiptEvidence, JobTerminalEvidence, TransitionError,
    transition_job, transition_attempt, transition_artifact,
)
from pb_studio.jobs.wire import parse_job_receipt, parse_provider_job_event


def identity():
    value = str(uuid4())
    return ProjectIdentity(project_id=7, catalog_uuid=value, file_uuid=value,
                           canonical_root="C:/project", runtime_epoch=11)


def job(state="planned"):
    return LogicalJobSnapshot(job_uuid=str(uuid4()), project=identity(),
                              state=state, state_revision=0)


def attempt(state="prepared"):
    return AttemptIdentity(attempt_uuid=str(uuid4()), job_uuid=str(uuid4()),
                           endpoint_id="local", prompt_uuid=str(uuid4()),
                           state=state, state_revision=0)


def artifact(state="discovered"):
    return ArtifactReceipt(artifact_uuid=str(uuid4()),
                           origin_attempt_uuid=str(uuid4()), slot_id="video", ordinal=0,
                           state=state, state_revision=0)


def receipt(record, kind, digest="a" * 64):
    return AttemptReceiptEvidence(kind=kind, attempt_uuid=record.attempt_uuid,
                                  job_uuid=record.job_uuid, endpoint_id=record.endpoint_id,
                                  prompt_uuid=record.prompt_uuid, receipt_sha256=digest)


def job_terminal_event(record, kind, event_uuid=None):
    return JobTerminalEvidence(kind=kind, event_uuid=event_uuid or str(uuid4()),
                               job_uuid=record.job_uuid,
                               project_uuid=record.project.project_uuid)


def test_project_identity_reuses_catalog_uuid_not_runtime_epoch():
    original = identity()
    assert original.project_uuid == original.catalog_uuid
    assert replace(original, runtime_epoch=12).project_uuid == original.project_uuid
    with pytest.raises(ValueError):
        replace(original, file_uuid=str(uuid4()))


def test_job_transition_closed_terminal_and_progress_not_ready():
    pending = transition_job(job(), "pending", expected_revision=0, evidence="intent_persisted")
    assert pending.state_revision == 1
    with pytest.raises(TransitionError):
        transition_job(pending, "ready", expected_revision=1, evidence="progress")
    with pytest.raises(TransitionError):
        transition_job(pending, "cancelled", expected_revision=1, evidence="cancel_intent")
    terminal_event = job_terminal_event(pending, "cancel_intent")
    cancelled = transition_job(pending, "cancelled", expected_revision=1,
                               evidence=terminal_event)
    assert transition_job(cancelled, "cancelled", expected_revision=2,
                          evidence=terminal_event) == cancelled
    with pytest.raises(TransitionError):
        transition_job(cancelled, "cancelled", expected_revision=2,
                       evidence="same_event")
    with pytest.raises(TransitionError):
        transition_job(cancelled, "cancelled", expected_revision=2,
                       evidence=job_terminal_event(pending, "cancel_intent"))
    with pytest.raises(TransitionError):
        transition_job(pending, "cancelled", expected_revision=1,
                       evidence=replace(terminal_event, project_uuid=str(uuid4())))
    with pytest.raises(TransitionError):
        transition_job(cancelled, "ready", expected_revision=2, evidence="remote_success")
    with pytest.raises(TransitionError):
        transition_job(pending, "active", expected_revision=0, evidence="outbox_durable")


def test_waiting_for_user_is_nonterminal_and_requires_explicit_intent():
    waiting = job("awaiting_import")
    with pytest.raises(TransitionError):
        transition_job(waiting, "failed", expected_revision=0, evidence="timeout")
    active = transition_job(waiting, "active", expected_revision=0, evidence="local_import_intent")
    assert active.state == "active"


def test_ready_requires_bound_terminal_event_and_cannot_reactivate():
    active = job("active")
    with pytest.raises(TransitionError):
        transition_job(active, "ready", expected_revision=0,
                       evidence="mandatory_receipts_confirmed")
    event = job_terminal_event(active, "mandatory_receipts_confirmed")
    ready = transition_job(active, "ready", expected_revision=0, evidence=event)
    assert ready.terminal_event_uuid == event.event_uuid
    assert transition_job(ready, "ready", expected_revision=1, evidence=event) == ready
    with pytest.raises(TransitionError):
        transition_job(ready, "active", expected_revision=1, evidence="backoff_complete")


def test_unknown_submission_cannot_be_rejected_by_empty_history():
    unknown = attempt("submission_unknown")
    for evidence in ("empty_history", "proxy_400", "timeout"):
        with pytest.raises(TransitionError):
            transition_attempt(unknown, "rejected", expected_revision=0, evidence=evidence)
    with pytest.raises(TransitionError):
        transition_attempt(unknown, "rejected", expected_revision=0,
                           evidence="authoritative_not_accepted")
    rejected = transition_attempt(unknown, "rejected", expected_revision=0,
                                  evidence=receipt(unknown, "authoritative_not_accepted"))
    assert rejected.state == "rejected"
    with pytest.raises(TransitionError):
        transition_attempt(rejected, "queued", expected_revision=1, evidence="late_progress")


def test_early_remote_observation_does_not_skip_dispatching():
    with pytest.raises(TransitionError):
        transition_attempt(attempt(), "running", expected_revision=0,
                           evidence="remote_running")
    dispatching = transition_attempt(attempt(), "dispatching", expected_revision=0,
                                     evidence="durable_outbox_and_lease")
    assert dispatching.state == "dispatching"


def test_remote_cancel_request_is_not_terminal_confirmation():
    requested = transition_attempt(attempt("running"), "cancel_requested",
                                   expected_revision=0, evidence="own_cancel_intent")
    assert requested.cancel_intent is True
    with pytest.raises(TransitionError):
        transition_attempt(requested, "cancelled", expected_revision=1,
                           evidence="http_200")
    uncertain = transition_attempt(requested, "needs_decision", expected_revision=1,
                                   evidence="bounded_reconciliation_exhausted")
    assert uncertain.state == "needs_decision"
    assert uncertain.cancel_intent is True


def test_artifact_progress_is_not_catalog_commit_or_ready():
    discovered = artifact()
    with pytest.raises(TransitionError):
        transition_artifact(discovered, "catalog_committed", expected_revision=0,
                            evidence="progress")
    staged = transition_artifact(discovered, "staging", expected_revision=0,
                                 evidence="owned_staging_claim")
    assert staged.state == "staging"


def test_batch_keeps_project_and_ordered_unique_jobs_without_runtime_uuid():
    first, second = str(uuid4()), str(uuid4())
    batch = ProductionBatch(batch_uuid=str(uuid4()), project=identity(),
                            revision=0, ordered_job_uuids=(first, second), paused=True)
    assert batch.ordered_job_uuids == (first, second)
    assert replace(batch, project=replace(batch.project, runtime_epoch=99)).project.project_uuid == batch.project.project_uuid
    with pytest.raises(ValueError):
        replace(batch, ordered_job_uuids=(first, first))


def test_artifact_waiting_and_cancel_after_catalog_commit():
    waiting = transition_artifact(artifact("validated"), "awaiting_import",
                                  expected_revision=0, evidence="import_not_requested")
    with pytest.raises(TransitionError):
        transition_artifact(waiting, "rejected", expected_revision=1, evidence="timeout")
    committed = artifact("catalog_committed")
    assert transition_artifact(committed, "locally_cancelled", expected_revision=0,
                               evidence="cancel_after_commit").state == "locally_cancelled"
    with pytest.raises(TransitionError):
        transition_artifact(committed, "quarantined", expected_revision=0,
                            evidence="cancel_or_obsolete_owned_output")


def test_artifact_terminal_same_event_string_is_not_an_identity():
    completed = artifact("completed")
    with pytest.raises(TransitionError):
        transition_artifact(completed, "completed", expected_revision=0,
                            evidence="same_event")


def test_unknown_attempt_keeps_cancel_intent_out_of_retry_path():
    uncertain = attempt("needs_decision")
    with pytest.raises(TransitionError):
        transition_attempt(uncertain, "dispatching", expected_revision=0,
                           evidence="durable_outbox_and_lease")


@pytest.mark.parametrize("field,value", [
    ("job_uuid", "not-a-uuid"),
    ("state", "readyish"),
    ("state_revision", -1),
    ("state_revision", True),
    ("state_revision", 2**63),
])
def test_invalid_job_snapshot_cannot_enter_state_machine(field, value):
    with pytest.raises(ValueError):
        replace(job(), **{field: value})


@pytest.mark.parametrize("field,value", [
    ("attempt_uuid", "not-a-uuid"),
    ("job_uuid", "not-a-uuid"),
    ("prompt_uuid", "not-a-uuid"),
    ("endpoint_id", ""),
    ("state", "success"),
    ("state_revision", -1),
])
def test_invalid_attempt_identity_cannot_enter_state_machine(field, value):
    with pytest.raises(ValueError):
        replace(attempt(), **{field: value})


@pytest.mark.parametrize("field,value", [
    ("artifact_uuid", "not-a-uuid"),
    ("origin_attempt_uuid", "not-a-uuid"),
    ("slot_id", ""),
    ("ordinal", -1),
    ("state", "unknown"),
    ("state_revision", 2**63),
])
def test_invalid_artifact_receipt_cannot_enter_state_machine(field, value):
    with pytest.raises(ValueError):
        replace(artifact(), **{field: value})


def test_job_receipt_wire_rejects_missing_null_unknown_and_overflow():
    value = {
        "schema_version": 1, "request_id": str(uuid4()),
        "client_request_id": str(uuid4()), "project_uuid": str(uuid4()),
        "job_uuid": str(uuid4()), "state": "pending", "state_revision": 0,
        "store_generation_uuid": str(uuid4()),
    }
    assert parse_job_receipt(value).state == "pending"
    for patch in ({"state": "almost_ready"}, {"state": None},
                  {"state_revision": 2**63}, {"state_revision": True},
                  {"schema_version": 2}, {"job_uuid": None},
                  {"project_uuid": str(uuid4()).upper()}):
        with pytest.raises(ValueError):
            parse_job_receipt(value | patch)
    missing = value.copy()
    del missing["client_request_id"]
    with pytest.raises(ValueError):
        parse_job_receipt(missing)


def test_provider_event_wire_binds_identity_and_explicit_nullable_attempt():
    job_id = str(uuid4())
    value = {
        "schema_version": 1, "event_uuid": str(uuid4()),
        "store_generation_uuid": str(uuid4()), "job_change_seq": 0,
        "project_uuid": str(uuid4()), "entity_kind": "job",
        "entity_uuid": job_id, "entity_revision": 0,
        "job_uuid": job_id, "attempt_uuid": None, "state_revision": 0,
    }
    assert parse_provider_job_event(value).attempt_uuid is None
    for patch in ({"entity_kind": "other"}, {"entity_uuid": str(uuid4())},
                  {"attempt_uuid": "bad"}, {"job_change_seq": -1},
                  {"entity_revision": 2**63}, {"state_revision": None}):
        with pytest.raises(ValueError):
            parse_provider_job_event(value | patch)
    missing = value.copy()
    del missing["attempt_uuid"]
    with pytest.raises(ValueError):
        parse_provider_job_event(missing)


def test_repair_returns_only_to_last_persisted_artifact_phase():
    committed = artifact("catalog_committed")
    repair = transition_artifact(committed, "repair_pending", expected_revision=0,
                                 evidence="partial_local_commit")
    assert repair.last_confirmed_phase == "catalog_committed"
    with pytest.raises(TransitionError):
        transition_artifact(repair, "completed", expected_revision=1,
                            evidence="recovery_verified")
    restored = transition_artifact(repair, "catalog_committed", expected_revision=1,
                                   evidence="recovery_verified")
    assert restored.last_confirmed_phase is None


def test_remote_receipt_must_bind_exact_attempt_and_terminal_deduplicates_by_hash():
    unknown = attempt("submission_unknown")
    valid = receipt(unknown, "authoritative_success")
    for wrong in (replace(valid, attempt_uuid=str(uuid4())),
                  replace(valid, job_uuid=str(uuid4())),
                  replace(valid, endpoint_id="other"),
                  replace(valid, prompt_uuid=str(uuid4()))):
        with pytest.raises(TransitionError):
            transition_attempt(unknown, "execution_succeeded", expected_revision=0,
                               evidence=wrong)
    succeeded = transition_attempt(unknown, "execution_succeeded", expected_revision=0,
                                   evidence=valid)
    assert succeeded.terminal_receipt_sha256 == "a" * 64
    assert transition_attempt(succeeded, "execution_succeeded", expected_revision=1,
                              evidence=valid) == succeeded
    with pytest.raises(TransitionError):
        transition_attempt(succeeded, "execution_succeeded", expected_revision=1,
                           evidence=receipt(unknown, "authoritative_success", "b" * 64))
    with pytest.raises(TransitionError):
        transition_attempt(succeeded, "execution_succeeded", expected_revision=1,
                           evidence=receipt(unknown, "authoritative_failure"))
    with pytest.raises(TransitionError):
        transition_attempt(succeeded, "execution_failed", expected_revision=1,
                           evidence=receipt(unknown, "authoritative_failure"))


def test_catalog_commit_without_autoanalysis_persists_wait_reason_only():
    committed = artifact("catalog_committed")
    waiting = transition_artifact(committed, "catalog_committed", expected_revision=0,
                                  evidence="analysis_not_requested")
    assert waiting.state == "catalog_committed"
    assert waiting.user_wait_reason == "analysis_not_requested"
    assert waiting.state_revision == 1
    with pytest.raises(TransitionError):
        transition_artifact(waiting, "completed", expected_revision=1,
                            evidence="analysis_not_requested")
    active = transition_artifact(waiting, "analysis_pending", expected_revision=1,
                                 evidence="analysis_intent")
    assert active.user_wait_reason is None
