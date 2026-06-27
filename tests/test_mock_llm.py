"""Tests for deterministic demo responses."""

import json

import pytest

from src.core.mock_llm import MockLLM


def test_mock_responses_are_selected_by_stage_name() -> None:
    mock = MockLLM()

    tests_response = json.loads(mock.call("tests"))
    plan_response = json.loads(mock.call("plan"))

    assert tests_response["files"][0]["file_path"] == "tests/test_todos.py"
    assert plan_response["project_name"] == "todo_api"


def test_unknown_mock_response_fails_clearly() -> None:
    with pytest.raises(ValueError, match="Unknown mock response"):
        MockLLM().call("missing")
