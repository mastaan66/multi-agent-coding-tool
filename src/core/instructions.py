"""Hierarchical repository instruction loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.repository import resolve_repository_path


@dataclass(frozen=True)
class InstructionDocument:
    """One instruction file and its repository-relative scope."""

    path: str
    scope: str
    content: str


@dataclass(frozen=True)
class InstructionSet:
    """Ordered instructions applying to one repository path."""

    documents: tuple[InstructionDocument, ...]

    @property
    def combined(self) -> str:
        sections = [
            f"# Instructions from {document.path}\n\n{document.content.strip()}"
            for document in self.documents
        ]
        return "\n\n".join(sections)


def load_instruction_hierarchy(
    root: Path,
    target_path: str = ".",
    *,
    file_name: str = "AGENTS.md",
    max_bytes: int = 64 * 1024,
) -> InstructionSet:
    """Load root-to-leaf instruction files that apply to a target path."""
    resolved_root = root.resolve()
    target = resolve_repository_path(resolved_root, target_path)
    target_directory = target if target.is_dir() else target.parent
    relative_directory = target_directory.relative_to(resolved_root)

    directories = [resolved_root]
    current = resolved_root
    for part in relative_directory.parts:
        current = current / part
        directories.append(current)

    documents: list[InstructionDocument] = []
    for directory in directories:
        instruction_path = directory / file_name
        if not instruction_path.is_file() or instruction_path.is_symlink():
            continue
        if instruction_path.stat().st_size > max_bytes:
            raise ValueError(f"Instruction file exceeds {max_bytes} bytes: {instruction_path}")
        scope_path = directory.relative_to(resolved_root).as_posix()
        documents.append(
            InstructionDocument(
                path=instruction_path.relative_to(resolved_root).as_posix(),
                scope="." if scope_path == "." else scope_path,
                content=instruction_path.read_text(encoding="utf-8"),
            )
        )
    return InstructionSet(documents=tuple(documents))
