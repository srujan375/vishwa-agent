"""
Smart file reading strategies - handles large files intelligently.

This module provides strategies for reading files efficiently:
1. Import-only reading (just the top of the file)
2. Symbol-targeted reading (read specific functions/classes)
3. Summary reading (get file structure without full content)

These are the exact strategies Claude Code uses for large files.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class FileStructure:
    """Summary of file structure without full content."""
    path: str
    total_lines: int
    imports: List[str]
    classes: List[Tuple[str, int]]  # (class_name, line_number)
    functions: List[Tuple[str, int]]  # (function_name, line_number)
    language: str


class SmartFileReader:
    """
    Intelligent file reading that mimics Claude Code's strategies.

    Instead of reading huge files entirely, use targeted strategies:
    - Read just imports (top of file)
    - Search for specific symbols
    - Build structure summary
    """

    def __init__(self):
        self.cache = {}  # Cache file structures

    def read_imports_only(self, path: str, max_lines: int = 100) -> List[str]:
        """
        Read just the imports from a file.

        This is what Claude Code does - don't read the whole file,
        just get the dependencies from the top.

        Args:
            path: File path
            max_lines: How many lines to scan (default: 100)

        Returns:
            List of import statements
        """
        language = self._detect_language(path)

        with open(path, 'r', encoding='utf-8') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line)

        imports = []

        if language == "python":
            for line in lines:
                line = line.strip()
                if line.startswith('import ') or line.startswith('from '):
                    imports.append(line)
                elif line and not line.startswith('#'):
                    # Once we hit non-import code, we're done with imports
                    if imports and not line.startswith('import') and not line.startswith('from'):
                        # But continue if we see more imports
                        if 'import' not in line:
                            pass

        elif language in ["javascript", "typescript"]:
            for line in lines:
                line = line.strip()
                if line.startswith('import ') or line.startswith('from '):
                    imports.append(line)
                elif 'require(' in line:
                    imports.append(line)

        return imports

    def get_file_structure(self, path: str) -> FileStructure:
        """
        Get file structure summary WITHOUT reading entire file.

        This is Claude Code's strategy for understanding large files:
        1. Count total lines (fast)
        2. Read imports from top
        3. Grep for class/function definitions
        4. Return summary

        Args:
            path: File path

        Returns:
            FileStructure with summary info
        """
        # Check cache
        if path in self.cache:
            return self.cache[path]

        language = self._detect_language(path)

        # Count total lines (fast - don't read into memory)
        total_lines = self._count_lines(path)

        # Get imports (read just top of file)
        imports = self.read_imports_only(path)

        # Find classes and functions (grep, don't read whole file)
        classes = self._find_classes(path, language)
        functions = self._find_functions(path, language)

        structure = FileStructure(
            path=path,
            total_lines=total_lines,
            imports=imports,
            classes=classes,
            functions=functions,
            language=language
        )

        # Cache it
        self.cache[path] = structure

        return structure

    def read_symbol_section(self, path: str, symbol_name: str,
                           symbol_type: str = "function") -> Tuple[int, int, str]:
        """
        Read just the section containing a specific symbol.

        Claude Code strategy: Instead of reading whole file,
        find the symbol and read just that section.

        Args:
            path: File path
            symbol_name: Name of function/class
            symbol_type: "function" or "class"

        Returns:
            (start_line, end_line, content)
        """
        structure = self.get_file_structure(path)

        # Find the symbol
        if symbol_type == "class":
            symbols = structure.classes
        else:
            symbols = structure.functions

        for name, line_num in symbols:
            if name == symbol_name:
                # Read from that line + some context
                # Estimate: functions are usually < 100 lines
                start_line = line_num
                end_line = min(line_num + 100, structure.total_lines)

                content = self._read_lines(path, start_line, end_line)
                return (start_line, end_line, content)

        raise ValueError(f"Symbol {symbol_name} not found in {path}")

    def _detect_language(self, path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(path).suffix.lower()

        mapping = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
        }

        return mapping.get(ext, 'unknown')

    def _count_lines(self, path: str) -> int:
        """Count lines in file without reading into memory."""
        with open(path, 'rb') as f:
            return sum(1 for _ in f)

    def _find_classes(self, path: str, language: str) -> List[Tuple[str, int]]:
        """Find all class definitions and their line numbers."""
        classes = []

        if language == "python":
            pattern = r'^class\s+(\w+)'
        elif language in ["javascript", "typescript"]:
            pattern = r'class\s+(\w+)'
        elif language == "java":
            pattern = r'class\s+(\w+)'
        else:
            return classes

        with open(path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                match = re.match(pattern, line.strip())
                if match:
                    class_name = match.group(1)
                    classes.append((class_name, line_num))

        return classes

    def _find_functions(self, path: str, language: str) -> List[Tuple[str, int]]:
        """Find all function definitions and their line numbers."""
        functions = []

        if language == "python":
            pattern = r'^def\s+(\w+)'
        elif language in ["javascript", "typescript"]:
            pattern = r'function\s+(\w+)|const\s+(\w+)\s*=\s*\([^)]*\)\s*=>'
        else:
            return functions

        with open(path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                match = re.match(pattern, line.strip())
                if match:
                    func_name = match.group(1) or match.group(2)
                    if func_name:
                        functions.append((func_name, line_num))

        return functions

    def _read_lines(self, path: str, start_line: int, end_line: int) -> str:
        """Read specific line range from file."""
        with open(path, 'r', encoding='utf-8') as f:
            lines = []
            for i, line in enumerate(f, 1):
                if i < start_line:
                    continue
                if i > end_line:
                    break
                lines.append(line)

        return ''.join(lines)


# Global instance
_smart_reader = SmartFileReader()


# Convenience functions
def read_imports(path: str) -> List[str]:
    """Get just the imports from a file (fast)."""
    return _smart_reader.read_imports_only(path)


def get_structure(path: str) -> FileStructure:
    """Get file structure without reading entire file."""
    return _smart_reader.get_file_structure(path)


def read_symbol(path: str, symbol_name: str, symbol_type: str = "function") -> str:
    """Read just a specific function/class from a file."""
    _, _, content = _smart_reader.read_symbol_section(path, symbol_name, symbol_type)
    return content
