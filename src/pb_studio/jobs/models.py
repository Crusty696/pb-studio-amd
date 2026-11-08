"""T010 isolated Q1/Q2/Q3 state contracts; no dispatch or persistence here."""
from __future__ import annotations

from dataclasses import dataclass, replace
import re
from uuid import UUID


class TransitionError(ValueError):
    """Illegal transition, stale revision or missing authoritative guard."""


_MAX_INT64 = 2**63 - 1
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def _uuid(value: str) -> str:
    try:
        normalized = str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("valid UUID required") from exc
    if value != normalized:
        raise ValueError("canonical UUID required")
    return normalized


def _revision(value: int) -> None:
    if type(value) is not int or not 0 <= value <= _MAX_INT64:
        raise ValueError("nonnegative int64 revision required")


@dataclass(frozen=True)
class ProjectIdentity:
    project_id: int
    catalog_uuid: str
    file_uuid: str
    canonical_root: str
    runtime_epoch: int

    def __post_init__(self) -> None:
        if (type(self.project_id) is not int or not 0 < self.project_id <= _MAX_INT64
                or not isinstance(self.canonical_root, str) or not self.canonical_root):
            raise ValueError("invalid project context")
        _revision(self.runtime_epoch)
        if _uuid(self.catalog_uuid) != _uuid(self.file_uuid):
            raise ValueError("catalog/file project UUID mismatch")

    @property
    def project_uuid(self) -> str:
        return _uuid(self.catalog_uuid)


@dataclass(frozen=True)
class ProductionBatch:
    batch_uuid: str
    project: ProjectIdentity
    revision: int
    ordered_job_uuids: tuple[str, ...]
    paused: bool = False

    def __post_init__(self) -> None:
        _uuid(self.batch_uuid)
        _revision(self.revision)
        normalized = tuple(_uuid(value) for value in self.ordered_job_uuids)
        if len(normalized) != len(set(normalized)):
            raise ValueError("duplicate batch job UUID")


@dataclass(frozen=True)
class LogicalJobSnapshot:
    job_uuid: str
    project: ProjectIdentity
    state: str
    state_revision: int
    terminal_event_uuid: str | None = None
    terminal_evidence_kind: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.job_uuid)
        if (not isinstance(self.project, ProjectIdentity)
                or self.state not in _JOB and self.state not in _JOB_TERMINAL):
            raise ValueError("invalid job identity or state")
        _revision(self.state_revision)
        if (self.terminal_event_uuid is None) != (self.terminal_evidence_kind is None):
            raise ValueError("terminal event identity/kind must be paired")
        if self.terminal_event_uuid is not None:
            _uuid(self.terminal_event_uuid)
            if (self.state not in _JOB_TERMINAL
                    or self.terminal_evidence_kind not in _JOB_TERMINAL_KINDS):
                raise ValueError("terminal event invalid for job state")


@dataclass(frozen=True)
class JobTerminalEvidence:
    """Identity fixture for one durable job-terminal domain event."""

    kind: str
    event_uuid: str
    job_uuid: str
    project_uuid: str

    def __post_init__(self) -> None:
        if self.kind not in _JOB_TERMINAL_KINDS:
            raise ValueError("unknown job-terminal evidence kind")
        _uuid(self.event_uuid)
        _uuid(self.job_uuid)
        _uuid(self.project_uuid)


@dataclass(frozen=True)
class AttemptIdentity:
    attempt_uuid: str
    job_uuid: str
    endpoint_id: str
    prompt_uuid: str
    state: str
    state_revision: int
    terminal_receipt_sha256: str | None = None
    terminal_receipt_kind: str | None = None
    cancel_intent: bool = False

    def __post_init__(self) -> None:
        _uuid(self.attempt_uuid)
        _uuid(self.job_uuid)
        _uuid(self.prompt_uuid)
        if (not isinstance(self.endpoint_id, str) or not self.endpoint_id
                or self.state not in _ATTEMPT and self.state not in _ATTEMPT_TERMINAL):
            raise ValueError("invalid attempt identity or state")
        _revision(self.state_revision)
        if type(self.cancel_intent) is not bool:
            raise ValueError("invalid cancel intent")
        if self.terminal_receipt_sha256 is not None:
            if (self.state not in _ATTEMPT_TERMINAL
                    or not _SHA256_RE.fullmatch(self.terminal_receipt_sha256)):
                raise ValueError("invalid terminal receipt hash")
        if (self.terminal_receipt_kind is None) != (self.terminal_receipt_sha256 is None):
            raise ValueError("terminal receipt kind/hash must be paired")
        if (self.terminal_receipt_kind is not None
                and self.terminal_receipt_kind not in _BOUND_ATTEMPT_EVIDENCE):
            raise ValueError("invalid terminal receipt kind")


@dataclass(frozen=True)
class AttemptReceiptEvidence:
    """Receipt identity fixture; source authority is checked by a later adapter."""

    kind: str
    attempt_uuid: str
    job_uuid: str
    endpoint_id: str
    prompt_uuid: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        if self.kind not in _BOUND_ATTEMPT_EVIDENCE:
            raise ValueError("unknown receipt kind")
        _uuid(self.attempt_uuid)
        _uuid(self.job_uuid)
        _uuid(self.prompt_uuid)
        if (not isinstance(self.endpoint_id, str) or not self.endpoint_id
                or not isinstance(self.receipt_sha256, str)
                or not _SHA256_RE.fullmatch(self.receipt_sha256)):
            raise ValueError("invalid receipt binding or hash")


@dataclass(frozen=True)
class ArtifactReceipt:
    artifact_uuid: str
    origin_attempt_uuid: str
    slot_id: str
    ordinal: int
    state: str
    state_revision: int
    last_confirmed_phase: str | None = None
    user_wait_reason: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.artifact_uuid)
        _uuid(self.origin_attempt_uuid)
        if (not isinstance(self.slot_id, str) or not self.slot_id
                or type(self.ordinal) is not int or not 0 <= self.ordinal <= _MAX_INT64
                or self.state not in _ARTIFACT and self.state not in _ARTIFACT_TERMINAL):
            raise ValueError("invalid artifact identity or state")
        _revision(self.state_revision)
        if self.state == "repair_pending":
            if self.last_confirmed_phase not in _ARTIFACT or self.last_confirmed_phase == "repair_pending":
                raise ValueError("repair origin phase required")
        elif self.last_confirmed_phase is not None:
            raise ValueError("repair origin only valid during repair")
        if self.user_wait_reason not in (None, "import_not_requested", "analysis_not_requested"):
            raise ValueError("invalid user wait reason")


_JOB = {
    "planned": {"pending": {"intent_persisted"}},
    "pending": {"waiting_for_provider": {"provider_unavailable"},
                "waiting_for_resources": {"admission_unavailable"},
                "active": {"outbox_durable", "local_import_claim_durable"},
                "needs_decision": {"restore_uncertain"}},
    "waiting_for_provider": {"pending": {"provider_rechecked"},
                             "needs_decision": {"restore_uncertain"}},
    "waiting_for_resources": {"pending": {"resources_rechecked"},
                              "needs_decision": {"restore_uncertain"}},
    "active": {"awaiting_import": {"mandatory_output_waiting"},
               "needs_decision": {"unresolved_receipt"},
               "available_partial": {"imported_analysis_missing"},
               "ready": {"mandatory_receipts_confirmed"},
               "retry_wait": {"definitive_retryable_failure"}},
    "available_partial": {"awaiting_import": {"mandatory_output_waiting"},
                          "active": {"analysis_continuation_intent"},
                          "needs_decision": {"unresolved_receipt"},
                          "ready": {"mandatory_receipts_confirmed"}},
    "awaiting_import": {"active": {"local_import_intent"}},
    "needs_decision": {"active": {"authoritative_reconciliation_existing_attempt",
                                  "authoritative_reconciliation_existing_import"}},
    "retry_wait": {"pending": {"backoff_complete"},
                   "needs_decision": {"restore_uncertain"}},
}
_JOB_TERMINAL = {"ready", "failed", "cancelled", "obsolete"}
_JOB_TERMINAL_KINDS = {
    "mandatory_receipts_confirmed", "cancel_intent", "source_plan_obsolete",
    "definitive_failure",
}
_JOB_NONTERMINAL = set(_JOB)

_ATTEMPT = {
    "prepared": {"dispatching": {"durable_outbox_and_lease"},
                 "submission_unknown": {"restore_send_uncertain"},
                 "cancelled": {"proved_non_send"}},
    "dispatching": {"queued": {"authoritative_accept"},
                    "submission_unknown": {"send_outcome_unknown"},
                    "rejected": {"authoritative_not_accepted", "proved_non_send"}},
    "submission_unknown": {"queued": {"authoritative_queued"},
                           "running": {"authoritative_running"},
                           "execution_succeeded": {"authoritative_success"},
                           "execution_failed": {"authoritative_failure"},
                           "cancelled": {"authoritative_cancelled"},
                           "rejected": {"authoritative_not_accepted", "proved_non_send"},
                           "needs_decision": {"bounded_reconciliation_exhausted"}},
    "needs_decision": {"queued": {"authoritative_queued"},
                       "running": {"authoritative_running"},
                       "execution_succeeded": {"authoritative_success"},
                       "execution_failed": {"authoritative_failure"},
                       "cancelled": {"authoritative_cancelled"},
                       "rejected": {"authoritative_not_accepted", "proved_non_send"}},
    "queued": {"running": {"authoritative_running"},
               "cancel_requested": {"own_cancel_intent"},
               "needs_decision": {"bounded_reconciliation_exhausted"},
               "execution_succeeded": {"authoritative_success"},
               "execution_failed": {"authoritative_failure"},
               "cancelled": {"authoritative_cancelled"}},
    "running": {"cancel_requested": {"own_cancel_intent"},
                "needs_decision": {"bounded_reconciliation_exhausted"},
                "execution_succeeded": {"authoritative_success"},
                "execution_failed": {"authoritative_failure"},
                "cancelled": {"authoritative_cancelled"}},
    "cancel_requested": {"cancelled": {"authoritative_cancelled"},
                         "needs_decision": {"bounded_reconciliation_exhausted"},
                         "execution_succeeded": {"authoritative_success"},
                         "execution_failed": {"authoritative_failure"}},
}
_ATTEMPT_TERMINAL = {"rejected", "execution_succeeded", "execution_failed", "cancelled"}
_BOUND_ATTEMPT_EVIDENCE = {
    "authoritative_accept", "authoritative_queued", "authoritative_running",
    "authoritative_success", "authoritative_failure", "authoritative_cancelled",
    "authoritative_not_accepted", "proved_non_send",
}

_ARTIFACT = {
    "discovered": {"staging": {"owned_staging_claim"}},
    "staging": {"validating": {"writer_complete"}},
    "validating": {"validated": {"full_decode_qc"},
                   "rejected": {"validation_failure"}},
    "validated": {"awaiting_import": {"import_not_requested"},
                  "published": {"durable_publish"}},
    "awaiting_import": {"published": {"approved_import_and_revalidated"}},
    "published": {"catalog_committed": {"canonical_import_claim"}},
    "catalog_committed": {"analysis_pending": {"analysis_intent"},
                          "locally_cancelled": {"cancel_after_commit", "obsolete_after_commit"}},
    "analysis_pending": {"vector_pending": {"required_vector_pending"},
                         "completed": {"no_vector_required_and_complete"},
                         "locally_cancelled": {"cancel_after_commit", "obsolete_after_commit"}},
    "vector_pending": {"completed": {"vector_add_receipt"},
                       "locally_cancelled": {"cancel_after_commit", "obsolete_after_commit"}},
    "repair_pending": {},
}
for _phase in ("discovered", "staging", "validating", "validated", "awaiting_import", "published"):
    _ARTIFACT[_phase]["quarantined"] = {"cancel_or_obsolete_owned_output"}
for _phase in ("discovered", "staging", "validating", "validated", "awaiting_import", "published",
               "catalog_committed", "analysis_pending", "vector_pending"):
    _ARTIFACT[_phase]["repair_pending"] = {"partial_local_commit"}
_ARTIFACT_TERMINAL = {"completed", "rejected", "quarantined", "locally_cancelled"}


def _advance(record, target: str, expected_revision: int, evidence: str,
             graph: dict[str, dict[str, set[str]]], terminal: set[str]):
    if type(expected_revision) is not int or record.state_revision != expected_revision:
        raise TransitionError("state revision conflict")
    if record.state in terminal:
        raise TransitionError("terminal state requires a bound event for deduplication")
    if evidence not in graph.get(record.state, {}).get(target, set()):
        raise TransitionError("transition or evidence not allowed")
    if record.state_revision == _MAX_INT64:
        raise TransitionError("state revision overflow")
    return replace(record, state=target, state_revision=record.state_revision + 1)


def transition_job(record: LogicalJobSnapshot, target: str, *, expected_revision: int,
                   evidence: str | JobTerminalEvidence) -> LogicalJobSnapshot:
    terminal_evidence = isinstance(evidence, JobTerminalEvidence)
    if terminal_evidence:
        if (evidence.job_uuid != record.job_uuid
                or evidence.project_uuid != record.project.project_uuid):
            raise TransitionError("job-terminal event identity mismatch")
        kind = evidence.kind
    elif isinstance(evidence, str):
        kind = evidence
    else:
        raise TransitionError("invalid job evidence")
    if record.state in _JOB_TERMINAL:
        if type(expected_revision) is not int or record.state_revision != expected_revision:
            raise TransitionError("state revision conflict")
        if (target == record.state and terminal_evidence
                and evidence.event_uuid == record.terminal_event_uuid
                and kind == record.terminal_evidence_kind):
            return record
        raise TransitionError("terminal job event conflict")
    if target in _JOB_TERMINAL and not terminal_evidence:
        raise TransitionError("bound terminal job event required")
    if terminal_evidence and target not in _JOB_TERMINAL:
        raise TransitionError("terminal event cannot drive nonterminal job")
    if record.state in _JOB_NONTERMINAL and target in {"cancelled", "obsolete", "failed"}:
        expected = {"cancelled": "cancel_intent", "obsolete": "source_plan_obsolete",
                    "failed": "definitive_failure"}[target]
        if kind != expected:
            raise TransitionError("terminal guard missing")
        if type(expected_revision) is not int or record.state_revision != expected_revision:
            raise TransitionError("state revision conflict")
        if record.state_revision == _MAX_INT64:
            raise TransitionError("state revision overflow")
        return replace(record, state=target, state_revision=record.state_revision + 1,
                       terminal_event_uuid=evidence.event_uuid,
                       terminal_evidence_kind=kind)
    advanced = _advance(record, target, expected_revision, kind, _JOB, _JOB_TERMINAL)
    if target in _JOB_TERMINAL:
        return replace(advanced, terminal_event_uuid=evidence.event_uuid,
                       terminal_evidence_kind=kind)
    return advanced


def transition_attempt(record: AttemptIdentity, target: str, *, expected_revision: int,
                       evidence: str | AttemptReceiptEvidence) -> AttemptIdentity:
    if isinstance(evidence, AttemptReceiptEvidence):
        if ((evidence.attempt_uuid, evidence.job_uuid, evidence.endpoint_id,
             evidence.prompt_uuid) !=
            (record.attempt_uuid, record.job_uuid, record.endpoint_id, record.prompt_uuid)):
            raise TransitionError("receipt does not bind this attempt")
        kind = evidence.kind
    else:
        kind = evidence
    if kind in _BOUND_ATTEMPT_EVIDENCE and not isinstance(evidence, AttemptReceiptEvidence):
        raise TransitionError("bound receipt required")
    if record.state in _ATTEMPT_TERMINAL and target == record.state:
        if type(expected_revision) is not int or expected_revision != record.state_revision:
            raise TransitionError("state revision conflict")
        if (not isinstance(evidence, AttemptReceiptEvidence)
                or evidence.receipt_sha256 != record.terminal_receipt_sha256
                or evidence.kind != record.terminal_receipt_kind):
            raise TransitionError("conflicting terminal receipt")
        return record
    advanced = _advance(record, target, expected_revision, kind, _ATTEMPT,
                        _ATTEMPT_TERMINAL)
    if target in _ATTEMPT_TERMINAL:
        if not isinstance(evidence, AttemptReceiptEvidence):
            raise TransitionError("terminal receipt required")
        return replace(advanced, terminal_receipt_sha256=evidence.receipt_sha256,
                       terminal_receipt_kind=evidence.kind)
    if target == "cancel_requested":
        return replace(advanced, cancel_intent=True)
    return advanced


def transition_artifact(record: ArtifactReceipt, target: str, *, expected_revision: int,
                        evidence: str) -> ArtifactReceipt:
    if (record.state == "catalog_committed" and target == "catalog_committed"
            and evidence == "analysis_not_requested"):
        if type(expected_revision) is not int or expected_revision != record.state_revision:
            raise TransitionError("state revision conflict")
        if record.user_wait_reason == "analysis_not_requested":
            return record
        if record.state_revision == _MAX_INT64:
            raise TransitionError("state revision overflow")
        return replace(record, state_revision=record.state_revision + 1,
                       user_wait_reason="analysis_not_requested")
    if record.state == "repair_pending":
        if type(expected_revision) is not int or expected_revision != record.state_revision:
            raise TransitionError("state revision conflict")
        if target != record.last_confirmed_phase or evidence != "recovery_verified":
            raise TransitionError("repair can only return to confirmed phase")
        if record.state_revision == _MAX_INT64:
            raise TransitionError("state revision overflow")
        return replace(record, state=target, state_revision=record.state_revision + 1,
                       last_confirmed_phase=None)
    if target == "repair_pending":
        if type(expected_revision) is not int or expected_revision != record.state_revision:
            raise TransitionError("state revision conflict")
        if (evidence not in _ARTIFACT.get(record.state, {}).get(target, set())
                or record.state_revision == _MAX_INT64):
            raise TransitionError("repair transition not allowed")
        return replace(record, state=target, state_revision=record.state_revision + 1,
                       last_confirmed_phase=record.state)
    advanced = _advance(record, target, expected_revision, evidence, _ARTIFACT,
                        _ARTIFACT_TERMINAL)
    if target == "awaiting_import":
        return replace(advanced, user_wait_reason="import_not_requested")
    if target in {"published", "analysis_pending"}:
        return replace(advanced, user_wait_reason=None)
    return advanced
