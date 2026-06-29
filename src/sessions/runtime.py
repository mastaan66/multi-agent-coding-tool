"""Persistent session wrapper for AgentRuntime resume and replay."""

from __future__ import annotations

import asyncio
from typing import Callable

from src.core.context import ContextCompiler
from src.core.events import ModelMessage, RuntimeEvent, ToolCall
from src.core.runtime import AgentRuntime, RuntimeResult
from src.providers.base import ModelProvider
from src.sessions.store import SQLiteSessionStore
from src.tools.base import ToolContext, ToolRegistry, ToolResult


class PersistentAgentSession:
    """Bind one agent runtime to durable events, messages, and replay history."""

    def __init__(
        self,
        *,
        store: SQLiteSessionStore,
        session_id: str,
        provider: ModelProvider,
        tools: ToolRegistry,
        tool_context: ToolContext,
        max_turns: int = 12,
        repeated_tool_call_limit: int = 2,
        event_handler: Callable[[RuntimeEvent], None] | None = None,
        context_compiler: ContextCompiler | None = None,
        result_processor: Callable[[ToolCall, ToolResult], ToolResult] | None = None,
    ) -> None:
        store.get_session(session_id)
        self.store = store
        self.session_id = session_id
        persist_event = store.event_handler(session_id)

        def handle_event(event: RuntimeEvent) -> None:
            persist_event(event)
            if event_handler is not None:
                event_handler(event)

        self.runtime = AgentRuntime(
            provider,
            tools,
            tool_context,
            max_turns=max_turns,
            repeated_tool_call_limit=repeated_tool_call_limit,
            event_handler=handle_event,
            message_handler=store.message_handler(session_id),
            context_compiler=context_compiler,
            result_processor=result_processor,
        )

    def replay(self) -> tuple[ModelMessage, ...]:
        """Return provider-safe history, repairing interrupted tool batches."""
        return self.store.replay_messages(self.session_id)

    async def run(
        self,
        prompt: str,
        *,
        instructions: str = "",
        state_context: str | None = None,
    ) -> RuntimeResult:
        """Resume persisted history and execute one bounded runtime invocation."""
        self.store.set_session_status(self.session_id, "active")
        durable_state = (
            self.store.build_state_context(self.session_id)
            if state_context is None
            else state_context
        )
        try:
            return await self.runtime.run(
                prompt,
                instructions=instructions,
                state_context=durable_state,
                prior_messages=self.replay(),
            )
        except (asyncio.CancelledError, KeyboardInterrupt):
            self.store.set_session_status(self.session_id, "interrupted")
            raise
        except Exception:
            self.store.set_session_status(self.session_id, "failed")
            raise
