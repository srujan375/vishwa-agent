"""
Code intelligence module - understand code structure and dependencies.

This module provides smart code analysis WITHOUT reading entire files:
- Smart file reading (read only what's needed)
- Dependency tracking (understand file relationships)
- Structure analysis (get file overview without reading all content)

These are the strategies Claude Code uses for large codebases.
"""

from vishwa.code_intelligence.smart_reader import (
    SmartFileReader,
    read_imports,
    get_structure,
    read_symbol
)

from vishwa.code_intelligence.dependencies import (
    DependencyGraph,
    get_dependency_graph,
    analyze_codebase
)

__all__ = [
    'SmartFileReader',
    'read_imports',
    'get_structure',
    'read_symbol',
    'DependencyGraph',
    'get_dependency_graph',
    'analyze_codebase',
]
