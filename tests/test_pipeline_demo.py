"""Offline end-to-end tests for the legacy generation pipeline."""

from pathlib import Path

from src.core.config import settings
from src.core.models import PipelineStage
from src.core.pipeline import Pipeline


def test_demo_pipeline_completes_offline(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.setattr(settings, "output_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_review_iterations", 1)
    monkeypatch.setattr(settings, "max_test_fix_iterations", 1)

    state = Pipeline(demo=True).run("Build a todo API")
    capsys.readouterr()

    assert state.current_stage is PipelineStage.COMPLETE
    assert state.test_result is not None
    assert state.test_result.passed
    assert state.test_result.total_tests == 3
    assert state.deployment is not None

    project_dirs = list(tmp_path.glob("todo_api_*"))
    assert len(project_dirs) == 1
    project_dir = project_dirs[0]
    assert (project_dir / "tests" / "test_todos.py").is_file()
    assert (project_dir / "Dockerfile").is_file()
    assert (project_dir / "DEPLOYMENT.md").is_file()
    assert (project_dir / "app" / "routers" / "__init__.py").is_file()
    assert "auth" not in (project_dir / "app" / "main.py").read_text(
        encoding="utf-8"
    )
    assert (project_dir / "requirements.txt").read_text(
        encoding="utf-8"
    ).splitlines() == ["fastapi==0.115.0", "uvicorn==0.30.0", "pydantic==2.9.0"]
    assert "\n## Docker\n" in (project_dir / "DEPLOYMENT.md").read_text(
        encoding="utf-8"
    )
