"""
Context builder for autocomplete suggestions.

Extracts relevant context from the current file and cursor position.
"""

from typing import List, Optional
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class AutocompleteContext:
    """Context for autocomplete suggestion."""
    file_path: str
    language: str
    current_line: str
    lines_before: List[str]
    lines_after: List[str]
    cursor_position: int  # Character position in current line
    in_function: bool
    function_name: Optional[str]
    indent_level: int


class ContextBuilder:
    """Builds context for autocomplete from file content and cursor position."""

    # Language detection patterns
    LANGUAGE_PATTERNS = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.jsx': 'javascript',
        '.java': 'java',
        '.go': 'go',
        '.rs': 'rust',
        '.cpp': 'cpp',
        '.c': 'c',
        '.h': 'c',
        '.hpp': 'cpp',
        '.rb': 'ruby',
        '.php': 'php',
    }

    def __init__(self, context_lines: int = 20):
        """
        Initialize context builder.

        Args:
            context_lines: Number of lines before/after cursor to include
        """
        self.context_lines = context_lines

    def build_context(
        self,
        file_path: str,
        content: str,
        cursor_line: int,
        cursor_char: int
    ) -> AutocompleteContext:
        """
        Build autocomplete context from file and cursor position.

        Args:
            file_path: Path to the file being edited
            content: Full content of the file
            cursor_line: Line number (0-indexed)
            cursor_char: Character position in line (0-indexed)

        Returns:
            AutocompleteContext with relevant information
        """
        lines = content.split('\n')

        # Ensure cursor is within bounds
        if cursor_line >= len(lines):
            cursor_line = len(lines) - 1

        current_line = lines[cursor_line] if cursor_line < len(lines) else ''

        # Get lines before and after cursor
        start_line = max(0, cursor_line - self.context_lines)
        end_line = min(len(lines), cursor_line + self.context_lines + 1)

        lines_before = lines[start_line:cursor_line]
        lines_after = lines[cursor_line + 1:end_line]

        # Detect language
        language = self._detect_language(file_path)

        # Detect if we're in a function and get function name
        in_function, function_name = self._detect_function_context(
            lines_before, language
        )

        # Get indent level
        indent_level = self._get_indent_level(current_line)

        return AutocompleteContext(
            file_path=file_path,
            language=language,
            current_line=current_line,
            lines_before=lines_before,
            lines_after=lines_after,
            cursor_position=cursor_char,
            in_function=in_function,
            function_name=function_name,
            indent_level=indent_level
        )

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        suffix = Path(file_path).suffix.lower()
        return self.LANGUAGE_PATTERNS.get(suffix, 'unknown')

    def _detect_function_context(
        self,
        lines_before: List[str],
        language: str
    ) -> tuple[bool, Optional[str]]:
        """
        Detect if cursor is inside a function and get function name.

        Returns:
            (in_function, function_name)
        """
        if language == 'python':
            return self._detect_python_function(lines_before)
        elif language in ['javascript', 'typescript']:
            return self._detect_js_function(lines_before)
        # Add more languages as needed
        return False, None

    def _detect_python_function(
        self,
        lines_before: List[str]
    ) -> tuple[bool, Optional[str]]:
        """Detect Python function context."""
        # Look backwards for def or class
        for line in reversed(lines_before):
            # Check for function definition
            func_match = re.match(r'\s*def\s+(\w+)\s*\(', line)
            if func_match:
                return True, func_match.group(1)

            # Check for class (also counts as context)
            class_match = re.match(r'\s*class\s+(\w+)', line)
            if class_match:
                return True, class_match.group(1)

        return False, None

    def _detect_js_function(
        self,
        lines_before: List[str]
    ) -> tuple[bool, Optional[str]]:
        """Detect JavaScript/TypeScript function context."""
        for line in reversed(lines_before):
            # Function declaration: function foo()
            func_match = re.match(r'\s*function\s+(\w+)\s*\(', line)
            if func_match:
                return True, func_match.group(1)

            # Arrow function: const foo = () =>
            arrow_match = re.match(r'\s*(?:const|let|var)\s+(\w+)\s*=\s*\(.*\)\s*=>', line)
            if arrow_match:
                return True, arrow_match.group(1)

            # Method: foo() {
            method_match = re.match(r'\s*(\w+)\s*\([^)]*\)\s*\{', line)
            if method_match:
                return True, method_match.group(1)

        return False, None

    def _get_indent_level(self, line: str) -> int:
        """Get indentation level of a line."""
        indent = len(line) - len(line.lstrip())
        # Assume 4 spaces per indent level
        return indent // 4

    def format_context_for_llm(self, context: AutocompleteContext) -> str:
        """
        Format context into a prompt for the LLM.

        Args:
            context: AutocompleteContext to format

        Returns:
            Formatted string for LLM prompt
        """
        # Build the prompt with context
        prompt_parts = []

        prompt_parts.append(f"Language: {context.language}")
        prompt_parts.append(f"File: {Path(context.file_path).name}")

        if context.in_function and context.function_name:
            prompt_parts.append(f"Current function: {context.function_name}")

        prompt_parts.append("\nCode before cursor:")
        # Show last 10 lines before cursor for context
        relevant_before = context.lines_before[-10:] if len(context.lines_before) > 10 else context.lines_before
        for line in relevant_before:
            prompt_parts.append(line)

        # Show current line up to cursor
        current_up_to_cursor = context.current_line[:context.cursor_position]
        prompt_parts.append(current_up_to_cursor + "<CURSOR>")

        # Show a few lines after for context
        prompt_parts.append("\nCode after cursor:")
        relevant_after = context.lines_after[:3]
        for line in relevant_after:
            prompt_parts.append(line)

        return '\n'.join(prompt_parts)
