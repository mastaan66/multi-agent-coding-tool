"""Iterative provider-neutral model and tool runtime."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Callable

from src.core.events import (
    MessageRole,
    ModelEventType,
    ModelMessage,
    RuntimeEvent,
    RuntimeEventType,
    ToolCall,
)
from src.providers.base import ModelProvider
from src.tools.base import ToolContext, ToolRegistry, ToolResult


class RuntimeLimitError(RuntimeError):
    """Raised when a bounded runtime guard stops an agent loop."""


@dataclass(frozen=True)
class RuntimeResult:
    """Final output and trace from one runtime execution."""

    response: str
    turns: int
    messages: tuple[ModelMessage, ...]
    events: tuple[RuntimeEvent, ...]


EventHandler = Callable[[RuntimeEvent], None]


class AgentRuntime:
    """Run streamed model turns and validated tools until completion."""

    def __init__(
        self,
        provider: ModelProvider,
        tools: ToolRegistry,
        context: ToolContext,
        *,
        max_turns: int = 12,
        repeated_tool_call_limit: int = 2,
        event_handler: EventHandler | None = None,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be positive")
        if repeated_tool_call_limit < 1:
            raise ValueError("repeated_tool_call_limit must be positive")
        self.provider = provider
        self.tools = tools
        self.context = context
        self.max_turns = max_turns
        self.repeated_tool_call_limit = repeated_tool_call_limit
        self.event_handler = event_handler

    def _emit(self, events: list[RuntimeEvent], event: RuntimeEvent) -> None:
        events.append(event)
        if self.event_handler is not None:
            self.event_handler(event)

    async def run(self, prompt: str, *, instructions: str = "") -> RuntimeResult:
        """Run a bounded model/tool conversation until a text-only response."""
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        messages = [ModelMessage(role=MessageRole.USER, content=prompt.strip())]
        events: list[RuntimeEvent] = []
        repeated_calls: Counter[str] = Counter()

        for turn in range(1, self.max_turns + 1):
            self._emit(
                events,
                RuntimeEvent(type=RuntimeEventType.TURN_STARTED, turn=turn),
            )
            text_parts: list[str] = []
            tool_calls: list[ToolCall] = []

            async for model_event in self.provider.stream(
                messages=tuple(messages),
                tools=tuple(self.tools.definitions),
                instructions=instructions,
            ):
                if model_event.type is ModelEventType.TEXT_DELTA:
                    text_parts.append(model_event.text)
                    self._emit(
                        events,
                        RuntimeEvent(
                            type=RuntimeEventType.TEXT_DELTA,
                            turn=turn,
                            text=model_event.text,
                        ),
                    )
                elif model_event.type is ModelEventType.TOOL_CALL:
                    if model_event.tool_call is None:
                        raise ValueError("Tool-call event is missing a tool call")
                    tool_calls.append(model_event.tool_call)

            response_text = "".join(text_parts)
            messages.append(
                ModelMessage(
                    role=MessageRole.ASSISTANT,
                    content=response_text,
                    tool_calls=tuple(tool_calls),
                )
            )

            if not tool_calls:
                self._emit(
                    events,
                    RuntimeEvent(
                        type=RuntimeEventType.TURN_COMPLETED,
                        turn=turn,
                        text=response_text,
                    ),
                )
                return RuntimeResult(
                    response=response_text,
                    turns=turn,
                    messages=tuple(messages),
                    events=tuple(events),
                )

            for tool_call in tool_calls:
                signature = json.dumps(
                    [tool_call.name, tool_call.arguments],
                    sort_keys=True,
                    separators=(",", ":"),
                )
                repeated_calls[signature] += 1
                if repeated_calls[signature] > self.repeated_tool_call_limit:
                    raise RuntimeLimitError(
                        f"Repeated tool-call limit reached for {tool_call.name}"
                    )

                self._emit(
                    events,
                    RuntimeEvent(
                        type=RuntimeEventType.TOOL_STARTED,
                        turn=turn,
                        tool_call=tool_call,
                    ),
                )
                result = await self.tools.execute(
                    tool_call.name,
                    tool_call.arguments,
                    self.context,
                )
                self._emit_tool_result(events, turn, tool_call, result)
                messages.append(
                    ModelMessage(
                        role=MessageRole.TOOL,
                        content=result.to_model_text(),
                        tool_call_id=tool_call.id,
                    )
                )

            self._emit(
                events,
                RuntimeEvent(type=RuntimeEventType.TURN_COMPLETED, turn=turn),
            )

        raise RuntimeLimitError(f"Maximum turn limit reached: {self.max_turns}")

    def _emit_tool_result(
        self,
        events: list[RuntimeEvent],
        turn: int,
        tool_call: ToolCall,
        result: ToolResult,
    ) -> None:
        self._emit(
            events,
            RuntimeEvent(
                type=RuntimeEventType.TOOL_COMPLETED,
                turn=turn,
                tool_call=tool_call,
                text=result.content,
                data={"success": result.success, "error": result.error},
            ),
        )
