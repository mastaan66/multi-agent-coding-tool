"""Test Generator Agent — writes automated tests."""

from crewai import Agent, Task

TESTER_BACKSTORY = """You are a QA test engineer who writes comprehensive, well-structured
test suites. You believe in testing every code path: happy paths, edge cases, error
conditions, and boundary values.

Your testing philosophy:
- Every public function gets at least one test
- Edge cases are not optional
- Tests should be independent and repeatable
- Use descriptive test names that explain what is being tested
- Mock external dependencies appropriately
- Test both success and failure scenarios
"""

TEST_TASK_DESCRIPTION = """Generate comprehensive automated tests for the following codebase.

## Code Files
{codebase}

## Architecture Plan
{plan}

## Rules
1. Output ONLY a JSON object with a "files" key
2. Each file object has: "file_path", "content", "language"
3. Use pytest as the testing framework
4. Create test files following the pattern: tests/test_<module>.py
5. Include:
   - Unit tests for all functions and methods
   - Integration tests for API endpoints (if applicable)
   - Edge case tests (empty input, invalid data, boundary values)
   - Error handling tests
6. Use descriptive test function names: test_<what>_<scenario>
7. Include necessary imports and fixtures
8. Tests must be runnable with: pytest tests/

Output ONLY valid JSON. No extra text.
"""


def create_tester_agent(llm) -> Agent:
    """Create the Test Generator agent."""
    return Agent(
        role="QA Test Engineer",
        goal=(
            "Write comprehensive pytest tests covering all functions, "
            "edge cases, error conditions, and integration scenarios."
        ),
        backstory=TESTER_BACKSTORY,
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def create_test_task(
    agent: Agent, codebase_json: str, plan_json: str
) -> Task:
    """Create the test generation task."""
    return Task(
        description=TEST_TASK_DESCRIPTION.format(
            codebase=codebase_json,
            plan=plan_json,
        ),
        expected_output="A valid JSON object with test 'files' list.",
        agent=agent,
    )
