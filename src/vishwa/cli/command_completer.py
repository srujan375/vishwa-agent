"""
Command autocomplete for / commands in Vishwa.

This module provides autocomplete when users type / in the interactive prompt.
"""

from typing import Dict, Iterable
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document


class CommandCompleter(Completer):
    """
    Autocompletes slash commands when user types / in the prompt.

    Shows available commands with their descriptions.
    """

    def __init__(self, commands: Dict[str, str]):
        """
        Initialize the command completer.

        Args:
            commands: Dictionary mapping command names to descriptions
        """
        self.commands = commands

    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """
        Generate command completions for / commands.

        Args:
            document: Current prompt document
            complete_event: Completion event

        Yields:
            Completion objects for matching commands
        """
        text_before_cursor = document.text_before_cursor

        # Only complete if we're at the start and have /
        if not text_before_cursor.startswith('/'):
            return

        # Get the query after /
        query = text_before_cursor[1:].lower()

        # If there's a space, don't complete (command already entered)
        if ' ' in query:
            return

        # Find matching commands
        for cmd_name, description in sorted(self.commands.items()):
            # Filter by query
            if query and not cmd_name.lower().startswith(query):
                continue

            # Calculate start position (after /)
            start_position = -len(query)

            yield Completion(
                text=cmd_name,
                start_position=start_position,
                display=f"/{cmd_name}",
                display_meta=description,
            )
