"""Deployment Agent — creates deployment infrastructure."""

from crewai import Agent, Task

DEPLOYER_BACKSTORY = """You are a senior DevOps engineer who creates production-ready
deployment configurations. You follow the principle of infrastructure as code and
make deployments reproducible, secure, and well-documented.

Your configurations always include:
- Multi-stage Docker builds for minimal image size
- Proper security (non-root user, no hardcoded secrets)
- Environment variable configuration
- Health checks
- Clear documentation
"""

DEPLOY_TASK_DESCRIPTION = """Create complete deployment infrastructure for this project.

## Architecture Plan
{plan}

## Code Files
{codebase}

## Required Deliverables
Generate the following deployment files:

1. **Dockerfile** — multi-stage build, non-root user, health check
2. **docker-compose.yml** — including any required services (database, cache, etc.)
3. **.github/workflows/ci.yml** — GitHub Actions CI pipeline (lint, test, build)
4. **deployment instructions section** for the README

## Rules
1. Output ONLY a JSON object with these keys:
   - "files": list of file objects with "file_path", "content", "language"
   - "instructions": string — human-readable deployment instructions (markdown)
2. Use environment variables for all configuration (no hardcoded values)
3. Include proper .dockerignore content in the Dockerfile comments
4. CI pipeline should: install deps, run linting, run tests, build Docker image

Output ONLY valid JSON. No extra text.
"""


def create_deployer_agent(llm) -> Agent:
    """Create the Deployment agent."""
    return Agent(
        role="Senior DevOps Engineer",
        goal=(
            "Create production-ready deployment infrastructure with "
            "Docker, CI/CD, and clear deployment instructions."
        ),
        backstory=DEPLOYER_BACKSTORY,
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )


def create_deploy_task(
    agent: Agent, plan_json: str, codebase_json: str
) -> Task:
    """Create the deployment task."""
    return Task(
        description=DEPLOY_TASK_DESCRIPTION.format(
            plan=plan_json,
            codebase=codebase_json,
        ),
        expected_output="A valid JSON object with deployment 'files' and 'instructions'.",
        agent=agent,
    )
