"""AI Software Factory — Interactive Terminal Application.

Launch:
    python3 -m src.main
    python3 -m src.main "Create a REST API for a todo app"
    ./run.sh
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.text import Text

from src.core.config import settings, save_api_key
from src.core.instructions import load_instruction_hierarchy
from src.core.pipeline import Pipeline
from src.core.repository import build_repository_snapshot, format_repository_snapshot

console = Console()

# ──────────────────────────────────────────────
# Banner & Branding
# ──────────────────────────────────────────────

BANNER = r"""
    _    ___   ____         __ _                          
   / \  |_ _| / ___|  ___  / _| |___      ____ _ _ __ ___ 
  / _ \  | |  \___ \ / _ \| |_| __\ \ /\ / / _` | '__/ _ \
 / ___ \ | |   ___) | (_) |  _| |_ \ V  V / (_| | | |  __/
/_/   \_\___| |____/ \___/|_|  \__| \_/\_/ \__,_|_|  \___|
                 _____ _    ____ _____ ___  ______   __
                |  ___/ \  / ___|_   _/ _ \|  _ \ \ / /
                | |_ / _ \| |     | || | | | |_) \ V / 
                |  _/ ___ \ |___  | || |_| |  _ < | |  
                |_|/_/   \_\____| |_| \___/|_| \_\|_|  
"""

TAGLINE = "Multiple specialized AI agents collaborating like a real engineering team."

MODEL_CHOICES = {
    "1": ("gpt-4o", "GPT-4o — Best balance of speed & quality"),
    "2": ("gpt-4o-mini", "GPT-4o Mini — Fastest & cheapest"),
    "3": ("gpt-4.1", "GPT-4.1 — Latest & most capable"),
    "4": ("gpt-4.1-mini", "GPT-4.1 Mini — Fast & capable"),
    "5": ("gpt-4.1-nano", "GPT-4.1 Nano — Ultra fast & light"),
}


def print_banner():
    """Display the welcome banner."""
    console.print()
    banner_text = Text(BANNER, style="bold cyan")
    console.print(banner_text)
    console.print(
        Panel(
            f"[bold white]{TAGLINE}[/bold white]",
            border_style="dim cyan",
            padding=(0, 2),
        )
    )
    console.print()


def print_divider(label: str = ""):
    """Print a styled divider."""
    if label:
        console.print(f"\n[bold cyan]{'─' * 3} {label} {'─' * (50 - len(label))}[/bold cyan]")
    else:
        console.print(f"[dim]{'─' * 60}[/dim]")


# ──────────────────────────────────────────────
# Setup Wizard
# ──────────────────────────────────────────────

def _graceful_exit():
    """Print a clean exit message and terminate."""
    console.print("\n\n  [dim]Goodbye! Run again anytime.[/dim]\n")
    sys.exit(0)


def setup_api_key() -> str:
    """Prompt for and save the OpenAI API key."""
    print_divider("API Key Setup")
    console.print()
    console.print("  [dim]Your API key is needed to power the AI agents.[/dim]")
    console.print("  [dim]It will be saved locally in .env (never shared).[/dim]")
    console.print("  [dim]Leave blank to run in Demo Mode (Mock LLM response).[/dim]")
    console.print()

    while True:
        try:
            api_key = Prompt.ask(
                "  [bold yellow]Paste your OpenAI API key[/bold yellow]",
                password=True,
            )
        except (KeyboardInterrupt, EOFError):
            _graceful_exit()

        api_key = api_key.strip()

        if not api_key:
            try:
                if Confirm.ask("  [yellow]Run in Demo Mode (Mock LLM)?[/yellow]", default=True):
                    return ""
            except (KeyboardInterrupt, EOFError):
                _graceful_exit()
            continue

        if not api_key.startswith("sk-"):
            console.print("  [yellow]⚠ Key doesn't start with 'sk-'. Are you sure?[/yellow]")
            try:
                if not Confirm.ask("  [dim]Continue anyway?[/dim]", default=False):
                    continue
            except (KeyboardInterrupt, EOFError):
                _graceful_exit()

        # Save it
        save_api_key(api_key)
        settings.openai_api_key = api_key
        console.print("  [green]✓ API key saved to .env[/green]")
        return api_key


def setup_model() -> str:
    """Let user pick an LLM model."""
    print_divider("Model Selection")
    console.print()

    for key, (model, desc) in MODEL_CHOICES.items():
        marker = " [green]◀ default[/green]" if model == "gpt-4o" else ""
        console.print(f"  [bold cyan]{key}[/bold cyan]  {desc}{marker}")

    console.print()
    try:
        choice = Prompt.ask(
            "  [bold yellow]Select model[/bold yellow]",
            choices=list(MODEL_CHOICES.keys()),
            default="1",
        )
    except (KeyboardInterrupt, EOFError):
        _graceful_exit()

    model_name = MODEL_CHOICES[choice][0]
    settings.openai_model_name = model_name
    console.print(f"  [green]✓ Using {model_name}[/green]")
    return model_name


def setup_iterations():
    """Let user configure iteration limits."""
    print_divider("Pipeline Settings")
    console.print()
    console.print("  [dim]How many times should agents retry to improve code?[/dim]")
    console.print()

    try:
        review_max = IntPrompt.ask(
            "  [bold yellow]Max review-improve cycles[/bold yellow]",
            default=settings.max_review_iterations,
        )
        settings.max_review_iterations = max(1, min(review_max, 10))

        test_max = IntPrompt.ask(
            "  [bold yellow]Max test-fix cycles[/bold yellow]",
            default=settings.max_test_fix_iterations,
        )
        settings.max_test_fix_iterations = max(1, min(test_max, 10))
    except (KeyboardInterrupt, EOFError):
        _graceful_exit()

    console.print(
        f"  [green]✓ Review loops: {settings.max_review_iterations}, "
        f"Test-fix loops: {settings.max_test_fix_iterations}[/green]"
    )


def get_project_prompt() -> str:
    """Get the project description from the user."""
    print_divider("What do you want to build?")
    console.print()
    console.print("  [dim]Describe the software project you want the AI team to build.[/dim]")
    console.print("  [dim]Be as specific as possible for best results.[/dim]")
    console.print()
    console.print("  [dim italic]Examples:[/dim italic]")
    console.print('  [dim]  • "Create a REST API for a todo app with FastAPI and PostgreSQL"[/dim]')
    console.print('  [dim]  • "Build a CLI weather tool that fetches data from OpenWeatherMap"[/dim]')
    console.print('  [dim]  • "Create a URL shortener service with analytics tracking"[/dim]')
    console.print()

    while True:
        try:
            prompt = Prompt.ask("  [bold yellow]Your project[/bold yellow]")
        except (KeyboardInterrupt, EOFError):
            _graceful_exit()

        prompt = prompt.strip()
        if prompt:
            return prompt
        console.print("  [red]Please describe what you want to build.[/red]")


# ──────────────────────────────────────────────
# Interactive Mode
# ──────────────────────────────────────────────

def run_interactive(demo: bool = False):
    """Run the full interactive terminal experience."""
    try:
        print_banner()

        # Step 1: API Key
        has_key = (
            settings.openai_api_key
            and settings.openai_api_key != "sk-your-api-key-here"
            and len(settings.openai_api_key) > 10
        )

        is_demo = demo
        if not is_demo:
            if has_key:
                masked = settings.openai_api_key[:7] + "..." + settings.openai_api_key[-4:]
                console.print(f"  [green]✓ API key loaded:[/green] [dim]{masked}[/dim]")
            else:
                api_key = setup_api_key()
                if not api_key:
                    is_demo = True

        # Step 2: Model
        if is_demo:
            console.print("  [green]✓ Demo Mode:[/green] [dim]Mock LLM (No API Key)[/dim]")
        else:
            console.print(f"  [green]✓ Current model:[/green] [dim]{settings.openai_model_name}[/dim]")
            try:
                if Confirm.ask("\n  [dim]Change model or settings?[/dim]", default=False):
                    setup_model()
                    setup_iterations()
            except (KeyboardInterrupt, EOFError):
                _graceful_exit()

        # Step 3: Project prompt
        user_request = get_project_prompt()

        # Step 4: Confirm & launch
        print_divider("Ready to Build")
        console.print()

        model_display = "Demo Mode (Mock LLM)" if is_demo else settings.openai_model_name
        summary_panel = Panel(
            f"[bold white]{user_request}[/bold white]\n\n"
            f"[dim]Model:[/dim] {model_display}  "
            f"[dim]Review loops:[/dim] {settings.max_review_iterations}  "
            f"[dim]Test-fix loops:[/dim] {settings.max_test_fix_iterations}",
            title="[bold cyan]Project Summary[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
        console.print(summary_panel)

        try:
            if not Confirm.ask("\n  [bold yellow]Launch the AI team?[/bold yellow]", default=True):
                console.print("\n  [dim]Cancelled. Run again anytime![/dim]\n")
                sys.exit(0)
        except (KeyboardInterrupt, EOFError):
            _graceful_exit()

        # Step 5: Run pipeline
        console.print()
        pipeline = Pipeline(demo=is_demo)

        state = pipeline.run(user_request)

        if state.errors:
            console.print(f"\n[yellow]⚠ {len(state.errors)} warning(s):[/yellow]")
            for err in state.errors:
                console.print(f"  [dim]• {err}[/dim]")

        # Final message
        console.print(
            Panel(
                "[bold green]Your project is ready![/bold green]\n\n"
                "[dim]Check the output directory for your generated project.[/dim]",
                border_style="green",
                padding=(1, 2),
            )
        )

    except KeyboardInterrupt:
        console.print("\n\n  [yellow]⚠ Interrupted. Partial output may be in output/.[/yellow]")
        console.print("  [dim]Run again anytime![/dim]\n")
        sys.exit(130)
    except Exception as e:
        console.print(
            Panel(
                f"[red bold]Pipeline Error[/red bold]\n\n{e}",
                border_style="red",
                padding=(1, 2),
            )
        )
        sys.exit(1)


def _create_generate_parser(prog: str = "ai-factory") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=(
            "AI Software Factory — Multiple specialized AI agents "
            "collaborating like a real engineering team."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ai-factory generate "Create a REST API"
  ai-factory generate --demo "Build a snake game"
  ai-factory "Create a REST API"          Backward-compatible generation
""",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Project description. If omitted, launches the generation wizard.",
    )
    parser.add_argument(
        "-m",
        "--model",
        help="Override the LLM model to use (e.g. gpt-4o, gpt-4.1-mini)",
    )
    parser.add_argument("--api-key", help="Pass OpenAI API key directly")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run in demo mode (Mock LLM) without requiring an API key",
    )
    parser.add_argument(
        "--review-loops",
        type=int,
        help="Maximum review-improve cycles",
    )
    parser.add_argument(
        "--test-loops",
        type=int,
        help="Maximum test-fix cycles",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory to save the generated project",
    )
    return parser


def _run_generate_cli(arguments: list[str], *, prog: str = "ai-factory") -> None:
    parser = _create_generate_parser(prog)
    args = parser.parse_args(arguments)

    if args.model:
        settings.openai_model_name = args.model
    if args.api_key:
        settings.openai_api_key = args.api_key
    if args.review_loops:
        settings.max_review_iterations = args.review_loops
    if args.test_loops:
        settings.max_test_fix_iterations = args.test_loops
    if args.output_dir:
        settings.output_dir = args.output_dir

    prompt = " ".join(args.prompt).strip()
    if prompt:
        _run_direct(prompt, demo=args.demo)
    else:
        run_interactive(demo=args.demo)


def _run_inspect_cli(arguments: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="ai-factory inspect",
        description="Inspect repository structure without sending content to a model.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Repository path")
    parser.add_argument("--limit", type=int, default=5_000, help="Maximum files to scan")
    parser.add_argument("--preview", type=int, default=40, help="Files shown in text output")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(arguments)

    snapshot = build_repository_snapshot(args.path, limit=args.limit)
    requested_path = Path(args.path).expanduser().resolve()
    target_path = requested_path.relative_to(snapshot.root).as_posix()
    instructions = load_instruction_hierarchy(snapshot.root, target_path)

    if args.json:
        print(
            json.dumps(
                {
                    "root": str(snapshot.root),
                    "file_count": len(snapshot.files),
                    "files": list(snapshot.files),
                    "languages": dict(snapshot.languages),
                    "instructions": [
                        {"path": document.path, "scope": document.scope}
                        for document in instructions.documents
                    ],
                },
                indent=2,
            )
        )
        return

    console.print(format_repository_snapshot(snapshot, preview_limit=args.preview))
    if instructions.documents:
        console.print("Instructions:")
        for document in instructions.documents:
            console.print(f"  {document.path} (scope: {document.scope})")
    else:
        console.print("Instructions: none")


def main() -> None:
    """Dispatch repository commands while preserving legacy generation usage."""
    load_dotenv()
    arguments = sys.argv[1:]
    if arguments and arguments[0] == "inspect":
        _run_inspect_cli(arguments[1:])
        return
    if arguments and arguments[0] == "generate":
        _run_generate_cli(arguments[1:], prog="ai-factory generate")
        return
    if "--help" in arguments or "-h" in arguments:
        print_banner()
    _run_generate_cli(arguments)


def _run_direct(user_request: str, demo: bool = False):
    """Run pipeline directly with a prompt (no wizard)."""
    if not demo and (not settings.openai_api_key or settings.openai_api_key == "sk-your-api-key-here"):
        console.print("[red]Error:[/red] Set OPENAI_API_KEY in .env or environment, or use --demo.")
        sys.exit(1)

    pipeline = Pipeline(demo=demo)
    try:
        state = pipeline.run(user_request)
        if state.errors:
            for err in state.errors:
                console.print(f"  [dim]• {err}[/dim]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red bold]Error: {e}[/red bold]")
        sys.exit(1)


if __name__ == "__main__":
    main()

