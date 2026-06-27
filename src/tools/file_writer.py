"""File writer tool for generated project files."""

from pathlib import Path

from src.core.errors import UnsafeProjectPathError


def resolve_project_path(file_path: str, output_dir: Path) -> Path:
    """Resolve a generated path and ensure it remains inside the output directory."""
    relative_path = Path(file_path)
    if not file_path or relative_path.is_absolute():
        raise UnsafeProjectPathError(file_path)

    resolved_output = output_dir.resolve()
    resolved_path = (resolved_output / relative_path).resolve()
    if resolved_path == resolved_output or not resolved_path.is_relative_to(resolved_output):
        raise UnsafeProjectPathError(file_path)
    return resolved_path


def write_project_files(files: list[dict], output_dir: Path) -> list[str]:
    """Validate and write generated files inside the output directory."""
    resolved_output = output_dir.resolve()
    pending_writes: list[tuple[str, Path, str]] = []

    for file_info in files:
        relative_path = file_info["file_path"]
        full_path = resolve_project_path(relative_path, resolved_output)
        pending_writes.append((relative_path, full_path, file_info["content"]))

    resolved_output.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for _, full_path, content in pending_writes:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        written.append(str(full_path))

    return written
