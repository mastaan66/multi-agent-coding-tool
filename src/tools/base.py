"""Versioned tool contracts and registry."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError


class ToolEffect(str, Enum):
    """High-level side effect classification used by future policy engines."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"


class ToolInput(BaseModel):
    """Base class for strict tool arguments."""

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class ToolContext:
    """Runtime context supplied to every tool execution."""

    repository_root: Path
    allow_sensitive_files: bool = False


@dataclass(frozen=True)
class ToolDefinition:
    """Provider-neutral tool schema."""

    name: str
    description: str
    input_schema: dict[str, Any]
    effect: ToolEffect
    version: str = "1"


@dataclass(frozen=True)
class ToolResult:
    """Structured result returned by a tool."""

    success: bool
    content: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_model_text(self) -> str:
        """Serialize a stable result for the model conversation."""
        return json.dumps(
            {
                "success": self.success,
                "content": self.content,
                "data": self.data,
                "error": self.error,
            },
            ensure_ascii=False,
        )


class Tool(ABC):
    """Base class for validated agent tools."""

    name: str
    description: str
    effect: ToolEffect
    input_model: type[ToolInput]
    version = "1"

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
            effect=self.effect,
            version=self.version,
        )

    @abstractmethod
    async def execute(self, context: ToolContext, arguments: ToolInput) -> ToolResult:
        """Execute a validated tool call."""


class ToolRegistry:
    """Lookup and execution boundary for built-in and future extension tools."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool is already registered: {tool.name}")
        self._tools[tool.name] = tool

    @property
    def definitions(self) -> list[ToolDefinition]:
        return [self._tools[name].definition for name in sorted(self._tools)]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(success=False, content="", error=f"Unknown tool: {name}")
        try:
            validated = tool.input_model.model_validate(arguments)
        except ValidationError as error:
            return ToolResult(
                success=False,
                content="",
                error=f"Invalid arguments for {name}: {error}",
            )
        try:
            return await tool.execute(context, validated)
        except (OSError, ValueError) as error:
            return ToolResult(success=False, content="", error=str(error))
