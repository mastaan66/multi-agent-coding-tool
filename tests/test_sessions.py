"""Tests for durable session state and content-addressed artifacts."""

import json
from pathlib import Path

import pytest

from src.core.events import RuntimeEvent, RuntimeEventType, ToolCall
from src.sessions.artifacts import ArtifactBackedResultProcessor, ArtifactStore
from src.sessions.store import SQLiteSessionStore, TaskStatus
from src.tools.base import ToolResult


def test_session_store_persists_events_and_verified_tasks(tmp_path: Path) -> None:
    database = tmp_path / "state" / "sessions.db"
    with SQLiteSessionStore(database) as store:
        session = store.create_session(tmp_path, session_id="session-1")
        task = store.create_task(
            session.id,
            "Implement persistent events",
            acceptance_criteria=("Events survive process exit",),
            priority=10,
            task_id="task-1",
        )
        call = ToolCall(id="call-1", name="read_file", arguments={"path": "README.md"})
        handler = store.event_handler(session.id)
        handler(
            RuntimeEvent(
                type=RuntimeEventType.TEXT_DELTA,
                turn=1,
                text="streamed but not persisted",
            )
        )
        handler(
            RuntimeEvent(
                type=RuntimeEventType.TOOL_COMPLETED,
                turn=1,
                text="read",
                tool_call=call,
                data={"success": True},
            )
        )

        with pytest.raises(ValueError, match="verification evidence"):
            store.update_task_status(task.id, TaskStatus.COMPLETED)

        completed = store.update_task_status(
            task.id,
            TaskStatus.COMPLETED,
            verification="pytest tests/test_sessions.py",
        )
        events = store.list_events(session.id)
        state_context = json.loads(store.build_state_context(session.id))

        assert completed.status is TaskStatus.COMPLETED
        assert completed.verification == "pytest tests/test_sessions.py"
        assert events[0].tool_call == call
        assert events[0].data == {"success": True}
        assert state_context["tasks"][0]["status"] == "completed"
        assert state_context["tasks"][0]["verification"] == "pytest tests/test_sessions.py"

    with SQLiteSessionStore(database) as reopened:
        assert reopened.schema_version == 2
        assert reopened.get_session("session-1").repository_root == str(tmp_path.resolve())
        assert reopened.list_tasks("session-1")[0].status is TaskStatus.COMPLETED
        assert reopened.list_events("session-1")[0].text == "read"
        assert [session.id for session in reopened.list_sessions()] == ["session-1"]


def test_artifact_store_deduplicates_and_externalizes_large_results(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    first = store.put_text("same output")
    second = store.put_text("same output")
    processor = ArtifactBackedResultProcessor(store, max_model_characters=512)
    result = ToolResult(
        success=True,
        content='large "output" ' * 200,
        data={"duplicate": "value" * 500},
    )

    bounded = processor(
        ToolCall(id="call-1", name="shell", arguments={"command": "tests"}),
        result,
    )

    assert first.id == second.id
    assert bounded.truncated
    assert bounded.artifact_ref is not None
    assert len(bounded.to_model_text()) <= 512
    assert "large" in store.read_text(bounded.artifact_ref)
    assert store.path_for(bounded.artifact_ref).is_file()


def test_artifact_store_rejects_invalid_identifiers(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")

    with pytest.raises(ValueError, match="Invalid artifact ID"):
        store.read_text("../../secret")
