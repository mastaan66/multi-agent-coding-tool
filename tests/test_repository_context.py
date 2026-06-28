"""Tests for repository discovery and instruction scoping."""

from pathlib import Path

import pytest

from src.core.instructions import load_instruction_hierarchy
from src.core.repository import (
    RepositoryPathError,
    build_repository_snapshot,
    resolve_repository_path,
)


def test_snapshot_skips_common_generated_directories(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("ignored\n", encoding="utf-8")

    snapshot = build_repository_snapshot(tmp_path)

    assert snapshot.files == ("src/app.py",)
    assert snapshot.languages == (("Python", 1),)


def test_repository_path_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RepositoryPathError):
        resolve_repository_path(root, "linked/secret.txt")


def test_instruction_hierarchy_applies_root_to_leaf(tmp_path: Path) -> None:
    nested = tmp_path / "services" / "api"
    nested.mkdir(parents=True)
    (tmp_path / "AGENTS.md").write_text("Root rules\n", encoding="utf-8")
    (tmp_path / "services" / "AGENTS.md").write_text(
        "Service rules\n", encoding="utf-8"
    )
    (nested / "app.py").write_text("pass\n", encoding="utf-8")

    instructions = load_instruction_hierarchy(tmp_path, "services/api/app.py")

    assert [document.path for document in instructions.documents] == [
        "AGENTS.md",
        "services/AGENTS.md",
    ]
    assert "Root rules" in instructions.combined
    assert "Service rules" in instructions.combined
