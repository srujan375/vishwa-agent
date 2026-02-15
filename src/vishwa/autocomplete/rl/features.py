"""
Feature extraction for the autocomplete contextual bandit.

Extracts categorical features from AutocompleteContext to form a bucket key
for the Thompson Sampling policy.
"""

import re
from vishwa.autocomplete.context_builder import AutocompleteContext


def extract_language(context: AutocompleteContext) -> str:
    """Categorize language into a small set of buckets."""
    lang = context.language.lower()
    if lang in ("python",):
        return "python"
    if lang in ("javascript",):
        return "javascript"
    if lang in ("typescript",):
        return "typescript"
    return "other"


def extract_scope(context: AutocompleteContext) -> str:
    """Determine whether cursor is in a function, class, or top-level scope."""
    if not context.in_function:
        return "top_level"
    # Heuristic: if function_name starts with uppercase, it's likely a class
    if context.function_name and context.function_name[0].isupper():
        return "class"
    return "function"


def extract_file_size(context: AutocompleteContext) -> str:
    """Categorize file size based on total line count."""
    # Count total lines: lines_before + current_line + lines_after
    # This is an approximation since context_builder clips to context_lines
    # But for bucketing purposes it's sufficient
    total_lines = len(context.lines_before) + 1 + len(context.lines_after)
    if total_lines < 100:
        return "small"
    if total_lines <= 500:
        return "medium"
    return "large"


def extract_position(context: AutocompleteContext) -> str:
    """Determine cursor position within current block (start/mid/end)."""
    current_line = context.current_line
    current_indent = len(current_line) - len(current_line.lstrip()) if current_line.strip() else 0

    # Check if at start of block: previous line has lower indent or ends with ':'
    if context.lines_before:
        prev_line = context.lines_before[-1]
        prev_stripped = prev_line.strip()
        if prev_stripped:
            prev_indent = len(prev_line) - len(prev_line.lstrip())
            # Indent just increased (new block)
            if current_indent > prev_indent:
                return "start"
            # Previous line ends with block opener
            if prev_stripped.endswith((':',  '{')) :
                return "start"

    # Check if at end of block: next line has lower indent or is closing brace
    if context.lines_after:
        next_line = context.lines_after[0]
        next_stripped = next_line.strip()
        if next_stripped:
            next_indent = len(next_line) - len(next_line.lstrip())
            if next_indent < current_indent:
                return "end"
            if next_stripped in ('}', ')', ']'):
                return "end"
        elif not next_stripped:
            # Empty next line could indicate end of block
            if len(context.lines_after) > 1:
                after_next = context.lines_after[1].strip()
                if after_next and (len(context.lines_after[1]) - len(context.lines_after[1].lstrip())) < current_indent:
                    return "end"

    return "mid"


def extract_bucket_key(context: AutocompleteContext) -> str:
    """
    Extract a bucket key from the autocomplete context.

    Format: "language:scope:file_size:position"
    Example: "python:function:medium:mid"
    """
    language = extract_language(context)
    scope = extract_scope(context)
    file_size = extract_file_size(context)
    position = extract_position(context)
    return f"{language}:{scope}:{file_size}:{position}"
