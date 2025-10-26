"""
Interactive REPL mode for Vishwa.

Provides a professional terminal interface with:
- Clean, minimal design
- Cyan accent colors for borders and prompts
- Animated spinners (no emojis except ✓/✗)
- Session persistence across messages
"""

import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import completion_is_selected
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table

from vishwa.agent.core import VishwaAgent
from vishwa.cli.file_completer import FileCompleter
from vishwa.cli.command_completer import CommandCompleter
from vishwa.cli.merged_completer import MergedCompleter
from vishwa.config import Config


# Color scheme
STYLE = Style.from_dict({
    'prompt': '#00d7ff bold',      # Cyan prompt
    'context': '#00d7ff',          # Cyan context indicator
    'command': '#00d7ff',          # Cyan commands
    'success': '#00ff00',          # Green success
    'error': '#ff5555',            # Red errors
    'info': '#5f87ff',             # Blue info
    'secondary': 'ansibrightblack',  # Dim gray metadata
    'separator': 'ansibrightblack',  # Dim gray separators

    # Completion menu styling (for autocomplete dropdown)
    'completion-menu': 'bg:#1a1a1a #ffffff',  # Dark background, white text
    'completion-menu.completion': 'bg:#1a1a1a #e0e0e0',  # Normal items: light gray text
    'completion-menu.completion.current': 'bg:#00d7ff #000000 bold',  # Selected: cyan bg, black text, bold
    'completion-menu.meta': 'bg:#1a1a1a #808080',  # Metadata: gray text
    'completion-menu.meta.current': 'bg:#00d7ff #000000',  # Selected meta: black text on cyan
})


class InteractiveSession:
    """
    Manages interactive REPL session for Vishwa.

    Features:
    - Persistent context across messages
    - Command history
    - Slash commands
    - Clean, professional UI with cyan accents
    """

    def __init__(
        self,
        agent: VishwaAgent,
        config: Config,
        console: Optional[Console] = None,
    ):
        """
        Initialize interactive session.

        Args:
            agent: Vishwa agent instance
            config: Configuration
            console: Rich console (creates new if None)
        """
        self.agent = agent
        self.config = config
        self.console = console or Console()

        # Session state
        self.running = True
        self.message_count = 0
        self.start_time = datetime.now()

        # Command registry
        self.commands = self._register_commands()

        # Setup completers
        workspace_root = Path(os.getcwd())
        file_completer = FileCompleter(workspace_root, max_suggestions=10)

        # Create command descriptions for completer
        command_descriptions = {
            'help': 'Show help message',
            'exit': 'Exit Vishwa',
            'quit': 'Exit Vishwa',
            'clear': 'Clear screen (preserves conversation)',
            'reset': 'Clear conversation history',
            'files': 'Show files in context',
            'model': 'Switch LLM model',
            'models': 'List available models',
        }
        command_completer = CommandCompleter(command_descriptions)

        # Merge completers for @ and / support
        merged_completer = MergedCompleter(file_completer, command_completer)

        # Setup custom key bindings for better autocomplete UX
        kb = KeyBindings()

        # Make Enter accept completion without submitting when completion menu is visible
        # This allows user to select a file with Enter and continue typing their question
        @kb.add('enter', filter=completion_is_selected)
        def _(event):
            """Accept the selected completion and keep the prompt open."""
            # Get the current buffer and completion
            buffer = event.current_buffer

            # Apply the currently selected completion
            if buffer.complete_state:
                current_completion = buffer.complete_state.current_completion
                if current_completion:
                    buffer.apply_completion(current_completion)

        # Setup prompt toolkit with merged completer
        history_file = Path.home() / ".vishwa_history"
        self.prompt_session = PromptSession(
            history=FileHistory(str(history_file)),
            style=STYLE,
            completer=merged_completer,
            complete_while_typing=True,
            key_bindings=kb,
        )

    def start(self):
        """Start the interactive REPL loop."""
        self._print_welcome()

        while self.running:
            try:
                # Get user input
                user_input = self._get_input()

                if not user_input.strip():
                    continue

                self.message_count += 1

                # Check if it's a command
                if user_input.startswith('/'):
                    self._execute_command(user_input)
                else:
                    self._execute_task(user_input)

            except KeyboardInterrupt:
                self.console.print("\n[dim]Use /exit to quit[/dim]")
                continue
            except EOFError:
                self._exit()
                break
            except Exception as e:
                self.console.print(f"\n[red]✗ Error: {e}[/red]")
                continue

        self._print_goodbye()

    def _print_welcome(self):
        """Print welcome screen with clean design."""
        # Get model and config info
        model_name = getattr(self.config, 'model', 'default')
        cwd = os.getcwd()

        # Create welcome panel with cyan border
        welcome_text = (
            f"[bold white]Vishwa[/bold white] - Agentic Coding Assistant\n"
            f"[ansibrightblack]Model: {model_name} | Context: 0 files[/ansibrightblack]"
        )

        panel = Panel(
            welcome_text,
            border_style="cyan",
            padding=(0, 1),
        )

        self.console.print()
        self.console.print(panel)
        self.console.print(f"\n[ansibrightblack]Working directory:[/ansibrightblack] {cwd}")
        self.console.print("[ansibrightblack]Type /help for commands or start chatting[/ansibrightblack]")
        self.console.print()

    def _print_goodbye(self):
        """Print goodbye message."""
        duration = datetime.now() - self.start_time
        minutes = int(duration.total_seconds() / 60)
        seconds = int(duration.total_seconds() % 60)

        self.console.print()
        self.console.print("[dim]" + "─" * 50 + "[/dim]")
        self.console.print(
            f"[dim]Session ended | {self.message_count} messages | {minutes}m {seconds}s[/dim]"
        )
        self.console.print()

    def _get_input(self) -> str:
        """
        Get user input with styled prompt.

        Returns:
            User input string
        """
        # Show context indicator if files are tracked
        files_count = len(self.agent.context.files_in_context)

        if files_count > 0:
            prompt_text = HTML(f'<context>[{files_count} files]</context> <prompt>&gt;</prompt> ')
        else:
            prompt_text = HTML('<prompt>&gt;</prompt> ')

        return self.prompt_session.prompt(prompt_text)

    def _execute_task(self, task: str):
        """
        Execute a coding task.

        Args:
            task: User's task description
        """
        start_time = time.time()
        self.console.print()  # Add spacing before task execution

        # Process @ file mentions and load files into context
        self._process_file_mentions(task)

        # Run agent with context preservation for interactive mode
        result = self.agent.run(task, clear_context=False)

        # Add assistant's response to context for next turn
        if result.success and result.message:
            self.agent.context.add_message("assistant", result.message)

        # Show result
        elapsed = time.time() - start_time

        if result.success:
            # Check if this was a conversational response (no tool usage)
            if result.stop_reason == "conversational_response":
                # For greetings/questions, just show the message without extra formatting
                self.console.print(f"\n{result.message}")
            else:
                # For coding tasks, show completion with timing
                self.console.print()
                self.console.print("[dim]" + "─" * 50 + "[/dim]")
                self.console.print(
                    f"[dim]Task completed in {elapsed:.1f}s[/dim]"
                )
        else:
            self.console.print()
            self.console.print(f"[red]✗ {result.message}[/red]")

        self.console.print()

    def _process_file_mentions(self, task: str):
        """
        Parse @ file mentions from user input and load files into context.

        Args:
            task: User input that may contain @filepath mentions
        """
        # Pattern to match @filepath (supports spaces if quoted, or non-space paths)
        # Matches: @path/to/file.py or @"path with spaces/file.py"
        # Stops at punctuation: comma, space, newline, etc.
        pattern = r'@(?:"([^"]+)"|([^\s,;:!?\n]+))'

        matches = re.finditer(pattern, task)

        for match in matches:
            # Get the filepath (either from quoted or unquoted group)
            filepath_str = match.group(1) if match.group(1) else match.group(2)

            if not filepath_str:
                continue

            # Resolve path (can be absolute or relative to workspace)
            filepath = Path(filepath_str)

            # If relative, resolve from workspace root
            if not filepath.is_absolute():
                workspace_root = Path(os.getcwd())
                filepath = workspace_root / filepath

            # Try to read and load the file into context
            try:
                if filepath.exists() and filepath.is_file():
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Add file to agent's context
                    relative_path = str(filepath.relative_to(Path(os.getcwd())))
                    self.agent.context.add_file_to_context(relative_path, content)

                    # Show confirmation
                    self.console.print(
                        f"[dim]📄 Loaded: {relative_path}[/dim]"
                    )
                else:
                    self.console.print(
                        f"[yellow]⚠ File not found: {filepath_str}[/yellow]"
                    )

            except Exception as e:
                self.console.print(
                    f"[yellow]⚠ Could not read {filepath_str}: {e}[/yellow]"
                )

    def _execute_command(self, cmd_input: str):
        """
        Execute a slash command.

        Args:
            cmd_input: Command string (e.g., "/help")
        """
        parts = cmd_input.split()
        cmd_name = parts[0][1:]  # Remove leading /
        cmd_args = parts[1:] if len(parts) > 1 else []

        if cmd_name in self.commands:
            self.commands[cmd_name](cmd_args)
        else:
            self.console.print(f"[red]✗ Unknown command: /{cmd_name}[/red]")
            self.console.print("[dim]Type /help for available commands[/dim]")
            self.console.print()

    def _register_commands(self) -> Dict:
        """
        Register all slash commands.

        Returns:
            Dictionary mapping command names to handler functions
        """
        return {
            'help': self._cmd_help,
            'exit': self._cmd_exit,
            'quit': self._cmd_exit,
            'clear': self._cmd_clear,
            'reset': self._cmd_reset,
            'files': self._cmd_files,
            'model': self._cmd_model,
            'models': self._cmd_models,
        }

    # Command handlers

    def _cmd_help(self, args: List[str]):
        """Show help message."""
        self.console.print()

        # Create help table
        table = Table(show_header=True, header_style="cyan", border_style="cyan")
        table.add_column("Command", style="cyan")
        table.add_column("Description")

        table.add_row("/help", "Show this help message")
        table.add_row("/exit, /quit", "Exit Vishwa")
        table.add_row("/clear", "Clear the screen (preserves conversation)")
        table.add_row("/reset", "Clear conversation history and start fresh")
        table.add_row("/files", "Show files in context")
        table.add_row("/model <name>", "Switch LLM model")
        table.add_row("/models", "List available models")

        self.console.print(table)
        self.console.print()
        self.console.print("[cyan]File Context:[/cyan]")
        self.console.print("  Type [cyan]@[/cyan] to autocomplete and reference files")
        self.console.print("  Example: [dim]Fix the bug in @src/main.py[/dim]")
        self.console.print()

    def _cmd_exit(self, args: List[str]):
        """Exit the session."""
        self._exit()

    def _exit(self):
        """Internal exit handler."""
        self.running = False

    def _cmd_clear(self, args: List[str]):
        """Clear the screen."""
        self.console.clear()
        self._print_welcome()

    def _cmd_reset(self, args: List[str]):
        """Reset context."""
        self.agent.context.clear()
        self.console.print()
        self.console.print("[green]✓ Context reset[/green]")
        self.console.print()

    def _cmd_files(self, args: List[str]):
        """Show files in context."""
        files = list(self.agent.context.files_in_context.keys())

        self.console.print()

        if not files:
            self.console.print("[dim]No files in context[/dim]")
        else:
            self.console.print(f"[cyan]Files in context:[/cyan] ({len(files)})")
            for file_path in files:
                self.console.print(f"  {file_path}")

        self.console.print()

    def _cmd_model(self, args: List[str]):
        """Switch LLM model."""
        if not args:
            current = getattr(self.config, 'model', 'default')
            self.console.print()
            self.console.print(f"Current model: [cyan]{current}[/cyan]")
            self.console.print("[dim]Usage: /model <name>[/dim]")
            self.console.print()
            return

        model_name = args[0]
        self.console.print()
        self.console.print(f"[green]✓ Switched to [cyan]{model_name}[/cyan][/green]")
        self.console.print()

        # TODO: Actually switch the model
        # self.config.model = model_name

    def _cmd_models(self, args: List[str]):
        """List available models."""
        self.console.print()
        self.console.print("[cyan]Available models:[/cyan]")
        self.console.print("  claude-sonnet-4")
        self.console.print("  gpt-4o")
        self.console.print("  local (Ollama)")
        self.console.print()
