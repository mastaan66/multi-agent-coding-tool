"""Code Improver Agent — fixes code based on review feedback."""

from crewai import Agent, Task

IMPROVER_BACKSTORY = """You are a code improvement specialist. You take review feedback
and systematically fix every issue while maintaining code correctness and readability.

Your approach:
- Fix ALL reported issues, starting with critical ones
- Never introduce new bugs while fixing old ones
- Maintain the existing code structure and style
- Improve error handling and input validation
- Add missing type hints and documentation
- Ensure all files remain complete and runnable
"""

IMPROVE_TASK_DESCRIPTION = """Improve the following code based on the review feedback.

## Current Code
{codebase}

## Review Feedback
{review}

## Rules
1. Fix ALL issues mentioned in the review
2. Output ONLY a JSON object with a "files" key (same format as input)
3. Each file object has: "file_path", "content", "language"
4. Include ALL files from the original codebase, even if unchanged
5. Every file must be complete — no placeholders
6. Do NOT remove any functionality while fixing issues

Output ONLY valid JSON. No extra text.
"""


def create_improver_agent(llm) -> Agent:
    """Create the Code Improver agent."""
    return Agent(
        role="Code Improvement Specialist",
        goal=(
            "Fix all reported issues in the code while maintaining "
            "functionality, readability, and code structure."
        ),
        backstory=IMPROVER_BACKSTORY,
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def create_improve_task(
    agent: Agent, codebase_json: str, review_json: str
) -> Task:
    """Create the code improvement task."""
    return Task(
        description=IMPROVE_TASK_DESCRIPTION.format(
            codebase=codebase_json,
            review=review_json,
        ),
        expected_output="A valid JSON object with the improved 'files' list.",
        agent=agent,
    )
