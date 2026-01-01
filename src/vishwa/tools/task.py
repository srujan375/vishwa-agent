"""
Task delegation tool - launches sub-agents for complex multi-step operations.

Based on Claude Code's Task tool specification.
Implements Explore and Plan agents that autonomously handle multi-round searches.
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import uuid
from datetime import datetime

from vishwa.tools.base import Tool, ToolResult
from vishwa.utils.logger import logger
from vishwa.cli.ui import (
    print_subagent_start,
    print_subagent_complete,
    create_subagent_spinner,
)


class SubAgentStorage:
    """Store and retrieve sub-agent detailed findings to minimize context bloat."""

    def __init__(self, storage_dir: str = "~/.vishwa/subagents"):
        self.storage_dir = Path(storage_dir).expanduser()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def store(self, data: Dict[str, Any]) -> str:
        """Store full details, return unique key."""
        # Generate unique key: {subagent_type}-{timestamp}-{uuid}
        subagent_type = data.get("subagent_type", "unknown")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        key = f"{subagent_type}-{timestamp}-{uuid.uuid4().hex[:8]}"
        filepath = self.storage_dir / f"{key}.json"
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return key

    def retrieve(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve full details by key."""
        filepath = self.storage_dir / f"{key}.json"
        if filepath.exists():
            with open(filepath, 'r') as f:
                return json.load(f)
        return None

    def list_recent(self, subagent_type: Optional[str] = None, limit: int = 10) -> List[str]:
        """List recent stored keys."""
        keys = []
        for f in sorted(self.storage_dir.glob("*.json"), reverse=True):
            key = f.stem
            if subagent_type is None or key.startswith(subagent_type):
                keys.append(key)
                if len(keys) >= limit:
                    break
        return keys


class TaskTool(Tool):
    """
    Launch specialized sub-agents for autonomous task execution.

    Prevents context bloat by running searches in isolated agents
    that return only summaries instead of full intermediate results.

    This is the #1 accuracy improvement from Claude Code - using
    multi-round autonomous search instead of single grep/glob calls.
    """

    def __init__(self, llm, tool_registry, storage_dir: str = "~/.vishwa/subagents", context_store=None):
        """
        Initialize Task tool.

        Args:
            llm: LLM instance to use for sub-agents
            tool_registry: Main tool registry (to get tools for sub-agents)
            storage_dir: Directory for storing detailed sub-agent findings
            context_store: Optional ContextStore for sharing context with sub-agents
        """
        self.llm = llm
        self.tool_registry = tool_registry
        self.storage = SubAgentStorage(storage_dir)
        self.context_store = context_store

    @property
    def name(self) -> str:
        return "task"

    @property
    def templates(self) -> Dict[str, str]:
        """Pre-built prompt templates for common tasks.

        Usage: templates["template_name"].format(key=value)
        """
        return {
            "analyze_tests": """Find all tests for {module}. Identify:
1. Testing framework and tools used
2. Test patterns and conventions
3. Coverage gaps in {module}
4. Files that need tests

Return structured findings with file references.""",

            "review_code": """Review {file} for code smells:
1. Long functions (>50 lines)
2. Duplicate code patterns
3. Magic numbers/strings
4. Complex conditionals
5. God modules/classes

Return findings with file:line references and severity levels.""",

            "document_api": """Generate API documentation for {file}:
1. All functions/classes with signatures
2. Parameters and return types
3. Purpose and usage examples
4. Dependencies and related code

Return structured output.""",

            "plan_feature": """Create implementation plan for {feature}:
1. Find related existing code
2. Identify integration points
3. List files to modify
4. Steps to implement
5. Testing approach

Return structured plan with file references.""",

            "find_pattern": """Find all occurrences of {pattern} in the codebase:
1. Where it's defined
2. Where it's used
3. Related patterns
4. Integration points

Return findings with file:line references.""",

            "analyze_architecture": """Analyze the architecture for {component}:
1. Main files and their responsibilities
2. Data flow and dependencies
3. Interface points
4. Patterns used

Return structured summary.""",
        }

    @property
    def description(self) -> str:
        return """Launch a new agent to handle complex, multi-step tasks autonomously.

## When to Delegate

Multi-step tasks that require iteration should NOT be done manually - delegate to a sub-agent.

| Task Type | Sub-agent | Trigger Keywords |
|-----------|-----------|------------------|
| Test analysis | Test | "test", "coverage", "fixtures" |
| Code review | Refactor | "refactor", "code smells", "review" |
| Docs generation | Documentation | "document", "docs", "comments" |
| Planning | Plan | "plan", "implement", "approach" |
| Exploration | Explore | "find", "where", "how does" |

## Available Sub-agents

- Explore: Fast agent specialized for exploring codebases. Use this when you need to quickly find files by patterns (eg. "src/components/**/*.tsx"), search code for keywords (eg. "API endpoints"), or answer questions about the codebase (eg. "how do API endpoints work?"). When calling this agent, specify the desired thoroughness level: "quick" for basic searches, "medium" for moderate exploration, or "very thorough" for comprehensive analysis across multiple locations and naming conventions. (Tools: grep, glob, read_file, goto_definition, find_references, hover_info)
- Plan: Agent for planning implementations
- Test: Agent specialized for writing and understanding tests
- Refactor: Agent for code improvement and restructuring
- Documentation: Agent for generating documentation
- CodeReview: Agent for comprehensive code review with severity levels. Identifies CRITICAL issues (SOLID violations, security, bugs) and MEDIUM issues (code smells, missing error handling). (Tools: read_file, grep, glob, goto_definition, find_references)

## Pre-built Templates

Use templates to make delegation easier:
- analyze_tests, review_code, document_api, plan_feature, find_pattern, analyze_architecture

Example: task(subagent_type="Test", prompt=templates["analyze_tests"].format(module="auth"), description="Analyze auth tests")

## Output Format

Sub-agents return structured summaries. Details are stored and retrievable via full_details_key in metadata.
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "subagent_type": {
                    "type": "string",
                    "enum": ["Explore", "Plan", "Test", "Refactor", "Documentation", "CodeReview"],
                    "description": "The type of specialized agent to use for this task",
                },
                "prompt": {
                    "type": "string",
                    "description": "The detailed task for the agent to perform autonomously. Include what to search for and what to return.",
                },
                "description": {
                    "type": "string",
                    "description": "A short (3-5 word) description of the task for logging",
                },
                "thoroughness": {
                    "type": "string",
                    "enum": ["quick", "medium", "very thorough"],
                    "description": "How thorough the exploration should be (default: medium)",
                },
            },
            "required": ["subagent_type", "prompt", "description"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute a task by launching a specialized sub-agent.

        Args:
            subagent_type: Type of agent ("Explore", "Plan", "Test", "Refactor", or "Documentation")
            prompt: Detailed task description
            description: Short description for logging
            thoroughness: "quick", "medium", or "very thorough"

        Returns:
            ToolResult with agent's final summary
        """
        self.validate_params(**kwargs)

        subagent_type = kwargs["subagent_type"]
        task_prompt = kwargs["prompt"]
        description = kwargs["description"]
        thoroughness = kwargs.get("thoroughness", "medium")

        # Log task launch (using tool_start pattern from existing code)
        logger.tool_start("task", {"subagent_type": subagent_type, "description": description})

        # Configure agent based on type
        if subagent_type == "Explore":
            system_prompt = self._build_explore_prompt(task_prompt, thoroughness)
            tools = ["grep", "glob", "read_file", "goto_definition", "find_references", "hover_info"]
            max_iterations = self._get_iterations_for_thoroughness(thoroughness)

        elif subagent_type == "Plan":
            system_prompt = self._build_plan_prompt(task_prompt, thoroughness)
            tools = ["grep", "glob", "read_file"]
            max_iterations = 10

        elif subagent_type == "Test":
            system_prompt = self._build_test_prompt(task_prompt, thoroughness)
            tools = ["grep", "glob", "read_file"]
            max_iterations = 10

        elif subagent_type == "Refactor":
            system_prompt = self._build_refactor_prompt(task_prompt, thoroughness)
            tools = ["grep", "glob", "read_file"]
            max_iterations = 10

        elif subagent_type == "Documentation":
            system_prompt = self._build_documentation_prompt(task_prompt, thoroughness)
            tools = ["grep", "glob", "read_file"]
            max_iterations = 10

        elif subagent_type == "CodeReview":
            # Get context from store for code review (modified files, their content, imports)
            review_context = None
            if self.context_store:
                review_context = self.context_store.get_context_for_review()

            system_prompt = self._build_code_review_prompt(task_prompt, thoroughness, review_context)
            tools = ["read_file", "grep", "glob", "goto_definition", "find_references"]
            max_iterations = 15

        else:
            return ToolResult(
                success=False,
                error=f"Unknown subagent_type: {subagent_type}",
                suggestion="Use 'Explore', 'Plan', 'Test', 'Refactor', 'Documentation', or 'CodeReview'",
            )

        try:
            # Import here to avoid circular dependency
            from vishwa.agent.core import VishwaAgent
            from vishwa.tools.base import ToolRegistry

            # ═══════════════════════════════════════════════════════════════
            # VISUAL INDICATOR: Show sub-agent starting
            # ═══════════════════════════════════════════════════════════════
            print_subagent_start(subagent_type, description, thoroughness)

            # Create sub-tool registry with only allowed tools
            sub_tool_registry = ToolRegistry()
            for tool_name in tools:
                tool = self.tool_registry.get(tool_name)
                if tool:
                    sub_tool_registry.register(tool)

            # Launch sub-agent
            # Key: auto_approve=True for read-only tools (no user prompts)
            sub_agent = VishwaAgent(
                llm=self.llm,
                tools=sub_tool_registry,
                max_iterations=max_iterations,
                auto_approve=True,  # Auto-approve read-only tools
                verbose=False,  # Don't spam user with sub-agent's thinking
            )

            # Run agent with the task (with spinner)
            spinner = create_subagent_spinner(subagent_type, description)
            with spinner:
                task_id = spinner.add_task(description, total=None)
                result = sub_agent.run(system_prompt, clear_context=True)

            # Extract final answer from agent
            final_answer = result.message

            # ═══════════════════════════════════════════════════════════════
            # VISUAL INDICATOR: Show sub-agent completion
            # ═══════════════════════════════════════════════════════════════
            print_subagent_complete(
                subagent_type=subagent_type,
                success=result.success,
                iterations_used=result.iterations_used,
                stop_reason=result.stop_reason or "",
            )

            # Log completion using tool_result pattern
            logger.tool_result("task", result.success, f"Completed in {result.iterations_used} iterations", None)

            # Return success based on sub-agent's actual result
            return ToolResult(
                success=result.success,
                output=final_answer,
                error=None if result.success else f"Sub-agent stopped: {result.stop_reason}",
                metadata={
                    "subagent_type": subagent_type,
                    "iterations_used": result.iterations_used,
                    "thoroughness": thoroughness,
                    "description": description,
                    "stop_reason": result.stop_reason,
                },
            )

        except Exception as e:
            # ═══════════════════════════════════════════════════════════════
            # VISUAL INDICATOR: Show sub-agent failure
            # ═══════════════════════════════════════════════════════════════
            print_subagent_complete(
                subagent_type=subagent_type,
                success=False,
                iterations_used=0,
                stop_reason=str(e),
            )

            logger.error("task", f"Sub-agent failed: {str(e)}", exception=e)
            return ToolResult(
                success=False,
                error=f"Sub-agent failed: {str(e)}",
                metadata={
                    "subagent_type": subagent_type,
                    "description": description,
                },
            )

    def _build_explore_prompt(self, task: str, thoroughness: str) -> str:
        """Build system prompt for Explore agent."""

        thoroughness_guidance = {
            "quick": """
Be quick and focused:
- Try 1-2 search patterns
- Read only the most relevant files (1-3 files max)
- Return concise summary quickly
Target: 5-8 iterations. Signal completion with "Final Answer:" as soon as you have enough info.
""",
            "medium": """
Be moderately thorough:
- Try 3-5 different search patterns
- Check multiple file locations
- Read key files to understand implementation
- Return detailed summary with examples
Target: 10-15 iterations. Signal completion with "Final Answer:" when done.
""",
            "very thorough": """
Be extremely thorough:
- Try many search patterns and variations
- Check all possible locations and naming conventions
- Read multiple files to understand full context
- Check test files too
- Return comprehensive summary with all findings
Target: 15-25 iterations. Signal completion with "Final Answer:" when done.
"""
        }

        return f"""You are an Explore agent - specialized for autonomous codebase exploration.

YOUR TASK:
{task}

THOROUGHNESS LEVEL: {thoroughness}
{thoroughness_guidance.get(thoroughness, thoroughness_guidance["medium"])}

TOOLS AVAILABLE:
- grep: Search file contents with regex
- glob: Find files by pattern
- read_file: Read file contents
- goto_definition: Jump to where a symbol is defined (LSP - more precise than grep)
- find_references: Find all usages of a symbol (LSP - semantic, not text-based)
- hover_info: Get type/documentation for a symbol (LSP)

IMPORTANT RULES:
1. DO NOT make any modifications - you are read-only
2. Try multiple search strategies if first attempt doesn't find what you need
3. Read files to verify your findings
4. When done, provide a CLEAR FINAL SUMMARY with:
   - What you found
   - File:line references
   - Brief explanation of how it works
   - Any important related code

SEARCH STRATEGY:
1. Start with grep to find likely files
2. Use glob if you know file name patterns
3. Read the most promising files
4. If needed, try different search terms
5. For deeper understanding of a symbol:
   - Use goto_definition to find where it's defined
   - Use find_references to see how it's used
   - Use hover_info to get documentation
6. Compile findings into final summary

BEGIN YOUR EXPLORATION NOW. Think step-by-step and explain your search strategy as you go.

IMPORTANT: When you have gathered enough information, you MUST signal completion by starting your response with "Final Answer:" followed by your summary.

Final Answer:
## Summary
Brief 2-3 sentence overview

## Key Findings
- Finding 1 (file:line)
- Finding 2 (file:line)

## Details
Relevant details about your findings.
"""

    def _build_plan_prompt(self, task: str, thoroughness: str) -> str:
        """Build system prompt for Plan agent."""

        return f"""You are a Plan agent - specialized for creating implementation plans.

YOUR TASK:
{task}

TOOLS AVAILABLE:
- grep: Search file contents with regex
- glob: Find files by pattern
- read_file: Read file contents

YOUR JOB:
1. Search the codebase to understand current architecture
2. Find relevant existing code, patterns, and conventions
3. Create a detailed step-by-step implementation plan
4. DO NOT implement anything - just plan

PLAN SHOULD INCLUDE:
- Steps to implement the feature/fix
- Files that need to be modified (with specific line references if possible)
- Code patterns to follow (based on existing code)
- Potential challenges and considerations
- Testing strategy

SEARCH STRATEGY:
1. Find similar existing implementations
2. Understand the current architecture
3. Identify integration points
4. Check for relevant utilities/helpers

BEGIN PLANNING NOW. When done, signal completion with "Final Answer:" followed by your implementation plan.

Final Answer:
## Implementation Plan
[Your step-by-step plan here]
"""

    def _get_iterations_for_thoroughness(self, thoroughness: str) -> int:
        """Get max iterations based on thoroughness level."""
        return {
            "quick": 8,
            "medium": 15,
            "very thorough": 25,
        }.get(thoroughness, 15)

    # ==================== PROMPT BUILDERS ====================

    def _build_test_prompt(self, task: str, thoroughness: str) -> str:
        """Build system prompt for Test agent."""

        return f"""You are a Test agent - specialized for writing and understanding tests.

YOUR TASK:
{task}

TOOLS AVAILABLE:
- grep: Search file contents with regex
- glob: Find files by pattern
- read_file: Read file contents

YOUR JOB:
1. Explore the codebase to understand existing test patterns
2. Find the testing framework and tools used
3. Analyze test coverage and identify gaps
4. If asked to write tests, follow existing patterns and conventions
5. DO NOT modify production code - focus only on tests

TESTING FOCUS AREAS:
- Unit tests (individual functions/classes)
- Integration tests (module interactions)
- End-to-end tests (user workflows)
- Test fixtures and mocking patterns
- Test organization and naming conventions

SEARCH STRATEGY:
1. Find test directories and test files
2. Identify the testing framework (pytest, unittest, etc.)
3. Look at test patterns and fixtures
4. Analyze coverage of critical functionality
5. Provide recommendations or write tests as requested

BEGIN TESTING WORK NOW. When done, signal completion with "Final Answer:" followed by your summary.

Final Answer:
## Test Analysis Summary
- Testing framework and tools used
- Existing test patterns found
- Coverage gaps identified
"""


    def _build_refactor_prompt(self, task: str, thoroughness: str) -> str:
        """Build system prompt for Refactor agent."""

        return f"""You are a Refactor agent - specialized for code improvement and restructuring.

YOUR TASK:
{task}

TOOLS AVAILABLE:
- grep: Search file contents with regex
- glob: Find files by pattern
- read_file: Read file contents

YOUR JOB:
1. Analyze code for quality issues and code smells
2. Identify opportunities for improvement
3. Suggest refactoring strategies
4. DO NOT modify code - only analyze and suggest
5. Provide specific, actionable recommendations

CODE SMELLS TO IDENTIFY:
- Long functions (should be split into smaller ones)
- Large classes (should be decomposed)
- Duplicate code (should be extracted into utilities)
- Magic numbers/strings (should be named constants)
- Deeply nested conditionals (should be simplified)
- God modules/files (should be split by responsibility)
- Feature envy (data and methods should be closer)
- Data clumps (related data should be objects)

REFACTORING RECOMMENDATIONS SHOULD INCLUDE:
- File:line reference of the issue
- Description of the code smell
- Suggested refactoring approach
- Expected benefits (readability, maintainability, etc.)
- Priority (high/medium/low)

SEARCH STRATEGY:
1. Identify files/modules to analyze
2. Look for common anti-patterns
3. Check function/class lengths and complexity
4. Identify repeated code patterns
5. Provide prioritized recommendations

BEGIN REFACTORING ANALYSIS NOW. When done, signal completion with "Final Answer:" followed by your summary.

Final Answer:
## Refactoring Analysis
- Code smells identified with file:line references
- Prioritized recommendations
- Suggested refactoring steps
"""


    def _build_documentation_prompt(self, task: str, thoroughness: str) -> str:
        """Build system prompt for Documentation agent."""

        return f"""You are a Documentation agent - specialized for generating and improving documentation.

YOUR TASK:
{task}

TOOLS AVAILABLE:
- grep: Search file contents with regex
- glob: Find files by pattern
- read_file: Read file contents

YOUR JOB:
1. Understand the codebase structure and key components
2. Find existing documentation
3. Identify documentation gaps
4. Generate documentation as requested
5. Follow project documentation conventions

DOCUMENTATION TYPES:
- API documentation (function signatures, parameters, return values)
- Module documentation (purpose, usage, examples)
- Architecture documentation (system design, components)
- Inline comments (complex logic explanations)
- README files (getting started, setup instructions)

SEARCH STRATEGY:
1. Find existing documentation files (README.md, docs/, etc.)
2. Identify the project's documentation style
3. Explore the code to document
4. Look at existing comments and docstrings
5. Generate clear, concise documentation

DOCUMENTATION GUIDELINES:
- Use clear, simple language
- Include code examples where helpful
- Document parameters, return values, and exceptions
- Explain the "why" not just the "what"
- Follow existing documentation style

BEGIN DOCUMENTATION WORK NOW. When done, signal completion with "Final Answer:" followed by your summary.

Final Answer:
## Documentation Summary
Brief overview of documentation work

## Documentation Created/Updated
- File: What was documented

## Gaps and Recommendations
- Documentation gaps and future work needed
"""

    def _build_code_review_prompt(self, task: str, thoroughness: str, review_context: dict = None) -> str:
        """Build system prompt for CodeReview agent with injected context."""

        # Build context section if we have cached context
        context_section = ""
        if review_context and review_context.get("modified_files"):
            context_section = """
═══════════════════════════════════════════════════════════════
CONTEXT: FILES MODIFIED IN THIS SESSION
═══════════════════════════════════════════════════════════════

The following files were modified during this session and should be reviewed:

"""
            for file_path in review_context["modified_files"]:
                context_section += f"- {file_path}\n"

            # Add file contents if available
            if review_context.get("file_contents"):
                context_section += "\n--- FILE CONTENTS ---\n"
                for path, content in review_context["file_contents"].items():
                    # Limit content to avoid token explosion
                    lines = content.split("\n")
                    if len(lines) > 200:
                        content = "\n".join(lines[:200]) + f"\n\n... [{len(lines) - 200} more lines truncated]"

                    context_section += f"\n### {path}\n```\n{content}\n```\n"

            # Add imports info
            if review_context.get("imports"):
                context_section += "\n--- IMPORTS (for understanding dependencies) ---\n"
                for path, imports in review_context["imports"].items():
                    if imports:
                        context_section += f"\n{path} imports: {', '.join(imports)}\n"

            context_section += "\n"

        return f"""You are a CodeReview agent - specialized for comprehensive code review with severity-based issue categorization.
{context_section}
YOUR TASK:
{task}

TOOLS AVAILABLE:
- read_file: Read file contents
- grep: Search file contents with regex
- glob: Find files by pattern
- goto_definition: Jump to where a symbol is defined (LSP)
- find_references: Find all usages of a symbol (LSP)

YOUR JOB:
1. Review the specified code thoroughly
2. Categorize issues by severity (CRITICAL vs MEDIUM)
3. Provide specific file:line references for each issue
4. Suggest concrete fixes for each issue
5. DO NOT modify code - only review and report

═══════════════════════════════════════════════════════════════
CRITICAL ISSUES (Must Fix - Block Completion)
═══════════════════════════════════════════════════════════════
These issues MUST be fixed before code can be accepted:

- SOLID Principle Violations:
  * Single Responsibility: Class/function doing too many things
  * Open/Closed: Requires modification for extension
  * Liskov Substitution: Subtype not substitutable for base
  * Interface Segregation: Fat interfaces forcing unused implementations
  * Dependency Inversion: High-level depending on low-level details

- Security Vulnerabilities:
  * SQL Injection (unsanitized user input in queries)
  * XSS (unescaped user content in HTML)
  * Command Injection (user input in shell commands)
  * Path Traversal (user input in file paths)
  * Hardcoded credentials or secrets
  * Insecure deserialization

- Potential Bugs:
  * Null/None reference errors
  * Race conditions
  * Resource leaks (unclosed files/connections)
  * Off-by-one errors
  * Unhandled exceptions in critical paths
  * Infinite loops or recursion

- Logic Errors:
  * Incorrect algorithm implementation
  * Wrong boundary conditions
  * Inverted boolean logic
  * Missing validation at system boundaries

- Breaking Changes:
  * Public API signature changes without deprecation
  * Backward-incompatible changes to interfaces

═══════════════════════════════════════════════════════════════
MEDIUM ISSUES (Should Fix - Warn Only)
═══════════════════════════════════════════════════════════════
These issues should be addressed but don't block completion:

- Code Smells:
  * Long methods (>50 lines)
  * Large classes (>300 lines)
  * Duplicate code (copy-pasted logic)
  * Magic numbers/strings (unexplained literals)
  * Deeply nested conditionals (>3 levels)
  * God classes/modules (too many responsibilities)
  * Feature envy (method uses other class's data excessively)
  * Data clumps (same data groups appearing together)

- Missing Error Handling:
  * Unhandled exceptions
  * Silent failures (empty catch blocks)
  * Missing validation for optional parameters

- Poor Naming:
  * Non-descriptive variable/function names
  * Inconsistent naming conventions
  * Misleading names

- Design Issues:
  * Tight coupling between modules
  * Low cohesion within modules
  * Missing abstractions
  * Premature optimization

═══════════════════════════════════════════════════════════════
REVIEW PROCESS
═══════════════════════════════════════════════════════════════

1. Read the files to review carefully
2. For each file:
   a. Check for CRITICAL issues first
   b. Then check for MEDIUM issues
   c. Note file:line for each issue
3. Use goto_definition to understand symbol definitions
4. Use find_references to check how symbols are used
5. Consider the broader codebase context

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════

When done, signal completion with "Final Answer:" followed by your review.

Final Answer:
## Code Review Summary

### Critical Issues (Must Fix)
- [file:line] **Issue Category**: Description of the issue
  **Suggestion**: How to fix it

### Medium Issues (Should Fix)
- [file:line] **Issue Category**: Description of the issue
  **Suggestion**: How to fix it

### Overall Assessment
Brief summary of code quality (1-2 sentences).
Rate: GOOD / NEEDS_WORK / CRITICAL_ISSUES

If no critical issues found, state: "No critical issues found."
If no medium issues found, state: "No medium issues found."
"""
