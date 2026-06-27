"""Typed errors raised by the pipeline and its tools."""

from __future__ import annotations


class PipelineError(RuntimeError):
    """Base class for expected pipeline failures."""


class StructuredOutputError(PipelineError):
    """Raised when an agent response cannot be parsed as structured output."""

    def __init__(self, stage: str, detail: str) -> None:
        self.stage = stage
        self.detail = detail
        super().__init__(f"{stage} returned invalid structured output: {detail}")


class UnsafeProjectPathError(PipelineError):
    """Raised when a generated file path escapes the project directory."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        super().__init__(f"Generated file path is outside the project directory: {file_path}")
