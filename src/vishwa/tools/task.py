"""
Task delegation tool - launches sub-agents for complex multi-step operations.

Based on Claude Code's Task tool specification.
Implements Explore and Plan agents that autonomously handle multi-round searches.
"""

from typing import Any, Dict, Optional
from vishwa.tools.base import Tool, ToolResult
from vishwa.utils.logger import logger


class TaskTool(Tool):
    """
    Launch specialized sub-agents for autonomous task execution.

    Prevents context bloat by running searches in isolated agents
    that return only summaries instead of full intermediate results.

    This is the #1 accuracy improvement from Claude Code - using
    multi-round autonomous search instead of single grep/glob calls.
    """

    def __init__(self, llm, tool_registry):
        """
        Initialize Task tool.

        Args:
            llm: LLM instance to use for sub-agents
            tool_registry: Main tool registry (to get tools for sub-agents)
        """
        self.llm = llm
        self.tool_registry = tool_registry

    @property
    def name(self) -> str:
        return "task"

    @property
    def description(self) -> str:
        return """Launch a new agent to handle complex, multi-step tasks autonomously.

The Task tool launches specialized agents (subprocesses) that autonomously handle complex tasks. Each agent type has specific capabilities and tools available to it.

Available agent types and the tools they have access to:
- Explore: Fast agent specialized for exploring codebases. Use this when you need to quickly find files by patterns (eg. "src/components/**/*.tsx"), search code for keywords (eg. "API endpoints"), or answer questions about the codebase (eg. "how do API endpoints work?"). When calling this agent, specify the desired thoroughness level: "quick" for basic searches, "medium" for moderate exploration, or "very thorough" for comprehensive analysis across multiple locations and naming conventions. (Tools: grep, glob, read_file, goto_definition, find_references, hover_info)

- Plan: Agent for planning implementations. Use when you need to create an implementation plan but not execute it yet. (Tools: grep, glob, read_file)

When NOT to use the Task tool:
- If you want to read a specific file path, use read_file instead
- If searching for a specific class definition like "class Foo", use glob instead
- If searching for code within a specific file or set of 2-3 files, use read_file instead
- Other tasks that are not related to the agent descriptions above

Usage notes:
- The agent will return a single message back to you when done
- The result is not visible to the user - you should summarize it for them
- Each agent invocation is stateless
- Your prompt should contain a highly detailed task description for the agent to perform autonomously
- Specify exactly what information the agent should return in its final message
- Clearly tell the agent whether you expect it to write code or just do research (for Explore, it's always research only)

Examples:
- task(subagent_type="Explore", prompt="Find where client errors are handled. Search for error handling patterns, try-catch blocks, error classes, and error middleware. Return file:line references and brief descriptions.", description="Find error handling")
- task(subagent_type="Explore", prompt="Understand the database connection architecture. Look for connection pooling, ORM usage, and query builders. Be thorough - check config files too. Return architecture summary with key files.", description="Analyze DB architecture")
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "subagent_type": {
                    "type": "string",
                    "enum": ["Explore", "Plan"],
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
            subagent_type: Type of agent ("Explore" or "Plan")
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

        else:
            return ToolResult(
                success=False,
                error=f"Unknown subagent_type: {subagent_type}",
                suggestion="Use 'Explore' or 'Plan'",
            )

        try:
            # Import here to avoid circular dependency
            from vishwa.agent.core import VishwaAgent
            from vishwa.tools.base import ToolRegistry

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

            # Run agent with the task
            result = sub_agent.run(system_prompt, clear_context=True)

            # Extract final answer from agent
            final_answer = result.message

            # Log completion using tool_result pattern
            logger.tool_result("task", True, f"Completed in {result.iterations_used} iterations", None)

            return ToolResult(
                success=True,
                output=final_answer,
                metadata={
                    "subagent_type": subagent_type,
                    "iterations_used": result.iterations_used,
                    "thoroughness": thoroughness,
                    "description": description,
                    "stop_reason": result.stop_reason,
                },
            )

        except Exception as e:
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
- Return concise summary
Target: 3-5 iterations
""",
            "medium": """
Be moderately thorough:
- Try 3-5 different search patterns
- Check multiple file locations
- Read key files to understand implementation
- Return detailed summary with examples
Target: 5-8 iterations
""",
            "very thorough": """
Be extremely thorough:
- Try many search patterns and variations
- Check all possible locations and naming conventions
- Read multiple files to understand full context
- Check test files too
- Return comprehensive summary with all findings
Target: 8-12 iterations
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
When you have enough information, provide your final summary.
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

BEGIN PLANNING NOW. When done, provide a CLEAR IMPLEMENTATION PLAN with file references and specific steps.
"""

    def _get_iterations_for_thoroughness(self, thoroughness: str) -> int:
        """Get max iterations based on thoroughness level."""
        return {
            "quick": 5,
            "medium": 8,
            "very thorough": 12,
        }.get(thoroughness, 8)
