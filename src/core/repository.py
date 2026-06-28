"""Repository discovery and bounded context helpers."""

from __future__ import annotations

import os
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


DEFAULT_IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "target",
        "venv",
    }
)

LANGUAGE_BY_SUFFIX = {
    ".c": "C",
    ".cpp": "C++",
    ".css": "CSS",
    ".go": "Go",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".json": "JSON",
    ".kt": "Kotlin",
    ".md": "Markdown",
    ".php": "PHP",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".sh": "Shell",
    ".sql": "SQL",
    ".toml": "TOML",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".yaml": "YAML",
    ".yml": "YAML",
}

SENSITIVE_FILE_NAMES = frozenset(
    {
        ".env",
        ".npmrc",
        ".pypirc",
        "credentials.json",
        "id_dsa",
        "id_ed25519",
        "id_rsa",
    }
)
SENSITIVE_SUFFIXES = frozenset({".key", ".p12", ".pfx", ".pem"})


class RepositoryPathError(ValueError):
    """Raised when a requested path escapes the repository root."""


@dataclass(frozen=True)
class RepositorySnapshot:
    """A compact, deterministic summary of one repository."""

    root: Path
    files: tuple[str, ...]
    languages: tuple[tuple[str, int], ...]


def discover_repository(start: Path | str = ".") -> Path:
    """Return the nearest Git repository root, or the resolved start directory."""
    current = Path(start).expanduser().resolve()
    if current.is_file():
        current = current.parent
    if not current.is_dir():
        raise FileNotFoundError(f"Repository path does not exist: {current}")

    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def resolve_repository_path(root: Path, requested_path: str = ".") -> Path:
    """Resolve a relative path while enforcing repository containment."""
    relative = Path(requested_path)
    if relative.is_absolute():
        raise RepositoryPathError(f"Absolute paths are not allowed: {requested_path}")

    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    if resolved != resolved_root and not resolved.is_relative_to(resolved_root):
        raise RepositoryPathError(f"Path escapes repository root: {requested_path}")
    return resolved


def is_sensitive_path(path: Path) -> bool:
    """Return whether a path commonly contains credentials or private keys."""
    name = path.name.lower()
    return (
        name in SENSITIVE_FILE_NAMES
        or name.startswith(".env.")
        or path.suffix.lower() in SENSITIVE_SUFFIXES
    )


def _git_files(root: Path) -> list[str] | None:
    if not (root / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None

    files: list[str] = []
    for raw_path in result.stdout.decode("utf-8", errors="replace").split("\0"):
        if not raw_path:
            continue
        try:
            path = resolve_repository_path(root, raw_path)
        except RepositoryPathError:
            continue
        if path.is_file():
            files.append(path.relative_to(root).as_posix())
    return files


def _walk_files(root: Path) -> list[str]:
    files: list[str] = []
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in DEFAULT_IGNORED_DIRECTORIES
            and not (Path(directory) / name).is_symlink()
        )
        for file_name in sorted(file_names):
            path = Path(directory) / file_name
            try:
                resolved = resolve_repository_path(root, path.relative_to(root).as_posix())
            except RepositoryPathError:
                continue
            if resolved.is_file():
                files.append(resolved.relative_to(root).as_posix())
    return files


def list_repository_files(root: Path, limit: int = 5_000) -> list[str]:
    """List tracked and untracked files with Git ignore support when available."""
    if limit < 1:
        raise ValueError("File limit must be positive")
    files = _git_files(root)
    if files is None:
        files = _walk_files(root)
    return sorted(dict.fromkeys(files))[:limit]


def build_repository_snapshot(start: Path | str = ".", limit: int = 5_000) -> RepositorySnapshot:
    """Build a compact repository snapshot without reading file contents."""
    root = discover_repository(start)
    files = list_repository_files(root, limit=limit)
    language_counts = Counter(
        LANGUAGE_BY_SUFFIX.get(Path(file_name).suffix.lower(), "Other")
        for file_name in files
    )
    languages = tuple(
        sorted(language_counts.items(), key=lambda item: (-item[1], item[0]))
    )
    return RepositorySnapshot(root=root, files=tuple(files), languages=languages)


def format_repository_snapshot(snapshot: RepositorySnapshot, preview_limit: int = 40) -> str:
    """Render a human-readable repository snapshot."""
    language_summary = ", ".join(
        f"{language} ({count})" for language, count in snapshot.languages
    ) or "none"
    lines = [
        f"Repository: {snapshot.root}",
        f"Files: {len(snapshot.files)}",
        f"Languages: {language_summary}",
        "File preview:",
    ]
    lines.extend(f"  {file_name}" for file_name in snapshot.files[:preview_limit])
    remaining = len(snapshot.files) - preview_limit
    if remaining > 0:
        lines.append(f"  ... and {remaining} more")
    return "\n".join(lines)
