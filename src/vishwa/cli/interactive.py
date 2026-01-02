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
from vishwa.session import SessionManager, Session, CheckpointManager


# Color scheme
STYLE = Style.from_dict({
    # Prompt styling - more prominent
    'prompt': '#00d7ff bold',           # Cyan prompt symbol
    'prompt-symbol': '#00d7ff bold',    # Bold cyan for main symbol
    'context': '#8b5cf6 bold',          # Purple for file count
    'model': '#22c55e',                 # Green for model indicator
    'command': '#00d7ff',               # Cyan commands
    'success': '#00ff00',               # Green success
    'error': '#ff5555',                 # Red errors
    'info': '#5f87ff',                  # Blue info
    'secondary': 'ansibrightblack',     # Dim gray metadata
    'separator': 'ansibrightblack',     # Dim gray separators
    'input-border': '#00d7ff',          # Cyan border for input area

    # Completion menu styling (for autocomplete dropdown)
    'completion-menu': 'bg:#1a1a1a #ffffff',  # Dark background, white text
    'completion-menu.completion': 'bg:#1a1a1a #e0e0e0',  # Normal items: light gray text
    'completion-menu.completion.current': 'bg:#00d7ff #000000 bold',  # Selected: cyan bg, black text, bold
    'completion-menu.meta': 'bg:#1a1a1a #808080',  # Metadata: gray text
    'completion-menu.meta.current': 'bg:#00d7ff #000000',  # Selected meta: black text on cyan

    # Bottom toolbar styling
    'bottom-toolbar': 'bg:#1a1a2e #888888',
    'bottom-toolbar.text': '#888888',
    'bottom-toolbar.key': '#00d7ff bold',
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

        # Session persistence
        self.session_manager = SessionManager()
        self.session_id = self.session_manager.generate_session_id()
        self.session_name: Optional[str] = None

        # Checkpoint manager for rewind
        self.checkpoint_manager = CheckpointManager(self.session_id)

        # Tool results tracking
        self.tool_results: List[Dict[str, Any]] = []

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
            'ollama': 'Manage Ollama models',
            'review': 'Toggle code review on/off',
            'iterations': 'Set max iterations limit',
            'dangerous': 'Toggle dangerous mode (skip approvals)',
            'sessions': 'List saved sessions',
            'resume': 'Resume a previous session',
            'rename': 'Name the current session',
            'rewind': 'Rewind to a previous checkpoint',
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
        """Print welcome screen with clean, minimal design."""
        # Get model and config info
        model_name = getattr(self.config, 'model', 'default')
        cwd = os.getcwd()

        # Shorten working directory for display
        home = str(Path.home())
        if cwd.startswith(home):
            display_cwd = "~" + cwd[len(home):]
        else:
            display_cwd = cwd

        # Clean header - similar to Claude Code style
        self.console.print()
        self.console.print(f"[bold cyan]Vishwa[/bold cyan] [dim]- Agentic Coding Assistant[/dim]")
        self.console.print(f"[dim]{model_name}[/dim]")
        self.console.print(f"[dim]{display_cwd}[/dim]")
        self.console.print()
        self.console.print("[dim]Type /help for commands[/dim]")

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
        if self.message_count > 0:
            self.console.print(f"[dim]Session saved. Resume with: /resume 1[/dim]")
        self.console.print()

    def _get_input(self) -> str:
        """
        Get user input with styled prompt.

        Simple, clean design inspired by Claude Code:
        - Horizontal separator line above
        - Simple `>` prompt

        Returns:
            User input string
        """
        # Get terminal width
        terminal_width = self.console.width or 80
        separator_line = "─" * terminal_width

        # Print separator line (full width)
        self.console.print()
        self.console.print(f"[dim]{separator_line}[/dim]")

        # Simple prompt - just `>`
        prompt_text = HTML('<prompt-symbol>></prompt-symbol> ')

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
            'ollama': self._cmd_ollama,
            'review': self._cmd_review,
            'iterations': self._cmd_iterations,
            'dangerous': self._cmd_dangerous,
            'sessions': self._cmd_sessions,
            'resume': self._cmd_resume,
            'rename': self._cmd_rename,
            'rewind': self._cmd_rewind,
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
        table.add_row("/ollama [list|pull <model>]", "Manage Ollama models")
        table.add_row("/review", "Toggle code review on/off")
        table.add_row("/iterations [n]", "Set max iterations (no arg = unlimited)")
        table.add_row("/dangerous", "Toggle dangerous mode (skip all approvals)")
        table.add_row("/sessions", "List saved sessions")
        table.add_row("/resume [n]", "Resume session by number, name, or ID")
        table.add_row("/rename <name>", "Name the current session")
        table.add_row("/rewind [n]", "Rewind to checkpoint (n=1 most recent)")

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
        # Auto-save session before exiting
        self._save_current_session()
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
            current_model = self.agent.llm.model_name
            current_provider = self.agent.llm.provider_name
            self.console.print()
            self.console.print(f"Current model: [cyan]{current_model}[/cyan] ([dim]{current_provider}[/dim])")
            self.console.print("[dim]Usage: /model <name>[/dim]")
            self.console.print()
            return

        model_name = args[0]

        try:
            # Import LLMFactory
            from vishwa.llm import LLMFactory

            # Create new LLM instance
            new_llm = LLMFactory.create(model_name)

            # Update agent's LLM
            self.agent.llm = new_llm

            # Update config
            self.config.model = model_name

            self.console.print()
            self.console.print(f"[green]✓ Switched to [cyan]{new_llm.model_name}[/cyan] ([dim]{new_llm.provider_name}[/dim])[/green]")
            self.console.print()

        except Exception as e:
            self.console.print()
            self.console.print(f"[red]✗ Failed to switch model: {e}[/red]")
            self.console.print("[dim]Use /models to see available models[/dim]")
            self.console.print()

    def _cmd_models(self, args: List[str]):
        """List available models."""
        from vishwa.llm.config import LLMConfig
        from vishwa.llm.ollama_provider import OllamaProvider

        self.console.print()

        # Create table
        table = Table(show_header=True, header_style="cyan", border_style="cyan")
        table.add_column("Provider", style="cyan")
        table.add_column("Models")

        # Get models by provider
        models_by_provider = LLMConfig.list_available_models()

        # Anthropic models
        anthropic_models = sorted(set(models_by_provider.get("anthropic", [])))
        if anthropic_models:
            table.add_row("Anthropic", "\n".join(anthropic_models))

        # OpenAI models
        openai_models = sorted(set(models_by_provider.get("openai", [])))
        if openai_models:
            table.add_row("OpenAI", "\n".join(openai_models))

        # Ollama models - check if running and list actual available models
        ollama_models = []
        if OllamaProvider.is_ollama_running():
            try:
                available = OllamaProvider.list_available_models()
                if available:
                    ollama_models = sorted(available)
                    table.add_row("Ollama (local)", "\n".join(ollama_models))
                else:
                    table.add_row("Ollama (local)", "[dim]No models installed[/dim]\n[dim]Use /ollama pull <model>[/dim]")
            except:
                table.add_row("Ollama (local)", "[dim]Error listing models[/dim]")
        else:
            table.add_row("Ollama (local)", "[red]Not running[/red]")

        self.console.print(table)
        self.console.print()
        self.console.print("[dim]Aliases: claude → claude-sonnet-4-5, openai → gpt-4o, local → deepseek-coder:33b[/dim]")
        self.console.print()

    def _cmd_ollama(self, args: List[str]):
        """Manage Ollama models."""
        from vishwa.llm.ollama_provider import OllamaProvider
        import subprocess

        if not args or args[0] == "list":
            # List available Ollama models
            self.console.print()

            if not OllamaProvider.is_ollama_running():
                self.console.print("[red]✗ Ollama is not running[/red]")
                self.console.print("[dim]Install from: https://ollama.com/download[/dim]")
                self.console.print()
                return

            try:
                models = OllamaProvider.list_available_models()
                if models:
                    self.console.print("[cyan]Installed Ollama models:[/cyan]")
                    for model in sorted(models):
                        self.console.print(f"  • {model}")
                else:
                    self.console.print("[dim]No models installed[/dim]")
                    self.console.print("[dim]Pull a model: /ollama pull deepseek-coder:33b[/dim]")
            except Exception as e:
                self.console.print(f"[red]✗ Error listing models: {e}[/red]")

            self.console.print()

        elif args[0] == "pull":
            # Pull a new Ollama model
            if len(args) < 2:
                self.console.print()
                self.console.print("[red]✗ Model name required[/red]")
                self.console.print("[dim]Usage: /ollama pull <model>[/dim]")
                self.console.print("[dim]Example: /ollama pull deepseek-coder:33b[/dim]")
                self.console.print()
                return

            model_name = args[1]

            if not OllamaProvider.is_ollama_running():
                self.console.print()
                self.console.print("[red]✗ Ollama is not running[/red]")
                self.console.print("[dim]Install from: https://ollama.com/download[/dim]")
                self.console.print()
                return

            self.console.print()
            self.console.print(f"[cyan]Pulling {model_name}...[/cyan]")
            self.console.print("[dim]This may take a few minutes for large models[/dim]")
            self.console.print()

            try:
                # Run ollama pull command
                result = subprocess.run(
                    ["ollama", "pull", model_name],
                    capture_output=True,
                    text=True,
                    check=True
                )

                self.console.print(f"[green]✓ Successfully pulled {model_name}[/green]")
                self.console.print(f"[dim]Use it with: /model {model_name}[/dim]")
                self.console.print()

            except subprocess.CalledProcessError as e:
                self.console.print(f"[red]✗ Failed to pull model: {e.stderr}[/red]")
                self.console.print()
            except FileNotFoundError:
                self.console.print("[red]✗ 'ollama' command not found[/red]")
                self.console.print("[dim]Make sure Ollama is installed and in PATH[/dim]")
                self.console.print()
            except Exception as e:
                self.console.print(f"[red]✗ Error: {e}[/red]")
                self.console.print()

        else:
            self.console.print()
            self.console.print(f"[red]✗ Unknown ollama subcommand: {args[0]}[/red]")
            self.console.print("[dim]Usage: /ollama [list|pull <model>][/dim]")
            self.console.print()

    def _cmd_review(self, args: List[str]):
        """Toggle code review on/off."""
        self.console.print()

        # Toggle the skip_review flag
        current_state = getattr(self.agent, 'skip_review', False)
        new_state = not current_state
        self.agent.skip_review = new_state

        if new_state:
            self.console.print("[yellow]⚠ Code review disabled[/yellow]")
            self.console.print("[dim]Code will not be reviewed before completion[/dim]")
        else:
            self.console.print("[green]✓ Code review enabled[/green]")
            self.console.print("[dim]Code will be reviewed for critical and medium issues[/dim]")

        self.console.print()

    def _cmd_iterations(self, args: List[str]):
        """Set maximum iterations limit."""
        self.console.print()

        if not args:
            # No argument - set to unlimited
            self.agent.max_iterations = None
            self.console.print("[green]✓ Iterations set to unlimited[/green]")
            self.console.print("[dim]Agent will run until task completion[/dim]")
        else:
            try:
                limit = int(args[0])
                if limit <= 0:
                    self.console.print("[red]✗ Iterations must be a positive number[/red]")
                    self.console.print()
                    return

                self.agent.max_iterations = limit
                self.console.print(f"[green]✓ Max iterations set to {limit}[/green]")
            except ValueError:
                self.console.print(f"[red]✗ Invalid number: {args[0]}[/red]")
                self.console.print("[dim]Usage: /iterations [n] (no arg = unlimited)[/dim]")

        # Show current setting
        current = self.agent.max_iterations
        if current:
            self.console.print(f"[dim]Current limit: {current} iterations[/dim]")
        else:
            self.console.print("[dim]Current limit: unlimited[/dim]")

        self.console.print()

    def _cmd_dangerous(self, args: List[str]):
        """Toggle dangerous mode (skip all approval prompts)."""
        from vishwa.tools import ToolRegistry

        self.console.print()

        # Toggle auto_approve
        current_state = getattr(self.agent, 'auto_approve', False)
        new_state = not current_state
        self.agent.auto_approve = new_state

        # Reload tools with new auto_approve setting
        self.agent.tools = ToolRegistry.load_default(auto_approve=new_state)

        if new_state:
            self.console.print("[red bold]⚠ DANGEROUS MODE ENABLED[/red bold]")
            self.console.print("[yellow]All file edits and commands will run without approval[/yellow]")
            self.console.print("[dim]Use /dangerous again to disable[/dim]")
        else:
            self.console.print("[green]✓ Dangerous mode disabled[/green]")
            self.console.print("[dim]File edits and risky commands will require approval[/dim]")

        self.console.print()

    def _cmd_sessions(self, args: List[str]):
        """List saved sessions."""
        self.console.print()

        sessions = self.session_manager.list_sessions(limit=10)

        if not sessions:
            self.console.print("[dim]No saved sessions found[/dim]")
            self.console.print("[dim]Sessions are auto-saved when you exit[/dim]")
            self.console.print()
            return

        # Create table
        table = Table(show_header=True, header_style="cyan", border_style="cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("Name", style="cyan")
        table.add_column("Date", style="dim")
        table.add_column("Branch", style="dim")
        table.add_column("Msgs", justify="right")
        table.add_column("Summary")

        for idx, session in enumerate(sessions, 1):
            # Format date
            try:
                dt = datetime.fromisoformat(session.updated_at)
                date_str = dt.strftime("%m/%d %H:%M")
            except:
                date_str = session.updated_at[:16]

            # Session name or truncated summary
            name = session.name if session.name else "-"

            # Truncate summary
            summary = session.summary[:30] + "..." if len(session.summary) > 30 else session.summary

            # Git branch
            branch = session.git_branch or "-"

            table.add_row(
                str(idx),
                name,
                date_str,
                branch,
                str(session.message_count),
                summary,
            )

        self.console.print(table)
        self.console.print()
        self.console.print("[dim]Resume with: /resume <number> or /resume <name>[/dim]")
        self.console.print()

    def _cmd_resume(self, args: List[str]):
        """Resume a previous session."""
        self.console.print()

        if not args:
            self.console.print("[red]✗ Session number or ID required[/red]")
            self.console.print("[dim]Usage: /resume <number> or /resume <session-id>[/dim]")
            self.console.print("[dim]Use /sessions to see available sessions[/dim]")
            self.console.print()
            return

        session_ref = args[0]

        # Try to load by index first
        session = None
        try:
            index = int(session_ref)
            session = self.session_manager.get_session_by_index(index)
        except ValueError:
            # Not a number, try as session ID
            session = self.session_manager.load_session(session_ref)

        if not session:
            self.console.print(f"[red]✗ Session not found: {session_ref}[/red]")
            self.console.print("[dim]Use /sessions to see available sessions[/dim]")
            self.console.print()
            return

        # Restore session state
        self.session_id = session.id
        self.session_name = session.name
        self.message_count = session.message_count
        self.tool_results = session.tool_results

        # Restore checkpoint manager for this session
        self.checkpoint_manager = CheckpointManager(session.id)

        # Clear current context and restore from session
        self.agent.context.clear()

        # Restore messages
        for msg_data in session.messages:
            self.agent.context.add_message(
                role=msg_data.get("role", "user"),
                content=msg_data.get("content", ""),
                tool_call_id=msg_data.get("tool_call_id"),
                tool_calls=msg_data.get("tool_calls"),
            )

        # Restore files in context
        for path, content in session.files_in_context.items():
            self.agent.context.add_file_to_context(path, content)

        # Show resume info
        name_info = f" ({session.name})" if session.name else ""
        branch_info = f" on {session.git_branch}" if session.git_branch else ""
        self.console.print(f"[green]✓ Resumed session{name_info}{branch_info}[/green]")
        self.console.print(f"[dim]Restored {len(session.messages)} messages, {len(session.files_in_context)} files, {len(session.checkpoints)} checkpoints[/dim]")
        self.console.print()

    def _save_current_session(self) -> None:
        """Save the current session to disk."""
        # Only save if we have messages
        if self.message_count == 0:
            return

        # Get messages from agent context
        messages = self.agent.context.get_messages()

        # Create session object
        session = Session(
            id=self.session_id,
            name=self.session_name,
            created_at=self.start_time.isoformat(),
            updated_at=datetime.now().isoformat(),
            working_directory=os.getcwd(),
            git_branch=None,  # Will be set by save_session
            model=getattr(self.agent.llm, 'model_name', 'unknown'),
            message_count=self.message_count,
            summary=self.session_manager.create_summary(messages),
            messages=messages,
            tool_results=self.tool_results,
            files_in_context=dict(self.agent.context.files_in_context),
            modifications=[
                {
                    "file_path": mod.file_path,
                    "tool": mod.tool,
                    "timestamp": mod.timestamp,
                }
                for mod in self.agent.context.modifications
            ],
            checkpoints=[
                {
                    "id": cp.id,
                    "timestamp": cp.timestamp,
                    "message_index": cp.message_index,
                    "description": cp.description,
                }
                for cp in self.checkpoint_manager.get_checkpoints()
            ],
        )

        # Save to disk
        self.session_manager.save_session(session)

        # Cleanup old sessions (keep last 50)
        self.session_manager.cleanup_old_sessions(keep_count=50)

    def _cmd_rename(self, args: List[str]):
        """Rename the current session."""
        self.console.print()

        if not args:
            if self.session_name:
                self.console.print(f"[dim]Current session name: {self.session_name}[/dim]")
            else:
                self.console.print("[dim]Session has no name[/dim]")
            self.console.print("[dim]Usage: /rename <name>[/dim]")
            self.console.print()
            return

        new_name = " ".join(args)
        self.session_name = new_name

        # Save immediately to persist the name
        self._save_current_session()

        self.console.print(f"[green]✓ Session renamed to: {new_name}[/green]")
        self.console.print(f"[dim]Resume later with: /resume {new_name}[/dim]")
        self.console.print()

    def _cmd_rewind(self, args: List[str]):
        """Rewind to a previous checkpoint."""
        self.console.print()

        checkpoints = self.checkpoint_manager.get_checkpoints()

        if not checkpoints:
            self.console.print("[dim]No checkpoints available[/dim]")
            self.console.print("[dim]Checkpoints are created before file edits[/dim]")
            self.console.print()
            return

        # If no args, show available checkpoints
        if not args:
            table = Table(show_header=True, header_style="cyan", border_style="cyan")
            table.add_column("#", style="dim", width=3)
            table.add_column("Time", style="cyan")
            table.add_column("Description")
            table.add_column("Files", justify="right")

            # Show in reverse order (most recent first)
            for idx, cp in enumerate(reversed(checkpoints), 1):
                try:
                    dt = datetime.fromisoformat(cp.timestamp)
                    time_str = dt.strftime("%H:%M:%S")
                except:
                    time_str = cp.timestamp[:8]

                desc = cp.description[:40] + "..." if len(cp.description) > 40 else cp.description
                table.add_row(str(idx), time_str, desc, str(len(cp.file_states)))

            self.console.print(table)
            self.console.print()
            self.console.print("[dim]Rewind with: /rewind <number>[/dim]")
            self.console.print("[dim]Options: /rewind 1 code    - rewind code only[/dim]")
            self.console.print("[dim]         /rewind 1 both    - rewind code and conversation[/dim]")
            self.console.print()
            return

        # Parse arguments
        try:
            index = int(args[0])
        except ValueError:
            self.console.print(f"[red]✗ Invalid checkpoint number: {args[0]}[/red]")
            self.console.print()
            return

        # Check rewind mode
        rewind_code = True
        rewind_conversation = False

        if len(args) > 1:
            mode = args[1].lower()
            if mode == "code":
                rewind_code = True
                rewind_conversation = False
            elif mode == "both":
                rewind_code = True
                rewind_conversation = True
            elif mode == "conversation":
                rewind_code = False
                rewind_conversation = True

        # Perform rewind
        checkpoint = self.checkpoint_manager.rewind_to_index(index, rewind_code=rewind_code)

        if not checkpoint:
            self.console.print(f"[red]✗ Checkpoint {index} not found[/red]")
            self.console.print()
            return

        # Rewind conversation if requested
        if rewind_conversation and checkpoint.message_index < len(self.agent.context.messages):
            self.agent.context.messages = self.agent.context.messages[:checkpoint.message_index]

        files_restored = len(checkpoint.file_states) if rewind_code else 0
        self.console.print(f"[green]✓ Rewound to checkpoint {index}[/green]")
        if rewind_code:
            self.console.print(f"[dim]Restored {files_restored} file(s)[/dim]")
        self.console.print()
