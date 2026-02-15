"""
Context-building strategies for autocomplete RL.

Each strategy controls how the LLM prompt is constructed:
lines before/after cursor, imports, function references, and max tokens.
"""

from dataclasses import dataclass
from typing import List


STRATEGY_NAMES = ["minimal", "compact", "standard", "rich", "scope_aware"]


@dataclass(frozen=True)
class Strategy:
    """A discrete context-building strategy for autocomplete prompts."""
    name: str
    lines_before: int       # Number of lines before cursor to include
    lines_after: int        # Number of lines after cursor to include
    include_imports: bool   # Whether to include import statements
    max_imports: int        # Max number of imports to include
    include_functions: bool # Whether to include referenced function signatures
    max_functions: int      # Max number of function signatures to include
    max_tokens: int         # Max tokens for LLM response
    dynamic_scope: bool     # If True, lines_before is dynamic (current function/class scope)
    max_scope_lines: int    # Cap for dynamic scope lines


STRATEGIES = {
    "minimal": Strategy(
        name="minimal",
        lines_before=5,
        lines_after=0,
        include_imports=False,
        max_imports=0,
        include_functions=False,
        max_functions=0,
        max_tokens=60,
        dynamic_scope=False,
        max_scope_lines=0,
    ),
    "compact": Strategy(
        name="compact",
        lines_before=10,
        lines_after=2,
        include_imports=False,
        max_imports=0,
        include_functions=False,
        max_functions=0,
        max_tokens=80,
        dynamic_scope=False,
        max_scope_lines=0,
    ),
    "standard": Strategy(
        name="standard",
        lines_before=15,
        lines_after=2,
        include_imports=True,
        max_imports=10,
        include_functions=True,
        max_functions=5,
        max_tokens=100,
        dynamic_scope=False,
        max_scope_lines=0,
    ),
    "rich": Strategy(
        name="rich",
        lines_before=20,
        lines_after=5,
        include_imports=True,
        max_imports=15,
        include_functions=True,
        max_functions=8,
        max_tokens=120,
        dynamic_scope=False,
        max_scope_lines=0,
    ),
    "scope_aware": Strategy(
        name="scope_aware",
        lines_before=0,  # Ignored when dynamic_scope=True
        lines_after=3,
        include_imports=True,
        max_imports=10,
        include_functions=True,
        max_functions=5,
        max_tokens=100,
        dynamic_scope=True,
        max_scope_lines=30,
    ),
}


def get_strategy(name: str) -> Strategy:
    """Get a strategy by name. Raises KeyError if not found."""
    return STRATEGIES[name]
