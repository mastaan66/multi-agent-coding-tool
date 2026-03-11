"""Code Generator Agent — writes actual code files."""

from crewai import Agent, Task

CODER_BACKSTORY = """You are an elite software engineer who writes clean, production-ready
code. You follow best practices religiously: proper error handling, input validation,
clear variable names, comprehensive docstrings, and type hints.

Rules you always follow:
- Output ONLY code, never explanations
- Every file must be complete and runnable
- Include proper imports
- Include docstrings for all modules, classes, and functions
- Follow the exact file structure from the architecture plan
- Use type hints throughout
- Handle errors gracefully
"""

CODE_TASK_DESCRIPTION = """Generate complete, production-ready code for the following project.

## Architecture Plan
{plan}

## Rules
1. Generate ALL files listed in the file structure
2. Output ONLY a JSON object (no markdown, no code fences)
3. The JSON must have a single key "files" containing a list of objects
4. Each file object has: "file_path" (string), "content" (string), "language" (string)
5. Every file must be complete — no placeholders, no TODOs, no "..." 
6. Include all imports, error handling, and documentation
7. Make the code production-ready

Output ONLY valid JSON. No extra text.
"""


def create_coder_agent(llm) -> Agent:
    """Create the Code Generator agent."""
    return Agent(
        role="Senior Software Engineer",
        goal=(
            "Write clean, complete, production-ready code that follows "
            "the architecture plan exactly, with proper error handling "
            "and documentation."
        ),
        backstory=CODER_BACKSTORY,
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def create_code_task(agent: Agent, plan_json: str) -> Task:
    """Create the code generation task."""
    return Task(
        description=CODE_TASK_DESCRIPTION.format(plan=plan_json),
        expected_output="A valid JSON object with a 'files' list containing all code files.",
        agent=agent,
    )
