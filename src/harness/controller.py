"""Persistent ORIENT -> PLAN -> ACT -> VERIFY -> RECORD -> HANDOFF controller."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.sessions.store import HarnessStateRecord, SQLiteSessionStore, TaskStatus


class HarnessPhase(str, Enum):
    ORIENT = "orient"
    PLAN = "plan"
    ACT = "act"
    VERIFY = "verify"
    RECORD = "record"
    HANDOFF = "handoff"
    COMPLETE = "complete"


class HarnessTransitionError(RuntimeError):
    """Raised when a caller attempts an invalid lifecycle transition."""


@dataclass(frozen=True)
class HarnessSnapshot:
    session_id: str
    phase: HarnessPhase
    objective: str
    active_task_id: str | None
    data: dict[str, Any]
    revision: int


class HarnessController:
    """Enforce and persist incremental, verification-gated agent work."""

    _ALLOWED = {
        HarnessPhase.ORIENT: {HarnessPhase.PLAN},
        HarnessPhase.PLAN: {HarnessPhase.ACT},
        HarnessPhase.ACT: {HarnessPhase.VERIFY},
        HarnessPhase.VERIFY: {HarnessPhase.ACT, HarnessPhase.RECORD},
        HarnessPhase.RECORD: {HarnessPhase.HANDOFF},
        HarnessPhase.HANDOFF: {HarnessPhase.ORIENT, HarnessPhase.COMPLETE},
        HarnessPhase.COMPLETE: set(),
    }

    def __init__(self, store: SQLiteSessionStore) -> None:
        self.store = store

    def start(self, session_id: str, objective: str) -> HarnessSnapshot:
        state = self.store.initialize_harness_state(
            session_id,
            phase=HarnessPhase.ORIENT.value,
            objective=self._required(objective, "Objective"),
        )
        return self._snapshot(state)

    def resume(self, session_id: str) -> HarnessSnapshot:
        """Load the exact durable lifecycle position without advancing it."""
        return self._snapshot(self.store.get_harness_state(session_id))

    def orient(self, session_id: str, repository_summary: str) -> HarnessSnapshot:
        current = self.resume(session_id)
        data = dict(current.data)
        data["orientation"] = self._required(repository_summary, "Orientation summary")
        return self._transition(
            current,
            HarnessPhase.PLAN,
            data=data,
            note="Repository and session state oriented",
        )

    def plan(self, session_id: str, task_id: str, plan: str) -> HarnessSnapshot:
        current = self.resume(session_id)
        self._assert_transition(current.phase, HarnessPhase.ACT)
        task = self.store.get_task(task_id)
        planned_work = self._required(plan, "Plan")
        if task.session_id != session_id:
            raise HarnessTransitionError("Task belongs to a different session")
        if task.status is TaskStatus.COMPLETED:
            raise HarnessTransitionError("Completed tasks cannot be planned again")
        data = dict(current.data)
        data["plan"] = planned_work
        data.pop("verification", None)
        data.pop("record", None)
        return self._transition(
            current,
            HarnessPhase.ACT,
            active_task_id=task_id,
            start_task_id=task_id,
            data=data,
            note=f"Plan accepted for task {task_id}",
        )

    def action_completed(self, session_id: str, action_summary: str) -> HarnessSnapshot:
        current = self.resume(session_id)
        if current.active_task_id is None:
            raise HarnessTransitionError("ACT requires an active task")
        data = dict(current.data)
        data["action"] = self._required(action_summary, "Action summary")
        return self._transition(
            current,
            HarnessPhase.VERIFY,
            data=data,
            note="Action ready for verification",
        )

    def verify(
        self,
        session_id: str,
        *,
        passed: bool,
        evidence: str,
    ) -> HarnessSnapshot:
        current = self.resume(session_id)
        if current.active_task_id is None:
            raise HarnessTransitionError("VERIFY requires an active task")
        verified_evidence = self._required(evidence, "Verification evidence")
        data = dict(current.data)
        if not passed:
            failures = list(data.get("verification_failures", []))
            failures.append(verified_evidence)
            data["verification_failures"] = failures
            return self._transition(
                current,
                HarnessPhase.ACT,
                data=data,
                note="Verification failed; returning to ACT",
                evidence=verified_evidence,
            )

        data["verification"] = verified_evidence
        return self._transition(
            current,
            HarnessPhase.RECORD,
            complete_task_id=current.active_task_id,
            task_verification=verified_evidence,
            data=data,
            note="Verification passed",
            evidence=verified_evidence,
        )

    def record(self, session_id: str, summary: str) -> HarnessSnapshot:
        current = self.resume(session_id)
        data = dict(current.data)
        data["record"] = self._required(summary, "Record summary")
        return self._transition(
            current,
            HarnessPhase.HANDOFF,
            data=data,
            note="Verified work recorded",
        )

    def handoff(
        self,
        session_id: str,
        summary: str,
        *,
        continue_work: bool = False,
    ) -> HarnessSnapshot:
        current = self.resume(session_id)
        handoff_summary = self._required(summary, "Handoff summary")
        data = dict(current.data)
        data["handoff"] = handoff_summary
        if continue_work:
            return self._transition(
                current,
                HarnessPhase.ORIENT,
                active_task_id=None,
                data={
                    "previous_handoff": handoff_summary,
                    "completed_task_id": current.active_task_id,
                },
                note="Handoff recorded; continuing with next objective",
                session_status="active",
            )

        return self._transition(
            current,
            HarnessPhase.COMPLETE,
            data=data,
            note="Handoff recorded; objective complete",
            session_status="completed",
        )

    def context(self, session_id: str) -> str:
        """Return the compact durable state packet for the next model request."""
        return self.store.build_state_context(session_id)

    def _transition(
        self,
        current: HarnessSnapshot,
        next_phase: HarnessPhase,
        *,
        active_task_id: str | None = None,
        data: dict[str, Any],
        note: str,
        evidence: str = "",
        start_task_id: str | None = None,
        complete_task_id: str | None = None,
        task_verification: str = "",
        session_status: str | None = None,
    ) -> HarnessSnapshot:
        self._assert_transition(current.phase, next_phase)
        if active_task_id is None and next_phase not in {
            HarnessPhase.ORIENT,
            HarnessPhase.COMPLETE,
        }:
            active_task_id = current.active_task_id
        state = self.store.transition_harness_state(
            current.session_id,
            expected_phase=current.phase.value,
            next_phase=next_phase.value,
            objective=current.objective,
            active_task_id=active_task_id,
            data=data,
            note=note,
            evidence=evidence,
            start_task_id=start_task_id,
            complete_task_id=complete_task_id,
            task_verification=task_verification,
            session_status=session_status,
        )
        return self._snapshot(state)

    def _assert_transition(
        self,
        current: HarnessPhase,
        requested: HarnessPhase,
    ) -> None:
        if requested not in self._ALLOWED[current]:
            raise HarnessTransitionError(
                f"Invalid harness transition: {current.value} -> {requested.value}"
            )

    def _snapshot(self, state: HarnessStateRecord) -> HarnessSnapshot:
        return HarnessSnapshot(
            session_id=state.session_id,
            phase=HarnessPhase(state.phase),
            objective=state.objective,
            active_task_id=state.active_task_id,
            data=state.data,
            revision=state.revision,
        )

    def _required(self, value: str, label: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"{label} cannot be empty")
        return cleaned
