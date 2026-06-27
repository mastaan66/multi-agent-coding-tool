"""Create a checksummed release archive around a PyInstaller executable."""

from __future__ import annotations

import argparse
import hashlib
import platform as host_platform
import shutil
import tarfile
import zipfile
from pathlib import Path


def normalize_platform(value: str) -> str:
    """Normalize operating-system names used in release assets."""
    normalized = value.lower()
    aliases = {
        "darwin": "macos",
        "macos": "macos",
        "linux": "linux",
        "windows": "windows",
    }
    try:
        return aliases[normalized]
    except KeyError as error:
        raise ValueError(f"Unsupported release platform: {value}") from error


def normalize_architecture(value: str) -> str:
    """Normalize machine architecture names used in release assets."""
    normalized = value.lower()
    aliases = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }
    try:
        return aliases[normalized]
    except KeyError as error:
        raise ValueError(f"Unsupported release architecture: {value}") from error


def sha256(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_release_archive(
    binary: Path,
    output_dir: Path,
    platform_name: str,
    architecture: str,
    repository_root: Path,
) -> tuple[Path, Path]:
    """Create a platform archive and matching checksum file."""
    platform_name = normalize_platform(platform_name)
    architecture = normalize_architecture(architecture)
    output_dir.mkdir(parents=True, exist_ok=True)

    executable_name = "ai-factory.exe" if platform_name == "windows" else "ai-factory"
    stage_dir = output_dir / f"ai-factory-{platform_name}-{architecture}"
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir()

    staged_binary = stage_dir / executable_name
    shutil.copy2(binary, staged_binary)
    staged_binary.chmod(0o755)
    shutil.copy2(repository_root / "README.md", stage_dir / "README.md")
    shutil.copy2(repository_root / "LICENSE", stage_dir / "LICENSE")

    base_name = f"ai-factory-{platform_name}-{architecture}"
    if platform_name == "windows":
        archive = output_dir / f"{base_name}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            for path in sorted(stage_dir.iterdir()):
                zip_file.write(path, arcname=path.name)
    else:
        archive = output_dir / f"{base_name}.tar.gz"
        with tarfile.open(archive, "w:gz") as tar_file:
            for path in sorted(stage_dir.iterdir()):
                tar_file.add(path, arcname=path.name)

    checksum = output_dir / f"{archive.name}.sha256"
    checksum.write_text(f"{sha256(archive)}  {archive.name}\n", encoding="utf-8")
    shutil.rmtree(stage_dir)
    return archive, checksum


def build_parser() -> argparse.ArgumentParser:
    """Build the release-packaging argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("dist/release"))
    parser.add_argument("--platform", default=host_platform.system())
    parser.add_argument("--arch", default=host_platform.machine())
    return parser


def main() -> None:
    """Package one executable for distribution."""
    args = build_parser().parse_args()
    binary = args.binary.resolve()
    if not binary.is_file():
        raise SystemExit(f"Executable does not exist: {binary}")

    repository_root = Path(__file__).resolve().parents[1]
    archive, checksum = create_release_archive(
        binary=binary,
        output_dir=args.output_dir.resolve(),
        platform_name=args.platform,
        architecture=args.arch,
        repository_root=repository_root,
    )
    print(archive)
    print(checksum)


if __name__ == "__main__":
    main()
