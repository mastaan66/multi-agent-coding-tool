"""Tests for the provider-neutral model and tool runtime."""

import asyncio
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest

from src.core.events import (
    ModelEvent,
    ModelEventType,
    ModelMessage,
    RuntimeEventType,
    ToolCall,
)
from src.core.runtime import AgentRuntime, RuntimeLimitError
from src.tools.base import ToolContext, ToolDefinition, ToolRegistry
from src.tools.repository import ReadFileTool


class ScriptedProvider:
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


def test_runtime_executes_tool_then_returns_text(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    provider = ScriptedProvider(
        [
            [
                ModelEvent(
                    type=ModelEventType.TOOL_CALL,
                    tool_call=ToolCall(
                        id="call-1",
                        name="read_file",
                        arguments={"path": "README.md"},
                    ),
                ),
                ModelEvent(
                    type=ModelEventType.USAGE,
                    usage={"input_tokens": 100, "cached_tokens": 40},
                ),
                ModelEvent(type=ModelEventType.COMPLETED),
            ],
            [
                ModelEvent(type=ModelEventType.TEXT_DELTA, text="Repository inspected."),
                ModelEvent(
                    type=ModelEventType.USAGE,
                    usage={"input_tokens": 120, "output_tokens": 5},
                ),
                ModelEvent(type=ModelEventType.COMPLETED),
            ],
        ]
    )
    runtime = AgentRuntime(
        provider,
        ToolRegistry([ReadFileTool()]),
        ToolContext(repository_root=tmp_path),
    )

    result = asyncio.run(runtime.run("Explain this repository"))

    assert result.response == "Repository inspected."
    assert result.turns == 2
    assert len(provider.requests) == 2
    assert '"success": true' in provider.requests[1][-1].content
    assert result.usage == {
        "input_tokens": 220,
        "cached_tokens": 40,
        "output_tokens": 5,
    }
    assert result.events[1].type is RuntimeEventType.CONTEXT_PREPARED


def test_runtime_stops_repeated_tool_calls(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    repeated_turn = [
        ModelEvent(
            type=ModelEventType.TOOL_CALL,
            tool_call=ToolCall(
                id="call",
                name="read_file",
                arguments={"path": "README.md"},
            ),
        )
    ]
    provider = ScriptedProvider([repeated_turn, repeated_turn])
    runtime = AgentRuntime(
        provider,
        ToolRegistry([ReadFileTool()]),
        ToolContext(repository_root=tmp_path),
        repeated_tool_call_limit=1,
    )

    with pytest.raises(RuntimeLimitError, match="Repeated tool-call limit"):
        asyncio.run(runtime.run("Loop forever"))
