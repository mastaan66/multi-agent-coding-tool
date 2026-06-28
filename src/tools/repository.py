"""Read-only tools for repository exploration and planning."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path

from pydantic import Field

from src.core.repository import (
    is_sensitive_path,
    list_repository_files,
    resolve_repository_path,
)
from src.tools.base import Tool, ToolContext, ToolEffect, ToolInput, ToolResult


MAX_READ_BYTES = 128 * 1024
MAX_SEARCH_BYTES = 256 * 1024


def _require_readable_file(context: ToolContext, path_text: str) -> Path:
    path = resolve_repository_path(context.repository_root, path_text)
    if not path.is_file():
        raise ValueError(f"File does not exist: {path_text}")
    if is_sensitive_path(path) and not context.allow_sensitive_files:
        raise ValueError(f"Sensitive file access is disabled: {path_text}")
    return path


class ListFilesInput(ToolInput):
    path: str = "."
    limit: int = Field(default=200, ge=1, le=5_000)


class ListFilesTool(Tool):
    name = "list_files"
    description = "List repository files while respecting Git ignore rules."
    effect = ToolEffect.READ
    input_model = ListFilesInput

    async def execute(self, context: ToolContext, arguments: ToolInput) -> ToolResult:
        parsed = ListFilesInput.model_validate(arguments.model_dump())
        target = resolve_repository_path(context.repository_root, parsed.path)
        if not target.is_dir():
            raise ValueError(f"Directory does not exist: {parsed.path}")
        prefix = target.relative_to(context.repository_root).as_posix()
        prefix = "" if prefix == "." else f"{prefix}/"
        files = [
            file_name
            for file_name in list_repository_files(context.repository_root)
            if not prefix or file_name.startswith(prefix)
        ][: parsed.limit]
        return ToolResult(
            success=True,
            content="\n".join(files) if files else "No files found.",
            data={"files": files, "truncated": len(files) == parsed.limit},
        )


class ReadFileInput(ToolInput):
    path: str
    start_line: int = Field(default=1, ge=1)
    end_line: int | None = Field(default=None, ge=1)


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a bounded UTF-8 text range from a repository file."
    effect = ToolEffect.READ
    input_model = ReadFileInput

    async def execute(self, context: ToolContext, arguments: ToolInput) -> ToolResult:
        parsed = ReadFileInput.model_validate(arguments.model_dump())
        path = _require_readable_file(context, parsed.path)
        if path.stat().st_size > MAX_READ_BYTES:
            raise ValueError(f"File exceeds the {MAX_READ_BYTES}-byte read limit: {parsed.path}")
        raw_content = path.read_bytes()
        if b"\0" in raw_content:
            raise ValueError(f"Binary files cannot be read: {parsed.path}")
        lines = raw_content.decode("utf-8").splitlines()
        end_line = parsed.end_line or min(len(lines), parsed.start_line + 199)
        if end_line < parsed.start_line:
            raise ValueError("end_line must be greater than or equal to start_line")
        selected = lines[parsed.start_line - 1 : end_line]
        numbered = [
            f"{line_number}: {line}"
            for line_number, line in enumerate(selected, start=parsed.start_line)
        ]
        return ToolResult(
            success=True,
            content="\n".join(numbered),
            data={
                "path": parsed.path,
                "start_line": parsed.start_line,
                "end_line": min(end_line, len(lines)),
                "total_lines": len(lines),
            },
        )


class SearchInput(ToolInput):
    query: str = Field(min_length=1, max_length=500)
    path: str = "."
    glob: str | None = None
    case_sensitive: bool = False
    limit: int = Field(default=100, ge=1, le=500)


class SearchTool(Tool):
    name = "search"
    description = "Search bounded repository text files and return matching lines."
    effect = ToolEffect.READ
    input_model = SearchInput

    async def execute(self, context: ToolContext, arguments: ToolInput) -> ToolResult:
        parsed = SearchInput.model_validate(arguments.model_dump())
        target = resolve_repository_path(context.repository_root, parsed.path)
        if not target.is_dir():
            raise ValueError(f"Directory does not exist: {parsed.path}")
        prefix = target.relative_to(context.repository_root).as_posix()
        prefix = "" if prefix == "." else f"{prefix}/"
        needle = parsed.query if parsed.case_sensitive else parsed.query.lower()
        matches: list[dict[str, object]] = []

        for file_name in list_repository_files(context.repository_root):
            if prefix and not file_name.startswith(prefix):
                continue
            if parsed.glob and not fnmatch.fnmatch(file_name, parsed.glob):
                continue
            path = resolve_repository_path(context.repository_root, file_name)
            if is_sensitive_path(path) and not context.allow_sensitive_files:
                continue
            if not path.is_file() or path.stat().st_size > MAX_SEARCH_BYTES:
                continue
            raw_content = path.read_bytes()
            if b"\0" in raw_content:
                continue
            for line_number, line in enumerate(
                raw_content.decode("utf-8", errors="replace").splitlines(), start=1
            ):
                haystack = line if parsed.case_sensitive else line.lower()
                if needle not in haystack:
                    continue
                matches.append(
                    {"path": file_name, "line": line_number, "text": line[:500]}
                )
                if len(matches) >= parsed.limit:
                    break
            if len(matches) >= parsed.limit:
                break

        content = "\n".join(
            f"{match['path']}:{match['line']}: {match['text']}" for match in matches
        ) or "No matches found."
        return ToolResult(
            success=True,
            content=content,
            data={"matches": matches, "truncated": len(matches) == parsed.limit},
        )


def _run_git(root: Path, arguments: list[str], timeout: int = 10) -> ToolResult:
    if not (root / ".git").exists():
        raise ValueError(f"Not a Git repository: {root}")
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    output = result.stdout if result.returncode == 0 else result.stderr
    return ToolResult(
        success=result.returncode == 0,
        content=output.strip() or "No output.",
        data={"return_code": result.returncode},
        error=None if result.returncode == 0 else output.strip(),
    )


class GitStatusInput(ToolInput):
    pass


class GitStatusTool(Tool):
    name = "git_status"
    description = "Show the concise repository branch and working-tree status."
    effect = ToolEffect.READ
    input_model = GitStatusInput

    async def execute(self, context: ToolContext, arguments: ToolInput) -> ToolResult:
        return _run_git(context.repository_root, ["status", "--short", "--branch"])


class GitDiffInput(ToolInput):
    staged: bool = False
    path: str | None = None


class GitDiffTool(Tool):
    name = "git_diff"
    description = "Show the current unstaged or staged Git diff."
    effect = ToolEffect.READ
    input_model = GitDiffInput

    async def execute(self, context: ToolContext, arguments: ToolInput) -> ToolResult:
        parsed = GitDiffInput.model_validate(arguments.model_dump())
        command = ["diff"]
        if parsed.staged:
            command.append("--cached")
        if parsed.path:
            path = resolve_repository_path(context.repository_root, parsed.path)
            command.extend(["--", path.relative_to(context.repository_root).as_posix()])
        result = _run_git(context.repository_root, command)
        if len(result.content) <= MAX_SEARCH_BYTES:
            return result
        return ToolResult(
            success=result.success,
            content=result.content[:MAX_SEARCH_BYTES] + "\n... diff truncated ...",
            data={**result.data, "truncated": True},
            error=result.error,
        )


def create_read_only_repository_tools() -> list[Tool]:
    """Return the built-in repository exploration tool set."""
    return [ListFilesTool(), ReadFileTool(), SearchTool(), GitStatusTool(), GitDiffTool()]
