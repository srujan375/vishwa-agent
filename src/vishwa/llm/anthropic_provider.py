"""
Anthropic Claude LLM provider.

Supports Claude 3.5 Sonnet, Opus, and Haiku models.
Converts between OpenAI format (internal) and Claude format (API).
"""

import os
from typing import Any, Dict, List, Optional

from anthropic import Anthropic, AnthropicError

from vishwa.llm.base import (
    BaseLLM,
    LLMAPIError,
    LLMAuthenticationError,
    LLMContextLengthError,
    LLMRateLimitError,
)
from vishwa.llm.response import LLMResponse


class AnthropicProvider(BaseLLM):
    """
    Anthropic Claude LLM provider.

    Handles conversion between OpenAI format (internal standard)
    and Claude's native format.
    """

    # Context limits for Claude models
    CONTEXT_LIMITS = {
        "claude-sonnet-4-5": 200000,  # Supports 1M with beta header
        "claude-sonnet-4": 200000,
        "claude-opus-4": 200000,
        "claude-haiku-4": 200000,
        "claude-3-5-sonnet-20241022": 200000,
        "claude-3-5-haiku-20241022": 200000,
    }

    def __init__(
        self,
        model: str = "claude-sonnet-4-5",
        api_key: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        """
        Initialize Claude provider.

        Args:
            model: Claude model name
            api_key: Anthropic API key (default: from ANTHROPIC_API_KEY env var)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 1.0)
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Initialize Anthropic client
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMAuthenticationError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY environment variable."
            )

        self.client = Anthropic(api_key=api_key)

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def supports_tools(self) -> bool:
        return True

    def get_max_tokens(self) -> Optional[int]:
        """Get context limit for current model"""
        return self.CONTEXT_LIMITS.get(self.model)

    def _convert_tools_to_claude_format(
        self, tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Convert tools from OpenAI format to Claude format.

        OpenAI format:
        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": {...}
            }
        }

        Claude format:
        {
            "name": "...",
            "description": "...",
            "input_schema": {...}
        }
        """
        claude_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                claude_tools.append({
                    "name": func["name"],
                    "description": func["description"],
                    "input_schema": func["parameters"],  # Key change: parameters → input_schema
                })
        return claude_tools

    def _convert_messages_to_claude_format(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Convert messages from OpenAI format to Claude format.

        Main difference: tool results
        - OpenAI: role="tool", content="...", tool_call_id="..."
        - Claude: role="user", content=[{"type": "tool_result", "tool_use_id": "...", "content": "..."}]
        """
        claude_messages = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "tool":
                # Convert tool result to Claude format
                claude_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_call_id", ""),
                            "content": content,
                        }
                    ],
                })
            elif role == "assistant" and isinstance(content, list):
                # Assistant message with tool calls (already in Claude format from previous response)
                claude_messages.append(msg)
            else:
                # Regular message
                claude_messages.append({"role": role, "content": content})

        return claude_messages

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Send chat request to Claude.

        Args:
            messages: Conversation history (OpenAI format)
            tools: Optional tools (OpenAI format)
            system: Optional system prompt
            **kwargs: Additional Claude parameters

        Returns:
            LLMResponse with unified format

        Raises:
            LLMAPIError: If API call fails
        """
        try:
            # Convert messages to Claude format
            claude_messages = self._convert_messages_to_claude_format(messages)

            # Prepare API call parameters
            api_params = {
                "model": self.model,
                "messages": claude_messages,
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "temperature": kwargs.get("temperature", self.temperature),
            }

            # Add system prompt if provided
            if system:
                api_params["system"] = system

            # Add tools if provided (convert to Claude format)
            if tools:
                claude_tools = self._convert_tools_to_claude_format(tools)
                api_params["tools"] = claude_tools

            # Make API call
            response = self.client.messages.create(**api_params)

            # Convert to unified format
            return LLMResponse.from_anthropic(response)

        except AnthropicError as e:
            error_msg = str(e)

            # Map to specific error types
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                raise LLMAuthenticationError(f"Claude authentication failed: {error_msg}")

            elif "rate limit" in error_msg.lower():
                raise LLMRateLimitError(f"Claude rate limit exceeded: {error_msg}")

            elif "context" in error_msg.lower() or "too long" in error_msg.lower():
                raise LLMContextLengthError(f"Context too long: {error_msg}")

            else:
                raise LLMAPIError(f"Claude API error: {error_msg}")

        except Exception as e:
            raise LLMAPIError(f"Unexpected error calling Claude: {str(e)}")
