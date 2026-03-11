"""QA / Test Runner Agent — analyzes test results and reports."""

from crewai import Agent, Task

TEST_RUNNER_BACKSTORY = """You are a QA analyst who specializes in analyzing test results.
You read test output carefully, identify root causes of failures, and provide clear,
actionable debugging guidance.

Your analysis includes:
- Which tests passed and which failed
- Root cause analysis for each failure
- Specific fix suggestions with file and line references
- Whether failures indicate a bug in code or a bug in tests
"""

TEST_RUNNER_TASK_DESCRIPTION = """Analyze the following test execution results.

## Test Output
{test_output}

## Code Files
{codebase}

## Rules
1. Output ONLY a JSON object with these keys:
   - "passed": boolean — whether all tests passed
   - "total_tests": integer
   - "passed_tests": integer
   - "failed_tests": integer
   - "failure_analysis": string — detailed analysis of failures with fix suggestions
2. If all tests passed, set "failure_analysis" to "All tests passed successfully."
3. If tests failed, provide specific fix suggestions with file paths and descriptions

Output ONLY valid JSON. No extra text.
"""


def create_test_runner_agent(llm) -> Agent:
    """Create the QA/Test Runner agent."""
    return Agent(
        role="QA Analyst",
        goal=(
            "Analyze test results, identify root causes of failures, "
            "and provide specific, actionable fix suggestions."
        ),
        backstory=TEST_RUNNER_BACKSTORY,
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def create_test_runner_task(
    agent: Agent, test_output: str, codebase_json: str
) -> Task:
    """Create the test analysis task."""
    return Task(
        description=TEST_RUNNER_TASK_DESCRIPTION.format(
            test_output=test_output,
            codebase=codebase_json,
        ),
        expected_output="A valid JSON object with test result analysis.",
        agent=agent,
    )
