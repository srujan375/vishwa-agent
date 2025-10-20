"""
Terminal UI utilities using Rich.

Provides:
- Colored console output
- Progress indicators
- Diff display
- Interactive prompts
"""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table

# Global console instance
console = Console()


def print_header(text: str) -> None:
    """Print a header"""
    console.print(f"\n[bold blue]{text}[/bold blue]\n")


def print_task(task: str) -> None:
    """Print the task being worked on"""
    panel = Panel(
        f"[bold]{task}[/bold]",
        title="🎯 Task",
        border_style="blue",
    )
    console.print(panel)


def print_iteration(current: int, total: int) -> None:
    """Print current iteration"""
    console.print(f"[dim]Iteration {current}/{total}[/dim]", end=" ")


def print_action(tool_name: str, arguments: dict) -> None:
    """Print tool action"""
    args_str = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
    # Truncate long arguments
    if len(args_str) > 100:
        args_str = args_str[:100] + "..."
    console.print(f"→ [cyan]{tool_name}[/cyan]({args_str})")


def print_observation(result: any) -> None:
    """Print tool observation"""
    success = getattr(result, "success", False)
    output = getattr(result, "output", None) or getattr(result, "error", "")

    # Truncate long output
    if len(str(output)) > 300:
        output = str(output)[:300] + "..."

    if success:
        console.print(f"  [green]✓[/green] {output}")
    else:
        console.print(f"  [red]✗[/red] {output}")


def print_success(message: str) -> None:
    """Print success message"""
    console.print(f"\n[bold green]✅ {message}[/bold green]\n")


def print_warning(message: str) -> None:
    """Print warning message"""
    console.print(f"\n[bold yellow]⚠️  {message}[/bold yellow]\n")


def print_error(message: str) -> None:
    """Print error message"""
    console.print(f"\n[bold red]❌ {message}[/bold red]\n")


def show_diff(filepath: str, old: str, new: str) -> None:
    """
    Display a colored diff.

    Args:
        filepath: File path
        old: Old content
        new: New content
    """
    import difflib

    # Generate unified diff
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
        lineterm="",
    )

    diff_text = "".join(diff)

    if diff_text:
        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
        panel = Panel(
            syntax,
            title=f"📝 Diff: {filepath}",
            border_style="yellow",
        )
        console.print(panel)
    else:
        console.print("[dim]No changes[/dim]")


def confirm_action(message: str, default: bool = False) -> bool:
    """
    Ask user to confirm an action.

    Args:
        message: Confirmation message
        default: Default value if user just presses enter

    Returns:
        True if confirmed
    """
    return Confirm.ask(f"⚠️  {message}", default=default)


def show_result_table(result: any) -> None:
    """
    Display agent result as a table.

    Args:
        result: AgentResult instance
    """
    table = Table(title="Agent Execution Summary")

    table.add_column("Attribute", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Success", "✓ Yes" if result.success else "✗ No")
    table.add_row("Message", result.message)
    table.add_row("Iterations Used", str(result.iterations_used))
    table.add_row("Stop Reason", result.stop_reason)
    table.add_row("Modifications", str(len(result.modifications)))

    console.print(table)


def show_modifications(modifications: list) -> None:
    """
    Display list of modifications.

    Args:
        modifications: List of Modification objects
    """
    if not modifications:
        console.print("[dim]No modifications made[/dim]")
        return

    table = Table(title="📝 Files Modified")

    table.add_column("#", style="dim")
    table.add_column("File", style="cyan")
    table.add_column("Tool", style="yellow")
    table.add_column("Time", style="dim")

    for i, mod in enumerate(modifications, 1):
        timestamp = getattr(mod, "timestamp", "")
        if timestamp and len(timestamp) > 19:
            timestamp = timestamp[:19]  # Truncate to YYYY-MM-DD HH:MM:SS

        table.add_row(
            str(i),
            mod.file_path,
            mod.tool,
            timestamp,
        )

    console.print(table)


def show_welcome() -> None:
    """Show welcome banner"""
    welcome_text = """
# Vishwa 🛠️

Terminal-based Agentic Coding Assistant

Named after Vishwakarma (विश्वकर्मा), the divine architect and craftsman.
"""
    md = Markdown(welcome_text)
    console.print(md)


def show_model_info(model_name: str, provider: str) -> None:
    """Show which model is being used"""
    console.print(f"[dim]Using: {model_name} ({provider})[/dim]")


def create_spinner(text: str):
    """
    Create a progress spinner.

    Returns:
        Progress context manager
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    )
