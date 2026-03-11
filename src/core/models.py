"""Pydantic data models shared across all agents."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Planning
# ──────────────────────────────────────────────

class Endpoint(BaseModel):
    """A single API endpoint definition."""
    method: str = Field(description="HTTP method (GET, POST, PUT, DELETE)")
    path: str = Field(description="URL path")
    description: str = Field(description="What the endpoint does")


class ProjectPlan(BaseModel):
    """Architectural plan output from the Planner agent."""
    project_name: str = Field(description="Name of the project")
    description: str = Field(description="Brief project description")
    tech_stack: list[str] = Field(description="Technologies to use")
    file_structure: list[str] = Field(
        description="List of file paths to create (e.g. 'app/main.py')"
    )
    modules: list[str] = Field(
        description="Key modules and their responsibilities"
    )
    endpoints: list[Endpoint] = Field(
        default_factory=list,
        description="API endpoints if applicable",
    )
    additional_notes: str = Field(
        default="",
        description="Any additional design decisions or notes",
    )


# ──────────────────────────────────────────────
# Code Generation
# ──────────────────────────────────────────────

class CodeFile(BaseModel):
    """A single generated source file."""
    file_path: str = Field(description="Relative path within the project")
    content: str = Field(description="Full file content")
    language: str = Field(default="python", description="Programming language")


class CodeBase(BaseModel):
    """Collection of generated code files."""
    files: list[CodeFile] = Field(default_factory=list)

    def get_file(self, path: str) -> Optional[CodeFile]:
        """Find a file by path."""
        for f in self.files:
            if f.file_path == path:
                return f
        return None

    def set_file(self, path: str, content: str, language: str = "python") -> None:
        """Add or update a file."""
        existing = self.get_file(path)
        if existing:
            existing.content = content
            existing.language = language
        else:
            self.files.append(CodeFile(
                file_path=path, content=content, language=language
            ))

    def summary(self) -> str:
        """Return a brief summary of all files."""
        lines = [f"CodeBase ({len(self.files)} files):"]
        for f in self.files:
            line_count = f.content.count("\n") + 1
            lines.append(f"  - {f.file_path} ({line_count} lines, {f.language})")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# Code Review
# ──────────────────────────────────────────────

class Severity(str, Enum):
    """Severity level for review comments."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ReviewComment(BaseModel):
    """A single review comment / issue found."""
    file_path: str = Field(description="File where the issue was found")
    severity: Severity = Field(description="Issue severity")
    category: str = Field(
        description="Category: bug, security, performance, style, architecture"
    )
    description: str = Field(description="What the issue is")
    suggestion: str = Field(default="", description="How to fix it")
    line_number: Optional[int] = Field(
        default=None, description="Approximate line number"
    )


class ReviewReport(BaseModel):
    """Complete review report from the Reviewer agent."""
    comments: list[ReviewComment] = Field(default_factory=list)
    overall_quality: str = Field(
        default="",
        description="Overall quality assessment: excellent, good, needs_improvement, poor",
    )
    summary: str = Field(default="", description="Brief summary of the review")

    @property
    def has_critical_issues(self) -> bool:
        return any(c.severity == Severity.CRITICAL for c in self.comments)

    @property
    def issue_count(self) -> int:
        return len(self.comments)


# ──────────────────────────────────────────────
# Testing
# ──────────────────────────────────────────────

class TestResult(BaseModel):
    """Result from running tests."""
    passed: bool = Field(default=False, description="Whether all tests passed")
    total_tests: int = Field(default=0)
    passed_tests: int = Field(default=0)
    failed_tests: int = Field(default=0)
    stdout: str = Field(default="", description="Test runner stdout")
    stderr: str = Field(default="", description="Test runner stderr")
    failure_analysis: str = Field(
        default="",
        description="Analysis of why tests failed and how to fix them",
    )


# ──────────────────────────────────────────────
# Deployment
# ──────────────────────────────────────────────

class DeploymentArtifact(BaseModel):
    """Deployment configuration output."""
    files: list[CodeFile] = Field(
        default_factory=list,
        description="Deployment files (Dockerfile, docker-compose, CI/CD configs)",
    )
    instructions: str = Field(
        default="",
        description="Human-readable deployment instructions",
    )


# ──────────────────────────────────────────────
# Pipeline State
# ──────────────────────────────────────────────

class PipelineStage(str, Enum):
    """Stages in the development pipeline."""
    PLANNING = "planning"
    CODING = "coding"
    REVIEWING = "reviewing"
    IMPROVING = "improving"
    TESTING = "testing"
    TEST_RUNNING = "test_running"
    DEPLOYING = "deploying"
    COMPLETE = "complete"
    FAILED = "failed"


class PipelineState(BaseModel):
    """Tracks the overall state of a pipeline run."""
    user_request: str = Field(description="Original user prompt")
    current_stage: PipelineStage = Field(default=PipelineStage.PLANNING)
    plan: Optional[ProjectPlan] = None
    codebase: Optional[CodeBase] = None
    review_report: Optional[ReviewReport] = None
    test_result: Optional[TestResult] = None
    deployment: Optional[DeploymentArtifact] = None
    review_iterations: int = Field(default=0)
    test_fix_iterations: int = Field(default=0)
    errors: list[str] = Field(default_factory=list)
