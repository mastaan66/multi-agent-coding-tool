"""Planner / Architect Agent — designs the system before coding begins."""

from crewai import Agent, Task

PLANNER_BACKSTORY = """You are a world-class software architect with 20 years of
experience designing scalable, maintainable systems. You think in terms of clean
architecture, separation of concerns, and pragmatic technology choices. You always
produce clear, actionable plans that developers can follow without ambiguity.

You design systems that are:
- Modular and well-structured
- Following industry best practices
- Using appropriate and modern technologies
- Well-defined with clear API contracts
"""

PLAN_TASK_DESCRIPTION = """Analyze the following project request and produce a
comprehensive architectural plan.

## User Request
{user_request}

## Required Output
You MUST produce a JSON object (and ONLY a JSON object, no extra text) with these keys:
- "project_name": string — concise project name
- "description": string — one-paragraph project description
- "tech_stack": list of strings — technologies (language, framework, database, etc.)
- "file_structure": list of strings — all file paths to create (e.g. "app/main.py")
- "modules": list of strings — key modules with brief responsibility descriptions
- "endpoints": list of objects with "method", "path", "description" — API endpoints (if applicable, else empty list)
- "additional_notes": string — any extra design decisions

Think step by step. Be specific about file paths and module boundaries.
Output ONLY valid JSON. No markdown, no code fences, no explanations.
"""


def create_planner_agent(llm) -> Agent:
    """Create the Planner/Architect agent."""
    return Agent(
        role="Senior Software Architect",
        goal=(
            "Design a comprehensive, production-ready software architecture "
            "that is modular, scalable, and follows best practices."
        ),
        backstory=PLANNER_BACKSTORY,
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def create_plan_task(agent: Agent, user_request: str) -> Task:
    """Create the planning task."""
    return Task(
        description=PLAN_TASK_DESCRIPTION.format(user_request=user_request),
        expected_output="A valid JSON object containing the project architecture plan.",
        agent=agent,
    )
