"""
Deep logging system for Vishwa agent.

Provides structured, readable logging to track agent execution flow,
decisions, and outputs without cluttering the codebase.

Logs are automatically organized in date-stamped folders with separate
files for each log level:
  logs/YYYY-MM-DD/debug.log
  logs/YYYY-MM-DD/info.log
  logs/YYYY-MM-DD/warning.log
  logs/YYYY-MM-DD/error.log
"""

import logging
import json
import time
import os
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime


class VishwaLogger:
    """Centralized logger for tracking agent behavior and decisions."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.logger = logging.getLogger("vishwa")
            self.json_mode = False
            self.session_start = time.time()
            self.log_dir = None
            self._initialized = True

    def _get_default_log_dir(self) -> Path:
        """Get the default log directory path with today's date."""
        today = datetime.now().strftime("%Y-%m-%d")
        return Path("logs") / today

    def configure(
        self,
        level: str = "INFO",
        log_dir: Optional[str] = None,
        json_mode: bool = False,
        enable_logging: bool = True,
    ):
        """
        Configure logging output.

        Args:
            level: DEBUG, INFO, WARNING, ERROR (minimum level to log)
            log_dir: Optional directory for logs (default: logs/YYYY-MM-DD/)
            json_mode: Use JSON format for structured parsing
            enable_logging: Enable file logging (default: True)
        """
        if not enable_logging:
            return

        self.json_mode = json_mode
        self.logger.handlers.clear()

        # Set logger to DEBUG to capture all levels
        self.logger.setLevel(logging.DEBUG)

        # Determine log directory
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = self._get_default_log_dir()

        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Format: concise but informative
        if json_mode:
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s [%(component)-8s] %(message)s',
                datefmt='%H:%M:%S'
            )

        # Create separate handlers for each log level
        min_level = getattr(logging, level.upper(), logging.INFO)

        log_levels = [
            (logging.DEBUG, 'debug.log'),
            (logging.INFO, 'info.log'),
            (logging.WARNING, 'warning.log'),
            (logging.ERROR, 'error.log'),
        ]

        for log_level, filename in log_levels:
            # Only create handler if this level meets the minimum threshold
            if log_level >= min_level:
                log_path = self.log_dir / filename
                handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
                handler.setLevel(log_level)
                handler.setFormatter(formatter)

                # Add filter to only log exact level (not higher levels)
                handler.addFilter(lambda record, level=log_level: record.levelno == level)

                self.logger.addHandler(handler)

    def get_log_directory(self) -> Optional[Path]:
        """Get the current log directory path."""
        return self.log_dir

    def _log(self, level: str, component: str, msg: str, **data):
        """Core logging with structured data."""
        extra = {'component': component, **data}
        getattr(self.logger, level)(msg, extra=extra)

    # === AGENT FLOW ===

    def agent_start(self, task: str, max_iterations: int):
        self._log('info', 'AGENT', f"Starting: {task}",
                  task=task, max_iterations=max_iterations)

    def agent_iteration(self, iteration: int, max_iterations: int):
        separator = "=" * 60
        self._log('info', 'AGENT', f"\n{separator}")
        self._log('info', 'AGENT', f"ITERATION {iteration}/{max_iterations}")
        self._log('info', 'AGENT', f"{separator}")

    def agent_thinking(self, content: str):
        """Log what the agent is thinking/responding."""
        # Log full content - this is what logs are for!
        self._log('info', 'AGENT', f"Thinking: {content}")

    def agent_decision(self, decision: str, reason: str, **extra):
        self._log('info', 'AGENT', f"Decision: {decision} - {reason}",
                  decision=decision, reason=reason, **extra)

    def agent_complete(self, reason: str, iterations: int, success: bool):
        status = "SUCCESS" if success else "INCOMPLETE"
        self._log('info', 'AGENT', f"Complete [{status}]: {reason} ({iterations} iterations)",
                  reason=reason, iterations=iterations, success=success)

    # === LLM INTERACTIONS ===

    def llm_request(self, provider: str, model: str, msg_count: int, tool_count: int):
        self._log('debug', 'LLM', f"Request to {model} ({msg_count} messages, {tool_count} tools)",
                  provider=provider, model=model)

    def llm_response(self, model: str, tool_calls: int, tokens: Optional[Dict] = None):
        token_str = f", {tokens['total_tokens']} tokens" if tokens else ""
        self._log('info', 'LLM', f"Response: {tool_calls} tool calls{token_str}",
                  model=model, tool_calls=tool_calls, tokens=tokens)

    def llm_error(self, model: str, error: str):
        self._log('error', 'LLM', f"Error from {model}: {error}", model=model, error=error)

    # === TOOL EXECUTION ===

    def tool_start(self, name: str, args: Dict):
        # INFO: Just show what tool is being called with brief args
        args_str = ', '.join(f'{k}={repr(v)}' for k, v in args.items())
        self._log('info', 'TOOL', f"Calling {name}",
                  tool=name)
        # DEBUG: Full arguments for troubleshooting
        self._log('debug', 'TOOL', f"Calling {name}({args_str})",
                  tool=name, tool_args=args)

    def tool_result(self, name: str, success: bool, output: Optional[str], error: Optional[str]):
        status = "SUCCESS" if success else "FAILED"

        # INFO: Just show success/failure with size, not full output
        output_size = len(output) if output else (len(error) if error else 0)
        if success:
            self._log('info', 'TOOL', f"[{status}] {name} ({output_size} bytes)",
                      tool=name, success=success)
        else:
            # Show error summary in info
            error_preview = error[:100] if error else "unknown error"
            self._log('info', 'TOOL', f"[{status}] {name}: {error_preview}",
                      tool=name, success=success)

        # DEBUG: Full output for detailed analysis
        result = output if output else (error if error else "(no output)")
        self._log('debug', 'TOOL', f"[{status}] {name} output: {result}",
                  tool=name, success=success, output_length=output_size)

    def tool_approval(self, name: str, approved: bool, reason: str = ""):
        status = "Approved" if approved else "Rejected"
        self._log('info', 'TOOL', f"[{status}]: {name} {reason}",
                  tool=name, approved=approved, reason=reason)

    # === CONTEXT MANAGEMENT ===

    def context_tokens(self, current: int, max_tokens: int):
        pct = (current / max_tokens * 100) if max_tokens > 0 else 0
        self._log('debug', 'CONTEXT', f"Token usage: {current:,}/{max_tokens:,} ({pct:.0f}%)",
                  tokens=current, max_tokens=max_tokens, percentage=pct)

    def context_pruned(self, before: int, after: int):
        saved = before - after
        self._log('info', 'CONTEXT', f"Pruned: {before:,} -> {after:,} tokens (saved {saved:,})",
                  before=before, after=after, saved=saved)

    def context_file_mod(self, path: str, tool: str):
        self._log('info', 'CONTEXT', f"Modified: {path} (via {tool})",
                  file=path, tool=tool)

    def context_clear(self):
        self._log('info', 'CONTEXT', "Context cleared")

    # === ERRORS & WARNINGS ===

    def error(self, component: str, message: str, exception: Optional[Exception] = None):
        import traceback

        error_details = message
        if exception:
            # Get full traceback
            tb_str = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
            error_details = f"{message}\n{tb_str}"

        self._log('error', component.upper(), f"ERROR: {error_details}",
                  error=str(exception) if exception else message)

    def warning(self, component: str, message: str):
        self._log('warning', component.upper(), f"WARNING: {message}")


class JsonFormatter(logging.Formatter):
    """Minimal JSON formatter for machine parsing."""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            'time': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'component': getattr(record, 'component', 'SYSTEM'),
            'message': record.getMessage(),
        }
        # Add extra fields from record
        for k, v in record.__dict__.items():
            if k not in {'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                        'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                        'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                        'thread', 'threadName', 'processName', 'process', 'message',
                        'component', 'asctime'}:
                data[k] = v
        return json.dumps(data, default=str)


# Global instance
logger = VishwaLogger()
