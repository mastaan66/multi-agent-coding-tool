"""Pipeline — the orchestration engine that chains agents together.

Workflow:
  User Request → Plan → Code → Review → Improve (loop) → Test → Fix (loop) → Deploy
"""

from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime
from pathlib import Path

from crewai import Crew, Process
from rich.console import Console
from rich.panel import Panel
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
from src.core.errors import StructuredOutputError
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

    # Strip a Markdown fence only when it wraps the entire response.
    fence_pattern = r"```(?:json)?\s*(.*?)\s*```"
    match = re.fullmatch(fence_pattern, text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    # Find the first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]

    return json.loads(text)


def _parse_json_response(text: str, stage: str) -> dict:
    """Parse agent JSON and raise a stage-specific error on failure."""
    try:
        return _extract_json(text)
    except (json.JSONDecodeError, ValueError) as error:
        raise StructuredOutputError(stage, str(error)) from error


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

    def _mock_response(self, response_name: str, spinner_label: str) -> str:
        """Return one deterministic named response in demo mode."""
        if self._mock_llm is None:
            raise RuntimeError("Mock LLM is not configured")
        with console.status(f"[bold cyan]{spinner_label}[/bold cyan]", spinner="dots"):
            return self._mock_llm.call(response_name)

    def _run_crew_or_mock(
        self,
        agent_fn,
        task_fn,
        task_args,
        spinner_label: str,
        mock_response: str,
    ) -> str:
        """Run a CrewAI crew or return a named response in demo mode."""
        if self.demo:
            return self._mock_response(mock_response, spinner_label)

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

        result = self._run_crew_or_mock(
            create_planner_agent,
            create_plan_task,
            (self.state.user_request,),
            "  Architect agent thinking...",
            "plan",
        )
        data = _parse_json_response(result, "planning")

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

        plan_json = self.state.plan.model_dump_json(indent=2)
        result = self._run_crew_or_mock(
            create_coder_agent,
            create_code_task,
            (plan_json,),
            "  Engineer agent coding...",
            "code",
        )
        data = _parse_json_response(result, "coding")

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

            codebase_json = self.state.codebase.model_dump_json(indent=2)
            result = self._run_crew_or_mock(
                create_reviewer_agent,
                create_review_task,
                (codebase_json,),
                "  Reviewer agent analyzing...",
                "review",
            )
            data = _parse_json_response(result, "reviewing")

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

            review_json = self.state.review_report.model_dump_json(indent=2)
            result = self._run_crew_or_mock(
                create_improver_agent,
                create_improve_task,
                (codebase_json, review_json),
                "  Improver agent fixing code...",
                "improvement",
            )
            data = _parse_json_response(result, "improving")

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

        codebase_json = self.state.codebase.model_dump_json(indent=2)
        plan_json = self.state.plan.model_dump_json(indent=2)
        result = self._run_crew_or_mock(
            create_tester_agent,
            create_test_task,
            (codebase_json, plan_json),
            "  QA agent writing tests...",
            "tests",
        )
        data = _parse_json_response(result, "testing")

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
            self.state.test_fix_iterations = iteration
            self._print_stage(
                5,
                f"Running tests (attempt {iteration}/{settings.max_test_fix_iterations})...",
            )

            if self.demo:
                result = self._mock_response(
                    "test_result", "  Simulating pytest execution..."
                )
                data = _parse_json_response(result, "test execution")
                self.state.test_result = TestResult(
                    passed=data.get("passed", False),
                    total_tests=data.get("total_tests", 0),
                    passed_tests=data.get("passed_tests", 0),
                    failed_tests=data.get("failed_tests", 0),
                    failure_analysis=data.get("failure_analysis", ""),
                )
                if self.state.test_result.passed:
                    console.print("  [green]✓ All demo tests passed![/green]")
                    break
                continue

            with tempfile.TemporaryDirectory(prefix="ai-factory-test-") as temp_dir:
                output_dir = Path(temp_dir)
                self._write_files_to_dir(output_dir)
                with console.status(
                    "[bold cyan]  Executing pytest...[/bold cyan]", spinner="dots"
                ):
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

            console.print("  [yellow]⚠ Some tests failed. Analyzing...[/yellow]")
            codebase_json = self.state.codebase.model_dump_json(indent=2)
            result = self._run_crew_or_mock(
                create_test_runner_agent,
                create_test_runner_task,
                (test_output, codebase_json),
                "  QA analyst investigating failures...",
                "test_result",
            )
            data = _parse_json_response(result, "test analysis")

            self.state.test_result = TestResult(
                passed=data.get("passed", False),
                total_tests=data.get("total_tests", 0),
                passed_tests=data.get("passed_tests", 0),
                failed_tests=data.get("failed_tests", 0),
                stdout=exec_result.stdout,
                stderr=exec_result.stderr,
                failure_analysis=data.get("failure_analysis", ""),
            )
            if self.state.test_result.passed:
                break

            if iteration < settings.max_test_fix_iterations:
                self.state.current_stage = PipelineStage.IMPROVING
                console.print("  [cyan]→ Sending back to Improver agent...[/cyan]")
                fix_review = json.dumps(
                    {
                        "comments": [
                            {
                                "file_path": "tests/",
                                "severity": "critical",
                                "category": "bug",
                                "description": self.state.test_result.failure_analysis,
                                "suggestion": (
                                    "Fix the code or tests based on the analysis above."
                                ),
                            }
                        ],
                        "overall_quality": "needs_improvement",
                        "summary": (
                            f"Test failures: {self.state.test_result.failed_tests} "
                            "tests failing."
                        ),
                    }
                )
                result = self._run_crew_or_mock(
                    create_improver_agent,
                    create_improve_task,
                    (codebase_json, fix_review),
                    "  Improver agent fixing issues...",
                    "improvement",
                )
                data = _parse_json_response(result, "test fixing")

                for file_data in data.get("files", []):
                    self.state.codebase.set_file(
                        file_data.get("file_path", "unknown.py"),
                        file_data.get("content", ""),
                        file_data.get("language", "python"),
                    )

    def _run_deployment(self):
        """Stage 7: Generate deployment infrastructure."""
        self.state.current_stage = PipelineStage.DEPLOYING
        self._print_stage(6, "DevOps agent creating deployment configs...")

        plan_json = self.state.plan.model_dump_json(indent=2)
        codebase_json = self.state.codebase.model_dump_json(indent=2)
        result = self._run_crew_or_mock(
            create_deployer_agent,
            create_deploy_task,
            (plan_json, codebase_json),
            "  DevOps agent building infrastructure...",
            "deployment",
        )
        data = _parse_json_response(result, "deployment")

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
            console.print("  [green]✓[/green] DEPLOYMENT.md")

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
