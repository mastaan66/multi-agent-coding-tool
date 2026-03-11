"""Pipeline — the orchestration engine that chains agents together.

Workflow:
  User Request → Plan → Code → Review → Improve (loop) → Test → Fix (loop) → Deploy
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from crewai import Crew, Process
from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.table import Table
from rich.tree import Tree

from src.agents.coder import create_code_task, create_coder_agent
from src.agents.deployer import create_deploy_task, create_deployer_agent
from src.agents.improver import create_improve_task, create_improver_agent
from src.agents.planner import create_plan_task, create_planner_agent
from src.agents.reviewer import create_review_task, create_reviewer_agent
from src.agents.test_runner import (
    create_test_runner_agent,
    create_test_runner_task,
)
from src.agents.tester import create_test_task, create_tester_agent
from src.core.config import settings
from src.core.models import (
    CodeBase,
    DeploymentArtifact,
    PipelineStage,
    PipelineState,
    ProjectPlan,
    ReviewReport,
    TestResult,
)
from src.tools.code_executor import run_command
from src.tools.file_writer import write_project_files

console = Console()

STAGES = [
    ("1", "Planning", "🏗️"),
    ("2", "Code Generation", "💻"),
    ("3", "Code Review", "🔍"),
    ("4", "Code Improvement", "✨"),
    ("5", "Test Generation", "🧪"),
    ("6", "Test Execution", "▶️"),
    ("7", "Deployment", "🚀"),
]


# ──────────────────────────────────────────────
# JSON parsing helpers
# ──────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """Extract a JSON object from LLM output, tolerating markdown fences."""
    text = text.strip()

    # Try to find JSON within code fences
    fence_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(fence_pattern, text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    # Find the first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]

    return json.loads(text)


def _safe_json(text: str, fallback: dict | None = None) -> dict:
    """Parse JSON with graceful fallback."""
    try:
        return _extract_json(text)
    except (json.JSONDecodeError, ValueError) as e:
        console.print(f"  [yellow]⚠ JSON parse error: {e}[/yellow]")
        return fallback or {}


# ──────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────

class Pipeline:
    """Orchestrates the full software development pipeline."""

    def __init__(self, llm=None, demo: bool = False):
        self.demo = demo
        self._mock_llm = None
        if demo:
            from src.core.mock_llm import MockLLM
            self._mock_llm = MockLLM()
            self.llm = None
        else:
            self.llm = llm or self._create_llm()
        self.state: PipelineState | None = None
        self._start_time: datetime | None = None
        self._output_dir: Path | None = None

    @staticmethod
    def _create_llm():
        """Create the LLM instance based on configuration."""
        from crewai import LLM

        return LLM(
            model=f"openai/{settings.openai_model_name}",
            api_key=settings.openai_api_key,
            temperature=settings.openai_temperature,
        )

    def _run_crew_or_mock(self, agent_fn, task_fn, task_args, spinner_label: str) -> str:
        """Run a CrewAI crew or return mock response in demo mode."""
        if self.demo:
            with console.status(f"[bold cyan]{spinner_label}[/bold cyan]", spinner="dots"):
                return self._mock_llm.call()

        agent = agent_fn(self.llm)
        task = task_fn(agent, *task_args)
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

        with console.status(f"[bold cyan]{spinner_label}[/bold cyan]", spinner="dots"):
            result = crew.kickoff()

        return str(result)

    def run(self, user_request: str) -> PipelineState:
        """Execute the full pipeline for a user request."""
        self._start_time = datetime.now()
        self.state = PipelineState(user_request=user_request)

        self._print_header(user_request)

        try:
            # Stage 1: Planning
            self._run_planning()

            # Stage 2: Code Generation
            self._run_coding()

            # Stage 3 & 4: Review → Improve Loop
            self._run_review_improve_loop()

            # Stage 5: Test Generation
            self._run_testing()

            # Stage 6: Test Execution & Fix Loop
            self._run_test_fix_loop()

            # Stage 7: Deployment
            self._run_deployment()

            # Stage 8: Write Output
            self._write_output()

            self.state.current_stage = PipelineStage.COMPLETE
            self._print_summary()

        except Exception as e:
            self.state.current_stage = PipelineStage.FAILED
            self.state.errors.append(str(e))
            console.print(
                Panel(
                    f"[red bold]Pipeline Failed[/red bold]\n\n{e}",
                    border_style="red",
                    padding=(1, 2),
                )
            )
            raise

        return self.state

    # ───── Stage Implementations ─────

    def _run_planning(self):
        """Stage 1: Generate the architecture plan."""
        self.state.current_stage = PipelineStage.PLANNING
        self._print_stage(0, "Architect agent is designing your system...")

        agent = create_planner_agent(self.llm)
        task = create_plan_task(agent, self.state.user_request)
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

        with console.status("[bold cyan]  Architect agent thinking...[/bold cyan]", spinner="dots"):
            result = crew.kickoff()

        data = _safe_json(str(result), {"project_name": "project", "tech_stack": [], "file_structure": [], "modules": []})

        self.state.plan = ProjectPlan(
            project_name=data.get("project_name", "project"),
            description=data.get("description", ""),
            tech_stack=data.get("tech_stack", []),
            file_structure=data.get("file_structure", []),
            modules=data.get("modules", []),
            endpoints=[
                {"method": e.get("method", "GET"), "path": e.get("path", "/"), "description": e.get("description", "")}
                for e in data.get("endpoints", [])
            ],
            additional_notes=data.get("additional_notes", ""),
        )

        self._print_plan_summary()

    def _run_coding(self):
        """Stage 2: Generate the codebase."""
        self.state.current_stage = PipelineStage.CODING
        self._print_stage(1, "Engineer agent is writing code...")

        agent = create_coder_agent(self.llm)
        plan_json = self.state.plan.model_dump_json(indent=2)
        task = create_code_task(agent, plan_json)
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

        with console.status("[bold cyan]  Engineer agent coding...[/bold cyan]", spinner="dots"):
            result = crew.kickoff()

        data = _safe_json(str(result), {"files": []})

        self.state.codebase = CodeBase()
        for f in data.get("files", []):
            self.state.codebase.set_file(
                f.get("file_path", "unknown.py"),
                f.get("content", ""),
                f.get("language", "python"),
            )

        console.print(f"  [green]✓ Generated {len(self.state.codebase.files)} files[/green]")
        self._print_file_tree("Generated Files", self.state.codebase)

    def _run_review_improve_loop(self):
        """Stages 3 & 4: Review → Improve iterative loop."""
        for iteration in range(1, settings.max_review_iterations + 1):
            # Review
            self.state.current_stage = PipelineStage.REVIEWING
            self._print_stage(
                2,
                f"Reviewer agent checking code (iteration {iteration}/{settings.max_review_iterations})...",
            )

            reviewer = create_reviewer_agent(self.llm)
            codebase_json = self.state.codebase.model_dump_json(indent=2)
            review_task = create_review_task(reviewer, codebase_json)
            crew = Crew(agents=[reviewer], tasks=[review_task], process=Process.sequential, verbose=False)

            with console.status("[bold cyan]  Reviewer agent analyzing...[/bold cyan]", spinner="dots"):
                result = crew.kickoff()

            data = _safe_json(str(result), {"comments": [], "overall_quality": "good", "summary": ""})

            self.state.review_report = ReviewReport(
                comments=data.get("comments", []),
                overall_quality=data.get("overall_quality", "good"),
                summary=data.get("summary", ""),
            )
            self.state.review_iterations = iteration

            self._print_review_summary()

            # Check if code is good enough
            if (
                self.state.review_report.overall_quality in ("excellent", "good")
                and not self.state.review_report.has_critical_issues
            ):
                console.print("  [green]✓ Code quality is satisfactory, moving on.[/green]")
                break

            # Improve
            self.state.current_stage = PipelineStage.IMPROVING
            self._print_stage(
                3,
                f"Improver agent fixing {self.state.review_report.issue_count} issues...",
            )

            improver = create_improver_agent(self.llm)
            review_json = self.state.review_report.model_dump_json(indent=2)
            improve_task = create_improve_task(improver, codebase_json, review_json)
            crew = Crew(agents=[improver], tasks=[improve_task], process=Process.sequential, verbose=False)

            with console.status("[bold cyan]  Improver agent fixing code...[/bold cyan]", spinner="dots"):
                result = crew.kickoff()

            data = _safe_json(str(result), {"files": []})

            improved_codebase = CodeBase()
            for f in data.get("files", []):
                improved_codebase.set_file(
                    f.get("file_path", "unknown.py"),
                    f.get("content", ""),
                    f.get("language", "python"),
                )

            if improved_codebase.files:
                self.state.codebase = improved_codebase
                console.print(f"  [green]✓ Improved {len(improved_codebase.files)} files[/green]")

    def _run_testing(self):
        """Stage 5: Generate tests."""
        self.state.current_stage = PipelineStage.TESTING
        self._print_stage(4, "QA agent writing tests...")

        agent = create_tester_agent(self.llm)
        codebase_json = self.state.codebase.model_dump_json(indent=2)
        plan_json = self.state.plan.model_dump_json(indent=2)
        task = create_test_task(agent, codebase_json, plan_json)
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

        with console.status("[bold cyan]  QA agent writing tests...[/bold cyan]", spinner="dots"):
            result = crew.kickoff()

        data = _safe_json(str(result), {"files": []})

        test_count = 0
        for f in data.get("files", []):
            path = f.get("file_path", "")
            self.state.codebase.set_file(
                path,
                f.get("content", ""),
                f.get("language", "python"),
            )
            test_count += 1

        console.print(f"  [green]✓ Generated {test_count} test files[/green]")

    def _run_test_fix_loop(self):
        """Stage 6: Execute tests → Analyze → Fix loop."""
        for iteration in range(1, settings.max_test_fix_iterations + 1):
            self.state.current_stage = PipelineStage.TEST_RUNNING
            self._print_stage(
                5,
                f"Running tests (attempt {iteration}/{settings.max_test_fix_iterations})...",
            )

            # Write files to a temporary location and run tests
            output_dir = settings.output_path / "_test_run"
            self._write_files_to_dir(output_dir)

            # Execute pytest
            with console.status("[bold cyan]  Executing pytest...[/bold cyan]", spinner="dots"):
                exec_result = run_command(
                    ["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
                    cwd=output_dir,
                    timeout=60,
                )

            test_output = f"STDOUT:\n{exec_result.stdout}\n\nSTDERR:\n{exec_result.stderr}"

            if exec_result.success:
                console.print("  [green]✓ All tests passed![/green]")
                self.state.test_result = TestResult(
                    passed=True,
                    stdout=exec_result.stdout,
                    stderr=exec_result.stderr,
                    failure_analysis="All tests passed successfully.",
                )
                break

            # Analyze failures
            console.print("  [yellow]⚠ Some tests failed. Analyzing...[/yellow]")

            runner = create_test_runner_agent(self.llm)
            codebase_json = self.state.codebase.model_dump_json(indent=2)
            runner_task = create_test_runner_task(runner, test_output, codebase_json)
            crew = Crew(agents=[runner], tasks=[runner_task], process=Process.sequential, verbose=False)

            with console.status("[bold cyan]  QA analyst investigating failures...[/bold cyan]", spinner="dots"):
                result = crew.kickoff()

            data = _safe_json(str(result), {"passed": False})

            self.state.test_result = TestResult(
                passed=data.get("passed", False),
                total_tests=data.get("total_tests", 0),
                passed_tests=data.get("passed_tests", 0),
                failed_tests=data.get("failed_tests", 0),
                stdout=exec_result.stdout,
                stderr=exec_result.stderr,
                failure_analysis=data.get("failure_analysis", ""),
            )
            self.state.test_fix_iterations = iteration

            if self.state.test_result.passed:
                break

            # Try to fix
            if iteration < settings.max_test_fix_iterations:
                self.state.current_stage = PipelineStage.IMPROVING
                console.print("  [cyan]→ Sending back to Improver agent...[/cyan]")

                improver = create_improver_agent(self.llm)
                fix_review = json.dumps({
                    "comments": [{
                        "file_path": "tests/",
                        "severity": "critical",
                        "category": "bug",
                        "description": self.state.test_result.failure_analysis,
                        "suggestion": "Fix the code or tests based on the analysis above.",
                    }],
                    "overall_quality": "needs_improvement",
                    "summary": f"Test failures: {self.state.test_result.failed_tests} tests failing.",
                })
                improve_task = create_improve_task(improver, codebase_json, fix_review)
                crew = Crew(agents=[improver], tasks=[improve_task], process=Process.sequential, verbose=False)

                with console.status("[bold cyan]  Improver agent fixing issues...[/bold cyan]", spinner="dots"):
                    result = crew.kickoff()

                data = _safe_json(str(result), {"files": []})

                for f in data.get("files", []):
                    self.state.codebase.set_file(
                        f.get("file_path", "unknown.py"),
                        f.get("content", ""),
                        f.get("language", "python"),
                    )

    def _run_deployment(self):
        """Stage 7: Generate deployment infrastructure."""
        self.state.current_stage = PipelineStage.DEPLOYING
        self._print_stage(6, "DevOps agent creating deployment configs...")

        agent = create_deployer_agent(self.llm)
        plan_json = self.state.plan.model_dump_json(indent=2)
        codebase_json = self.state.codebase.model_dump_json(indent=2)
        task = create_deploy_task(agent, plan_json, codebase_json)
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

        with console.status("[bold cyan]  DevOps agent building infrastructure...[/bold cyan]", spinner="dots"):
            result = crew.kickoff()

        data = _safe_json(str(result), {"files": [], "instructions": ""})

        # Add deployment files to codebase
        for f in data.get("files", []):
            self.state.codebase.set_file(
                f.get("file_path", ""),
                f.get("content", ""),
                f.get("language", "yaml"),
            )

        self.state.deployment = DeploymentArtifact(
            files=data.get("files", []),
            instructions=data.get("instructions", ""),
        )

        console.print(f"  [green]✓ Generated {len(data.get('files', []))} deployment files[/green]")

    # ───── Output ─────

    def _write_output(self):
        """Write all generated files to the output directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_name = self.state.plan.project_name.lower().replace(" ", "_")
        self._output_dir = settings.output_path / f"{project_name}_{timestamp}"

        console.print(f"\n[bold]📁 Writing project to:[/bold] [cyan]{self._output_dir}[/cyan]")

        files = [
            {"file_path": f.file_path, "content": f.content}
            for f in self.state.codebase.files
        ]
        write_project_files(files, self._output_dir)

        # Write deployment instructions as README section
        if self.state.deployment and self.state.deployment.instructions:
            readme_path = self._output_dir / "DEPLOYMENT.md"
            readme_path.write_text(
                self.state.deployment.instructions, encoding="utf-8"
            )
            console.print(f"  [green]✓[/green] DEPLOYMENT.md")

    def _write_files_to_dir(self, output_dir: Path):
        """Write current codebase to a directory (for test execution)."""
        files = [
            {"file_path": f.file_path, "content": f.content}
            for f in self.state.codebase.files
        ]
        write_project_files(files, output_dir)

    # ───── Display Helpers ─────

    def _print_header(self, request: str):
        console.print()
        # Progress bar showing all stages
        stages_text = "  ".join(
            f"[dim]{icon} {name}[/dim]" for _, name, icon in STAGES
        )
        console.print(
            Panel(
                f"[bold white]{request}[/bold white]\n\n"
                f"[dim]Pipeline:[/dim] {stages_text}",
                title="[bold cyan]🏭 AI Software Factory[/bold cyan]",
                subtitle="[dim]Multi-Agent Development Pipeline[/dim]",
                border_style="cyan",
                padding=(1, 2),
            )
        )
        console.print()

    def _print_stage(self, stage_idx: int, description: str):
        num, name, icon = STAGES[stage_idx]
        console.print(
            f"\n[bold blue]{icon} [{num}/7] {name}[/bold blue]"
        )
        console.print(f"  [dim]{description}[/dim]")

    def _print_plan_summary(self):
        if not self.state.plan:
            return
        plan = self.state.plan
        table = Table(show_header=False, border_style="dim", padding=(0, 2))
        table.add_column("Key", style="bold cyan", width=14)
        table.add_column("Value")
        table.add_row("Project", plan.project_name)
        table.add_row("Description", plan.description[:120] + ("..." if len(plan.description) > 120 else ""))
        table.add_row("Stack", ", ".join(plan.tech_stack))
        table.add_row("Files", str(len(plan.file_structure)))
        if plan.endpoints:
            endpoints_str = ", ".join(
                f"{e.method} {e.path}" for e in plan.endpoints[:5]
            )
            if len(plan.endpoints) > 5:
                endpoints_str += f" (+{len(plan.endpoints) - 5} more)"
            table.add_row("Endpoints", endpoints_str)
        console.print(table)
        console.print("  [green]✓ Architecture plan ready[/green]")

    def _print_file_tree(self, title: str, codebase: CodeBase):
        """Show files as a tree."""
        tree = Tree(f"[bold]{title}[/bold]", guide_style="dim")
        dirs: dict[str, Tree] = {}

        for f in sorted(codebase.files, key=lambda x: x.file_path):
            parts = f.file_path.split("/")
            parent = tree
            # Build directory nodes
            for i, part in enumerate(parts[:-1]):
                dir_key = "/".join(parts[: i + 1])
                if dir_key not in dirs:
                    dirs[dir_key] = parent.add(f"[bold blue]{part}/[/bold blue]")
                parent = dirs[dir_key]
            # Add file leaf
            lines = f.content.count("\n") + 1
            parent.add(f"[green]{parts[-1]}[/green] [dim]({lines} lines)[/dim]")

        console.print(tree)

    def _print_review_summary(self):
        if not self.state.review_report:
            return
        report = self.state.review_report
        color_map = {
            "excellent": "green",
            "good": "green",
            "needs_improvement": "yellow",
            "poor": "red",
        }
        color = color_map.get(report.overall_quality, "white")

        console.print(f"  Quality: [{color}]{report.overall_quality}[/{color}]  |  Issues: {report.issue_count}")

        # Show top issues with colors
        severity_colors = {"critical": "red", "warning": "yellow", "info": "dim"}
        severity_icons = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
        for comment in report.comments[:5]:
            sev = comment.severity if isinstance(comment.severity, str) else comment.severity.value
            c = severity_colors.get(sev, "white")
            icon = severity_icons.get(sev, "•")
            desc = comment.description if isinstance(comment, dict) else comment.description
            fp = comment.file_path if isinstance(comment, dict) else comment.file_path
            console.print(f"    {icon} [{c}]{fp}[/{c}]: {desc[:80]}")

        remaining = report.issue_count - 5
        if remaining > 0:
            console.print(f"    [dim]... and {remaining} more issues[/dim]")

    def _print_summary(self):
        elapsed = datetime.now() - self._start_time

        # File tree of final output
        if self.state.codebase:
            self._print_file_tree("Final Project Files", self.state.codebase)

        console.print()
        table = Table(
            title="✅ Pipeline Complete",
            border_style="green",
            title_style="bold green",
            padding=(0, 2),
        )
        table.add_column("Metric", style="bold")
        table.add_column("Value")
        table.add_row("Project", self.state.plan.project_name)
        table.add_row("Files Generated", str(len(self.state.codebase.files)))
        table.add_row("Review Iterations", str(self.state.review_iterations))
        table.add_row("Test Fix Iterations", str(self.state.test_fix_iterations))
        table.add_row(
            "Tests Passed",
            "[green]Yes ✓[/green]"
            if (self.state.test_result and self.state.test_result.passed)
            else "[yellow]No / Skipped[/yellow]",
        )
        table.add_row("Duration", str(elapsed).split(".")[0])
        if self._output_dir:
            table.add_row("Output", str(self._output_dir))
        console.print(table)
        console.print()
