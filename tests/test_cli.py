"""Tests for command-line configuration."""

import sys
from pathlib import Path

import src.main as main_module
from src.core.config import settings


def test_main_applies_output_directory(
    monkeypatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}
    original_output_dir = settings.output_dir
    monkeypatch.setattr(settings, "output_dir", original_output_dir)

    def fake_run_direct(user_request: str, demo: bool = False) -> None:
        captured["request"] = user_request
        captured["demo"] = demo
        captured["output_dir"] = settings.output_dir

    monkeypatch.setattr(main_module, "_run_direct", fake_run_direct)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ai-factory",
            "--demo",
            "--output-dir",
            str(tmp_path),
            "Build",
            "a",
            "CLI",
        ],
    )

    main_module.main()

    assert captured == {
        "request": "Build a CLI",
        "demo": True,
        "output_dir": str(tmp_path),
    }
