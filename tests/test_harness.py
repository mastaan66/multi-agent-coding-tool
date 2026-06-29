"""Tests for the durable long-running agent harness lifecycle."""

import json
from pathlib import Path

import pytest

from src.harness import HarnessController, HarnessPhase, HarnessTransitionError
from src.sessions.store import SQLiteSessionStore, TaskStatus


def test_harness_enforces_verified_lifecycle_and_resumes(tmp_path: Path) -> None:
    database = tmp_path / "sessions.db"
    with SQLiteSessionStore(database) as store:
        session = store.create_session(tmp_path, session_id="session-1")
        task = store.create_task(
            session.id,
            "Persist messages",
            acceptance_criteria=("Messages survive restart",),
            task_id="task-1",
        )
        controller = HarnessController(store)

        assert controller.start(session.id, "Build durable resume").phase is HarnessPhase.ORIENT
        with pytest.raises(HarnessTransitionError):
            controller.action_completed(session.id, "Too early")

        assert controller.orient(session.id, "Repository is healthy").phase is HarnessPhase.PLAN
        with pytest.raises(ValueError, match="Plan cannot be empty"):
            controller.plan(session.id, task.id, " ")
        assert store.get_task(task.id).status is TaskStatus.PENDING

        assert controller.plan(session.id, task.id, "Add persistence").phase is HarnessPhase.ACT
        assert controller.action_completed(session.id, "Implemented tables").phase is HarnessPhase.VERIFY
        failed = controller.verify(
            session.id,
            passed=False,
            evidence="Replay test failed",
        )
        assert failed.phase is HarnessPhase.ACT
        assert store.get_task(task.id).status is TaskStatus.IN_PROGRESS

        controller.action_completed(session.id, "Corrected replay ordering")
        passed = controller.verify(
            session.id,
            passed=True,
            evidence="pytest tests/test_harness.py",
        )
        assert passed.phase is HarnessPhase.RECORD
        assert store.get_task(task.id).status is TaskStatus.COMPLETED
        assert controller.record(session.id, "Durable lifecycle verified").phase is HarnessPhase.HANDOFF
        context = json.loads(controller.context(session.id))
        assert context["harness"]["phase"] == "handoff"
        assert context["harness"]["active_task_id"] == task.id

    with SQLiteSessionStore(database) as reopened:
        controller = HarnessController(reopened)
        assert controller.resume("session-1").phase is HarnessPhase.HANDOFF
        completed = controller.handoff("session-1", "Ready for the next slice")

        assert completed.phase is HarnessPhase.COMPLETE
        assert completed.active_task_id is None
        assert reopened.get_session("session-1").status == "completed"
        transitions = reopened.list_harness_transitions("session-1")
        assert transitions[0].from_phase is None
        assert transitions[-1].to_phase == "complete"
        assert any(item.evidence == "Replay test failed" for item in transitions)


def test_handoff_can_continue_with_a_compact_orientation_state(tmp_path: Path) -> None:
    with SQLiteSessionStore(":memory:") as store:
        session = store.create_session(tmp_path)
        task = store.create_task(session.id, "First task")
        controller = HarnessController(store)
        controller.start(session.id, "Complete several tasks")
        controller.orient(session.id, "Ready")
        controller.plan(session.id, task.id, "Implement first task")
        controller.action_completed(session.id, "Implemented")
        controller.verify(session.id, passed=True, evidence="focused test passed")
        controller.record(session.id, "First task recorded")

        continued = controller.handoff(
            session.id,
            "First task complete; choose the next task",
            continue_work=True,
        )

        assert continued.phase is HarnessPhase.ORIENT
        assert continued.active_task_id is None
        assert continued.data == {
            "previous_handoff": "First task complete; choose the next task",
            "completed_task_id": task.id,
        }
        assert store.get_session(session.id).status == "active"
