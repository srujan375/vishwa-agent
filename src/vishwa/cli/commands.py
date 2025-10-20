"""
CLI commands for Vishwa.

Main entry point: `vishwa "your task"` or `vishwa` for interactive mode
"""

import os
import sys

import click
from dotenv import load_dotenv
from rich.console import Console

from vishwa.agent import VishwaAgent
from vishwa.cli import ui
from vishwa.llm import LLMFactory
from vishwa.tools import ToolRegistry


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
    default=15,
    help="Maximum iterations for agent loop",
    type=int,
)
@click.option(
    "--auto-approve",
    is_flag=True,
    help="Auto-approve all actions (use with caution!)",
)
@click.option(
    "--fallback",
    default=None,
    help="Fallback chain: 'quality', 'cost', 'privacy', or 'default'",
)
@click.option(
    "--verbose/--quiet",
    default=True,
    help="Show detailed output",
)
@click.pass_context
def main(
    ctx,
    task: str,
    model: str,
    max_iter: int,
    auto_approve: bool,
    fallback: str,
    verbose: bool,
):
    """
    Vishwa - Terminal-based Agentic Coding Assistant

    Usage:
        vishwa                                           # Interactive mode
        vishwa "add docstring to main function"          # One-shot mode
        vishwa "fix the bug in auth.py" --model claude
        vishwa "run tests and fix failures" --max-iter 20

    Examples:
        vishwa "search for TODO comments" --model local
        vishwa "refactor the database code" --fallback quality
    """
    # Load environment variables
    load_dotenv()

    # If no task provided, enter interactive mode or show help
    if not task:
        if ctx.invoked_subcommand is None:
            # Enter interactive mode
            _run_interactive(
                model=model,
                max_iter=max_iter,
                auto_approve=auto_approve,
                fallback=fallback,
                verbose=verbose,
            )
            sys.exit(0)
        return

    # Show welcome
    if verbose:
        ui.show_welcome()

    try:
        # Create LLM
        if fallback:
            llm = LLMFactory.create_with_fallback(
                primary_model=model, fallback_chain=fallback
            )
            if verbose:
                ui.show_model_info(f"Fallback chain: {fallback}", "multiple")
        elif model:
            llm = LLMFactory.create(model)
            if verbose:
                ui.show_model_info(llm.model_name, llm.provider_name)
        else:
            # Use default with fallback
            llm = LLMFactory.create_with_fallback()
            if verbose:
                ui.show_model_info("Default fallback chain", "multiple")

        # Load tools
        tools = ToolRegistry.load_default()

        # Create agent
        agent = VishwaAgent(
            llm=llm,
            tools=tools,
            max_iterations=max_iter,
            auto_approve=auto_approve,
            verbose=verbose,
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
    max_iter: int,
    auto_approve: bool,
    fallback: str,
    verbose: bool,
):
    """
    Run Vishwa in interactive REPL mode.

    Args:
        model: LLM model name
        max_iter: Max iterations
        auto_approve: Auto-approve flag
        fallback: Fallback chain
        verbose: Verbose output
    """
    from vishwa.cli.interactive import InteractiveSession
    from vishwa.config import Config

    try:
        # Create config
        config = Config()
        if model:
            config.model = model

        # Determine which model to use
        model_to_use = model or config.model or "claude"

        # Load LLM
        llm = LLMFactory.create_with_fallback(
            primary_model=model_to_use,
            fallback_chain=fallback or "default",
        )

        # Load tools
        tools = ToolRegistry.load_default()

        # Create agent (verbose=True to show step-by-step execution)
        agent = VishwaAgent(
            llm=llm,
            tools=tools,
            max_iterations=max_iter,
            auto_approve=auto_approve,
            verbose=True,  # Show tool execution and progress
        )

        # Create console
        console = Console()

        # Start interactive session
        session = InteractiveSession(agent=agent, config=config, console=console)
        session.start()

    except KeyboardInterrupt:
        console.print("\n")
        sys.exit(130)

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {str(e)}")
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
