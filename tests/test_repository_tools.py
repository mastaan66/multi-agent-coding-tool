"""Tests for read-only repository tools."""

import asyncio
from pathlib import Path

from src.tools.base import ToolContext, ToolRegistry
from src.tools.repository import create_read_only_repository_tools


def execute_tool(
    registry: ToolRegistry,
    context: ToolContext,
    name: str,
    arguments: dict[str, object],
):
    return asyncio.run(registry.execute(name, arguments, context))


def test_read_and_search_repository_files(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "def greet():\n    return 'hello'\n", encoding="utf-8"
    )
    registry = ToolRegistry(create_read_only_repository_tools())
    context = ToolContext(repository_root=tmp_path)

    read_result = execute_tool(
        registry,
        context,
        "read_file",
        {"path": "src/app.py", "start_line": 1, "end_line": 2},
    )
    search_result = execute_tool(
        registry,
        context,
        "search",
        {"query": "hello", "glob": "*.py"},
    )

    assert read_result.success
    assert "1: def greet():" in read_result.content
    assert search_result.success
    assert "src/app.py:2" in search_result.content


def test_sensitive_files_are_denied_by_default(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    registry = ToolRegistry(create_read_only_repository_tools())
    context = ToolContext(repository_root=tmp_path)

    result = execute_tool(registry, context, "read_file", {"path": ".env"})

    assert not result.success
    assert result.error is not None
    assert "Sensitive file access is disabled" in result.error


def test_tool_registry_rejects_unknown_arguments(tmp_path: Path) -> None:
    registry = ToolRegistry(create_read_only_repository_tools())
    context = ToolContext(repository_root=tmp_path)

    result = execute_tool(
        registry,
        context,
        "list_files",
        {"path": ".", "unexpected": True},
    )

    assert not result.success
    assert result.error is not None
    assert "Invalid arguments" in result.error
