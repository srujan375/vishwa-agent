"""
Vishwa Agent Core - ReAct Loop Implementation.

The main orchestrator that coordinates LLM, tools, and context.
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from vishwa.agent.context import ContextManager
from vishwa.llm.base import BaseLLM, LLMError
from vishwa.llm.response import LLMResponse, ToolCall
from vishwa.prompts import get_platform_commands, get_system_prompt
from vishwa.tools.base import Tool, ToolNotFoundError, ToolRegistry, ToolResult


@dataclass
class AgentResult:
    """Result from agent execution"""

    success: bool
    message: str
    iterations_used: int
    modifications: List[Any]
    stop_reason: str
    metadata: Optional[Dict[str, Any]] = None


class VishwaAgent:
    """
    Main Vishwa agent implementing the ReAct pattern.

    ReAct = Reasoning + Acting
    Loop: Thought → Action → Observation → Repeat

    Responsibilities:
    - Run the agent loop (max iterations)
    - Coordinate LLM and tools
    - Manage context and state
    - Handle stopping conditions
    - Track modifications
    """

    def __init__(
        self,
        llm: BaseLLM,
        tools: Optional[ToolRegistry] = None,
        max_iterations: int = 15,
        auto_approve: bool = False,
        verbose: bool = True,
    ):
        """
        Initialize Vishwa agent.

        Args:
            llm: LLM provider instance
            tools: Tool registry (default: load all core tools)
            max_iterations: Maximum agent loop iterations
            auto_approve: Auto-approve all actions (dangerous!)
            verbose: Print progress to console
        """
        self.llm = llm
        self.tools = tools or ToolRegistry.load_default()
        self.max_iterations = max_iterations
        self.auto_approve = auto_approve
        self.verbose = verbose

        # State
        self.context = ContextManager()
        self.iteration = 0
        self.stop_reason = None
        self.task = ""

    def run(self, task: str, clear_context: bool = True) -> AgentResult:
        """
        Execute the agent loop for a given task.

        Args:
            task: The task to accomplish
            clear_context: Whether to clear context before running (default: True).
                          Set to False for interactive sessions to maintain conversation history.

        Returns:
            AgentResult with success/failure and details
        """
        self.task = task
        self.iteration = 0
        self.stop_reason = None

        # Initialize context with task
        if clear_context:
            self.context.clear()
        self.context.add_message("user", task)

        # Main ReAct loop
        for self.iteration in range(1, self.max_iterations + 1):
            try:
                # Step 1: Get LLM response (Thought + Action)
                response = self._get_llm_response()

                # Step 2: Check if this is a conversational response (no tools)
                if not response.has_tool_calls():
                    # No tool calls - check if there's a text response
                    if response.content and response.content.strip():
                        # This is a conversational response (greeting, clarification, etc.)
                        # Don't print task header or iteration for conversational responses
                        self.stop_reason = "conversational_response"
                        return AgentResult(
                            success=True,
                            message=response.content,
                            iterations_used=self.iteration,
                            modifications=self.context.modifications,
                            stop_reason="conversational_response",
                        )
                    else:
                        # LLM didn't call any tools and didn't provide content
                        self.stop_reason = "no_action"
                        return self._finalize_incomplete(
                            "Agent did not call any tools or provide a response"
                        )

                # This is a tool-based task - show task header on first iteration
                if self.iteration == 1 and self.verbose:
                    print(f"\n🎯 Task: {task}\n")

                # Show iteration counter for tool-based tasks
                if self.verbose:
                    print(f"[{self.iteration}/{self.max_iterations}] ", end="", flush=True)

                # Step 3: Check if done (Final Answer)
                if self._is_final_answer(response):
                    self.stop_reason = "final_answer"
                    return self._finalize_success(response.content or "Task completed")

                # Step 4: Execute tool calls (Action → Observation)
                # Execute each tool call
                for tool_call in response.tool_calls:
                    result = self._execute_tool_call(tool_call)

                    # Add to context
                    self.context.add_tool_result(tool_call, result)

                # Step 4: Prune context if needed
                self.context.prune_if_needed()

                # Step 5: Check stopping conditions
                if self._should_stop():
                    return self._finalize_success("Stopping conditions met")

            except LLMError as e:
                self.stop_reason = "llm_error"
                return self._finalize_error(f"LLM error: {str(e)}")

            except KeyboardInterrupt:
                self.stop_reason = "user_interrupt"
                return self._finalize_incomplete("Interrupted by user")

            except Exception as e:
                self.stop_reason = "unexpected_error"
                return self._finalize_error(f"Unexpected error: {str(e)}")

        # Max iterations reached
        self.stop_reason = "max_iterations"
        return self._finalize_incomplete(
            f"Max iterations ({self.max_iterations}) reached"
        )

    def _get_llm_response(self) -> LLMResponse:
        """
        Get response from LLM.

        Returns:
            LLMResponse with content and/or tool calls
        """
        system_prompt = self._build_system_prompt()
        messages = self.context.get_messages()
        tools = self.tools.to_openai_format()

        return self.llm.chat(
            messages=messages,
            tools=tools,
            system=system_prompt,
        )

    def _build_system_prompt(self) -> str:
        """
        Build system prompt with ReAct instructions.

        Loads prompt from src/vishwa/prompts/system_prompt.txt
        and fills in the template variables.

        Returns:
            System prompt string
        """
        cwd = os.getcwd()
        files = list(self.context.files_in_context.keys())
        mods = len(self.context.modifications)

        return get_system_prompt(
            tools_description=self._format_tools_description(),
            working_directory=cwd,
            files_in_context=files if files else "None",
            modifications_count=mods,
            current_iteration=self.iteration,
            max_iterations=self.max_iterations,
            task=self.task,
            platform_commands=get_platform_commands(),
        )

    def _format_tools_description(self) -> str:
        """Format tools for system prompt"""
        descriptions = []
        for tool in self.tools.all():
            descriptions.append(f"- {tool.name}: {tool.description.split('.')[0]}")
        return "\n".join(descriptions)

    def _is_final_answer(self, response: LLMResponse) -> bool:
        """
        Check if response is a final answer.

        Args:
            response: LLM response

        Returns:
            True if this is a final answer
        """
        if response.is_final_answer():
            return True

        # Check for explicit "Final Answer:" in content
        if response.content and "final answer:" in response.content.lower():
            return True

        return False

    def _execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call.

        Args:
            tool_call: Tool call from LLM

        Returns:
            ToolResult from execution
        """
        tool_name = tool_call.name
        arguments = tool_call.arguments

        if self.verbose:
            print(f"→ {tool_name}({', '.join(f'{k}={v!r}' for k, v in arguments.items())})")

        # Get tool
        tool = self.tools.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {tool_name}",
                suggestion="Use one of the available tools",
            )

        # Check if needs approval
        if self._needs_approval(tool_call):
            approval_result = self._get_user_approval(tool_call)
            if not approval_result:
                # Ask user for feedback on why they rejected it
                feedback = self._get_rejection_feedback(tool_call)
                return ToolResult(
                    success=False,
                    error="Action rejected by user",
                    suggestion=feedback if feedback else "User rejected without feedback",
                )

        # Check if trying to create a file that was already created this session
        if tool_name == "write_file":
            file_path = arguments.get("path", "")
            if self.context.was_file_created(file_path):
                return ToolResult(
                    success=False,
                    error=f"File '{file_path}' was already created in this session",
                    suggestion="The file already exists. Use str_replace to modify it, or use a different filename.",
                )

        # Execute tool
        try:
            result = tool.execute(**arguments)

            # Track file creation
            if tool_name == "write_file" and result.success:
                self.context.mark_file_created(arguments.get("path", ""))

            # Track modifications
            if tool_name == "str_replace" and result.success:
                self.context.track_modification(
                    file_path=arguments.get("path", ""),
                    tool=tool_name,
                )

            if self.verbose:
                status = "✓" if result.success else "✗"
                output = result.output or result.error
                # Truncate long output
                if output and len(output) > 200:
                    output = output[:200] + "..."
                print(f"  {status} {output}")

            return result

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
            )

    def _needs_approval(self, tool_call: ToolCall) -> bool:
        """
        Check if tool call needs user approval.

        Args:
            tool_call: Tool call to check

        Returns:
            True if approval needed
        """
        if self.auto_approve:
            return False

        # Always ask for destructive operations
        if tool_call.name in ["str_replace", "write_file"]:
            return True

        # Ask for risky bash commands
        if tool_call.name == "bash":
            command = tool_call.arguments.get("command", "")
            risky_patterns = ["rm ", "mv ", "git push", "git reset", "git rebase"]
            if any(pattern in command for pattern in risky_patterns):
                return True

        return False

    def _get_rejection_feedback(self, tool_call: ToolCall) -> str:
        """
        Ask user for feedback when they reject a tool call.

        This helps the agent understand what needs to be changed instead of
        blindly retrying the same approach.

        Args:
            tool_call: The tool call that was rejected

        Returns:
            User's feedback as a string
        """
        from rich.console import Console
        from prompt_toolkit import prompt as pt_prompt

        console = Console()

        console.print("\n[yellow]💬 Help me understand:[/yellow]")
        console.print("[dim]What would you like me to change about this approach?[/dim]")
        console.print("[dim](Press Enter to skip, or Ctrl+C to cancel the task)[/dim]\n")

        try:
            feedback = pt_prompt("Your feedback: ", multiline=False)
            return feedback.strip() if feedback.strip() else None
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Task cancelled by user[/yellow]")
            raise KeyboardInterrupt()

    def _get_user_approval(self, tool_call: ToolCall) -> bool:
        """
        Get user approval for tool call with interactive buttons.

        Shows preview for file operations.

        Args:
            tool_call: Tool call to approve

        Returns:
            True if approved
        """
        from vishwa.cli.ui import confirm_action, show_diff

        # Show preview for write_file
        if tool_call.name == "write_file":
            path = tool_call.arguments.get("path", "")
            content = tool_call.arguments.get("content", "")

            print(f"\n📝 Creating new file: {path}")
            print("=" * 60)

            # Show content with line numbers (limited preview)
            lines = content.split('\n')
            preview_lines = min(len(lines), 30)  # Show max 30 lines

            for i, line in enumerate(lines[:preview_lines], 1):
                print(f"{i:3d} | {line}")

            if len(lines) > preview_lines:
                print(f"... ({len(lines) - preview_lines} more lines)")

            print("=" * 60)
            print(f"Total: {len(lines)} lines, {len(content)} characters\n")

            return confirm_action(f"Create file '{path}'?", default=False)

        # Show preview for str_replace
        elif tool_call.name == "str_replace":
            path = tool_call.arguments.get("path", "")
            old_str = tool_call.arguments.get("old_str", "")
            new_str = tool_call.arguments.get("new_str", "")

            print(f"\n📝 Modifying file: {path}")

            # Use the fancy diff display
            show_diff(path, old_str, new_str)

            return confirm_action(f"Apply changes to '{path}'?", default=False)

        else:
            # For other operations, use interactive confirmation
            args_preview = ", ".join(f"{k}={v!r}" for k, v in tool_call.arguments.items())
            if len(args_preview) > 100:
                args_preview = args_preview[:100] + "..."

            return confirm_action(
                f"Execute {tool_call.name}({args_preview})?",
                default=False
            )

    def _should_stop(self) -> bool:
        """
        Check if loop should stop.

        Returns:
            True if should stop
        """
        # Check if stuck in loop (same tool called many times)
        if len(self.context.recent_tool_outputs) >= 5:
            recent_tools = [out["tool"] for out in self.context.recent_tool_outputs]
            # If last 5 tools are the same, probably stuck
            if len(set(recent_tools[-5:])) == 1:
                self.stop_reason = "stuck_in_loop"
                return True

        # Check if tests passed (if task involves tests)
        if "test" in self.task.lower():
            last_result = self.context.get_last_tool_result("bash")
            if last_result and last_result.success:
                output = last_result.output or ""
                if "passed" in output.lower() and "failed" not in output.lower():
                    self.stop_reason = "tests_passed"
                    return True

        return False

    def _finalize_success(self, message: str) -> AgentResult:
        """Finalize with success"""
        if self.verbose:
            print(f"\n✅ {message}\n")

        return AgentResult(
            success=True,
            message=message,
            iterations_used=self.iteration,
            modifications=self.context.modifications,
            stop_reason=self.stop_reason or "completed",
        )

    def _finalize_incomplete(self, message: str) -> AgentResult:
        """Finalize with incomplete status"""
        if self.verbose:
            print(f"\n⚠️  {message}\n")

        return AgentResult(
            success=False,
            message=message,
            iterations_used=self.iteration,
            modifications=self.context.modifications,
            stop_reason=self.stop_reason or "incomplete",
        )

    def _finalize_error(self, message: str) -> AgentResult:
        """Finalize with error"""
        if self.verbose:
            print(f"\n❌ {message}\n")

        return AgentResult(
            success=False,
            message=message,
            iterations_used=self.iteration,
            modifications=self.context.modifications,
            stop_reason=self.stop_reason or "error",
        )
