"""Provider-neutral model and runtime events."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class ToolCall:
    """One normalized model request to execute a tool."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelMessage:
    """One normalized conversation message."""

    role: MessageRole
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None


class ModelEventType(str, Enum):
    TEXT_DELTA = "text_delta"
    TOOL_CALL = "tool_call"
    USAGE = "usage"
    COMPLETED = "completed"


@dataclass(frozen=True)
class ModelEvent:
    """One streamed event emitted by a model provider."""

    type: ModelEventType
    text: str = ""
    tool_call: ToolCall | None = None
    usage: dict[str, int] = field(default_factory=dict)


class RuntimeEventType(str, Enum):
    TURN_STARTED = "turn_started"
    CONTEXT_PREPARED = "context_prepared"
    MODEL_USAGE = "model_usage"
    TEXT_DELTA = "text_delta"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TURN_COMPLETED = "turn_completed"


@dataclass(frozen=True)
class RuntimeEvent:
    """Observable lifecycle event emitted by the agent runtime."""

    type: RuntimeEventType
    turn: int
    text: str = ""
    tool_call: ToolCall | None = None
    data: dict[str, Any] = field(default_factory=dict)
