"""Durable Brain feedback logging across project state and global weights.

Each feedback operation is first written to an atomically replaced outbox file.
Recovery compares the complete affected weight-bucket snapshot, so a crash after
the weights commit cannot apply the same click twice.  The raw feedback event is
then inserted idempotently into the project state DB.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from .bridge_dimensions import BRIDGE_AXES
from .weight_store import WeightStore
from pb_studio.storage.recovery_barrier import recovery_write_operation

logger = logging.getLogger(__name__)

RATING_MAP: dict[str, tuple[float, float]] = {
    "perfect":   (2.0, 0.0),
    "fits":      (1.0, 0.0),
    "not_quite": (0.0, 1.0),
    "no_match":  (0.0, 2.0),
}

_OUTBOX_SCHEMA_VERSION = 1
_OUTBOX_LOCK = threading.RLock()
_MIN_AXIS_RELEVANCE = 0.05

_AUDIO_TRIGGER_AXES = {
    "beat_weight", "onset_weight", "kick_weight", "snare_weight",
    "hihat_weight", "energy_weight", "energy_threshold",
    "onset_sensitivity",
}
_LENGTH_AXES = {"min_clip_length", "max_clip_length"}
_MOTION_AXES = {
    "motion_match_weight", "scene_cut_weight", "pace_match_weight",
}
_SEMANTIC_AXES = {
    "brightness_match_weight", "color_temp_match_weight",
    "semantic_match_weight", "mood_match_weight",
}
_CONTEXT_LEVEL_WEIGHTS = {
    0: 0.25,
    1: 0.50,
    2: 0.60,
    3: 0.75,
    4: 0.85,
    5: 1.00,
}


class FeedbackOperationConflictError(ValueError):
    """A caller operation ID was reused with a different feedback payload."""


@dataclass(frozen=True)
class FeedbackLogResult:
    updated_buckets: int
    applied: bool


class FeedbackLogger:
    """Persist raw feedback and Beta-Bernoulli updates crash-consistently."""

    def __init__(
        self,
        *,
        weight_store: WeightStore,
        state_conn: sqlite3.Connection,
        outbox_path: Optional[str | Path] = None,
        fault_injector: Optional[Callable[[str], None]] = None,
    ):
        self.weights = weight_store
        self.state_conn = state_conn
        self.outbox_path = (
            Path(outbox_path)
            if outbox_path is not None
            else self._default_outbox_path(state_conn)
        )
        self.receipt_path = self.outbox_path.with_name("feedback_receipts.json")
        self._fault_injector = fault_injector

    def log_feedback(
        self,
        *,
        cut_id: int,
        rating: str,
        context_keys: list[str],
        assignments: list[dict],
        timestamp: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> int:
        return self.log_feedback_result(
            cut_id=cut_id,
            rating=rating,
            context_keys=context_keys,
            assignments=assignments,
            timestamp=timestamp,
            operation_id=operation_id,
        ).updated_buckets

    def lookup_feedback_result(
        self,
        *,
        operation_id: str,
        cut_id: int,
        rating: str,
    ) -> Optional[FeedbackLogResult]:
        """Return a durable prior result before current cut evidence is read."""
        if rating not in RATING_MAP:
            raise ValueError(f"unknown rating: {rating}")
        caller_operation_id = self._validate_client_operation_id(operation_id)
        if caller_operation_id is None:
            return None
        project_uuid = self._state_project_uuid(self.state_conn)
        request_fingerprint = self._request_fingerprint(
            project_uuid=project_uuid,
            cut_id=cut_id,
            rating=rating,
        )
        with _OUTBOX_LOCK:
            self._recover_pending_locked()
            return self._result_from_receipt(
                caller_operation_id,
                request_fingerprint,
            )

    @recovery_write_operation("brain-feedback")
    def log_feedback_result(
        self,
        *,
        cut_id: int,
        rating: str,
        context_keys: list[str],
        assignments: list[dict],
        timestamp: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> FeedbackLogResult:
        """Apply one feedback event once, even across process interruption."""
        if rating not in RATING_MAP:
            raise ValueError(f"unknown rating: {rating}")
        if not context_keys:
            context_keys = [""]

        caller_operation_id = self._validate_client_operation_id(operation_id)
        state_db_path = self._connection_path(self.state_conn)
        project_uuid = self._state_project_uuid(self.state_conn)
        request_fingerprint = self._request_fingerprint(
            project_uuid=project_uuid,
            cut_id=cut_id,
            rating=rating,
        )
        with _OUTBOX_LOCK:
            self._recover_pending_locked()
            if caller_operation_id is not None:
                receipt = self._result_from_receipt(
                    caller_operation_id,
                    request_fingerprint,
                )
                if receipt is not None:
                    return receipt
            if not assignments:
                raise ValueError(
                    "Cut has no relevant, available Brain feature evidence; "
                    "feedback was not applied"
                )

            alpha_delta, beta_delta = RATING_MAP[rating]
            ts = timestamp or self._unique_timestamp(self.state_conn)
            operation = {
                "schema_version": _OUTBOX_SCHEMA_VERSION,
                "operation_id": uuid.uuid4().hex,
                "event_uuid": str(uuid.uuid4()),
                "project_uuid": project_uuid,
                "caller_operation_id": caller_operation_id,
                "request_fingerprint": request_fingerprint,
                "stage": "prepared",
                "state_db_path": state_db_path,
                "cut_id": int(cut_id),
                "rating": rating,
                "alpha_delta": float(alpha_delta),
                "beta_delta": float(beta_delta),
                "context_keys": list(context_keys),
                "assignments": list(assignments),
                "feedback_count_before": self.weights.total_clicks(),
                "timestamp": ts,
                "before": self._snapshot_weights(
                    assignments,
                    alpha_delta=alpha_delta,
                    beta_delta=beta_delta,
                ),
            }
            self._write_outbox(operation)
            self._inject_fault("after_prepare")

            self._apply_weight_delta(operation)
            self._inject_fault("after_weights_commit")

            operation["stage"] = "weights_applied"
            self._write_outbox(operation)
            try:
                self._ensure_feedback_event(self.state_conn, operation)
            except LookupError:
                self._restore_weight_snapshot(operation)
                self._clear_outbox()
                raise
            self._inject_fault("after_event_insert")
            self._record_feedback_receipt(operation)
            self._clear_outbox()

        return FeedbackLogResult(
            updated_buckets=len(operation["before"]),
            applied=True,
        )

    def recover_pending(self) -> bool:
        """Complete or compensate one durable operation. Returns recovery work."""
        with _OUTBOX_LOCK:
            return self._recover_pending_locked()

    def _recover_pending_locked(self) -> bool:
        operation = self._read_outbox()
        if operation is None:
            return False
        self._validate_operation(operation)

        relation = self._weight_relation(operation)
        if relation == "before":
            self._apply_weight_delta(operation)
        elif relation != "after":
            raise RuntimeError(
                "Brain feedback outbox conflicts with current weights; "
                "automatic recovery refused"
            )

        operation["stage"] = "weights_applied"
        self._write_outbox(operation)

        target_conn, must_close = self._open_target_state(operation)
        if target_conn is None:
            self._restore_weight_snapshot(operation)
            self._clear_outbox()
            logger.warning(
                "Brain feedback %s compensated because project state DB is missing",
                operation["operation_id"],
            )
            return True
        try:
            try:
                self._ensure_feedback_event(target_conn, operation)
            except LookupError:
                self._restore_weight_snapshot(operation)
                logger.warning(
                    "Brain feedback %s compensated because cut %s no longer exists",
                    operation["operation_id"],
                    operation["cut_id"],
                )
            else:
                self._record_feedback_receipt(operation)
            self._clear_outbox()
            return True
        finally:
            if must_close:
                target_conn.close()

    def _snapshot_weights(
        self,
        assignments: list[dict],
        *,
        alpha_delta: float,
        beta_delta: float,
    ) -> list[dict]:
        snapshot: list[dict] = []
        seen: set[tuple[str, int, str]] = set()
        with self.weights._conn_lock:
            for assignment in assignments:
                axis = str(assignment.get("axis") or "")
                level = int(assignment.get("level", -1))
                key = str(assignment.get("key") or "")
                credit = float(assignment.get("credit", 0.0))
                identity = (axis, level, key)
                if (
                    axis not in BRIDGE_AXES
                    or level < 0
                    or level > 5
                    or not math.isfinite(credit)
                    or credit <= 0.0
                    or credit > 1.0
                    or identity in seen
                ):
                    raise ValueError(f"invalid feedback credit assignment: {assignment!r}")
                seen.add(identity)
                row = self.weights.conn.execute(
                    "SELECT positive_count, negative_count FROM axis_weights "
                    "WHERE axis=? AND context_level=? AND context_key=?",
                    identity,
                ).fetchone()
                snapshot.append({
                    "axis": axis,
                    "level": level,
                    "key": key,
                    "credit": credit,
                    "alpha_delta": float(alpha_delta) * credit,
                    "beta_delta": float(beta_delta) * credit,
                    "exists": row is not None,
                    "alpha": float(row[0]) if row is not None else 0.0,
                    "beta": float(row[1]) if row is not None else 0.0,
                })
        return snapshot

    def _weight_relation(self, operation: dict) -> str:
        all_before = True
        all_after = True
        with self.weights._conn_lock:
            for item in operation["before"]:
                row = self.weights.conn.execute(
                    "SELECT positive_count, negative_count FROM axis_weights "
                    "WHERE axis=? AND context_level=? AND context_key=?",
                    (item["axis"], int(item["level"]), item["key"]),
                ).fetchone()
                exists = row is not None
                alpha = float(row[0]) if row is not None else 0.0
                beta = float(row[1]) if row is not None else 0.0
                alpha_delta = float(
                    item.get("alpha_delta", operation["alpha_delta"])
                )
                beta_delta = float(
                    item.get("beta_delta", operation["beta_delta"])
                )
                all_before &= (
                    exists == bool(item["exists"])
                    and self._same(alpha, float(item["alpha"]))
                    and self._same(beta, float(item["beta"]))
                )
                all_after &= (
                    exists
                    and self._same(alpha, float(item["alpha"]) + alpha_delta)
                    and self._same(beta, float(item["beta"]) + beta_delta)
                )
            if "feedback_count_before" in operation:
                row = self.weights.conn.execute(
                    "SELECT value FROM brain_meta WHERE key='feedback_count'"
                ).fetchone()
                current_count = int(row[0]) if row is not None else -1
                before_count = int(operation["feedback_count_before"])
                all_before &= current_count == before_count
                all_after &= current_count == before_count + 1
        if all_before:
            return "before"
        if all_after:
            return "after"
        return "conflict"

    def _apply_weight_delta(self, operation: dict) -> None:
        ts = str(operation["timestamp"])
        with self.weights._conn_lock:
            try:
                self.weights.conn.execute("BEGIN IMMEDIATE")
                for item in operation["before"]:
                    alpha_delta = float(
                        item.get("alpha_delta", operation["alpha_delta"])
                    )
                    beta_delta = float(
                        item.get("beta_delta", operation["beta_delta"])
                    )
                    self.weights.conn.execute(
                        "INSERT INTO axis_weights (axis, context_level, context_key, "
                        "positive_count, negative_count, last_updated) "
                        "VALUES (?,?,?,?,?,?) "
                        "ON CONFLICT(axis, context_level, context_key) DO UPDATE SET "
                        "positive_count=positive_count+excluded.positive_count, "
                        "negative_count=negative_count+excluded.negative_count, "
                        "last_updated=excluded.last_updated",
                        (
                            item["axis"], int(item["level"]), item["key"],
                            alpha_delta, beta_delta, ts,
                        ),
                    )
                if "feedback_count_before" in operation:
                    next_count = int(operation["feedback_count_before"]) + 1
                    self.weights.conn.execute(
                        "INSERT INTO brain_meta(key, value) VALUES "
                        "('feedback_count', ?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (str(next_count),),
                    )
                self.weights.conn.execute("COMMIT")
            except Exception:
                self.weights.conn.execute("ROLLBACK")
                raise
        self.weights._invalidate()

    def _restore_weight_snapshot(self, operation: dict) -> None:
        with self.weights._conn_lock:
            try:
                self.weights.conn.execute("BEGIN IMMEDIATE")
                for item in operation["before"]:
                    if item["exists"]:
                        self.weights.conn.execute(
                            "INSERT INTO axis_weights (axis, context_level, context_key, "
                            "positive_count, negative_count, last_updated) "
                            "VALUES (?,?,?,?,?,?) "
                            "ON CONFLICT(axis, context_level, context_key) DO UPDATE SET "
                            "positive_count=excluded.positive_count, "
                            "negative_count=excluded.negative_count, "
                            "last_updated=excluded.last_updated",
                            (
                                item["axis"], int(item["level"]), item["key"],
                                float(item["alpha"]), float(item["beta"]),
                                str(operation["timestamp"]),
                            ),
                        )
                    else:
                        self.weights.conn.execute(
                            "DELETE FROM axis_weights WHERE axis=? "
                            "AND context_level=? AND context_key=?",
                            (item["axis"], int(item["level"]), item["key"]),
                        )
                if "feedback_count_before" in operation:
                    self.weights.conn.execute(
                        "INSERT INTO brain_meta(key, value) VALUES "
                        "('feedback_count', ?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (str(int(operation["feedback_count_before"])),),
                    )
                self.weights.conn.execute("COMMIT")
            except Exception:
                self.weights.conn.execute("ROLLBACK")
                raise
        self.weights._invalidate()

    @classmethod
    def _ensure_feedback_event(
        cls, conn: sqlite3.Connection, operation: dict,
    ) -> None:
        project_uuid = operation.get("project_uuid") or cls._state_project_uuid(conn)
        project_uuid = str(uuid.UUID(str(project_uuid)))
        raw_event_uuid = operation.get("event_uuid")
        event_uuid = (
            str(uuid.UUID(str(raw_event_uuid)))
            if raw_event_uuid
            else str(
                uuid.uuid5(
                    uuid.UUID(project_uuid),
                    f"outbox:{operation['operation_id']}",
                )
            )
        )
        operation["project_uuid"] = project_uuid
        operation["event_uuid"] = event_uuid
        existing_event = conn.execute(
            "SELECT project_uuid FROM feedback_events WHERE event_uuid=?",
            (event_uuid,),
        ).fetchone()
        if existing_event is not None:
            if str(existing_event[0]) != project_uuid:
                raise FeedbackOperationConflictError(
                    "Brain feedback event_uuid belongs to another project"
                )
            return

        caller_operation_id = operation.get("caller_operation_id")
        if caller_operation_id:
            receipt = cls._find_event_receipt(conn, caller_operation_id)
            if receipt is not None:
                if (
                    receipt.get("request_fingerprint")
                    != operation.get("request_fingerprint")
                ):
                    raise FeedbackOperationConflictError(
                        "Brain feedback operation_id was already used with "
                        "a different request"
                    )
                return

        context_payload = cls._feedback_context_json(operation)
        exists = conn.execute(
            "SELECT 1 FROM feedback_events WHERE cut_id=? AND rating=? "
            "AND alpha_delta=? AND beta_delta=? AND context_keys_json=? "
            "AND timestamp=? LIMIT 1",
            (
                int(operation["cut_id"]), operation["rating"],
                float(operation["alpha_delta"]), float(operation["beta_delta"]),
                context_payload,
                operation["timestamp"],
            ),
        ).fetchone()
        if exists is not None:
            return
        cut_exists = conn.execute(
            "SELECT 1 FROM timeline_cuts WHERE id=?",
            (int(operation["cut_id"]),),
        ).fetchone()
        if cut_exists is None:
            raise LookupError(f"Cut {operation['cut_id']} no longer exists")
        conn.execute(
            "INSERT INTO feedback_events (cut_id, rating, alpha_delta, "
            "beta_delta, context_keys_json, timestamp, project_uuid, event_uuid) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                int(operation["cut_id"]), operation["rating"],
                float(operation["alpha_delta"]), float(operation["beta_delta"]),
                context_payload,
                operation["timestamp"],
                project_uuid,
                event_uuid,
            ),
        )

    @staticmethod
    def _feedback_context_json(operation: dict) -> str:
        caller_operation_id = operation.get("caller_operation_id")
        if not caller_operation_id:
            return json.dumps(operation["context_keys"])
        return json.dumps(
            {
                "context_keys": list(operation["context_keys"]),
                "operation_id": str(caller_operation_id),
                "request_fingerprint": str(operation["request_fingerprint"]),
                "schema_version": 2,
                "updated_buckets": len(operation["before"]),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _find_event_receipt(
        conn: sqlite3.Connection,
        operation_id: str,
    ) -> Optional[dict]:
        rows = conn.execute(
            "SELECT context_keys_json FROM feedback_events "
            "WHERE context_keys_json LIKE ? ORDER BY id DESC",
            (f"%{operation_id}%",),
        ).fetchall()
        for row in rows:
            try:
                payload = json.loads(row[0])
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if (
                isinstance(payload, dict)
                and payload.get("operation_id") == operation_id
                and payload.get("schema_version") == 2
            ):
                return payload
        return None

    def _result_from_receipt(
        self,
        operation_id: str,
        request_fingerprint: str,
    ) -> Optional[FeedbackLogResult]:
        receipt = self._read_feedback_receipts().get(operation_id)
        if receipt is None:
            receipt = self._find_event_receipt(self.state_conn, operation_id)
        if receipt is None:
            return None
        if receipt.get("request_fingerprint") != request_fingerprint:
            raise FeedbackOperationConflictError(
                "Brain feedback operation_id was already used with "
                "a different request"
            )
        return FeedbackLogResult(
            updated_buckets=int(receipt.get("updated_buckets", 0)),
            applied=False,
        )

    def _record_feedback_receipt(self, operation: dict) -> None:
        operation_id = operation.get("caller_operation_id")
        if not operation_id:
            return
        receipts = self._read_feedback_receipts()
        existing = receipts.get(operation_id)
        receipt = {
            "cut_id": int(operation["cut_id"]),
            "rating": str(operation["rating"]),
            "request_fingerprint": str(operation["request_fingerprint"]),
            "state_db_path": str(operation["state_db_path"]),
            "project_uuid": str(operation["project_uuid"]),
            "event_uuid": str(operation["event_uuid"]),
            "timestamp": str(operation["timestamp"]),
            "updated_buckets": len(operation["before"]),
        }
        if existing is not None:
            if existing.get("request_fingerprint") != receipt["request_fingerprint"]:
                raise FeedbackOperationConflictError(
                    "Brain feedback operation_id was already used with "
                    "a different request"
                )
            return
        receipts[operation_id] = receipt
        self._write_feedback_receipts(receipts)

    def _read_feedback_receipts(self) -> dict[str, dict]:
        if not self.receipt_path.is_file():
            return {}
        try:
            payload = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(
                f"Brain feedback receipts are unreadable: {self.receipt_path}"
            ) from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise RuntimeError("Unsupported Brain feedback receipt schema")
        receipts = payload.get("receipts")
        if not isinstance(receipts, dict):
            raise RuntimeError("Invalid Brain feedback receipt store")
        return receipts

    def _write_feedback_receipts(self, receipts: dict[str, dict]) -> None:
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.receipt_path.with_suffix(self.receipt_path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                {"receipts": receipts, "schema_version": 1},
                handle,
                ensure_ascii=False,
                sort_keys=True,
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, self.receipt_path)

    @staticmethod
    def _request_fingerprint(
        *,
        project_uuid: str,
        cut_id: int,
        rating: str,
    ) -> str:
        payload = json.dumps(
            {
                "cut_id": int(cut_id),
                "rating": str(rating),
                "project_uuid": str(uuid.UUID(str(project_uuid))),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _validate_client_operation_id(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip()
        if not 16 <= len(normalized) <= 128:
            raise ValueError("operation_id must contain 16 to 128 characters")
        allowed = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-"
        )
        if normalized[0] not in allowed or any(ch not in allowed for ch in normalized):
            raise ValueError("operation_id contains unsupported characters")
        return normalized

    def _open_target_state(
        self, operation: dict,
    ) -> tuple[Optional[sqlite3.Connection], bool]:
        target = Path(operation["state_db_path"])
        if not target.is_file():
            return None, False
        if target.resolve() == Path(self._connection_path(self.state_conn)).resolve():
            return self.state_conn, False
        from ..storage.sqlite_init import init_connection

        conn = sqlite3.connect(
            str(target), isolation_level=None, check_same_thread=False,
        )
        init_connection(conn)
        return conn, True

    def _write_outbox(self, operation: dict) -> None:
        self.outbox_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.outbox_path.with_suffix(self.outbox_path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(operation, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, self.outbox_path)

    def _read_outbox(self) -> Optional[dict]:
        if not self.outbox_path.is_file():
            return None
        try:
            return json.loads(self.outbox_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(
                f"Brain feedback outbox is unreadable: {self.outbox_path}"
            ) from exc

    def _clear_outbox(self) -> None:
        self.outbox_path.unlink(missing_ok=True)

    def _inject_fault(self, stage: str) -> None:
        if self._fault_injector is not None:
            self._fault_injector(stage)

    @staticmethod
    def _validate_operation(operation: dict) -> None:
        required = {
            "schema_version", "operation_id", "stage", "state_db_path",
            "cut_id", "rating", "alpha_delta", "beta_delta", "context_keys",
            "timestamp", "before",
        }
        if operation.get("schema_version") != _OUTBOX_SCHEMA_VERSION:
            raise RuntimeError("Unsupported Brain feedback outbox schema")
        if not required.issubset(operation):
            raise RuntimeError("Incomplete Brain feedback outbox")
        if operation["stage"] not in {"prepared", "weights_applied"}:
            raise RuntimeError("Invalid Brain feedback outbox stage")
        if operation["rating"] not in RATING_MAP:
            raise RuntimeError("Invalid Brain feedback rating in outbox")
        caller_operation_id = operation.get("caller_operation_id")
        if caller_operation_id is not None:
            FeedbackLogger._validate_client_operation_id(caller_operation_id)
            if not operation.get("request_fingerprint"):
                raise RuntimeError("Brain feedback outbox lacks request fingerprint")

    @staticmethod
    def _connection_path(conn: sqlite3.Connection) -> str:
        rows = conn.execute("PRAGMA database_list").fetchall()
        for _seq, name, path in rows:
            if name == "main" and path:
                return str(Path(path).resolve())
        raise RuntimeError("Durable Brain feedback requires a file-backed state DB")

    @classmethod
    def _state_project_uuid(cls, conn: sqlite3.Connection) -> str:
        row = conn.execute(
            "SELECT project_uuid FROM project_identity WHERE singleton_id=1"
        ).fetchone()
        if row is not None:
            return str(uuid.UUID(str(row[0])))
        state_path = Path(cls._connection_path(conn)).resolve()
        fallback = str(uuid.uuid5(uuid.NAMESPACE_URL, state_path.as_uri()))
        conn.execute(
            "INSERT INTO project_identity(singleton_id, project_uuid) VALUES (1, ?)",
            (fallback,),
        )
        logger.warning(
            "Feedback state %s had no catalog identity; initialized standalone UUID",
            state_path,
        )
        return fallback

    @classmethod
    def _default_outbox_path(cls, conn: sqlite3.Connection) -> Path:
        state_path = Path(cls._connection_path(conn))
        return state_path.with_suffix(state_path.suffix + ".brain-feedback-outbox.json")

    @staticmethod
    def _unique_timestamp(conn: sqlite3.Connection) -> str:
        current = datetime.now(timezone.utc)
        while True:
            value = current.isoformat(timespec="microseconds")
            exists = conn.execute(
                "SELECT 1 FROM feedback_events WHERE timestamp=? LIMIT 1",
                (value,),
            ).fetchone()
            if exists is None:
                return value
            current += timedelta(microseconds=1)

    @staticmethod
    def _same(left: float, right: float) -> bool:
        return abs(left - right) <= 1e-9


def build_credit_assignments(
    *,
    metadata: dict,
    brain_scores: dict,
    context_keys: list[str],
) -> list[dict]:
    """Derive sparse, evidence-weighted axis/context credit for one cut."""
    bridge_values = metadata.get("bridge_values")
    values = bridge_values if isinstance(bridge_values, dict) else brain_scores
    axis_status = metadata.get("brain_axis_status") or {}
    strict_axis_status = metadata.get("brain_axis_status_version") == 1
    assignments: list[dict] = []

    if not isinstance(axis_status, dict):
        return assignments

    for axis in BRIDGE_AXES:
        if axis not in values:
            continue
        status = axis_status.get(axis)
        if status is None:
            if strict_axis_status:
                continue
        elif not isinstance(status, dict) or status.get("status") != "available":
            continue
        try:
            relevance = float(values[axis])
        except (TypeError, ValueError):
            continue
        if not math.isfinite(relevance):
            continue
        relevance = max(0.0, min(1.0, relevance))
        if relevance < _MIN_AXIS_RELEVANCE:
            continue

        for level in _levels_for_axis(axis):
            if level >= len(context_keys):
                continue
            assignments.append({
                "axis": axis,
                "level": level,
                "key": str(context_keys[level]),
                "credit": round(
                    relevance * _CONTEXT_LEVEL_WEIGHTS[level],
                    6,
                ),
            })
    return assignments


def _levels_for_axis(axis: str) -> tuple[int, ...]:
    if axis in _AUDIO_TRIGGER_AXES:
        return (0, 1, 4, 5)
    if axis in _LENGTH_AXES:
        return (0, 1, 5)
    if axis in _MOTION_AXES:
        return (0, 1, 3, 5)
    if axis in _SEMANTIC_AXES:
        return (0, 2, 3, 5)
    return (0, 5)
