"""AI Software Factory — Interactive Terminal Application.

Launch:
    python3 -m src.main
    python3 -m src.main "Create a REST API for a todo app"
    ./run.sh
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.text import Text
from rich.columns import Columns

from src.core.config import settings, save_api_key
from src.core.pipeline import Pipeline

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
            console.print("  [red]API key cannot be empty.[/red]")
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

def run_interactive():
    """Run the full interactive terminal experience."""
    try:
        print_banner()

        # Step 1: API Key
        has_key = (
            settings.openai_api_key
            and settings.openai_api_key != "sk-your-api-key-here"
            and len(settings.openai_api_key) > 10
        )

        if has_key:
            masked = settings.openai_api_key[:7] + "..." + settings.openai_api_key[-4:]
            console.print(f"  [green]✓ API key loaded:[/green] [dim]{masked}[/dim]")
        else:
            setup_api_key()

        # Step 2: Model
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

        summary_panel = Panel(
            f"[bold white]{user_request}[/bold white]\n\n"
            f"[dim]Model:[/dim] {settings.openai_model_name}  "
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
        pipeline = Pipeline()

        state = pipeline.run(user_request)

        if state.errors:
            console.print(f"\n[yellow]⚠ {len(state.errors)} warning(s):[/yellow]")
            for err in state.errors:
                console.print(f"  [dim]• {err}[/dim]")

        # Final message
        console.print(
            Panel(
                "[bold green]Your project is ready![/bold green]\n\n"
                f"[dim]Check the output directory for your generated project.[/dim]",
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


# ──────────────────────────────────────────────
# CLI Entry Point
# ──────────────────────────────────────────────

def main():
    """Main entry point — supports both interactive and direct modes."""
    load_dotenv()

    # If called with a prompt argument, run directly (power-user mode)
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        user_request = " ".join(sys.argv[1:])
        _run_direct(user_request)
    elif "--help" in sys.argv or "-h" in sys.argv:
        _print_help()
    else:
        run_interactive()


def _run_direct(user_request: str):
    """Run pipeline directly with a prompt (no wizard)."""
    if not settings.openai_api_key or settings.openai_api_key == "sk-your-api-key-here":
        console.print("[red]Error:[/red] Set OPENAI_API_KEY in .env or environment.")
        sys.exit(1)

    pipeline = Pipeline()
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


def _print_help():
    """Print usage help."""
    print_banner()
    console.print("[bold]Usage:[/bold]")
    console.print()
    console.print("  [cyan]python3 -m src.main[/cyan]")
    console.print("    Launch interactive mode (recommended)")
    console.print()
    console.print('  [cyan]python3 -m src.main "Create a REST API for todos"[/cyan]')
    console.print("    Run directly with a prompt")
    console.print()
    console.print("  [cyan]./run.sh[/cyan]")
    console.print("    One-command launch (auto-activates virtualenv)")
    console.print()
    console.print("[bold]Environment:[/bold]")
    console.print()
    console.print("  OPENAI_API_KEY     Your OpenAI API key")
    console.print("  OPENAI_MODEL_NAME  Model to use (default: gpt-4o)")
    console.print()


if __name__ == "__main__":
    main()
