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
from vishwa.utils.logger import logger


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
        self.tools = tools or ToolRegistry.load_default(auto_approve=auto_approve)
        self.max_iterations = max_iterations
        self.auto_approve = auto_approve
        self.verbose = verbose

        # State
        self.context = ContextManager()
        self.iteration = 0
        self.stop_reason = None
        self.task = ""

    def run(self, task: str, clear_context: bool = False) -> AgentResult:
        """
        Execute the agent loop for a given task.

        Args:
            task: The task to accomplish
            clear_context: Whether to clear context before running (default: False).
                          Context is retained by default for conversational flow.
                          Set to True to start fresh (useful for new unrelated tasks).

        Returns:
            AgentResult with success/failure and details
        """
        self.task = task
        self.iteration = 0
        self.stop_reason = None

        # Log agent start
        logger.agent_start(task, self.max_iterations)

        # Initialize context with task
        if clear_context:
            self.context.clear()
        self.context.add_message("user", task)

        # Main ReAct loop
        for self.iteration in range(1, self.max_iterations + 1):
            try:
                # Log iteration start
                logger.agent_iteration(self.iteration, self.max_iterations)

                # Step 1: Get LLM response (Thought + Action)
                response = self._get_llm_response()

                # Step 2: Show LLM's thinking/message if present
                if response.content and response.content.strip() and self.verbose:
                    # Print the LLM's message with markdown rendering
                    from rich.markdown import Markdown
                    from rich.console import Console

                    console = Console()
                    console.print(Markdown(response.content))
                    logger.agent_thinking(response.content)

                # Step 3: Check if this is purely conversational (no tools, no task context)
                if not response.has_tool_calls():
                    # No tool calls - check if there's content
                    if response.content and response.content.strip():
                        # Check for repeated identical messages (stuck in loop)
                        recent_messages = self.context.get_messages()
                        if len(recent_messages) >= 2:
                            last_assistant_msg = None
                            for msg in reversed(recent_messages):
                                if msg.get("role") == "assistant":
                                    last_assistant_msg = msg.get("content", "")
                                    break

                            # If this exact message was just sent, we're stuck
                            if last_assistant_msg and last_assistant_msg.strip() == response.content.strip():
                                self.stop_reason = "repeated_message"
                                logger.agent_decision("stop", "LLM repeating same message")
                                return self._finalize_incomplete(
                                    f"Agent appears stuck (repeating same message). Last message: {response.content[:100]}..."
                                )

                        # Add message to context for next iteration
                        self.context.add_message("assistant", response.content)

                        # Check if this seems like a final answer or just mid-task commentary
                        if self._is_final_answer(response):
                            # This is the final answer
                            self.stop_reason = "final_answer"
                            logger.agent_decision("stop", "final answer (no tools)")
                            return AgentResult(
                                success=True,
                                message=response.content,
                                iterations_used=self.iteration,
                                modifications=self.context.modifications,
                                stop_reason="final_answer",
                            )
                        else:
                            # This is mid-task commentary - continue loop
                            # But limit consecutive text-only responses to prevent infinite loops
                            # Count consecutive assistant messages without tools
                            consecutive_text_only = 0
                            for msg in reversed(recent_messages):
                                if msg.get("role") == "assistant":
                                    consecutive_text_only += 1
                                elif msg.get("role") == "tool":
                                    break

                            if consecutive_text_only >= 3:
                                # Too many text responses without action
                                self.stop_reason = "too_many_text_responses"
                                logger.agent_decision("stop", "too many text-only responses without tool calls")
                                return self._finalize_incomplete(
                                    "Agent is thinking but not taking action. Please try rephrasing your request or provide more specific instructions."
                                )

                            logger.agent_decision("continue", "text-only response, continuing loop")
                            continue
                    else:
                        # LLM didn't call any tools and didn't provide content
                        self.stop_reason = "no_action"
                        logger.agent_decision("stop", "no action taken")
                        return self._finalize_incomplete(
                            "Agent did not call any tools or provide a response"
                        )

                # Step 4: Check if done (Final Answer with tools)
                if self._is_final_answer(response):
                    self.stop_reason = "final_answer"
                    logger.agent_decision("stop", "final answer detected")
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
                    logger.agent_decision("stop", f"stopping condition met: {self.stop_reason}")
                    return self._finalize_success("Stopping conditions met")

            except LLMError as e:
                self.stop_reason = "llm_error"
                logger.error("agent", f"LLM error: {str(e)}", exception=e)
                return self._finalize_error(f"LLM error: {str(e)}")

            except KeyboardInterrupt:
                self.stop_reason = "user_interrupt"
                logger.agent_decision("stop", "user interrupt")
                return self._finalize_incomplete("Interrupted by user")

            except Exception as e:
                self.stop_reason = "unexpected_error"
                logger.error("agent", f"Unexpected error: {str(e)}", exception=e)
                return self._finalize_error(f"Unexpected error: {str(e)}")

        # Max iterations reached
        self.stop_reason = "max_iterations"
        logger.agent_decision("stop", "max iterations reached")
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

        # Log LLM request
        logger.llm_request(
            provider=self.llm.provider_name,
            model=self.llm.model_name,
            msg_count=len(messages),
            tool_count=len(tools)
        )

        response = self.llm.chat(
            messages=messages,
            tools=tools,
            system=system_prompt,
        )

        # Log LLM response
        tokens = None
        if response.usage:
            tokens = {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
        logger.llm_response(
            model=response.model,
            tool_calls=len(response.tool_calls),
            tokens=tokens
        )

        return response

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

        # Log tool call
        logger.tool_start(tool_name, arguments)

        # Note: Tool syntax is hidden - tools handle their own preview/approval
        # The conversational output is shown by the LLM's messages instead

        # Get tool
        tool = self.tools.get(tool_name)
        if not tool:
            result = ToolResult(
                success=False,
                error=f"Tool not found: {tool_name}",
                suggestion="Use one of the available tools",
            )
            logger.tool_result(tool_name, False, None, result.error)
            return result

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

            # Log tool result
            logger.tool_result(tool_name, result.success, result.output, result.error)

            # Track file creation
            if tool_name == "write_file" and result.success:
                self.context.mark_file_created(arguments.get("path", ""))

            # Track modifications
            if tool_name == "str_replace" and result.success:
                self.context.track_modification(
                    file_path=arguments.get("path", ""),
                    tool=tool_name,
                )

            # Note: Tool results are hidden - tools show their own diffs/output
            # Errors are still logged but not printed (LLM will see them and can explain)

            return result

        except Exception as e:
            result = ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
            )
            logger.tool_result(tool_name, False, None, result.error)
            logger.error("tool", f"Exception during {tool_name} execution", exception=e)
            return result

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
        # Close any pending VS Code tabs before finalizing
        from vishwa.cli.ui import is_vscode, _close_tabs_immediately, _pending_tab_close
        if is_vscode() and _pending_tab_close:
            _close_tabs_immediately()

        logger.agent_complete(
            reason=self.stop_reason or "completed",
            iterations=self.iteration,
            success=True
        )

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
        # Close any pending VS Code tabs before finalizing
        from vishwa.cli.ui import is_vscode, _close_tabs_immediately, _pending_tab_close
        if is_vscode() and _pending_tab_close:
            _close_tabs_immediately()

        logger.agent_complete(
            reason=self.stop_reason or "incomplete",
            iterations=self.iteration,
            success=False
        )

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
        # Close any pending VS Code tabs before finalizing
        from vishwa.cli.ui import is_vscode, _close_tabs_immediately, _pending_tab_close
        if is_vscode() and _pending_tab_close:
            _close_tabs_immediately()

        logger.agent_complete(
            reason=self.stop_reason or "error",
            iterations=self.iteration,
            success=False
        )

        if self.verbose:
            print(f"\n❌ {message}\n")

        return AgentResult(
            success=False,
            message=message,
            iterations_used=self.iteration,
            modifications=self.context.modifications,
            stop_reason=self.stop_reason or "error",
        )
