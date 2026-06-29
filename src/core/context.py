"""Token-bounded context assembly for provider requests."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Protocol, Sequence

from src.core.events import ModelMessage
from src.tools.base import ToolDefinition


class ContextBudgetError(RuntimeError):
    """Raised when mandatory context cannot fit inside the configured budget."""


class TokenEstimator(Protocol):
    """Estimate provider tokens without depending on a specific tokenizer."""

    def count_text(self, text: str) -> int:
        """Return an estimated token count for text."""
        ...

    def truncate_text(self, text: str, max_tokens: int) -> str:
        """Return a prefix that fits within an estimated token budget."""
        ...


class HeuristicTokenEstimator:
    """Conservative tokenizer fallback using four characters per token."""

    def count_text(self, text: str) -> int:
        if not text:
            return 0
        return max(1, (len(text) + 3) // 4)

    def truncate_text(self, text: str, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""
        max_characters = max_tokens * 4
        if len(text) <= max_characters:
            return text
        marker = "\n...[context truncated]..."
        if max_characters <= len(marker):
            return marker[:max_characters]
        return text[: max_characters - len(marker)] + marker


@dataclass(frozen=True)
class ContextBudget:
    """Input and output token limits for one provider request."""

    max_tokens: int = 32_000
    reserved_output_tokens: int = 4_000

    def __post_init__(self) -> None:
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        if self.reserved_output_tokens < 0:
            raise ValueError("reserved_output_tokens cannot be negative")
        if self.reserved_output_tokens >= self.max_tokens:
            raise ValueError("reserved_output_tokens must be smaller than max_tokens")

    @property
    def input_tokens(self) -> int:
        return self.max_tokens - self.reserved_output_tokens


@dataclass(frozen=True)
class CompiledContext:
    """The bounded provider input plus accounting metadata."""

    messages: tuple[ModelMessage, ...]
    instructions: str
    estimated_tokens: int
    dropped_messages: int = 0
    truncated_messages: int = 0


class ContextCompiler:
    """Keep mandatory state and the newest complete tool-use blocks in context."""

    _MESSAGE_OVERHEAD = 8
    _TOOL_OVERHEAD = 24

    def __init__(
        self,
        budget: ContextBudget | None = None,
        estimator: TokenEstimator | None = None,
    ) -> None:
        self.budget = budget or ContextBudget()
        self.estimator = estimator or HeuristicTokenEstimator()

    def compile(
        self,
        *,
        messages: Sequence[ModelMessage],
        instructions: str,
        tools: Sequence[ToolDefinition] = (),
        state_context: str = "",
    ) -> CompiledContext:
        """Assemble a bounded request without splitting assistant/tool-call blocks."""
        if not messages:
            raise ValueError("At least one message is required")

        compiled_instructions = instructions
        if state_context.strip():
            separator = "\n\n" if instructions else ""
            compiled_instructions += (
                f"{separator}# Active task state\n{state_context.strip()}"
            )
        fixed_tokens = self.estimator.count_text(compiled_instructions) + self._count_tools(tools)
        first_message = messages[0]
        mandatory_tokens = fixed_tokens + self._count_message(first_message)
        if mandatory_tokens > self.budget.input_tokens:
            raise ContextBudgetError(
                "Instructions, task state, tools, and the initial user request exceed the input budget"
            )

        blocks = self._blocks(messages[1:])
        remaining = self.budget.input_tokens - mandatory_tokens
        retained_reversed: list[tuple[ModelMessage, ...]] = []
        truncated_messages = 0

        for block in reversed(blocks):
            block_tokens = self._count_block(block)
            if block_tokens <= remaining:
                retained_reversed.append(block)
                remaining -= block_tokens
                continue
            if not retained_reversed:
                fitted, truncated = self._fit_block(block, remaining)
                if fitted:
                    retained_reversed.append(fitted)
                    remaining -= self._count_block(fitted)
                    truncated_messages += truncated
            break

        retained = list(reversed(retained_reversed))
        compiled_messages = (first_message, *(message for block in retained for message in block))
        dropped_messages = len(messages) - len(compiled_messages)
        estimated_tokens = fixed_tokens + sum(
            self._count_message(message) for message in compiled_messages
        )
        return CompiledContext(
            messages=tuple(compiled_messages),
            instructions=compiled_instructions,
            estimated_tokens=estimated_tokens,
            dropped_messages=dropped_messages,
            truncated_messages=truncated_messages,
        )

    def _blocks(self, messages: Sequence[ModelMessage]) -> list[tuple[ModelMessage, ...]]:
        blocks: list[list[ModelMessage]] = []
        for message in messages:
            if not blocks or message.role.value != "tool":
                blocks.append([message])
            else:
                blocks[-1].append(message)
        return [tuple(block) for block in blocks]

    def _fit_block(
        self,
        block: tuple[ModelMessage, ...],
        available_tokens: int,
    ) -> tuple[tuple[ModelMessage, ...], int]:
        fixed = sum(self._count_message(replace(message, content="")) for message in block)
        if fixed > available_tokens:
            return (), 0
        content_messages = [message for message in block if message.content]
        if not content_messages:
            return block, 0
        content_budget = available_tokens - fixed
        per_message = max(0, content_budget // len(content_messages))
        fitted: list[ModelMessage] = []
        truncated = 0
        for message in block:
            content = self.estimator.truncate_text(message.content, per_message)
            if content != message.content:
                truncated += 1
            fitted.append(replace(message, content=content))
        return tuple(fitted), truncated

    def _count_block(self, block: Sequence[ModelMessage]) -> int:
        return sum(self._count_message(message) for message in block)

    def _count_message(self, message: ModelMessage) -> int:
        tool_calls = [
            {"id": call.id, "name": call.name, "arguments": call.arguments}
            for call in message.tool_calls
        ]
        serialized_calls = json.dumps(tool_calls, sort_keys=True, ensure_ascii=False)
        return (
            self._MESSAGE_OVERHEAD
            + self.estimator.count_text(message.content)
            + self.estimator.count_text(serialized_calls)
            + self.estimator.count_text(message.tool_call_id or "")
        )

    def _count_tools(self, tools: Sequence[ToolDefinition]) -> int:
        payload = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "effect": tool.effect.value,
                "version": tool.version,
            }
            for tool in tools
        ]
        return self._TOOL_OVERHEAD + self.estimator.count_text(
            json.dumps(payload, sort_keys=True, ensure_ascii=False)
        )
