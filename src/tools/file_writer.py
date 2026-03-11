"""File writer tool — safely writes generated files to the output directory."""

from pathlib import Path

from rich.console import Console

console = Console()


def write_project_files(files: list[dict], output_dir: Path) -> list[str]:
    """Write a list of code files to the output directory.

    Args:
        files: List of dicts with 'file_path' and 'content' keys.
        output_dir: Root directory to write into.

    Returns:
        List of absolute paths that were written.
    """
    written: list[str] = []
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for file_info in files:
        rel_path = file_info["file_path"].lstrip("/")
        full_path = (output_dir / rel_path).resolve()

        # Safety: ensure we stay within output_dir
        if not str(full_path).startswith(str(output_dir)):
            console.print(
                f"  [red]✗ Skipped dangerous path: {rel_path}[/red]"
            )
            continue

        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(file_info["content"], encoding="utf-8")
        written.append(str(full_path))
        console.print(f"  [green]✓[/green] {rel_path}")

    return written
