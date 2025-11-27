"""
Context builder for autocomplete suggestions.

Extracts relevant context from the current file and cursor position.
"""

from typing import List, Optional
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class FunctionInfo:
    """Information about a function definition."""
    name: str
    signature: str  # Full signature including parameters
    docstring: Optional[str]
    body_preview: str  # First few lines of the body


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
    imports: List[str]  # Import statements from the file
    referenced_functions: List[FunctionInfo]  # Functions called within current scope


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

        # Extract imports from the file
        imports = self._extract_imports(lines, language)

        # Find function calls in the current scope (lines before cursor + current line)
        scope_lines = lines_before + [current_line[:cursor_char]]
        called_function_names = self._extract_function_calls(scope_lines, language)

        # Find definitions of called functions in the same file
        referenced_functions = self._find_function_definitions(
            lines, called_function_names, language
        )

        return AutocompleteContext(
            file_path=file_path,
            language=language,
            current_line=current_line,
            lines_before=lines_before,
            lines_after=lines_after,
            cursor_position=cursor_char,
            in_function=in_function,
            function_name=function_name,
            indent_level=indent_level,
            imports=imports,
            referenced_functions=referenced_functions
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

    def _extract_imports(self, lines: List[str], language: str) -> List[str]:
        """Extract import statements from the file."""
        imports = []
        for line in lines:
            stripped = line.strip()
            if language == 'python':
                if stripped.startswith('import ') or stripped.startswith('from '):
                    imports.append(stripped)
            elif language in ['javascript', 'typescript']:
                if stripped.startswith('import ') or stripped.startswith('const ') and ' require(' in stripped:
                    imports.append(stripped)
        return imports

    def _extract_function_calls(self, lines: List[str], language: str) -> List[str]:
        """
        Extract function names that are called in the given lines.

        Args:
            lines: Lines of code to analyze
            language: Programming language

        Returns:
            List of function names being called
        """
        function_calls = set()

        if language == 'python':
            # Match function calls: func_name( or self.method_name(
            pattern = r'(?<!def\s)(?<!class\s)\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
            for line in lines:
                # Skip function definitions
                if line.strip().startswith('def ') or line.strip().startswith('class '):
                    continue
                matches = re.findall(pattern, line)
                for match in matches:
                    # Exclude built-in functions and common keywords
                    builtins = {'print', 'len', 'range', 'str', 'int', 'float', 'list',
                               'dict', 'set', 'tuple', 'bool', 'type', 'isinstance',
                               'hasattr', 'getattr', 'setattr', 'open', 'input', 'super',
                               'zip', 'map', 'filter', 'sorted', 'reversed', 'enumerate',
                               'min', 'max', 'sum', 'abs', 'round', 'any', 'all', 'if', 'for', 'while'}
                    if match not in builtins:
                        function_calls.add(match)

        elif language in ['javascript', 'typescript']:
            # Match function calls
            pattern = r'(?<!function\s)\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\('
            for line in lines:
                if line.strip().startswith('function '):
                    continue
                matches = re.findall(pattern, line)
                for match in matches:
                    builtins = {'console', 'if', 'for', 'while', 'switch', 'catch',
                               'parseInt', 'parseFloat', 'String', 'Number', 'Boolean',
                               'Array', 'Object', 'Promise', 'setTimeout', 'setInterval'}
                    if match not in builtins:
                        function_calls.add(match)

        return list(function_calls)

    def _find_function_definitions(
        self,
        all_lines: List[str],
        function_names: List[str],
        language: str
    ) -> List[FunctionInfo]:
        """
        Find definitions of the specified functions in the file.

        Args:
            all_lines: All lines in the file
            function_names: Names of functions to find
            language: Programming language

        Returns:
            List of FunctionInfo for found functions
        """
        functions = []

        if language == 'python':
            functions = self._find_python_functions(all_lines, function_names)
        elif language in ['javascript', 'typescript']:
            functions = self._find_js_functions(all_lines, function_names)

        return functions

    def _find_python_functions(
        self,
        all_lines: List[str],
        function_names: List[str]
    ) -> List[FunctionInfo]:
        """Find Python function definitions."""
        functions = []
        i = 0

        while i < len(all_lines):
            line = all_lines[i]

            # Check for function definition
            func_match = re.match(r'^(\s*)def\s+(\w+)\s*\(([^)]*)\)([^:]*):(.*)$', line)
            if func_match:
                indent, name, params, return_hint, rest = func_match.groups()

                if name in function_names:
                    # Build signature
                    signature = f"def {name}({params}){return_hint}"

                    # Look for docstring
                    docstring = None
                    body_lines = []
                    j = i + 1
                    base_indent = len(indent)

                    while j < len(all_lines):
                        next_line = all_lines[j]
                        next_stripped = next_line.strip()

                        # Check if we're still in the function body
                        if next_stripped and not next_line.startswith(' ' * (base_indent + 1)) and not next_line.startswith('\t' * (base_indent // 4 + 1)):
                            if not next_stripped.startswith('#'):  # Not a comment
                                break

                        # Check for docstring (first non-empty line)
                        if docstring is None and next_stripped:
                            if next_stripped.startswith('"""') or next_stripped.startswith("'''"):
                                quote = next_stripped[:3]
                                if next_stripped.count(quote) >= 2:
                                    # Single line docstring
                                    docstring = next_stripped[3:-3].strip()
                                else:
                                    # Multi-line docstring
                                    doc_parts = [next_stripped[3:]]
                                    j += 1
                                    while j < len(all_lines):
                                        doc_line = all_lines[j]
                                        if quote in doc_line:
                                            doc_parts.append(doc_line.split(quote)[0])
                                            break
                                        doc_parts.append(doc_line.strip())
                                        j += 1
                                    docstring = ' '.join(doc_parts).strip()
                            else:
                                # No docstring, this is body
                                body_lines.append(next_stripped)
                        elif len(body_lines) < 3 and next_stripped:
                            body_lines.append(next_stripped)

                        j += 1
                        if len(body_lines) >= 3:
                            break

                    functions.append(FunctionInfo(
                        name=name,
                        signature=signature,
                        docstring=docstring,
                        body_preview='\n'.join(body_lines[:3])
                    ))
            i += 1

        return functions

    def _find_js_functions(
        self,
        all_lines: List[str],
        function_names: List[str]
    ) -> List[FunctionInfo]:
        """Find JavaScript/TypeScript function definitions."""
        functions = []

        for i, line in enumerate(all_lines):
            # Function declaration: function foo(params)
            func_match = re.match(r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)', line)
            if func_match:
                name, params = func_match.groups()
                if name in function_names:
                    signature = f"function {name}({params})"
                    body_preview = self._get_body_preview(all_lines, i + 1, 3)
                    functions.append(FunctionInfo(
                        name=name,
                        signature=signature,
                        docstring=self._find_jsdoc(all_lines, i),
                        body_preview=body_preview
                    ))
                continue

            # Arrow function: const foo = (params) =>
            arrow_match = re.match(r'^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*\w+)?\s*=>', line)
            if arrow_match:
                name, params = arrow_match.groups()
                if name in function_names:
                    signature = f"const {name} = ({params}) =>"
                    body_preview = self._get_body_preview(all_lines, i + 1, 3)
                    functions.append(FunctionInfo(
                        name=name,
                        signature=signature,
                        docstring=self._find_jsdoc(all_lines, i),
                        body_preview=body_preview
                    ))

        return functions

    def _get_body_preview(self, lines: List[str], start: int, count: int) -> str:
        """Get a preview of function body."""
        body_lines = []
        for j in range(start, min(start + count + 5, len(lines))):
            stripped = lines[j].strip()
            if stripped and not stripped.startswith('//') and not stripped.startswith('*'):
                body_lines.append(stripped)
                if len(body_lines) >= count:
                    break
        return '\n'.join(body_lines)

    def _find_jsdoc(self, lines: List[str], func_line: int) -> Optional[str]:
        """Find JSDoc comment above a function."""
        if func_line == 0:
            return None

        # Look for */ ending JSDoc
        prev_line = lines[func_line - 1].strip()
        if not prev_line.endswith('*/'):
            return None

        # Find start of JSDoc
        doc_lines = []
        for i in range(func_line - 1, -1, -1):
            line = lines[i].strip()
            doc_lines.insert(0, line)
            if line.startswith('/**'):
                break

        # Extract description from JSDoc
        description = []
        for line in doc_lines:
            line = line.strip('/* \t')
            if line.startswith('@'):
                break
            if line:
                description.append(line)

        return ' '.join(description) if description else None

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
