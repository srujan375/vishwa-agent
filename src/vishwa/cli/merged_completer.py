"""
Merged completer that combines file and command completion.

This module provides a single completer that handles both @ file mentions
and / slash commands.
"""

from typing import Iterable
from prompt_toolkit.completion import Completer, Completion, merge_completers
from prompt_toolkit.document import Document

from vishwa.cli.file_completer import FileCompleter
from vishwa.cli.command_completer import CommandCompleter


class MergedCompleter(Completer):
    """
    Combined completer for both @ file mentions and / commands.

    Routes completion requests to the appropriate completer based on context.
    """

    def __init__(self, file_completer: FileCompleter, command_completer: CommandCompleter):
        """
        Initialize the merged completer.

        Args:
            file_completer: Completer for @ file mentions
            command_completer: Completer for / commands
        """
        self.file_completer = file_completer
        self.command_completer = command_completer

    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """
        Generate completions based on context.

        Args:
            document: Current prompt document
            complete_event: Completion event

        Yields:
            Completion objects from the appropriate completer
        """
        text_before_cursor = document.text_before_cursor

        # Route to appropriate completer
        if text_before_cursor.startswith('/'):
            # Use command completer for slash commands
            yield from self.command_completer.get_completions(document, complete_event)
        elif '@' in text_before_cursor:
            # Use file completer for @ mentions
            yield from self.file_completer.get_completions(document, complete_event)
