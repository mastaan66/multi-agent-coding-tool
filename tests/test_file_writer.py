"""Tests for generated project path safety."""

from pathlib import Path

import pytest

from src.core.errors import UnsafeProjectPathError
from src.tools.file_writer import resolve_project_path, write_project_files


def test_write_project_files_writes_nested_files(tmp_path: Path) -> None:
    written = write_project_files(
        [{"file_path": "src/app.py", "content": "print('ok')\n"}],
        tmp_path,
    )

    expected = tmp_path / "src" / "app.py"
    assert written == [str(expected)]
    assert expected.read_text(encoding="utf-8") == "print('ok')\n"


@pytest.mark.parametrize("file_path", ["", "../escape.py", "/tmp/escape.py"])
def test_resolve_project_path_rejects_unsafe_paths(
    tmp_path: Path, file_path: str
) -> None:
    with pytest.raises(UnsafeProjectPathError):
        resolve_project_path(file_path, tmp_path)


def test_write_project_files_validates_all_paths_before_writing(tmp_path: Path) -> None:
    files = [
        {"file_path": "safe.py", "content": "safe = True\n"},
        {"file_path": "../escape.py", "content": "unsafe = True\n"},
    ]

    with pytest.raises(UnsafeProjectPathError):
        write_project_files(files, tmp_path)

    assert not (tmp_path / "safe.py").exists()


def test_resolve_project_path_rejects_symlink_escape(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    outside_dir = tmp_path / "outside"
    output_dir.mkdir()
    outside_dir.mkdir()
    (output_dir / "linked").symlink_to(outside_dir, target_is_directory=True)

    with pytest.raises(UnsafeProjectPathError):
        resolve_project_path("linked/escape.py", output_dir)
