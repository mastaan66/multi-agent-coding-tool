"""Tests for durable message replay and persistent runtime resume."""

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

from src.core.events import (
    MessageRole,
    ModelEvent,
    ModelEventType,
    ModelMessage,
    RuntimeEventType,
    ToolCall,
)
from src.providers.base import ModelProvider
from src.sessions.runtime import PersistentAgentSession
from src.sessions.store import SQLiteSessionStore
from src.tools.base import ToolContext, ToolDefinition, ToolRegistry
from src.tools.repository import ReadFileTool


class ScriptedProvider(ModelProvider):
    name = "scripted"

    def __init__(self, turns: list[list[ModelEvent]]) -> None:
        self.turns = turns
        self.requests: list[Sequence[ModelMessage]] = []

    async def stream(
        self,
        *,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolDefinition],
        instructions: str,
    ) -> AsyncIterator[ModelEvent]:
        self.requests.append(messages)
        for event in self.turns.pop(0):
            yield event


def test_replay_repairs_interrupted_tool_batch_without_persisting_retry(
    tmp_path: Path,
) -> None:
    first = ToolCall(id="call-1", name="read_file", arguments={"path": "a.py"})
    second = ToolCall(id="call-2", name="read_file", arguments={"path": "b.py"})
    with SQLiteSessionStore(tmp_path / "sessions.db") as store:
        session = store.create_session(tmp_path)
        store.append_message(
            session.id,
            ModelMessage(role=MessageRole.USER, content="Inspect both files"),
        )
        store.append_message(
            session.id,
            ModelMessage(role=MessageRole.ASSISTANT, tool_calls=(first, second)),
        )
        store.append_message(
            session.id,
            ModelMessage(
                role=MessageRole.TOOL,
                content='{"success":true}',
                tool_call_id=first.id,
            ),
        )

        replay = store.replay_messages(session.id)

        assert len(store.list_messages(session.id)) == 3
        assert len(replay) == 4
        assert replay[-1].role is MessageRole.TOOL
        assert replay[-1].tool_call_id == second.id
        repaired = json.loads(replay[-1].content)
        assert repaired["data"]["interrupted"] is True
        assert "not replayed automatically" in repaired["error"]


def test_persistent_session_resumes_messages_and_global_turns(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Durable\n", encoding="utf-8")
    database = tmp_path / "sessions.db"
    call = ToolCall(id="call-1", name="read_file", arguments={"path": "README.md"})

    with SQLiteSessionStore(database) as store:
        session = store.create_session(tmp_path, session_id="session-1")
        first_provider = ScriptedProvider(
            [
                [
                    ModelEvent(type=ModelEventType.TOOL_CALL, tool_call=call),
                    ModelEvent(type=ModelEventType.COMPLETED),
                ],
                [
                    ModelEvent(type=ModelEventType.TEXT_DELTA, text="Initial inspection done."),
                    ModelEvent(type=ModelEventType.COMPLETED),
                ],
            ]
        )
        first_run = PersistentAgentSession(
            store=store,
            session_id=session.id,
            provider=first_provider,
            tools=ToolRegistry([ReadFileTool()]),
            tool_context=ToolContext(repository_root=tmp_path),
        )

        result = asyncio.run(first_run.run("Inspect the repository"))

        assert result.turns == 2
        assert len(store.list_messages(session.id)) == 4

        second_provider = ScriptedProvider(
            [
                [
                    ModelEvent(type=ModelEventType.TEXT_DELTA, text="Continue with tests."),
                    ModelEvent(type=ModelEventType.COMPLETED),
                ]
            ]
        )
        resumed = PersistentAgentSession(
            store=store,
            session_id=session.id,
            provider=second_provider,
            tools=ToolRegistry([ReadFileTool()]),
            tool_context=ToolContext(repository_root=tmp_path),
        )
        resumed_result = asyncio.run(resumed.run("What should happen next?"))

        assert resumed_result.turns == 1
        assert len(second_provider.requests[0]) == 5
        assert second_provider.requests[0][0].content == "Inspect the repository"
        assert second_provider.requests[0][-1].content == "What should happen next?"
        assert len(store.list_messages(session.id)) == 6
        turn_starts = [
            event.turn
            for event in store.list_events(session.id)
            if event.type == RuntimeEventType.TURN_STARTED.value
        ]
        assert turn_starts == [1, 2, 3]
