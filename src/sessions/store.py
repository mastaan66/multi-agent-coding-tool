"""SQLite-backed sessions, append-only events, and structured task ledgers."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from src.core.events import (
    MessageRole,
    ModelMessage,
    RuntimeEvent,
    RuntimeEventType,
    ToolCall,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"


@dataclass(frozen=True)
class SessionRecord:
    id: str
    repository_root: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TaskRecord:
    id: str
    session_id: str
    title: str
    status: TaskStatus
    priority: int
    acceptance_criteria: tuple[str, ...]
    verification: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class StoredEvent:
    sequence: int
    session_id: str
    type: str
    turn: int
    text: str
    data: dict[str, Any]
    tool_call: ToolCall | None
    created_at: str


@dataclass(frozen=True)
class StoredMessage:
    sequence: int
    session_id: str
    message: ModelMessage
    created_at: str


@dataclass(frozen=True)
class HarnessStateRecord:
    session_id: str
    phase: str
    objective: str
    active_task_id: str | None
    data: dict[str, Any]
    revision: int
    updated_at: str


@dataclass(frozen=True)
class HarnessTransitionRecord:
    sequence: int
    session_id: str
    from_phase: str | None
    to_phase: str
    note: str
    evidence: str
    created_at: str


class SQLiteSessionStore:
    """Persist resumable session state with append-only runtime events."""

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = str(database_path)
        if self.database_path != ":memory:":
            parent = Path(self.database_path).expanduser().resolve().parent
            parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    @property
    def schema_version(self) -> int:
        row = self._connection.execute(
            "SELECT value FROM schema_metadata WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            raise RuntimeError("Session database has no schema version")
        return int(row["value"])

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> SQLiteSessionStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def create_session(
        self,
        repository_root: Path | str,
        session_id: str | None = None,
    ) -> SessionRecord:
        identifier = session_id or str(uuid.uuid4())
        timestamp = _now()
        root = str(Path(repository_root).resolve())
        with self._connection:
            self._connection.execute(
                "INSERT INTO sessions (id, repository_root, status, created_at, updated_at) "
                "VALUES (?, ?, 'active', ?, ?)",
                (identifier, root, timestamp, timestamp),
            )
        return self.get_session(identifier)

    def get_session(self, session_id: str) -> SessionRecord:
        row = self._connection.execute(
            "SELECT id, repository_root, status, created_at, updated_at "
            "FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown session: {session_id}")
        return SessionRecord(**dict(row))

    def list_sessions(
        self,
        *,
        repository_root: Path | str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> tuple[SessionRecord, ...]:
        if limit < 1:
            raise ValueError("Session limit must be positive")
        clauses: list[str] = []
        values: list[object] = []
        if repository_root is not None:
            clauses.append("repository_root = ?")
            values.append(str(Path(repository_root).resolve()))
        if status is not None:
            clauses.append("status = ?")
            values.append(status)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(limit)
        rows = self._connection.execute(
            "SELECT id, repository_root, status, created_at, updated_at "
            f"FROM sessions{where} ORDER BY updated_at DESC, id LIMIT ?",
            tuple(values),
        ).fetchall()
        return tuple(SessionRecord(**dict(row)) for row in rows)

    def set_session_status(self, session_id: str, status: str) -> SessionRecord:
        if status not in {"active", "completed", "failed", "interrupted"}:
            raise ValueError(f"Invalid session status: {status}")
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
                (status, _now(), session_id),
            )
        if cursor.rowcount != 1:
            raise KeyError(f"Unknown session: {session_id}")
        return self.get_session(session_id)

    def append_event(self, session_id: str, event: RuntimeEvent) -> StoredEvent:
        tool_call_json = None
        if event.tool_call is not None:
            tool_call_json = json.dumps(
                {
                    "id": event.tool_call.id,
                    "name": event.tool_call.name,
                    "arguments": event.tool_call.arguments,
                },
                sort_keys=True,
            )
        timestamp = _now()
        with self._connection:
            cursor = self._connection.execute(
                "INSERT INTO events "
                "(session_id, type, turn, text, data_json, tool_call_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    event.type.value,
                    event.turn,
                    event.text,
                    json.dumps(event.data, sort_keys=True),
                    tool_call_json,
                    timestamp,
                ),
            )
            self._connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (timestamp, session_id),
            )
        sequence = cursor.lastrowid
        if sequence is None:
            raise RuntimeError("SQLite did not return an event sequence")
        return self._event_by_sequence(sequence)

    def event_handler(
        self,
        session_id: str,
        *,
        persist_text_deltas: bool = False,
    ) -> Callable[[RuntimeEvent], None]:
        """Return a runtime callback, excluding high-volume text deltas by default."""

        def handle(event: RuntimeEvent) -> None:
            if event.type is RuntimeEventType.TEXT_DELTA and not persist_text_deltas:
                return
            self.append_event(session_id, event)

        return handle

    def list_events(self, session_id: str) -> tuple[StoredEvent, ...]:
        rows = self._connection.execute(
            "SELECT sequence, session_id, type, turn, text, data_json, "
            "tool_call_json, created_at FROM events WHERE session_id = ? ORDER BY sequence",
            (session_id,),
        ).fetchall()
        return tuple(self._row_to_event(row) for row in rows)

    def append_message(self, session_id: str, message: ModelMessage) -> StoredMessage:
        tool_calls_json = json.dumps(
            [
                {"id": call.id, "name": call.name, "arguments": call.arguments}
                for call in message.tool_calls
            ],
            sort_keys=True,
        )
        timestamp = _now()
        with self._connection:
            cursor = self._connection.execute(
                "INSERT INTO messages "
                "(session_id, role, content, tool_calls_json, tool_call_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    message.role.value,
                    message.content,
                    tool_calls_json,
                    message.tool_call_id,
                    timestamp,
                ),
            )
            self._connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (timestamp, session_id),
            )
        sequence = cursor.lastrowid
        if sequence is None:
            raise RuntimeError("SQLite did not return a message sequence")
        return self._message_by_sequence(sequence)

    def message_handler(self, session_id: str) -> Callable[[ModelMessage], None]:
        """Return a runtime callback that persists newly-created messages."""

        def handle(message: ModelMessage) -> None:
            self.append_message(session_id, message)

        return handle

    def list_messages(self, session_id: str) -> tuple[StoredMessage, ...]:
        rows = self._connection.execute(
            "SELECT sequence, session_id, role, content, tool_calls_json, "
            "tool_call_id, created_at FROM messages WHERE session_id = ? ORDER BY sequence",
            (session_id,),
        ).fetchall()
        return tuple(self._row_to_message(row) for row in rows)

    def replay_messages(self, session_id: str) -> tuple[ModelMessage, ...]:
        """Rebuild provider-safe history without rerunning interrupted tool calls."""
        replay: list[ModelMessage] = []
        pending: dict[str, ToolCall] = {}

        def close_interrupted_calls() -> None:
            for call in pending.values():
                replay.append(
                    ModelMessage(
                        role=MessageRole.TOOL,
                        content=json.dumps(
                            {
                                "success": False,
                                "content": "",
                                "data": {"interrupted": True},
                                "error": (
                                    f"{call.name} was not completed before interruption; "
                                    "it was not replayed automatically"
                                ),
                                "artifact_ref": None,
                                "truncated": False,
                            },
                            ensure_ascii=False,
                        ),
                        tool_call_id=call.id,
                    )
                )
            pending.clear()

        for stored in self.list_messages(session_id):
            message = stored.message
            if message.role is MessageRole.TOOL:
                replay.append(message)
                if message.tool_call_id is not None:
                    pending.pop(message.tool_call_id, None)
                continue
            if pending:
                close_interrupted_calls()
            replay.append(message)
            if message.role is MessageRole.ASSISTANT:
                pending.update({call.id: call for call in message.tool_calls})
        if pending:
            close_interrupted_calls()
        return tuple(replay)

    def _message_by_sequence(self, sequence: int) -> StoredMessage:
        row = self._connection.execute(
            "SELECT sequence, session_id, role, content, tool_calls_json, "
            "tool_call_id, created_at FROM messages WHERE sequence = ?",
            (sequence,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown message sequence: {sequence}")
        return self._row_to_message(row)

    def _row_to_message(self, row: sqlite3.Row) -> StoredMessage:
        calls = tuple(ToolCall(**item) for item in json.loads(row["tool_calls_json"]))
        return StoredMessage(
            sequence=row["sequence"],
            session_id=row["session_id"],
            message=ModelMessage(
                role=MessageRole(row["role"]),
                content=row["content"],
                tool_calls=calls,
                tool_call_id=row["tool_call_id"],
            ),
            created_at=row["created_at"],
        )

    def create_task(
        self,
        session_id: str,
        title: str,
        *,
        acceptance_criteria: tuple[str, ...] = (),
        priority: int = 0,
        task_id: str | None = None,
    ) -> TaskRecord:
        if not title.strip():
            raise ValueError("Task title cannot be empty")
        self.get_session(session_id)
        identifier = task_id or str(uuid.uuid4())
        timestamp = _now()
        with self._connection:
            self._connection.execute(
                "INSERT INTO tasks "
                "(id, session_id, title, status, priority, acceptance_json, verification, "
                "created_at, updated_at) VALUES (?, ?, ?, 'pending', ?, ?, '', ?, ?)",
                (
                    identifier,
                    session_id,
                    title.strip(),
                    priority,
                    json.dumps(acceptance_criteria),
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_task(identifier)

    def get_task(self, task_id: str) -> TaskRecord:
        row = self._connection.execute(
            "SELECT id, session_id, title, status, priority, acceptance_json, "
            "verification, created_at, updated_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown task: {task_id}")
        return self._row_to_task(row)

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        verification: str = "",
    ) -> TaskRecord:
        if status is TaskStatus.COMPLETED and not verification.strip():
            raise ValueError("Completed tasks require verification evidence")
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE tasks SET status = ?, verification = ?, updated_at = ? WHERE id = ?",
                (status.value, verification.strip(), _now(), task_id),
            )
        if cursor.rowcount != 1:
            raise KeyError(f"Unknown task: {task_id}")
        return self.get_task(task_id)

    def list_tasks(self, session_id: str) -> tuple[TaskRecord, ...]:
        rows = self._connection.execute(
            "SELECT id, session_id, title, status, priority, acceptance_json, "
            "verification, created_at, updated_at FROM tasks WHERE session_id = ? "
            "ORDER BY priority DESC, created_at, id",
            (session_id,),
        ).fetchall()
        return tuple(self._row_to_task(row) for row in rows)

    def initialize_harness_state(
        self,
        session_id: str,
        *,
        phase: str,
        objective: str,
    ) -> HarnessStateRecord:
        if not phase.strip():
            raise ValueError("Harness phase cannot be empty")
        if not objective.strip():
            raise ValueError("Harness objective cannot be empty")
        self.get_session(session_id)
        timestamp = _now()
        with self._connection:
            self._connection.execute(
                "INSERT INTO harness_state "
                "(session_id, phase, objective, active_task_id, data_json, revision, updated_at) "
                "VALUES (?, ?, ?, NULL, '{}', 0, ?)",
                (session_id, phase, objective.strip(), timestamp),
            )
            self._connection.execute(
                "INSERT INTO harness_transitions "
                "(session_id, from_phase, to_phase, note, evidence, created_at) "
                "VALUES (?, NULL, ?, ?, '', ?)",
                (session_id, phase, "Harness initialized", timestamp),
            )
        return self.get_harness_state(session_id)

    def get_harness_state(self, session_id: str) -> HarnessStateRecord:
        state = self.try_get_harness_state(session_id)
        if state is None:
            raise KeyError(f"Harness is not initialized for session: {session_id}")
        return state

    def try_get_harness_state(self, session_id: str) -> HarnessStateRecord | None:
        row = self._connection.execute(
            "SELECT session_id, phase, objective, active_task_id, data_json, "
            "revision, updated_at FROM harness_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return HarnessStateRecord(
            session_id=row["session_id"],
            phase=row["phase"],
            objective=row["objective"],
            active_task_id=row["active_task_id"],
            data=json.loads(row["data_json"]),
            revision=row["revision"],
            updated_at=row["updated_at"],
        )

    def transition_harness_state(
        self,
        session_id: str,
        *,
        expected_phase: str,
        next_phase: str,
        objective: str,
        active_task_id: str | None,
        data: dict[str, Any],
        note: str = "",
        evidence: str = "",
        start_task_id: str | None = None,
        complete_task_id: str | None = None,
        task_verification: str = "",
        session_status: str | None = None,
    ) -> HarnessStateRecord:
        current = self.get_harness_state(session_id)
        if current.phase != expected_phase:
            raise ValueError(
                f"Harness phase mismatch: expected {expected_phase}, found {current.phase}"
            )
        if session_status is not None and session_status not in {
            "active", "completed", "failed", "interrupted"
        }:
            raise ValueError(f"Invalid session status: {session_status}")
        timestamp = _now()
        next_revision = current.revision + 1
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE harness_state SET phase = ?, objective = ?, active_task_id = ?, "
                "data_json = ?, revision = ?, updated_at = ? "
                "WHERE session_id = ? AND revision = ?",
                (
                    next_phase,
                    objective,
                    active_task_id,
                    json.dumps(data, sort_keys=True),
                    next_revision,
                    timestamp,
                    session_id,
                    current.revision,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Harness state changed concurrently")
            if start_task_id is not None:
                task_cursor = self._connection.execute(
                    "UPDATE tasks SET status = ?, verification = '', updated_at = ? "
                    "WHERE id = ? AND session_id = ? AND status != ?",
                    (
                        TaskStatus.IN_PROGRESS.value,
                        timestamp,
                        start_task_id,
                        session_id,
                        TaskStatus.COMPLETED.value,
                    ),
                )
                if task_cursor.rowcount != 1:
                    raise ValueError(f"Task cannot be started: {start_task_id}")
            if complete_task_id is not None:
                if not task_verification.strip():
                    raise ValueError("Completed tasks require verification evidence")
                task_cursor = self._connection.execute(
                    "UPDATE tasks SET status = ?, verification = ?, updated_at = ? "
                    "WHERE id = ? AND session_id = ?",
                    (
                        TaskStatus.COMPLETED.value,
                        task_verification.strip(),
                        timestamp,
                        complete_task_id,
                        session_id,
                    ),
                )
                if task_cursor.rowcount != 1:
                    raise ValueError(f"Task cannot be completed: {complete_task_id}")
            if session_status is None:
                self._connection.execute(
                    "UPDATE sessions SET updated_at = ? WHERE id = ?",
                    (timestamp, session_id),
                )
            else:
                self._connection.execute(
                    "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
                    (session_status, timestamp, session_id),
                )
            self._connection.execute(
                "INSERT INTO harness_transitions "
                "(session_id, from_phase, to_phase, note, evidence, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    current.phase,
                    next_phase,
                    note.strip(),
                    evidence.strip(),
                    timestamp,
                ),
            )
        return self.get_harness_state(session_id)

    def list_harness_transitions(
        self,
        session_id: str,
    ) -> tuple[HarnessTransitionRecord, ...]:
        rows = self._connection.execute(
            "SELECT sequence, session_id, from_phase, to_phase, note, evidence, created_at "
            "FROM harness_transitions WHERE session_id = ? ORDER BY sequence",
            (session_id,),
        ).fetchall()
        return tuple(
            HarnessTransitionRecord(
                sequence=row["sequence"],
                session_id=row["session_id"],
                from_phase=row["from_phase"],
                to_phase=row["to_phase"],
                note=row["note"],
                evidence=row["evidence"],
                created_at=row["created_at"],
            )
            for row in rows
        )

    def build_state_context(self, session_id: str) -> str:
        """Render compact, structured session and task state for context assembly."""
        session = self.get_session(session_id)
        tasks = self.list_tasks(session_id)
        harness = self.try_get_harness_state(session_id)
        harness_payload = (
            None
            if harness is None
            else {
                "phase": harness.phase,
                "objective": harness.objective,
                "active_task_id": harness.active_task_id,
                "data": harness.data,
            }
        )
        payload = {
            "session": {"id": session.id, "status": session.status},
            "harness": harness_payload,
            "tasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "status": task.status.value,
                    "priority": task.priority,
                    "acceptance_criteria": task.acceptance_criteria,
                    "verification": task.verification or None,
                }
                for task in tasks
            ],
        }
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    def _event_by_sequence(self, sequence: int) -> StoredEvent:
        row = self._connection.execute(
            "SELECT sequence, session_id, type, turn, text, data_json, "
            "tool_call_json, created_at FROM events WHERE sequence = ?",
            (sequence,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown event sequence: {sequence}")
        return self._row_to_event(row)

    def _row_to_event(self, row: sqlite3.Row) -> StoredEvent:
        raw_call = json.loads(row["tool_call_json"]) if row["tool_call_json"] else None
        tool_call = ToolCall(**raw_call) if raw_call is not None else None
        return StoredEvent(
            sequence=row["sequence"],
            session_id=row["session_id"],
            type=row["type"],
            turn=row["turn"],
            text=row["text"],
            data=json.loads(row["data_json"]),
            tool_call=tool_call,
            created_at=row["created_at"],
        )

    def _row_to_task(self, row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            id=row["id"],
            session_id=row["session_id"],
            title=row["title"],
            status=TaskStatus(row["status"]),
            priority=row["priority"],
            acceptance_criteria=tuple(json.loads(row["acceptance_json"])),
            verification=row["verification"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _migrate(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    repository_root TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    type TEXT NOT NULL,
                    turn INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    tool_call_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS events_session_sequence
                    ON events(session_id, sequence);

                CREATE TABLE IF NOT EXISTS messages (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_calls_json TEXT NOT NULL,
                    tool_call_id TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS messages_session_sequence
                    ON messages(session_id, sequence);

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    acceptance_json TEXT NOT NULL,
                    verification TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS tasks_session_status
                    ON tasks(session_id, status, priority);
                CREATE TABLE IF NOT EXISTS harness_state (
                    session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
                    phase TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    active_task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
                    data_json TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS harness_transitions (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    from_phase TEXT,
                    to_phase TEXT NOT NULL,
                    note TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS harness_transitions_session_sequence
                    ON harness_transitions(session_id, sequence);

                CREATE TABLE IF NOT EXISTS schema_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                INSERT INTO schema_metadata (key, value)
                    VALUES ('schema_version', '2')
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value;

                """
            )
