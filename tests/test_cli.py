"""Tests for command-line configuration."""

import json
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


def test_generate_subcommand_preserves_legacy_pipeline(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_direct(user_request: str, demo: bool = False) -> None:
        captured["request"] = user_request
        captured["demo"] = demo

    monkeypatch.setattr(main_module, "_run_direct", fake_run_direct)
    monkeypatch.setattr(
        sys,
        "argv",
        ["ai-factory", "generate", "--demo", "Build", "an", "API"],
    )

    main_module.main()

    assert captured == {"request": "Build an API", "demo": True}


def test_inspect_subcommand_emits_json(monkeypatch, tmp_path: Path, capsys) -> None:
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["ai-factory", "inspect", str(tmp_path), "--json"],
    )

    main_module.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["root"] == str(tmp_path)
    assert payload["files"] == ["app.py"]
