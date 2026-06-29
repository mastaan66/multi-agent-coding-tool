"""Tests for bounded, tool-call-safe context compilation."""

import pytest

from src.core.context import ContextBudget, ContextBudgetError, ContextCompiler
from src.core.events import MessageRole, ModelMessage, ToolCall


def test_context_compiler_keeps_initial_request_and_latest_atomic_block() -> None:
    old_call = ToolCall(id="old", name="read_file", arguments={"path": "old.py"})
    new_call = ToolCall(id="new", name="read_file", arguments={"path": "new.py"})
    messages = (
        ModelMessage(role=MessageRole.USER, content="Investigate the repository"),
        ModelMessage(role=MessageRole.ASSISTANT, tool_calls=(old_call,)),
        ModelMessage(role=MessageRole.TOOL, content="o" * 800, tool_call_id="old"),
        ModelMessage(role=MessageRole.ASSISTANT, tool_calls=(new_call,)),
        ModelMessage(role=MessageRole.TOOL, content="n" * 800, tool_call_id="new"),
    )
    compiler = ContextCompiler(ContextBudget(max_tokens=220, reserved_output_tokens=20))

    compiled = compiler.compile(
        messages=messages,
        instructions="Follow repository rules.",
        state_context='{"task":"inspect"}',
    )

    assert compiled.messages[0] == messages[0]
    assert "# Active task state" in compiled.instructions
    assert '{"task":"inspect"}' in compiled.instructions
    assert compiled.messages[-2].tool_calls == (new_call,)
    assert compiled.messages[-1].tool_call_id == "new"
    assert all(message.tool_call_id != "old" for message in compiled.messages)
    assert compiled.dropped_messages == 2
    assert compiled.truncated_messages == 1
    assert compiled.estimated_tokens <= compiler.budget.input_tokens


def test_context_compiler_rejects_oversized_mandatory_context() -> None:
    compiler = ContextCompiler(ContextBudget(max_tokens=100, reserved_output_tokens=20))

    with pytest.raises(ContextBudgetError, match="initial user request"):
        compiler.compile(
            messages=(ModelMessage(role=MessageRole.USER, content="request"),),
            instructions="i" * 400,
        )


def test_context_budget_validation() -> None:
    with pytest.raises(ValueError, match="smaller"):
        ContextBudget(max_tokens=100, reserved_output_tokens=100)
