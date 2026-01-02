"""
Vishwa Agent Core - ReAct Loop Implementation.

The main orchestrator that coordinates LLM, tools, and context.
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from vishwa.agent.context import ContextManager
from vishwa.agent.context_store import ContextStore
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
        max_iterations: Optional[int] = None,
        auto_approve: bool = False,
        verbose: bool = True,
        loop_detection_threshold: int = 30,
        enable_code_review: bool = True,
        skip_review: bool = False,
    ):
        """
        Initialize Vishwa agent.

        Args:
            llm: LLM provider instance
            tools: Tool registry (default: load all core tools)
            max_iterations: Maximum agent loop iterations (None = unlimited)
            auto_approve: Auto-approve all actions (dangerous!)
            verbose: Print progress to console
            loop_detection_threshold: Number of repeated tool calls before detecting loop (default: 15)
            enable_code_review: Enable automatic code quality checks after edits (default: True)
            skip_review: Skip code review entirely (default: False)
        """
        self.llm = llm
        self.tools = tools or ToolRegistry.load_default(auto_approve=auto_approve)
        self.max_iterations = max_iterations
        self.auto_approve = auto_approve
        self.verbose = verbose
        self.loop_detection_threshold = loop_detection_threshold
        self.enable_code_review = enable_code_review
        self.skip_review = skip_review

        # Create session-scoped context store for caching and sharing context
        self.context_store = ContextStore()

        # Set context store on all tools for transparent caching
        self.tools.set_context_store(self.context_store)

        # Register Task tool (needs LLM and registry, so added after registry creation)
        if not self.tools.get("task"):
            from vishwa.tools.task import TaskTool
            self.tools.register(TaskTool(
                llm=self.llm,
                tool_registry=self.tools,
                context_store=self.context_store
            ))

        # State
        self.context = ContextManager()
        self.iteration = 0
        self.stop_reason = None
        self.task = ""
        self._quality_fix_attempts = 0
        self._max_quality_fix_attempts = 3  # Max times to request quality fixes
        self._pending_quality_issues: list[tuple[str, str]] = []  # (file_path, issues)
        self._file_quality_attempts: dict[str, int] = {}  # Track attempts per file
        self._max_file_quality_attempts = 2  # Max fix attempts per file before giving up

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
        self._quality_fix_attempts = 0  # Reset quality fix counter for new task
        self._pending_quality_issues.clear()  # Clear any stale issues
        self._file_quality_attempts.clear()  # Reset per-file attempt tracking

        # Log agent start
        logger.agent_start(task, self.max_iterations)

        # Initialize context with task
        if clear_context:
            self.context.clear()
        self.context.add_message("user", task)

        # Main ReAct loop
        self.iteration = 0
        while True:
            self.iteration += 1

            # Check max iterations if set
            if self.max_iterations and self.iteration > self.max_iterations:
                # Max iterations reached
                self.stop_reason = "max_iterations"
                logger.agent_decision("stop", "max iterations reached")
                return self._finalize_incomplete(
                    f"Max iterations ({self.max_iterations}) reached"
                )

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
                            # NOTE: Pre-completion review disabled - CodeReview sub-agent was
                            # hallucinating issues. Post-edit checks (with line filtering) still active.

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
                    # NOTE: Pre-completion review disabled - CodeReview sub-agent was
                    # hallucinating issues. Post-edit checks (with line filtering) still active.
                    self.stop_reason = "final_answer"
                    logger.agent_decision("stop", "final answer detected")
                    return self._finalize_success(response.content or "Task completed")

                # Step 4: Execute tool calls (Action → Observation)
                # Execute each tool call
                for tool_call in response.tool_calls:
                    result = self._execute_tool_call(tool_call)

                    # Add to context
                    self.context.add_tool_result(tool_call, result)

                # Step 4b: Inject quality issues for immediate fix (if any)
                if self._pending_quality_issues:
                    issues_text = "\n\n".join(
                        f"**{file_path}:**\n{issues}"
                        for file_path, issues in self._pending_quality_issues
                    )
                    self.context.add_message(
                        "user",
                        f"[Code Quality Issues - Fix ALL in ONE Edit]\n\n"
                        f"{issues_text}\n\n"
                        f"IMPORTANT: Fix ALL issues above in a SINGLE edit using str_replace or multi_edit.\n"
                        f"Common fixes:\n"
                        f"- Remove unused imports\n"
                        f"- Use `list` instead of `List`, `dict` instead of `Dict` (modern Python)\n"
                        f"- Sort imports: stdlib first, then third-party, then local\n"
                        f"- Add type hints where missing\n\n"
                        f"Do NOT explain - just fix the code."
                    )
                    self._pending_quality_issues.clear()

                # Step 5: Compress files and tool results (token optimization)
                # After the LLM has seen content, we replace with compact summaries.
                # Modified files keep full content. Recent read_file results kept intact.
                self.context.compress_unmodified_files()
                self.context.compress_old_tool_results(keep_recent=3)

                # Step 6: Prune context if still approaching limit
                self.context.prune_if_needed()

                # Step 7: Check stopping conditions
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
            max_iterations=self.max_iterations or "unlimited",
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

        # Show tool call to user
        if self.verbose:
            from vishwa.cli.ui import print_action
            print_action(tool_name, arguments)

        # Get tool
        tool = self.tools.get(tool_name)
        if not tool:
            result = ToolResult(
                success=False,
                error=f"Tool not found: {tool_name}",
                suggestion="Use one of the available tools",
            )
            logger.tool_result(tool_name, False, None, result.error)

            # Show error to user
            if self.verbose:
                from vishwa.cli.ui import print_observation
                print_observation(result)

            return result

        # Check if trying to create a file that was already created this session
        if tool_name == "write_file":
            file_path = arguments.get("path", "")
            if self.context.was_file_created(file_path):
                result = ToolResult(
                    success=False,
                    error=f"File '{file_path}' was already created in this session",
                    suggestion="The file already exists. Use str_replace to modify it, or use a different filename.",
                )

                # Show error to user
                if self.verbose:
                    from vishwa.cli.ui import print_observation
                    print_observation(result)

                return result

        # Validate required parameters BEFORE execution
        # This catches missing parameters early with helpful error messages
        try:
            tool.validate_params(**arguments)
        except ValueError as e:
            # Parameter validation failed - provide helpful error to LLM
            error_msg = str(e)

            # Get the tool's parameter schema to help LLM fix the issue
            required_params = tool.parameters.get("required", [])
            provided_params = list(arguments.keys())
            missing_params = [p for p in required_params if p not in provided_params]

            helpful_error = f"{error_msg}\n\n"
            helpful_error += f"Required parameters for {tool_name}: {required_params}\n"
            helpful_error += f"Provided parameters: {provided_params}\n"

            if missing_params:
                helpful_error += f"\nMissing: {missing_params}\n"
                helpful_error += f"\nPlease call {tool_name} again with ALL required parameters."

            result = ToolResult(
                success=False,
                error=helpful_error,
                suggestion=f"Retry {tool_name} with all required parameters: {required_params}"
            )
            logger.tool_result(tool_name, False, None, result.error)
            return result

        # Execute tool
        try:
            result = tool.execute(**arguments)

            # Log tool result
            logger.tool_result(tool_name, result.success, result.output, result.error)

            # Track file creation and modifications
            if tool_name == "write_file" and result.success:
                file_path = arguments.get("path", "")
                self.context.mark_file_created(file_path)
                # Also track as modification for quality review
                self.context.track_modification(
                    file_path=file_path,
                    tool=tool_name,
                )

            # Track modifications
            if tool_name in ("str_replace", "multi_edit") and result.success:
                self.context.track_modification(
                    file_path=arguments.get("path", ""),
                    tool=tool_name,
                )

            # Post-edit quality check for Python files (if enabled)
            # Skip temp/test scripts to avoid unnecessary review overhead
            if self.enable_code_review and result.success and tool_name in ("str_replace", "write_file", "multi_edit"):
                file_path = arguments.get("path", "")
                if file_path.endswith(".py") and not self._should_skip_quality_check(file_path):
                    # Show UI feedback for quality check (user visibility only)
                    if self.verbose:
                        from vishwa.cli.ui import (
                            print_quality_check_start,
                            print_quality_passed,
                            print_quality_issues,
                        )
                        print_quality_check_start(file_path)

                    # Extract modified lines from tool result for targeted quality check
                    # This filters out pre-existing issues and only reports issues on modified code
                    modified_lines = None
                    if result.metadata:
                        # Use affected_lines (includes context) for quality check
                        # This catches issues that might be indirectly caused by the edit
                        modified_lines = result.metadata.get("affected_lines")

                    quality_result = self._check_code_quality(file_path, modified_lines)

                    if quality_result:
                        if quality_result.success:
                            if self.verbose:
                                print_quality_passed(file_path)
                        else:
                            # Show issues to user AND store for immediate fix
                            metadata = quality_result.metadata or {}
                            if self.verbose:
                                print_quality_issues(
                                    file_path,
                                    metadata.get("issues_count", 0),
                                    metadata.get("errors", 0),
                                    metadata.get("warnings", 0),
                                    metadata.get("issues")
                                )
                            # Only inject issues for actual ERRORS (not warnings/style issues)
                            # This prevents wasting iterations on minor style fixes like import sorting
                            error_count = metadata.get("errors", 0)
                            if error_count > 0:
                                attempts = self._file_quality_attempts.get(file_path, 0)
                                if attempts < self._max_file_quality_attempts:
                                    self._file_quality_attempts[file_path] = attempts + 1
                                    self._pending_quality_issues.append(
                                        (file_path, quality_result.error)
                                    )
                                elif attempts == self._max_file_quality_attempts:
                                    # First time hitting limit - log it and stop retrying
                                    self._file_quality_attempts[file_path] = attempts + 1
                                    if self.verbose:
                                        from vishwa.cli.ui import print_warning
                                        print_warning(f"Skipping further quality fixes for {os.path.basename(file_path)} (max attempts reached)")

            # Show tool result to user
            if self.verbose:
                from vishwa.cli.ui import print_observation
                print_observation(result)

            return result

        except Exception as e:
            result = ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}",
            )
            logger.tool_result(tool_name, False, None, result.error)
            logger.error("tool", f"Exception during {tool_name} execution", exception=e)

            # Show error to user
            if self.verbose:
                from vishwa.cli.ui import print_observation
                print_observation(result)

            return result

    def _should_skip_quality_check(self, file_path: str) -> bool:
        """
        Determine if a file should be skipped for quality checks.

        Skips temporary files, test scripts, and other files where
        quality checks add unnecessary overhead.

        Args:
            file_path: Path to the file to check

        Returns:
            True if the file should be skipped, False otherwise
        """
        # Skip test files
        if "/test_" in file_path or "test_" in file_path.split("/")[-1]:
            return True
        if "/tests/" in file_path:
            return True

        # Skip temporary/scratch files
        if "/tmp/" in file_path or "/temp/" in file_path:
            return True

        # Skip configuration and setup files
        if file_path.endswith(("conftest.py", "setup.py", "__init__.py")):
            return True

        return False

    def _check_code_quality(
        self,
        file_path: str,
        modified_lines: Optional[List[int]] = None
    ) -> Optional[ToolResult]:
        """
        Run code quality checks on a file after modification.

        Args:
            file_path: Path to the file to check
            modified_lines: Optional list of line numbers that were modified.
                           If provided, only issues on these lines will be reported.

        Returns:
            ToolResult with any issues found, or None if check skipped
        """
        try:
            from vishwa.tools.code_quality import CodeQualityTool
            quality_tool = CodeQualityTool()

            # Pass modified lines to filter results to only modified code
            kwargs = {"path": file_path}
            if modified_lines:
                kwargs["lines"] = modified_lines

            return quality_tool.execute(**kwargs)
        except Exception as e:
            # Don't fail the edit if quality check fails
            logger.warning("agent", f"Code quality check failed: {str(e)}")
            return None

    def _run_pre_completion_review(self) -> Optional[str]:
        """
        Run a final code quality review on all modified Python files.

        Uses the CodeReview sub-agent for comprehensive review with severity levels.
        This is called before finalizing success to catch any remaining issues.

        Returns:
            Tuple of (critical_issues, medium_issues) - either can be None if no issues
        """
        if not self.enable_code_review or self.skip_review:
            return None, None

        # Get all modified Python files
        # Modifications are Modification objects with file_path attribute
        py_files = [
            mod.file_path
            for mod in self.context.modifications
            if mod.file_path.endswith(".py") and not self._should_skip_quality_check(mod.file_path)
        ]

        if not py_files:
            return None, None

        # Remove duplicates while preserving order
        unique_files = list(dict.fromkeys(py_files))

        # Try to use CodeReview sub-agent if available
        task_tool = self.tools.get("task")
        if task_tool:
            try:
                # Build file list for review
                file_list = "\n".join(f"- {f}" for f in unique_files)

                # Run CodeReview sub-agent
                result = task_tool.execute(
                    subagent_type="CodeReview",
                    prompt=f"Review the following modified files for code quality issues:\n{file_list}",
                    description="Code review",
                    thoroughness="medium",
                )

                if result.success and result.output:
                    return self._parse_review_result(result.output)
                elif not result.success:
                    logger.warning("agent", f"CodeReview sub-agent failed: {result.error}")
                    # Fall back to linter-based review
            except Exception as e:
                logger.warning("agent", f"CodeReview sub-agent error: {str(e)}")
                # Fall back to linter-based review

        # Fallback: Use linter-based review (all issues treated as critical for backward compatibility)
        all_issues = []
        for file_path in unique_files:
            if not os.path.exists(file_path):
                continue
            result = self._check_code_quality(file_path)
            # Only enforce actual errors, not warnings/style issues
            if result and not result.success and result.metadata:
                error_count = result.metadata.get("errors", 0)
                if error_count > 0 and result.error:
                    all_issues.append(f"{file_path}:\n{result.error}")

        if all_issues:
            return "\n\n".join(all_issues), None  # All linter issues are critical
        return None, None

    def _parse_review_result(self, review_output: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse CodeReview sub-agent output into critical and medium issues.

        Args:
            review_output: The output from the CodeReview sub-agent

        Returns:
            Tuple of (critical_issues, medium_issues)
        """
        critical_issues = None
        medium_issues = None

        # Look for Critical Issues section
        if "### Critical Issues" in review_output or "Critical Issues (Must Fix)" in review_output:
            # Extract critical section
            critical_start = review_output.find("### Critical Issues")
            if critical_start == -1:
                critical_start = review_output.find("Critical Issues (Must Fix)")

            if critical_start != -1:
                # Find the end of critical section (next ### or end)
                critical_end = review_output.find("###", critical_start + 10)
                if critical_end == -1:
                    critical_end = review_output.find("### Medium", critical_start + 10)
                if critical_end == -1:
                    critical_end = review_output.find("### Overall", critical_start + 10)
                if critical_end == -1:
                    critical_end = len(review_output)

                critical_section = review_output[critical_start:critical_end].strip()

                # Check if there are actual issues (not just "No critical issues found")
                if critical_section and "no critical issues" not in critical_section.lower():
                    # Check if there's content beyond the header
                    lines = critical_section.split("\n")
                    content_lines = [l for l in lines[1:] if l.strip() and not l.strip().startswith("#")]
                    if content_lines:
                        critical_issues = critical_section

        # Look for Medium Issues section
        if "### Medium Issues" in review_output or "Medium Issues (Should Fix)" in review_output:
            medium_start = review_output.find("### Medium Issues")
            if medium_start == -1:
                medium_start = review_output.find("Medium Issues (Should Fix)")

            if medium_start != -1:
                # Find the end of medium section
                medium_end = review_output.find("###", medium_start + 10)
                if medium_end == -1:
                    medium_end = review_output.find("### Overall", medium_start + 10)
                if medium_end == -1:
                    medium_end = len(review_output)

                medium_section = review_output[medium_start:medium_end].strip()

                # Check if there are actual issues
                if medium_section and "no medium issues" not in medium_section.lower():
                    lines = medium_section.split("\n")
                    content_lines = [l for l in lines[1:] if l.strip() and not l.strip().startswith("#")]
                    if content_lines:
                        medium_issues = medium_section

        return critical_issues, medium_issues

    def _should_stop(self) -> bool:
        """
        Check if loop should stop.

        Returns:
            True if should stop
        """
        # Check if stuck in loop (same tool with same output/errors repeatedly)
        threshold = self.loop_detection_threshold
        if len(self.context.recent_tool_outputs) >= threshold:
            # Convert deque to list for slicing support
            recent_outputs_list = list(self.context.recent_tool_outputs)
            recent_tools = [out["tool"] for out in recent_outputs_list]

            # If last N tools are the same tool (where N = threshold)
            if len(set(recent_tools[-threshold:])) == 1:
                # Check if it's producing the same error or exact same output
                # (different outputs mean legitimate exploration, not a loop)
                recent_outputs = []
                for out in recent_outputs_list[-threshold:]:
                    # Use error if present, otherwise use output hash
                    if out.get("error"):
                        recent_outputs.append(("error", out.get("error")))
                    elif out.get("output"):
                        # For bash/read_file, check if output is identical
                        output_str = str(out.get("output", ""))
                        recent_outputs.append(("output", output_str[:500]))  # Compare first 500 chars
                    else:
                        recent_outputs.append(("none", ""))

                # Only consider stuck if outputs/errors are very similar
                # Allow up to 20% unique outputs (e.g., 3 unique out of 15)
                unique_outputs = set(recent_outputs)
                max_unique = max(2, threshold // 5)  # At least 2, or 20% of threshold
                if len(unique_outputs) <= max_unique:
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
