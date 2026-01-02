"""
CLI commands for Vishwa.

Main entry point: `vishwa "your task"` or `vishwa` for interactive mode
"""

import os
import sys
from typing import Optional

import click
from dotenv import load_dotenv
from rich.console import Console

from vishwa.agent import VishwaAgent
from vishwa.cli import ui
from vishwa.llm import LLMFactory
from vishwa.tools import ToolRegistry
from vishwa.utils.logger import logger


@click.group(invoke_without_command=True)
@click.argument("task", required=False)
@click.option(
    "--model",
    "-m",
    default=None,
    help="LLM model to use (e.g., 'claude', 'gpt-4o', 'local')",
)
@click.option(
    "--max-iter",
    default=None,
    help="Maximum iterations for agent loop (default: unlimited)",
    type=int,
)
@click.option(
    "--auto-approve",
    is_flag=True,
    help="Auto-approve all actions (use with caution!)",
)
@click.option(
    "--verbose/--quiet",
    default=True,
    help="Show detailed output",
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Logging level (creates separate files per level)",
    show_default=True,
)
@click.option(
    "--log-dir",
    default=None,
    help="Log directory (default: logs/YYYY-MM-DD/)",
)
@click.option(
    "--log-json",
    is_flag=True,
    help="Use JSON format for logs (machine-readable)",
)
@click.option(
    "--no-log",
    is_flag=True,
    help="Disable file logging",
)
@click.option(
    "--loop-threshold",
    default=15,
    help="Number of repeated tool calls before detecting loop (default: 15)",
    type=int,
)
@click.option(
    "--skip-review",
    is_flag=True,
    help="Skip code review before completion",
)
@click.option(
    "--continue", "continue_session",
    is_flag=True,
    help="Continue the most recent session",
)
@click.option(
    "--resume",
    default=None,
    help="Resume a session by name or ID",
)
@click.pass_context
def main(
    ctx,
    task: str,
    model: str,
    max_iter: int,
    auto_approve: bool,
    verbose: bool,
    log_level: str,
    log_dir: str,
    log_json: bool,
    no_log: bool,
    loop_threshold: int,
    skip_review: bool,
    continue_session: bool,
    resume: str,
):
    """
    Vishwa - Terminal-based Agentic Coding Assistant

    Usage:
        vishwa                                           # Interactive mode
        vishwa "add docstring to main function"          # One-shot mode
        vishwa "fix the bug in auth.py" --model claude
        vishwa "run tests and fix failures" --max-iter 20
        vishwa --continue                                # Resume last session
        vishwa --resume my-feature                       # Resume named session

    Examples:
        vishwa "search for TODO comments" --model local
        vishwa "refactor the database code" --model gpt-4o
        vishwa --continue                                # Continue where you left off
        vishwa --resume auth-refactor                    # Resume by session name
    """
    # Load environment variables
    load_dotenv()

    # Load config from environment
    from vishwa.config import Config
    config = Config()

    # Merge CLI options with config (CLI takes precedence)
    # For flags, CLI only overrides if explicitly set (flag is True)
    effective_skip_review = skip_review or config.skip_review

    # Configure logging (enabled by default unless --no-log is used)
    logger.configure(
        level=log_level,
        log_dir=log_dir,
        json_mode=log_json,
        enable_logging=not no_log,
    )

    # Show log directory if logging is enabled
    if not no_log and verbose:
        log_dir_path = logger.get_log_directory()
        if log_dir_path:
            print(f"Logging to: {log_dir_path.absolute()}\n")

    # If no task provided, enter interactive mode or show help
    if not task:
        if ctx.invoked_subcommand is None:
            # Enter interactive mode
            _run_interactive(
                model=model,
                max_iter=max_iter,
                auto_approve=auto_approve,
                verbose=verbose,
                loop_threshold=loop_threshold,
                skip_review=effective_skip_review,
                continue_session=continue_session,
                resume_session=resume,
            )
            sys.exit(0)
        return

    # Show welcome
    if verbose:
        ui.show_welcome()

    try:
        # Create LLM (use specified model or default)
        llm = LLMFactory.create(model)
        if verbose:
            ui.show_model_info(llm.model_name, llm.provider_name)

        # Load tools
        tools = ToolRegistry.load_default()

        # Create agent
        agent = VishwaAgent(
            llm=llm,
            tools=tools,
            max_iterations=max_iter,
            auto_approve=auto_approve,
            verbose=verbose,
            loop_detection_threshold=loop_threshold,
            skip_review=effective_skip_review,
        )

        # Show task
        if verbose:
            ui.print_task(task)

        # Run agent
        result = agent.run(task)

        # Show result
        if verbose:
            ui.show_result_table(result)

            if result.modifications:
                ui.show_modifications(result.modifications)

        # Exit code based on success
        sys.exit(0 if result.success else 1)

    except KeyboardInterrupt:
        ui.print_warning("Interrupted by user")
        sys.exit(130)

    except Exception as e:
        ui.print_error(f"Error: {str(e)}")
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


def _run_interactive(
    model: str,
    max_iter: Optional[int],
    auto_approve: bool,
    verbose: bool,
    loop_threshold: int = 15,
    skip_review: bool = False,
    continue_session: bool = False,
    resume_session: Optional[str] = None,
):
    """
    Run Vishwa in interactive REPL mode.

    Args:
        model: LLM model name
        max_iter: Max iterations
        auto_approve: Auto-approve flag
        verbose: Verbose output
        loop_threshold: Loop detection threshold
        skip_review: Skip code review before completion
        continue_session: Continue most recent session
        resume_session: Resume session by name or ID
    """
    from vishwa.cli.interactive import InteractiveSession
    from vishwa.config import Config
    from vishwa.session import SessionManager

    # Create console first, before try block
    console = Console()

    try:
        # Create config
        config = Config()
        if model:
            config.model = model

        # Determine which model to use
        model_to_use = model or config.model

        # Load LLM (single model, no fallback)
        llm = LLMFactory.create(model_to_use)

        # Load tools
        tools = ToolRegistry.load_default()

        # Create agent (verbose=True to show step-by-step execution)
        agent = VishwaAgent(
            llm=llm,
            tools=tools,
            max_iterations=max_iter,
            auto_approve=auto_approve,
            verbose=True,  # Show tool execution and progress
            loop_detection_threshold=loop_threshold,
            skip_review=skip_review,
        )

        # Start interactive session
        session = InteractiveSession(agent=agent, config=config, console=console)

        # Handle --continue flag
        if continue_session:
            session_manager = SessionManager()
            recent = session_manager.get_most_recent_session()
            if recent:
                session._cmd_resume([recent.id])
            else:
                console.print("[dim]No previous session found[/dim]")

        # Handle --resume flag
        elif resume_session:
            session._cmd_resume([resume_session])

        session.start()

    except KeyboardInterrupt:
        console.print("\n")
        sys.exit(130)

    except Exception as e:
        console.print(f"[red] Error:[/red] {str(e)}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@main.command()
def models():
    """List available models"""
    from vishwa.llm import LLMConfig

    models_by_provider = LLMConfig.list_available_models()

    ui.console.print("\n[bold]Available Models:[/bold]\n")

    for provider, model_list in models_by_provider.items():
        ui.console.print(f"[cyan]{provider.upper()}:[/cyan]")
        for model in sorted(set(model_list)):
            ui.console.print(f"  • {model}")
        ui.console.print()


@main.command()
@click.option("--provider", help="Check specific provider (openai, anthropic, ollama)")
def check(provider: str):
    """Check environment and API keys"""
    load_dotenv()

    ui.console.print("\n[bold]Environment Check:[/bold]\n")

    # Check API keys
    checks = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "OLLAMA_BASE_URL": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    }

    for key, value in checks.items():
        status = "✓" if value else "✗"
        color = "green" if value else "red"
        ui.console.print(f"  [{color}]{status}[/{color}] {key}: {value or '(not set)'}")

    # Check Ollama
    ui.console.print("\n[bold]Ollama:[/bold]")
    from vishwa.llm.ollama_provider import OllamaProvider

    if OllamaProvider.is_ollama_running():
        ui.console.print("  [green]✓[/green] Ollama is running")

        models = OllamaProvider.list_available_models()
        if models:
            ui.console.print(f"  [dim]Available models: {', '.join(models[:5])}[/dim]")
    else:
        ui.console.print("  [red]✗[/red] Ollama not running")
        ui.console.print("  [dim]Install: https://ollama.com/download[/dim]")

    ui.console.print()


@main.command()
def version():
    """Show version information"""
    from vishwa import __version__

    ui.console.print(f"\n[bold]Vishwa[/bold] v{__version__}\n")
    ui.console.print("Terminal-based Agentic Coding Assistant")
    ui.console.print("Named after Vishwakarma (विश्वकर्मा)\n")


if __name__ == "__main__":
    main()
