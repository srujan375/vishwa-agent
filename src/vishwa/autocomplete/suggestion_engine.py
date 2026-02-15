"""
Suggestion engine for generating autocomplete suggestions using LLMs.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
import re

from vishwa.llm.factory import LLMFactory
from vishwa.llm.base import BaseLLM
from vishwa.autocomplete.context_builder import ContextBuilder, AutocompleteContext
from vishwa.autocomplete.rl.strategies import Strategy, STRATEGIES


@dataclass
class AutocompleteSuggestion:
    """An autocomplete suggestion."""
    text: str
    suggestion_type: str  # 'insertion' or 'edit'
    confidence: float = 1.0


class SuggestionEngine:
    """Generates code autocomplete suggestions using LLMs."""

    # Autocomplete-specific system prompt
    SYSTEM_PROMPT = """You are an expert code autocomplete assistant. Your job is to predict what the developer wants to type next.

CRITICAL RULES:
1. NEVER repeat any code that already exists - only provide NEW code to add
2. Provide ONLY the code to insert at the cursor position - no explanations, no markdown, no code fences
3. The code before <CURSOR> is already written - DO NOT include it in your response
4. If the line is complete, suggest what should come on the NEXT line
5. Match the existing code style and indentation exactly
6. Keep suggestions concise and relevant to the immediate context
7. Use the provided function signatures and imports to make accurate suggestions

WRONG - repeating existing code:
Given: "result = num1 + num2<CURSOR>"
Bad Response: "result = num1 + num2"  # This repeats existing code!
Good Response: ""  # Line is complete, or suggest next line

CORRECT examples:
Given: "def calculate_sum(a, b):\\n    return <CURSOR>"
Response: "a + b"

Given: "result = num1 + num2<CURSOR>" (line is complete)
Response: "" or the next logical line like "print(result)"

Given: "if user.is_authenticated:<CURSOR>"
Response: "\\n    return render(request, 'dashboard.html')"

Given: "    name = <CURSOR>"
Response: "input('Enter name: ')"
"""

    def __init__(self, model: str = "gemma3:4b", context_lines: int = 20):
        """
        Initialize suggestion engine.

        Args:
            model: Model to use for suggestions (e.g., 'gemma3:4b', 'claude-haiku-4-5', 'gpt-4o-mini')
            context_lines: Number of context lines to include
        """
        self.model = model
        self.context_builder = ContextBuilder(context_lines=context_lines)
        self.llm: Optional[BaseLLM] = None
        self._initialize_llm()

    def _initialize_llm(self):
        """Initialize the LLM provider."""
        try:
            self.llm = LLMFactory.create(self.model)
        except Exception as e:
            print(f"Warning: Failed to initialize LLM {self.model}: {e}")
            self.llm = None

    def set_model(self, model: str):
        """
        Change the model being used.

        Args:
            model: New model name
        """
        self.model = model
        self._initialize_llm()

    def generate_suggestion(
        self,
        file_path: str,
        content: str,
        cursor_line: int,
        cursor_char: int
    ) -> Optional[AutocompleteSuggestion]:
        """
        Generate autocomplete suggestion.

        Args:
            file_path: Path to file being edited
            content: Full file content
            cursor_line: Line number (0-indexed)
            cursor_char: Character position (0-indexed)

        Returns:
            AutocompleteSuggestion or None if no suggestion
        """
        if not self.llm:
            return None

        # Build context
        context = self.context_builder.build_context(
            file_path, content, cursor_line, cursor_char
        )

        # Check if we should skip suggestion
        if self._should_skip_suggestion(context):
            return None

        # Format context for LLM
        user_prompt = self._build_user_prompt(context)

        try:
            # Get suggestion from LLM
            response = self.llm.chat(
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                system=self.SYSTEM_PROMPT,
                temperature=0.2,  # Low temperature for more deterministic output
                max_tokens=100,   # Limit response length for speed
            )

            suggestion_text = response.content.strip()

            # Post-process suggestion
            suggestion_text = self._post_process_suggestion(suggestion_text, context)

            if not suggestion_text:
                return None

            return AutocompleteSuggestion(
                text=suggestion_text,
                suggestion_type='insertion',
                confidence=1.0
            )

        except Exception as e:
            print(f"Error generating suggestion: {e}")
            return None

    def generate_suggestion_with_strategy(
        self,
        file_path: str,
        content: str,
        cursor_line: int,
        cursor_char: int,
        strategy: Strategy,
    ) -> Optional[AutocompleteSuggestion]:
        """
        Generate autocomplete suggestion using a specific context strategy.

        Args:
            file_path: Path to file being edited
            content: Full file content
            cursor_line: Line number (0-indexed)
            cursor_char: Character position (0-indexed)
            strategy: Strategy controlling prompt construction

        Returns:
            AutocompleteSuggestion or None if no suggestion
        """
        if not self.llm:
            return None

        context = self.context_builder.build_context(
            file_path, content, cursor_line, cursor_char
        )

        if self._should_skip_suggestion(context):
            return None

        user_prompt = self._build_user_prompt(context, strategy=strategy)

        try:
            response = self.llm.chat(
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                system=self.SYSTEM_PROMPT,
                temperature=0.2,
                max_tokens=strategy.max_tokens,
            )

            suggestion_text = response.content.strip()
            suggestion_text = self._post_process_suggestion(suggestion_text, context)

            if not suggestion_text:
                return None

            return AutocompleteSuggestion(
                text=suggestion_text,
                suggestion_type='insertion',
                confidence=1.0
            )

        except Exception as e:
            print(f"Error generating suggestion: {e}")
            return None

    def _should_skip_suggestion(self, context: AutocompleteContext) -> bool:
        """
        Determine if we should skip generating a suggestion.

        Args:
            context: Autocomplete context

        Returns:
            True if we should skip
        """
        current_line = context.current_line
        cursor_pos = context.cursor_position

        # Skip if cursor is at the start of an empty line
        if cursor_pos == 0 and not current_line.strip():
            return True

        # Skip if we're in the middle of a word
        if cursor_pos < len(current_line):
            char_after = current_line[cursor_pos]
            if char_after.isalnum() or char_after == '_':
                return True

        # Check if cursor is at the end of the line (or only whitespace after)
        remaining_line = current_line[cursor_pos:].strip()
        is_at_line_end = len(remaining_line) == 0

        # If at end of line, allow suggestion for next line completion
        if is_at_line_end and cursor_pos > 0:
            return False

        # Get character before cursor
        if cursor_pos > 0:
            char_before = current_line[cursor_pos - 1]
            # Skip if we just typed an alphanumeric character (wait for space/punctuation)
            # But allow if we're at the end of a line (for next-line suggestions)
            if char_before.isalnum() or char_before == '_':
                # Allow suggestion after certain patterns like "return ", "def ", etc.
                line_up_to_cursor = current_line[:cursor_pos].strip()
                if not any(line_up_to_cursor.endswith(kw) for kw in [
                    'return', 'def', 'class', 'if', 'elif', 'else',
                    'for', 'while', 'import', 'from', 'const', 'let',
                    'var', 'function', 'async', 'await'
                ]):
                    return True

        return False

    def _build_user_prompt(
        self,
        context: AutocompleteContext,
        strategy: Optional[Strategy] = None,
    ) -> str:
        """
        Build user prompt for the LLM.

        Args:
            context: Autocomplete context
            strategy: Optional strategy to control prompt construction.
                      If None, uses the "standard" strategy defaults.

        Returns:
            Formatted prompt string
        """
        # Default to standard strategy parameters when no strategy provided
        if strategy is None:
            strategy = STRATEGIES["standard"]

        prompt_parts = []

        # Add language and file context
        prompt_parts.append(f"Complete the following {context.language} code:")
        prompt_parts.append("")

        # Include imports for context if strategy allows
        if strategy.include_imports and context.imports:
            prompt_parts.append("# Imports:")
            for imp in context.imports[:strategy.max_imports]:
                prompt_parts.append(imp)
            prompt_parts.append("")

        # Include referenced function definitions if strategy allows
        if strategy.include_functions and context.referenced_functions:
            prompt_parts.append("# Available functions in this file:")
            for func in context.referenced_functions[:strategy.max_functions]:
                prompt_parts.append(f"# {func.signature}")
                if func.docstring:
                    prompt_parts.append(f"#   \"\"\"{func.docstring}\"\"\"")
                if func.body_preview:
                    first_line = func.body_preview.split('\n')[0]
                    prompt_parts.append(f"#   {first_line}...")
            prompt_parts.append("")

        # Determine lines_before based on strategy
        if strategy.dynamic_scope:
            lines_before = self._get_scope_lines(context, strategy.max_scope_lines)
        else:
            n = strategy.lines_before
            lines_before = context.lines_before[-n:] if len(context.lines_before) > n else context.lines_before

        for line in lines_before:
            prompt_parts.append(line)

        # Show current line up to cursor
        current_up_to_cursor = context.current_line[:context.cursor_position]
        prompt_parts.append(current_up_to_cursor + "<CURSOR>")

        # Show lines after for context
        n_after = strategy.lines_after
        lines_after = context.lines_after[:n_after]
        if lines_after:
            prompt_parts.append("")
            prompt_parts.append("# Code after cursor (for context):")
            for line in lines_after:
                prompt_parts.append(line)

        prompt_parts.append("")
        prompt_parts.append("Complete the code at <CURSOR>. Provide ONLY the completion text, nothing else.")

        return '\n'.join(prompt_parts)

    def _get_scope_lines(
        self,
        context: AutocompleteContext,
        max_lines: int,
    ) -> list:
        """
        Get lines from the start of the current function/class scope to the cursor.

        For scope_aware strategy: includes from the def/class line to cursor,
        capped at max_lines.
        """
        if not context.in_function or not context.function_name:
            # Not in a function/class — fall back to last max_lines
            return context.lines_before[-max_lines:] if len(context.lines_before) > max_lines else context.lines_before

        # Search backwards for the function/class definition
        func_name = context.function_name
        scope_start_idx = None
        for i in range(len(context.lines_before) - 1, -1, -1):
            line = context.lines_before[i]
            # Match def funcname( or class ClassName
            if re.match(rf'\s*(?:def|class|function|async\s+function)\s+{re.escape(func_name)}\b', line):
                scope_start_idx = i
                break
            # Also match arrow functions: const funcname =
            if re.match(rf'\s*(?:const|let|var)\s+{re.escape(func_name)}\s*=', line):
                scope_start_idx = i
                break

        if scope_start_idx is not None:
            scope_lines = context.lines_before[scope_start_idx:]
            # Cap at max_lines
            if len(scope_lines) > max_lines:
                scope_lines = scope_lines[-max_lines:]
            return scope_lines

        # Couldn't find scope start, fall back
        return context.lines_before[-max_lines:] if len(context.lines_before) > max_lines else context.lines_before

    def _post_process_suggestion(
        self,
        suggestion: str,
        context: AutocompleteContext
    ) -> str:
        """
        Post-process the suggestion from LLM.

        Args:
            suggestion: Raw suggestion from LLM
            context: Autocomplete context

        Returns:
            Cleaned suggestion
        """
        # Remove common markdown artifacts
        suggestion = suggestion.strip()
        suggestion = suggestion.strip('`')

        # Syntax-aware: Check if suggestion should start on a new line
        # This handles cases where cursor is at end of a complete statement
        current_line = context.current_line
        cursor_pos = context.cursor_position
        line_up_to_cursor = current_line[:cursor_pos].rstrip()

        # If the line before cursor looks complete (ends with certain patterns)
        # and the suggestion doesn't start with a newline, prepend one
        if line_up_to_cursor and not suggestion.startswith('\n'):
            # Patterns that indicate a complete statement
            complete_patterns = [
                # Assignments and expressions
                lambda l: l[-1].isalnum() or l[-1] in ')]}',
                # Already ends with colon (block start)
                lambda l: l.endswith(':'),
            ]

            # Check if cursor is truly at the end of meaningful content
            remaining_line = current_line[cursor_pos:].strip()
            is_at_line_end = len(remaining_line) == 0

            if is_at_line_end and any(check(line_up_to_cursor) for check in complete_patterns):
                # The suggestion starts a new statement, prepend newline with proper indentation
                # Detect the current indentation
                current_indent = len(current_line) - len(current_line.lstrip())

                # For Python, check if we need to add indentation (after colon)
                if line_up_to_cursor.endswith(':'):
                    # Increase indent after block start
                    indent_char = '\t' if '\t' in current_line[:current_indent] else ' '
                    indent_size = 4 if indent_char == ' ' else 1
                    new_indent = current_indent + indent_size
                else:
                    # Keep same indentation level
                    new_indent = current_indent

                indent_str = current_line[:current_indent] if current_indent > 0 else ''
                # Use same indent character pattern
                if new_indent > current_indent:
                    indent_str = ' ' * new_indent if ' ' in indent_str or not indent_str else '\t' * (new_indent // 4 + 1)

                suggestion = '\n' + indent_str + suggestion.lstrip()

        # Remove language tags (e.g., ```python)
        if suggestion.startswith('```'):
            lines = suggestion.split('\n')
            if len(lines) > 2:
                suggestion = '\n'.join(lines[1:-1])
            else:
                suggestion = suggestion.replace('```', '').strip()

        # Remove any explanation text after the code
        # (LLM sometimes adds explanation despite instructions)
        lines = suggestion.split('\n')
        code_lines = []
        for line in lines:
            # Stop at explanation markers
            if line.strip().startswith('#') and any(marker in line.lower() for marker in ['explanation', 'note:', 'this ']):
                break
            code_lines.append(line)

        suggestion = '\n'.join(code_lines).rstrip()

        # Don't suggest empty completions
        if not suggestion or suggestion.isspace():
            return ""

        return suggestion

    def generate_streaming_suggestion(
        self,
        file_path: str,
        content: str,
        cursor_line: int,
        cursor_char: int
    ):
        """
        Generate autocomplete suggestion with streaming (for future use).

        Args:
            file_path: Path to file being edited
            content: Full file content
            cursor_line: Line number (0-indexed)
            cursor_char: Character position (0-indexed)

        Yields:
            str: Chunks of suggestion as they arrive
        """
        if not self.llm:
            return

        context = self.context_builder.build_context(
            file_path, content, cursor_line, cursor_char
        )

        if self._should_skip_suggestion(context):
            return

        user_prompt = self._build_user_prompt(context)

        try:
            # Use streaming chat if available
            for chunk in self.llm.chat_stream(
                messages=[{"role": "user", "content": user_prompt}],
                system=self.SYSTEM_PROMPT,
                temperature=0.2,
                max_tokens=200,
            ):
                yield chunk
        except NotImplementedError:
            # Fall back to non-streaming
            suggestion = self.generate_suggestion(
                file_path, content, cursor_line, cursor_char
            )
            if suggestion:
                yield suggestion.text
        except Exception as e:
            print(f"Error in streaming suggestion: {e}")
            return
