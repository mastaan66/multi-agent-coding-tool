"""Code Reviewer Agent — reviews code like a senior engineer."""

from crewai import Agent, Task

REVIEWER_BACKSTORY = """You are a meticulous senior code reviewer with deep expertise in
software security, performance, and clean code principles. You review code like you're
protecting a production system serving millions of users.

You systematically check for:
- Bugs and logic errors
- Security vulnerabilities (SQL injection, XSS, auth bypass, etc.)
- Performance issues (N+1 queries, unnecessary loops, memory leaks)
- Missing error handling
- Missing input validation
- Bad patterns and anti-patterns
- Code readability and maintainability
- Missing or incorrect type hints

You are thorough but fair. You give actionable, specific feedback.
"""

REVIEW_TASK_DESCRIPTION = """Review the following codebase thoroughly.

## Code Files
{codebase}

## Rules
1. Output ONLY a JSON object (no markdown, no code fences)
2. The JSON must have these keys:
   - "comments": list of review comment objects, each with:
     - "file_path": string — which file
     - "severity": "critical" | "warning" | "info"
     - "category": "bug" | "security" | "performance" | "style" | "architecture"
     - "description": string — what the issue is
     - "suggestion": string — how to fix it
     - "line_number": integer or null
   - "overall_quality": "excellent" | "good" | "needs_improvement" | "poor"
   - "summary": string — brief overall assessment

Be thorough. Check every file. Focus on critical issues first.
Output ONLY valid JSON. No extra text.
"""


def create_reviewer_agent(llm) -> Agent:
    """Create the Code Reviewer agent."""
    return Agent(
        role="Senior Code Reviewer",
        goal=(
            "Find all bugs, security issues, performance problems, and "
            "code quality issues. Provide specific, actionable feedback."
        ),
        backstory=REVIEWER_BACKSTORY,
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def create_review_task(agent: Agent, codebase_json: str) -> Task:
    """Create the code review task."""
    return Task(
        description=REVIEW_TASK_DESCRIPTION.format(codebase=codebase_json),
        expected_output="A valid JSON object with review comments, quality rating, and summary.",
        agent=agent,
    )
