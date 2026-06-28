"""Provider-neutral streaming model interface."""

from __future__ import annotations

from typing import AsyncIterator, Protocol, Sequence

from src.core.events import ModelEvent, ModelMessage
from src.tools.base import ToolDefinition


class ModelProvider(Protocol):
    """A model backend capable of streaming text and normalized tool calls."""

    name: str

    def stream(
        self,
        *,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolDefinition],
        instructions: str,
    ) -> AsyncIterator[ModelEvent]:
        """Stream one model turn."""
        ...
