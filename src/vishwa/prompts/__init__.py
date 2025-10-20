"""
Prompt templates for Vishwa agent.

Prompts are stored as text files with placeholders that can be customized.
"""

import platform
from pathlib import Path
from typing import Dict, Any


class PromptLoader:
    """Load and format prompt templates"""

    def __init__(self):
        self.prompts_dir = Path(__file__).parent

    def load_system_prompt(self, **kwargs: Any) -> str:
        """
        Load and format the system prompt.

        Args:
            **kwargs: Variables to substitute in the prompt template

        Returns:
            Formatted system prompt string

        Template variables:
            - tools_description: Description of available tools
            - working_directory: Current working directory
            - files_in_context: List of files currently in context
            - modifications_count: Number of modifications made
            - current_iteration: Current iteration number
            - max_iterations: Maximum iterations allowed
            - task: The user's task
        """
        template_path = self.prompts_dir / "system_prompt.txt"
        template = template_path.read_text(encoding="utf-8")
        return template.format(**kwargs)

    def load_platform_commands(self) -> str:
        """
        Load platform-specific command guidance.

        Returns:
            Platform-appropriate command instructions
        """
        system = platform.system()

        if system == "Windows":
            template_path = self.prompts_dir / "platform_windows.txt"
        else:  # Unix-like (Linux, macOS, etc.)
            template_path = self.prompts_dir / "platform_unix.txt"

        return template_path.read_text(encoding="utf-8")

    def load_custom_prompt(self, prompt_name: str, **kwargs: Any) -> str:
        """
        Load a custom prompt template.

        Args:
            prompt_name: Name of the prompt file (without .txt extension)
            **kwargs: Variables to substitute in the prompt

        Returns:
            Formatted prompt string
        """
        template_path = self.prompts_dir / f"{prompt_name}.txt"

        if not template_path.exists():
            raise FileNotFoundError(
                f"Prompt template not found: {prompt_name}.txt\n"
                f"Create it at: {template_path}"
            )

        template = template_path.read_text(encoding="utf-8")
        return template.format(**kwargs)


# Global instance
_loader = PromptLoader()


def get_system_prompt(**kwargs: Any) -> str:
    """
    Get the system prompt with variables filled in.

    This is the main function to use for loading prompts.

    Args:
        **kwargs: Variables to substitute

    Returns:
        Formatted system prompt
    """
    return _loader.load_system_prompt(**kwargs)


def get_platform_commands() -> str:
    """
    Get platform-specific command guidance.

    Returns:
        Platform-appropriate command instructions
    """
    return _loader.load_platform_commands()


def get_custom_prompt(prompt_name: str, **kwargs: Any) -> str:
    """
    Get a custom prompt template.

    Args:
        prompt_name: Name of the prompt file
        **kwargs: Variables to substitute

    Returns:
        Formatted prompt
    """
    return _loader.load_custom_prompt(prompt_name, **kwargs)


__all__ = ["get_system_prompt", "get_platform_commands", "get_custom_prompt", "PromptLoader"]
