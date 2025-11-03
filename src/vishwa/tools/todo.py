"""
Task management tool for tracking progress.

Provides TodoWrite functionality for organizing work.
"""

from typing import Any, Dict, List

from vishwa.tools.base import Tool, ToolResult


class TodoWriteTool(Tool):
    """
    Create and manage a structured task list.

    Helps track progress, organize complex tasks, and provide user visibility.
    """

    # Class variable to store todos across calls
    _todos: List[Dict[str, str]] = []

    @property
    def name(self) -> str:
        return "todo_write"

    @property
    def description(self) -> str:
        return """Create and manage a structured task list for your current coding session.

This helps you:
- Track progress through complex multi-step tasks
- Organize work and demonstrate thoroughness
- Give the user visibility into what you're doing

WHEN TO USE:
- Complex multi-step tasks (3+ distinct steps)
- Non-trivial tasks requiring careful planning
- User explicitly requests a todo list
- User provides multiple tasks (numbered or comma-separated)
- After receiving new instructions - capture requirements as todos
- When you start working on a task - mark it in_progress BEFORE beginning
- After completing a task - mark it completed and add any follow-up tasks

WHEN NOT TO USE:
- Single straightforward task
- Trivial task completable in < 3 steps
- Purely conversational/informational requests

Task States:
- pending: Not yet started
- in_progress: Currently working (limit to ONE task at a time)
- completed: Finished successfully

IMPORTANT:
- Each task needs two forms:
  * content: Imperative form (e.g., "Run tests")
  * activeForm: Present continuous (e.g., "Running tests")
- Mark tasks completed IMMEDIATELY after finishing
- Have exactly ONE task in_progress at any time

Example:
todos = [
    {"content": "Read the file", "activeForm": "Reading the file", "status": "completed"},
    {"content": "Apply the changes", "activeForm": "Applying the changes", "status": "in_progress"},
    {"content": "Run tests", "activeForm": "Running tests", "status": "pending"}
]
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "The updated todo list",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "minLength": 1,
                                "description": "Task description in imperative form",
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "Task status",
                            },
                            "activeForm": {
                                "type": "string",
                                "minLength": 1,
                                "description": "Task description in present continuous form",
                            },
                        },
                        "required": ["content", "status", "activeForm"],
                    },
                },
            },
            "required": ["todos"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Update the todo list.

        Args:
            todos: List of todo items with content, status, and activeForm

        Returns:
            ToolResult with updated todo list
        """
        self.validate_params(**kwargs)
        todos = kwargs["todos"]

        # Update class variable
        TodoWriteTool._todos = todos

        # Validate exactly one in_progress (if any todos exist)
        if todos:
            in_progress_count = sum(1 for t in todos if t["status"] == "in_progress")
            if in_progress_count > 1:
                return ToolResult(
                    success=False,
                    error=f"Multiple tasks in_progress ({in_progress_count})",
                    suggestion="Have exactly ONE task in_progress at a time",
                )

        # Count by status
        completed = sum(1 for t in todos if t["status"] == "completed")
        in_progress = sum(1 for t in todos if t["status"] == "in_progress")
        pending = sum(1 for t in todos if t["status"] == "pending")

        # Format output
        output_lines = [f"Todo list updated: {len(todos)} total tasks"]
        output_lines.append(f"  ✓ Completed: {completed}")
        output_lines.append(f"  → In Progress: {in_progress}")
        output_lines.append(f"  ○ Pending: {pending}")

        # Show current task
        current = next((t for t in todos if t["status"] == "in_progress"), None)
        if current:
            output_lines.append(f"\nCurrent: {current['activeForm']}")

        return ToolResult(
            success=True,
            output="\n".join(output_lines),
            metadata={
                "total": len(todos),
                "completed": completed,
                "in_progress": in_progress,
                "pending": pending,
                "todos": todos,
            },
        )

    @classmethod
    def get_todos(cls) -> List[Dict[str, str]]:
        """Get the current todo list."""
        return cls._todos

    @classmethod
    def clear_todos(cls):
        """Clear the todo list."""
        cls._todos = []
