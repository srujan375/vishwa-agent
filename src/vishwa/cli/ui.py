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
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.live import Live
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog, button_dialog
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML

# Cross-platform keyboard input
import sys
if sys.platform == 'win32':
    import msvcrt
else:
    import tty
    import termios

# Global console instance
console = Console()


def _get_key():
    """
    Get a single keypress from the user (cross-platform).

    Returns:
        str: The key pressed ('left', 'right', 'enter', or the character)
    """
    if sys.platform == 'win32':
        # Windows implementation
        key = msvcrt.getch()
        if key == b'\xe0':  # Arrow key prefix on Windows
            key = msvcrt.getch()
            if key == b'K':
                return 'left'
            elif key == b'M':
                return 'right'
            elif key == b'H':
                return 'up'
            elif key == b'P':
                return 'down'
        elif key == b'\r':
            return 'enter'
        elif key == b'\x03':  # Ctrl+C
            raise KeyboardInterrupt
        elif key == b'\x1b':  # Escape
            return 'escape'
        else:
            try:
                return key.decode('utf-8').lower()
            except:
                return ''
    else:
        # Unix implementation
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
            if ch == '\x1b':  # Escape sequence
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'D':
                        return 'left'
                    elif ch3 == 'C':
                        return 'right'
                    elif ch3 == 'A':
                        return 'up'
                    elif ch3 == 'B':
                        return 'down'
                return 'escape'
            elif ch == '\r' or ch == '\n':
                return 'enter'
            elif ch == '\x03':  # Ctrl+C
                raise KeyboardInterrupt
            else:
                return ch.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


class InlineSelector:
    """
    An inline selector that stays in the terminal flow.

    Features:
    - Arrow key navigation (← →)
    - Direct keyboard shortcuts
    - Visual highlighting of selected option
    - Doesn't take over the screen
    """

    def __init__(
        self,
        options: list,
        title: str = "Select an option",
        subtitle: str = None,
    ):
        """
        Initialize the selector.

        Args:
            options: List of tuples (label, value, shortcut, color)
                     e.g., [("Approve", "approve", "y", "green"), ...]
            title: Title to show above options
            subtitle: Optional subtitle/context
        """
        self.options = options
        self.title = title
        self.subtitle = subtitle
        self.selected_index = 0

    def _build_display(self) -> Panel:
        """Build the Rich renderable for current state."""
        lines = []

        # Subtitle if provided
        if self.subtitle:
            lines.append(Text(self.subtitle, style="dim"))
            lines.append(Text(""))

        # Build options line
        option_parts = []
        for i, (label, value, shortcut, color) in enumerate(self.options):
            if i == self.selected_index:
                # Selected option - highlighted
                option_parts.append(f"[bold black on cyan] {shortcut.upper()} [/bold black on cyan]")
                option_parts.append(f"[bold {color}] {label} [/bold {color}]")
            else:
                # Unselected option
                option_parts.append(f"[dim bold] {shortcut.upper()} [/dim bold]")
                option_parts.append(f"[{color}] {label} [/{color}]")

            if i < len(self.options) - 1:
                option_parts.append("  [dim]│[/dim]  ")

        options_text = Text.from_markup("".join(option_parts))
        lines.append(options_text)

        # Help text
        lines.append(Text(""))
        help_text = Text()
        help_text.append("← → ", style="cyan bold")
        help_text.append("navigate  ", style="dim")
        help_text.append("Enter ", style="cyan bold")
        help_text.append("select  ", style="dim")
        help_text.append("or press ", style="dim")
        shortcuts = "/".join(opt[2].upper() for opt in self.options)
        help_text.append(shortcuts, style="cyan bold")
        lines.append(help_text)

        # Create panel
        content = Group(*lines)
        return Panel(
            content,
            title=f"[bold yellow]{self.title}[/bold yellow]",
            border_style="cyan",
            padding=(0, 2),
        )

    def run(self) -> str:
        """
        Run the selector and return the selected value.

        Returns:
            The value of the selected option
        """
        # Build shortcut map
        shortcut_map = {opt[2].lower(): i for i, opt in enumerate(self.options)}

        try:
            # In VS Code integrated terminal, fall back to simple prompt
            # because raw terminal mode may not work properly
            if is_vscode():
                return self._run_simple()

            # Use refresh_per_second to prevent infinite refresh loops
            # Also set auto_refresh=False to prevent automatic refreshes
            with Live(
                self._build_display(),
                console=console,
                transient=True,
                refresh_per_second=4,  # Limit refresh rate to prevent infinite loops
                auto_refresh=False,  # Disable auto-refresh, only update on user input
            ) as live:
                # Initial display
                live.start()

                while True:
                    key = _get_key()

                    if key == 'left':
                        self.selected_index = (self.selected_index - 1) % len(self.options)
                        live.update(self._build_display(), refresh=True)

                    elif key == 'right':
                        self.selected_index = (self.selected_index + 1) % len(self.options)
                        live.update(self._build_display(), refresh=True)

                    elif key == 'enter':
                        # Return selected option
                        return self.options[self.selected_index][1]

                    elif key == 'escape':
                        # Return last option (usually cancel)
                        return self.options[-1][1]

                    elif key in shortcut_map:
                        # Direct shortcut pressed
                        self.selected_index = shortcut_map[key]
                        live.update(self._build_display(), refresh=True)
                        return self.options[self.selected_index][1]

        except KeyboardInterrupt:
            return self.options[-1][1]  # Return cancel/last option

    def _run_simple(self) -> str:
        """
        Run a simple text-based selector (fallback for VS Code terminal).

        Returns:
            The value of the selected option
        """
        # Display the options
        console.print()
        console.print(f"[bold yellow]{self.title}[/bold yellow]")
        if self.subtitle:
            console.print(f"[dim]{self.subtitle}[/dim]")
        console.print()

        for i, (label, value, shortcut, color) in enumerate(self.options):
            console.print(f"  [{color}]{shortcut.upper()}[/] {label}")

        console.print()

        # Prompt for input
        shortcuts = "/".join(opt[2].upper() for opt in self.options)
        while True:
            try:
                choice = prompt(f"Choose ({shortcuts}): ").strip().lower()

                # Check if input matches a shortcut
                for label, value, shortcut, color in self.options:
                    if choice == shortcut.lower():
                        return value

                console.print("[red]Invalid choice. Please try again.[/red]")
            except (KeyboardInterrupt, EOFError):
                return self.options[-1][1]  # Return cancel/last option

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
        title="Task",
        border_style="blue",
    )
    console.print(panel)


def print_iteration(current: int, total: int) -> None:
    """Print current iteration"""
    console.print(f"[dim]Iteration {current}/{total}[/dim]", end=" ")


def print_action(tool_name: str, arguments: dict) -> None:
    """Print tool action - subtle, single line"""
    # Show only key arguments, truncate aggressively
    key_args = []
    for k, v in arguments.items():
        v_str = str(v)
        if len(v_str) > 30:
            v_str = v_str[:27] + "..."
        key_args.append(f"{k}={v_str}")
    args_str = ", ".join(key_args)
    if len(args_str) > 60:
        args_str = args_str[:57] + "..."
    console.print(f"[dim]> {tool_name}({args_str})[/dim]")


def print_observation(result: any) -> None:
    """Print tool observation - compact, understated"""
    success = getattr(result, "success", False)
    output = getattr(result, "output", None) or getattr(result, "error", "")
    output_str = str(output)

    # Truncate aggressively - show just a brief summary
    if len(output_str) > 150:
        # Try to get first meaningful line
        first_line = output_str.split('\n')[0][:100]
        output_str = f"{first_line}... (+{len(output_str)} chars)"

    if success:
        console.print(f"  [dim green]ok[/dim green] [dim]{output_str}[/dim]")
    else:
        console.print(f"  [red]err[/red] [dim]{output_str}[/dim]")


def print_success(message: str) -> None:
    """Print success message"""
    console.print(f"\n[bold green][ok] {message}[/bold green]\n")


def print_warning(message: str) -> None:
    """Print warning message"""
    console.print(f"\n[bold yellow][warn] {message}[/bold yellow]\n")


def print_error(message: str) -> None:
    """Print error message"""
    console.print(f"\n[bold red][error] {message}[/bold red]\n")


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
    Ask user to confirm an action with an inline selector.

    Clean, minimal inline UI for simple yes/no decisions.
    Supports both arrow key navigation and direct shortcuts (Y/N).
    Automatically closes any open VS Code temp files after user choice.

    Args:
        message: Confirmation message
        default: Default value if user just presses enter

    Returns:
        True if confirmed
    """
    try:
        console.print()

        # Create inline selector with Yes/No options
        selector = InlineSelector(
            options=[
                ("Yes, proceed", True, "y", "green"),
                ("No, cancel", False, "n", "red"),
            ],
            title="Confirm Action",
            subtitle=message,
        )

        result = selector.run()

        # Show confirmation message
        if result:
            console.print("[green]✓ Approved[/green]")
        else:
            console.print("[red]✗ Rejected[/red]")

        console.print()

        # Close VS Code temp files
        close_vscode_temp_files()

        return result if result is not None else False

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Action cancelled[/yellow]")
        close_vscode_temp_files()
        return False


def confirm_file_change(filepath: str, action: str = "apply changes") -> str:
    """
    Ask user to confirm file changes with an inline selector.

    Uses arrow keys to navigate and Enter to select, or direct shortcuts.
    Stays inline in the terminal - doesn't take over the screen.

    Args:
        filepath: Path to the file being modified
        action: Description of the action (e.g., "apply changes", "create file")

    Returns:
        One of: 'approve', 'reject', 'edit', 'cancel'
    """
    try:
        console.print()

        # Show file context
        console.print(f"[dim]File:[/dim] [bold white]{filepath}[/bold white]")
        console.print()

        # Create inline selector with all options
        selector = InlineSelector(
            options=[
                ("Approve", "approve", "y", "green"),
                ("Reject", "reject", "n", "red"),
                ("Edit", "edit", "e", "yellow"),
                ("Cancel", "cancel", "c", "dim"),
            ],
            title=f"Approval Required",
            subtitle=f"Action: {action.title()}",
        )

        result = selector.run()

        # Show confirmation message
        if result == 'approve':
            console.print("[green]✓ Changes approved[/green]")
        elif result == 'reject':
            console.print("[red]✗ Changes rejected[/red]")
        elif result == 'edit':
            console.print("[yellow]✎ Opening for edit[/yellow]")
        else:
            console.print("[dim]⊗ Cancelled[/dim]")

        console.print()

        # Close VS Code temp files
        close_vscode_temp_files()

        return result if result else 'cancel'

    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Action cancelled[/yellow]")
        close_vscode_temp_files()
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

    table = Table(title="Files Modified")

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
# Vishwa

Terminal-based Agentic Coding Assistant

Named after Vishwakarma, the divine architect and craftsman.
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


# =============================================================================
# SUB-AGENT VISUAL INDICATORS
# =============================================================================

# Sub-agent type configurations for visual display
SUBAGENT_CONFIGS = {
    "Explore": {
        "icon": ">",
        "color": "cyan",
        "description": "Exploring codebase",
    },
    "Plan": {
        "icon": ">",
        "color": "blue",
        "description": "Planning implementation",
    },
    "Test": {
        "icon": ">",
        "color": "magenta",
        "description": "Analyzing tests",
    },
    "Refactor": {
        "icon": ">",
        "color": "yellow",
        "description": "Reviewing code",
    },
    "Documentation": {
        "icon": ">",
        "color": "green",
        "description": "Generating docs",
    },
}


def print_subagent_start(subagent_type: str, description: str, thoroughness: str = "medium") -> None:
    """
    Print a visual indicator when a sub-agent is launched.

    Creates a distinctive panel that clearly shows:
    - Which type of sub-agent is running
    - What task it's performing
    - Thoroughness level (for Explore agents)

    Args:
        subagent_type: Type of sub-agent (Explore, Plan, Test, Refactor, Documentation)
        description: Short description of the task
        thoroughness: Thoroughness level (quick, medium, very thorough)
    """
    config = SUBAGENT_CONFIGS.get(subagent_type, {
        "icon": "🤖",
        "color": "white",
        "description": "Running task",
    })

    icon = config["icon"]
    color = config["color"]

    # Build content
    content_lines = []
    content_lines.append(Text.from_markup(f"[bold {color}]{description}[/bold {color}]"))

    # Add thoroughness indicator for Explore agents
    if subagent_type == "Explore":
        content_lines.append(Text.from_markup(f"\n[dim]Thoroughness: {thoroughness}[/dim]"))

    content = Group(*content_lines)

    # Create a distinctive panel
    panel = Panel(
        content,
        title=f"[bold {color}]Sub-Agent: {subagent_type}[/bold {color}]",
        subtitle="[dim italic]autonomous execution[/dim italic]",
        border_style=color,
        padding=(0, 2),
    )

    console.print()
    console.print(panel)


def print_subagent_progress(iteration: int, max_iterations: int, status: str = "") -> None:
    """
    Print progress update for a running sub-agent.

    Args:
        iteration: Current iteration number
        max_iterations: Maximum iterations allowed
        status: Optional status message
    """
    # Create progress bar
    progress_width = 20
    filled = int((iteration / max_iterations) * progress_width)
    bar = "█" * filled + "░" * (progress_width - filled)

    progress_text = f"  [dim]Progress: [{bar}] {iteration}/{max_iterations}[/dim]"
    if status:
        progress_text += f" [dim italic]{status}[/dim italic]"

    console.print(progress_text)


def print_subagent_complete(
    subagent_type: str,
    success: bool,
    iterations_used: int,
    stop_reason: str = ""
) -> None:
    """
    Print completion indicator for a sub-agent.

    Creates a clear visual showing the sub-agent has finished
    and summarizes how it completed.

    Args:
        subagent_type: Type of sub-agent
        success: Whether the sub-agent completed successfully
        iterations_used: Number of iterations used
        stop_reason: Reason for stopping
    """
    config = SUBAGENT_CONFIGS.get(subagent_type, {"icon": ">", "color": "white"})
    color = config["color"]

    if success:
        status_icon = "[ok]"
        status_color = "green"
        status_text = "Complete"
    else:
        status_icon = "[fail]"
        status_color = "red"
        status_text = "Failed"

    # Build completion message
    completion_text = Text()
    completion_text.append(f"  <- ", style=f"bold {color}")
    completion_text.append(f"{subagent_type} ", style=f"bold {color}")
    completion_text.append(f"{status_icon} {status_text}", style=f"bold {status_color}")
    completion_text.append(f" | {iterations_used} iterations", style="dim")

    if stop_reason:
        completion_text.append(f" • {stop_reason}", style="dim italic")

    console.print(completion_text)
    console.print()


def create_subagent_spinner(subagent_type: str, description: str):
    """
    Create a spinner for sub-agent execution.

    Args:
        subagent_type: Type of sub-agent
        description: Task description

    Returns:
        Progress context manager with spinner
    """
    config = SUBAGENT_CONFIGS.get(subagent_type, {"icon": ">", "color": "cyan"})

    return Progress(
        SpinnerColumn("dots"),
        TextColumn(f"[{config['color']}]{subagent_type}:[/{config['color']}] {{task.description}}"),
        console=console,
        transient=True,
    )


# =============================================================================
# PRE-COMPLETION REVIEW INDICATORS
# =============================================================================

def print_pre_completion_review(file_count: int) -> None:
    """
    Print indicator that pre-completion code review is starting.

    Args:
        file_count: Number of Python files being reviewed
    """
    console.print()
    console.print(f"[cyan]Running code review on {file_count} modified file(s)...[/cyan]")


def print_pre_completion_issues(fix_attempt: int, max_attempts: int) -> None:
    """
    Print indicator that pre-completion review found issues and is attempting fixes.

    Args:
        fix_attempt: Current fix attempt number
        max_attempts: Maximum fix attempts allowed
    """
    console.print()
    console.print(f"[yellow]⚠ Code review found issues - attempting fix ({fix_attempt}/{max_attempts})[/yellow]")


def print_pre_completion_passed() -> None:
    """Print indicator that pre-completion review passed with no issues."""
    console.print("[green]✓ Code review passed - no critical or medium issues found[/green]")
    console.print()


# =============================================================================
# CODE QUALITY CHECK INDICATORS
# =============================================================================

def print_quality_check_start(file_path: str) -> None:
    """
    Print indicator that code quality check is starting for a file.

    Args:
        file_path: Path to the file being checked
    """
    console.print(f"[dim]Checking code quality: {file_path}[/dim]")


def print_quality_passed(file_path: str) -> None:
    """
    Print indicator that code quality check passed.

    Args:
        file_path: Path to the file that passed
    """
    console.print(f"[green]✓ Quality check passed: {file_path}[/green]")


def print_quality_issues(file_path: str, issues_count: int, errors: int, warnings: int) -> None:
    """
    Print code quality issues found in a file.

    Args:
        file_path: Path to the file with issues
        issues_count: Total number of issues
        errors: Number of errors
        warnings: Number of warnings
    """
    console.print(f"[yellow]⚠ Quality issues in {file_path}: {issues_count} issues ({errors} errors, {warnings} warnings)[/yellow]")
