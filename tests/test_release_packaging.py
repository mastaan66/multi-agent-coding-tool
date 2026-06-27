"""Tests for standalone release archive creation."""

from pathlib import Path

from scripts.package_release import (
    create_release_archive,
    normalize_architecture,
    normalize_platform,
)


def test_normalizes_release_targets() -> None:
    assert normalize_platform("Darwin") == "macos"
    assert normalize_architecture("aarch64") == "arm64"


def test_creates_tarball_and_checksum(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    binary = tmp_path / "input-binary"
    binary.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")

    archive, checksum = create_release_archive(
        binary=binary,
        output_dir=tmp_path / "release",
        platform_name="linux",
        architecture="x86_64",
        repository_root=repository_root,
    )

    assert archive.name == "ai-factory-linux-x86_64.tar.gz"
    assert archive.is_file()
    assert checksum.is_file()
    assert archive.name in checksum.read_text(encoding="utf-8")
