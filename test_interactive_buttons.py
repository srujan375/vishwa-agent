"""
Test script for interactive button-based confirmations.

Run this to see the new interactive approval UI in action.
"""

from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel
from prompt_toolkit.shortcuts import button_dialog
from prompt_toolkit.styles import Style

console = Console()


def confirm_action(message: str, default: bool = False) -> bool:
    """Interactive yes/no confirmation with buttons"""
    try:
        style = Style.from_dict({
            'dialog': 'bg:#1e1e1e',
            'dialog.body': 'bg:#1e1e1e #ffffff',
            'dialog shadow': 'bg:#000000',
            'button': 'bg:#4a4a4a #ffffff',
            'button.focused': 'bg:#0078d4 #ffffff bold',
            'button.arrow': '#ffffff',
        })

        result = button_dialog(
            title='Confirmation',
            text=f"⚠️  {message}",
            buttons=[
                ('Yes', True),
                ('No', False),
            ],
            style=style,
        ).run()

        return result if result is not None else default

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Action cancelled[/yellow]")
        return False


def confirm_file_change(filepath: str, action: str = "apply changes") -> str:
    """Interactive file change confirmation with multiple options"""
    try:
        style = Style.from_dict({
            'dialog': 'bg:#1e1e1e',
            'dialog.body': 'bg:#1e1e1e #ffffff',
            'dialog shadow': 'bg:#000000',
            'button': 'bg:#4a4a4a #ffffff',
            'button.focused': 'bg:#0078d4 #ffffff bold',
            'button.arrow': '#ffffff',
        })

        result = button_dialog(
            title=f'📝 {action.title()}',
            text=f"File: {filepath}\n\nWhat would you like to do?",
            buttons=[
                ('✓ Approve', 'approve'),
                ('✗ Reject', 'reject'),
                ('✎ Edit First', 'edit'),
                ('⊗ Cancel', 'cancel'),
            ],
            style=style,
        ).run()

        return result if result else 'cancel'

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Action cancelled[/yellow]")
        return 'cancel'


def show_diff(filepath: str, old: str, new: str) -> None:
    """Display a colored diff"""
    import difflib

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


def test_basic_confirmation():
    """Test basic yes/no confirmation"""
    console.print("\n[bold cyan]Test 1: Basic Confirmation[/bold cyan]")
    console.print("This will show a Yes/No dialog with arrow key navigation.\n")

    result = confirm_action("Do you want to proceed with this operation?")

    if result:
        console.print("[green]✓ You selected: Yes[/green]")
    else:
        console.print("[red]✗ You selected: No[/red]")


def test_file_change_confirmation():
    """Test file change confirmation with multiple options"""
    console.print("\n[bold cyan]Test 2: File Change Confirmation[/bold cyan]")
    console.print("This shows a more complex dialog with multiple options.\n")

    # Show a sample diff first
    old_content = """def hello():
    print("Hello")
    return True"""

    new_content = """def hello(name="World"):
    print(f"Hello, {name}!")
    return True"""

    show_diff("example.py", old_content, new_content)

    result = confirm_file_change("example.py", "apply changes")

    console.print(f"\n[yellow]You selected: {result}[/yellow]")

    if result == 'approve':
        console.print("[green]Changes would be applied[/green]")
    elif result == 'reject':
        console.print("[red]Changes would be discarded[/red]")
    elif result == 'edit':
        console.print("[blue]Opening file for editing...[/blue]")
    else:
        console.print("[dim]Operation cancelled[/dim]")


def main():
    """Run all tests"""
    console.print("[bold blue]Interactive Button UI Test[/bold blue]")
    console.print("Use arrow keys (← →) to navigate between buttons")
    console.print("Press Enter to select, Esc or Ctrl+C to cancel\n")

    try:
        test_basic_confirmation()

        console.print("\n" + "─" * 60 + "\n")

        test_file_change_confirmation()

        console.print("\n[bold green]✓ All tests completed![/bold green]\n")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Tests interrupted by user[/yellow]")


if __name__ == "__main__":
    main()
