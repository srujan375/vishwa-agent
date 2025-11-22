"""
Terminal UI utilities using Rich.

Provides:
- Colored console output
- Progress indicators
- Diff display
- Interactive prompts
"""

import os
import subprocess
import tempfile
import atexit
import shutil
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog, button_dialog
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML

# Global console instance
console = Console()

# Track temp directories for cleanup on exit
_temp_dirs_to_cleanup = set()


def _cleanup_temp_dirs():
    """Clean up temp directories on exit."""
    for temp_dir in _temp_dirs_to_cleanup:
        try:
            if Path(temp_dir).exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


# Register cleanup on exit
atexit.register(_cleanup_temp_dirs)


def is_vscode() -> bool:
    """
    Detect if the current process is running inside VS Code.

    Returns:
        True if running in VS Code, False otherwise
    """
    # Check for VS Code specific environment variables
    vscode_indicators = [
        'VSCODE_PID',
        'VSCODE_IPC_HOOK',
        'VSCODE_GIT_ASKPASS_NODE',
        'VSCODE_GIT_ASKPASS_MAIN',
        'TERM_PROGRAM',
    ]

    # Check environment variables
    for indicator in vscode_indicators:
        if indicator in os.environ:
            # TERM_PROGRAM should specifically be "vscode"
            if indicator == 'TERM_PROGRAM':
                if os.environ.get('TERM_PROGRAM') == 'vscode':
                    return True
            else:
                return True

    return False


# Global tracker for opened temp files
_opened_temp_files = []

# Track if we should close tabs before opening next diff
_pending_tab_close = False


def show_diff_in_vscode(filepath: str, old_content: str, new_content: str) -> bool:
    """
    Show diff in VS Code's built-in diff viewer.

    Creates temporary files for old and new content, then opens them in VS Code's diff viewer.
    Temp files are kept until Vishwa exits to avoid "file deleted" state in VS Code.
    The diff tab will show the original filename instead of "old ↔ new".

    Args:
        filepath: Original file path (for naming)
        old_content: Old content (empty string for new files)
        new_content: New content

    Returns:
        True if successfully opened in VS Code, False otherwise
    """
    global _pending_tab_close

    # If there's a pending close from previous approval, do it now before opening new diff
    if _pending_tab_close:
        _close_tabs_immediately()
        _pending_tab_close = False

    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix='vishwa_diff_')

        # Track this directory for cleanup on exit (not immediately)
        _temp_dirs_to_cleanup.add(temp_dir)

        # Get file extension and base name for proper syntax highlighting
        file_path_obj = Path(filepath)
        file_ext = file_path_obj.suffix or '.txt'
        file_stem = file_path_obj.stem  # filename without extension

        # Create temp files with meaningful names based on the original filename
        # This makes the diff tab show the actual filename instead of "old ↔ new"
        # Format: "core.old.py" and "core.new.py" for a file named "core.py"
        old_file = Path(temp_dir) / f"{file_stem}.old{file_ext}"
        new_file = Path(temp_dir) / f"{file_stem}.new{file_ext}"

        # Write content to temp files
        old_file.write_text(old_content, encoding='utf-8')
        new_file.write_text(new_content, encoding='utf-8')

        # Track these files for later cleanup
        _opened_temp_files.append((str(old_file), str(new_file)))

        # Open diff in VS Code (use shell=True on Windows for proper PATH resolution)
        import sys
        is_windows = sys.platform == 'win32'

        result = subprocess.run(
            ['code', '--diff', str(old_file), str(new_file)],
            capture_output=True,
            timeout=5,
            shell=is_windows  # Use shell on Windows to find code in PATH
        )

        if result.returncode == 0:
            console.print(f"[dim]Diff opened in VS Code for: {filepath}[/dim]")
            return True
        else:
            return False

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        # If VS Code command fails, fall back to terminal diff
        console.print(f"[dim]Could not open VS Code diff: {e}[/dim]")
        return False


def show_file_preview_in_vscode(filepath: str, content: str) -> bool:
    """
    Show new file preview in VS Code.

    Opens the content in VS Code for preview.
    Temp files are kept until Vishwa exits to avoid "file deleted" state in VS Code.

    Args:
        filepath: File path (for naming and syntax highlighting)
        content: File content

    Returns:
        True if successfully opened in VS Code, False otherwise
    """
    global _pending_tab_close

    # If there's a pending close from previous approval, do it now before opening new preview
    if _pending_tab_close:
        _close_tabs_immediately()
        _pending_tab_close = False

    try:
        # Create temporary file
        temp_dir = tempfile.mkdtemp(prefix='vishwa_preview_')

        # Track this directory for cleanup on exit (not immediately)
        _temp_dirs_to_cleanup.add(temp_dir)

        file_ext = Path(filepath).suffix or '.txt'
        temp_file = Path(temp_dir) / f"preview_{Path(filepath).name}"

        # Write content
        temp_file.write_text(content, encoding='utf-8')

        # Track this file for later cleanup
        _opened_temp_files.append((str(temp_file),))

        # Open in VS Code (use shell=True on Windows for proper PATH resolution)
        import sys
        is_windows = sys.platform == 'win32'

        result = subprocess.run(
            ['code', str(temp_file)],
            capture_output=True,
            timeout=5,
            shell=is_windows  # Use shell on Windows to find code in PATH
        )

        if result.returncode == 0:
            console.print(f"[dim]Preview opened in VS Code for: {filepath}[/dim]")
            return True
        else:
            return False

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        console.print(f"[dim]Could not open VS Code preview: {e}[/dim]")
        return False


def _close_tabs_immediately() -> None:
    """
    Internal function to immediately close VS Code tabs.

    Uses keyboard simulation to close tabs without any user messaging.
    """
    global _opened_temp_files

    if not _opened_temp_files:
        return

    try:
        import time
        import sys

        # Count total number of tabs to close
        num_tabs = sum(len(file_tuple) for file_tuple in _opened_temp_files)

        if num_tabs == 0:
            _opened_temp_files.clear()
            return

        # Try to use pyautogui for keyboard simulation
        try:
            import pyautogui

            # On Windows, try to bring VS Code window to focus first
            if sys.platform == 'win32':
                try:
                    import pygetwindow as gw
                    # Find VS Code window
                    vscode_windows = [w for w in gw.getAllWindows() if 'Visual Studio Code' in w.title]
                    if vscode_windows:
                        vscode_windows[0].activate()
                        time.sleep(0.2)  # Wait for window to activate
                except ImportError:
                    time.sleep(0.2)
            else:
                time.sleep(0.2)

            # Send Ctrl+W for each tab
            for i in range(num_tabs):
                pyautogui.hotkey('ctrl', 'w')
                time.sleep(0.1)

        except (ImportError, Exception):
            # Silently fail - tabs will remain open
            pass

        # Clear the tracker
        _opened_temp_files.clear()

    except Exception:
        _opened_temp_files.clear()


def close_vscode_temp_files() -> None:
    """
    Mark tabs for closing on next diff/preview open, or close immediately if no more diffs expected.

    This delayed approach ensures tabs don't close prematurely before the next diff opens.
    """
    global _pending_tab_close

    # Set flag to close tabs before the next diff/preview opens
    _pending_tab_close = True


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

    # Truncate long output (increased from 300 to 1000 for bash results)
    if len(str(output)) > 1000:
        output = str(output)[:1000] + f"... [truncated, {len(str(output))} chars total]"

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
    Display a diff - either in VS Code or terminal based on environment.

    Automatically detects if running in VS Code and uses the built-in diff viewer.
    Falls back to terminal diff if not in VS Code or if VS Code diff fails.

    Args:
        filepath: File path
        old: Old content
        new: New content
    """
    # Try VS Code diff first if available
    if is_vscode():
        if show_diff_in_vscode(filepath, old, new):
            return  # Successfully opened in VS Code

    # Fall back to terminal diff
    _show_diff_terminal(filepath, old, new)


def _show_diff_terminal(filepath: str, old: str, new: str) -> None:
    """
    Display a colored diff in the terminal with red background for deletions and green for additions.

    Args:
        filepath: File path
        old: Old content
        new: New content
    """
    import difflib
    from rich.text import Text

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

    # Build colored output
    diff_output = Text()

    for line in diff:
        line = line.rstrip('\n')

        if line.startswith('---') or line.startswith('+++'):
            # File headers - bold white
            diff_output.append(line + '\n', style="bold white")
        elif line.startswith('@@'):
            # Hunk headers - cyan
            diff_output.append(line + '\n', style="bold cyan")
        elif line.startswith('-'):
            # Deletions - red background with white text
            diff_output.append(line + '\n', style="white on red")
        elif line.startswith('+'):
            # Additions - green background with white text
            diff_output.append(line + '\n', style="white on green")
        else:
            # Context lines - dim white
            diff_output.append(line + '\n', style="dim white")

    if diff_output:
        panel = Panel(
            diff_output,
            title=f"Diff: {filepath}",
            border_style="yellow",
            expand=False,
        )
        console.print(panel)
    else:
        console.print("[dim]No changes[/dim]")


def confirm_action(message: str, default: bool = False) -> bool:
    """
    Ask user to confirm an action with inline selection.

    Simple inline prompt that doesn't take over the screen.
    Automatically closes any open VS Code temp files after user choice.

    Args:
        message: Confirmation message
        default: Default value if user just presses enter

    Returns:
        True if confirmed
    """
    from rich.prompt import Prompt

    try:
        # Show the message with rich formatting
        console.print(f"\n[bold yellow]{message}[/bold yellow]")

        # Create inline prompt with styled options
        console.print("[dim]Options:[/dim]")
        console.print("  [green bold]y[/green bold] → Yes, approve and proceed")
        console.print("  [red bold]n[/red bold] → No, reject this change")
        console.print()

        # Get user input with validation
        default_str = "y" if default else "n"
        choices = ["y", "yes", "n", "no"]

        while True:
            response = Prompt.ask(
                "Your choice",
                choices=["y", "n"],
                default=default_str,
                show_choices=False,
                show_default=True
            ).lower()

            if response in ["y", "yes"]:
                console.print("[green]Approved[/green]\n")
                # Close VS Code temp files
                close_vscode_temp_files()
                return True
            elif response in ["n", "no"]:
                console.print("[red]Rejected[/red]\n")
                # Close VS Code temp files
                close_vscode_temp_files()
                return False
            else:
                console.print(f"[yellow]Please enter 'y' or 'n'[/yellow]")

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Action cancelled[/yellow]")
        # Close VS Code temp files on cancellation too
        close_vscode_temp_files()
        return False


def confirm_file_change(filepath: str, action: str = "apply changes") -> str:
    """
    Ask user to confirm file changes with multiple options.

    Uses arrow keys to navigate and Enter to select.

    Args:
        filepath: Path to the file being modified
        action: Description of the action (e.g., "apply changes", "create file")

    Returns:
        One of: 'approve', 'reject', 'edit', 'cancel'
    """
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
