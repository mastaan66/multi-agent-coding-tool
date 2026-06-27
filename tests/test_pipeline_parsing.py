"""Tests for structured pipeline output parsing."""

import pytest

from src.core.errors import StructuredOutputError
from src.core.pipeline import _extract_json, _parse_json_response


def test_extract_json_accepts_outer_markdown_fence() -> None:
    response = """```json
{"project_name": "demo"}
```"""

    assert _extract_json(response) == {"project_name": "demo"}


def test_extract_json_preserves_fences_inside_json_strings() -> None:
    response = '{"instructions": "# Deploy\\n\\n```bash\\ndocker compose up\\n```"}'

    assert _extract_json(response)["instructions"].startswith("# Deploy")


def test_invalid_json_raises_typed_stage_error() -> None:
    with pytest.raises(StructuredOutputError, match="planning returned invalid"):
        _parse_json_response("not-json", "planning")
