"""
Dependency tracking - understand file relationships.

This implements Claude Code's dependency understanding:
- Track imports between files
- Build dependency graph
- Find files that depend on a changed file
- Do it efficiently (don't read entire large files)
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field

from vishwa.code_intelligence.smart_reader import read_imports, get_structure


@dataclass
class FileDependencies:
    """Dependencies for a single file."""
    path: str
    imports: List[str]  # What this file imports
    imported_by: List[str] = field(default_factory=list)  # Files that import this
    symbols_defined: List[str] = field(default_factory=list)  # Functions/classes defined here
    symbols_used: List[str] = field(default_factory=list)  # External symbols used


class DependencyGraph:
    """
    Track file dependencies across the codebase.

    This is what Claude Code uses internally (inferred):
    - Parse imports from files (using smart reader - just top of file)
    - Build graph of dependencies
    - Cache it for fast lookups
    - Update when files change

    Usage:
        graph = DependencyGraph()
        graph.analyze_directory("src/")

        # Find what imports auth.py
        dependents = graph.get_dependents("src/auth.py")
        # → ["src/views.py", "src/middleware.py"]

        # Find what auth.py imports
        dependencies = graph.get_dependencies("src/auth.py")
        # → ["src/models.py", "src/utils.py"]

        # Get impact radius
        affected = graph.get_impact_radius("src/models.py")
        # → Everything that transitively depends on models.py
    """

    def __init__(self):
        self.graph: Dict[str, FileDependencies] = {}
        self.project_root: Optional[str] = None

    def analyze_directory(self, root_path: str, extensions: Optional[List[str]] = None):
        """
        Analyze a directory and build dependency graph.

        Uses SMART reading - only reads imports (top of files),
        not entire file contents.

        Args:
            root_path: Root directory to analyze
            extensions: File extensions to analyze (default: .py, .js, .ts)
        """
        self.project_root = root_path

        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.jsx', '.tsx']

        # Find all source files
        files = []
        for ext in extensions:
            pattern = f"**/*{ext}"
            files.extend(Path(root_path).glob(pattern))

        # Analyze each file (smart - only read imports!)
        for file_path in files:
            self._analyze_file(str(file_path))

        # Build reverse dependencies (imported_by)
        self._build_reverse_dependencies()

    def _analyze_file(self, path: str):
        """
        Analyze a single file.

        Key: Uses smart_reader to read ONLY imports,
        not the entire file content!
        """
        # Get file structure (reads only imports + greps for symbols)
        structure = get_structure(path)

        # Parse imports to get actual file paths
        import_files = self._resolve_imports(path, structure.imports)

        # Store in graph
        self.graph[path] = FileDependencies(
            path=path,
            imports=import_files,
            symbols_defined=[name for name, _ in structure.classes + structure.functions]
        )

    def _resolve_imports(self, source_file: str, import_statements: List[str]) -> List[str]:
        """
        Resolve import statements to actual file paths.

        Example:
            "from models import User"
            → Resolves to "src/models.py"

            "from .utils import helper"
            → Resolves to "src/utils.py" (relative to source_file)
        """
        resolved = []
        source_dir = Path(source_file).parent

        for stmt in import_statements:
            # Parse the import statement
            imported_file = self._parse_import_statement(stmt, source_file)
            if imported_file:
                resolved.append(imported_file)

        return resolved

    def _parse_import_statement(self, stmt: str, source_file: str) -> Optional[str]:
        """
        Parse an import statement to get the file path.

        Python examples:
            "from models import User" → "models.py"
            "from .utils import helper" → "./utils.py"
            "import auth" → "auth.py"

        JS/TS examples:
            "import { User } from './models'" → "./models.ts"
            "const utils = require('./utils')" → "./utils.js"
        """
        source_dir = Path(source_file).parent
        language = Path(source_file).suffix

        if language == '.py':
            # Python import
            # from X import Y → X
            # import X → X
            match = re.match(r'from\s+([\w\.]+)\s+import', stmt)
            if match:
                module = match.group(1)
            else:
                match = re.match(r'import\s+([\w\.]+)', stmt)
                if match:
                    module = match.group(1)
                else:
                    return None

            # Resolve module to file path
            if module.startswith('.'):
                # Relative import
                relative_path = module.replace('.', '/')
                file_path = source_dir / f"{relative_path}.py"
            else:
                # Absolute import - try to find in project
                if self.project_root:
                    file_path = Path(self.project_root) / f"{module.replace('.', '/')}.py"
                else:
                    return None

            if file_path.exists():
                return str(file_path)

        elif language in ['.js', '.ts', '.jsx', '.tsx']:
            # JavaScript/TypeScript import
            # import X from 'Y' → Y
            # const X = require('Y') → Y
            match = re.search(r'[\'"]([^\'"]+)[\'"]', stmt)
            if match:
                module_path = match.group(1)

                # Resolve relative paths
                if module_path.startswith('.'):
                    file_path = (source_dir / module_path).resolve()

                    # Try with extensions
                    for ext in ['.js', '.ts', '.jsx', '.tsx']:
                        candidate = file_path.with_suffix(ext)
                        if candidate.exists():
                            return str(candidate)

                    # Try as directory with index file
                    for ext in ['.js', '.ts']:
                        candidate = file_path / f"index{ext}"
                        if candidate.exists():
                            return str(candidate)

        return None

    def _build_reverse_dependencies(self):
        """Build the 'imported_by' relationships."""
        for path, deps in self.graph.items():
            for imported_file in deps.imports:
                if imported_file in self.graph:
                    self.graph[imported_file].imported_by.append(path)

    def get_dependencies(self, file_path: str) -> List[str]:
        """
        Get files that this file imports (direct dependencies).

        Args:
            file_path: Path to file

        Returns:
            List of file paths this file depends on
        """
        if file_path in self.graph:
            return self.graph[file_path].imports
        return []

    def get_dependents(self, file_path: str) -> List[str]:
        """
        Get files that import this file (direct dependents).

        Args:
            file_path: Path to file

        Returns:
            List of file paths that depend on this file
        """
        if file_path in self.graph:
            return self.graph[file_path].imported_by
        return []

    def get_impact_radius(self, file_path: str, max_depth: int = 10) -> Set[str]:
        """
        Get all files that transitively depend on this file.

        This is KEY for understanding change impact:
        "If I change models.py, what else might break?"

        Args:
            file_path: Path to file that's changing
            max_depth: Maximum dependency depth to traverse

        Returns:
            Set of all files that might be affected
        """
        affected = set()
        queue = [(file_path, 0)]
        visited = set()

        while queue:
            current, depth = queue.pop(0)

            if current in visited or depth > max_depth:
                continue

            visited.add(current)
            affected.add(current)

            # Add files that import this one
            dependents = self.get_dependents(current)
            for dependent in dependents:
                if dependent not in visited:
                    queue.append((dependent, depth + 1))

        # Remove the original file from impact radius
        affected.discard(file_path)

        return affected

    def get_import_chain(self, from_file: str, to_file: str) -> Optional[List[str]]:
        """
        Find import chain from one file to another.

        Example:
            a.py imports b.py imports c.py
            get_import_chain("a.py", "c.py")
            → ["a.py", "b.py", "c.py"]

        Args:
            from_file: Starting file
            to_file: Target file

        Returns:
            List representing the import chain, or None if no chain exists
        """
        # BFS to find shortest path
        queue = [(from_file, [from_file])]
        visited = set()

        while queue:
            current, path = queue.pop(0)

            if current == to_file:
                return path

            if current in visited:
                continue

            visited.add(current)

            # Explore dependencies
            for dep in self.get_dependencies(current):
                if dep not in visited:
                    queue.append((dep, path + [dep]))

        return None

    def get_summary(self) -> str:
        """Get summary of dependency graph."""
        total_files = len(self.graph)
        total_dependencies = sum(len(deps.imports) for deps in self.graph.values())

        # Find most imported files
        import_counts = {
            path: len(deps.imported_by)
            for path, deps in self.graph.items()
        }
        most_imported = sorted(import_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        summary = f"""Dependency Graph Summary:
- Total files: {total_files}
- Total dependencies: {total_dependencies}
- Avg dependencies per file: {total_dependencies / max(total_files, 1):.1f}

Most imported files (hub files):"""

        for path, count in most_imported:
            file_name = Path(path).name
            summary += f"\n  - {file_name}: imported by {count} files"

        return summary


# Global instance (singleton pattern like logger)
_dependency_graph = DependencyGraph()


def get_dependency_graph() -> DependencyGraph:
    """Get the global dependency graph instance."""
    return _dependency_graph


def analyze_codebase(root_path: str):
    """Analyze codebase and build dependency graph (convenience function)."""
    graph = get_dependency_graph()
    graph.analyze_directory(root_path)
    return graph
