"""
OpenAI LLM provider.

Supports GPT-5, GPT-5.1, GPT-4.1, and other OpenAI models using the Responses API.
"""

import os
from typing import Any, Dict, List, Optional

from openai import OpenAI, OpenAIError

from vishwa.llm.base import (
    BaseLLM,
    LLMAPIError,
    LLMAuthenticationError,
    LLMContextLengthError,
    LLMRateLimitError,
)
from vishwa.llm.response import LLMResponse


class OpenAIProvider(BaseLLM):
    """
    OpenAI LLM provider.

    Uses the official OpenAI Python SDK with the Responses API.
    """

    # Context limits for different models
    CONTEXT_LIMITS = {
        "gpt-5.1": 200000,
        "gpt-5.1-pro": 200000,
        "gpt-5-pro-2025-10-06": 200000,
        "gpt-5-2025-08-07": 200000,
        "gpt-4.1-2025-04-14": 128000,
        "gpt-4o": 128000,
        "gpt-4-turbo": 128000,
        "gpt-4-turbo-2024-04-09": 128000,
        "gpt-4": 8192,
        "gpt-4-32k": 32768,
    }

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ):
        """
        Initialize OpenAI provider.

        Args:
            model: Model name (e.g., 'gpt-4o', 'gpt-4-turbo')
            api_key: OpenAI API key (default: from OPENAI_API_KEY env var)
            base_url: Optional custom base URL
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 2.0)
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Initialize OpenAI client
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMAuthenticationError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
            )

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def provider_name(self) -> str:
        return "openai"

    def supports_tools(self) -> bool:
        return True

    def get_max_tokens(self) -> Optional[int]:
        """Get context limit for current model"""
        return self.CONTEXT_LIMITS.get(self.model)

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Send chat request to OpenAI using Responses API.

        Args:
            messages: Conversation history
            tools: Optional tools in OpenAI format
            system: Optional system prompt (used as developer instructions)
            **kwargs: Additional OpenAI parameters

        Returns:
            LLMResponse with unified format

        Raises:
            LLMAPIError: If API call fails
        """
        try:
            # Convert messages to Responses API format
            input_messages = []

            # Add conversation messages
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")

                # Map roles: assistant stays assistant, system/user become user
                if role == "assistant":
                    input_messages.append({"role": "assistant", "content": content})
                else:
                    # Both system and user messages become user messages in Responses API
                    input_messages.append({"role": "user", "content": content})

            # Prepare API call parameters
            api_params = {
                "model": self.model,
                "input": input_messages,
            }

            # Add developer instructions (system prompt) if provided
            if system:
                api_params["instructions"] = system

            # Add max_output_tokens (Responses API uses this instead of max_tokens)
            api_params["max_output_tokens"] = kwargs.get("max_output_tokens", self.max_tokens)

            # Add temperature - only supported for GPT-5.1 with reasoning effort "none"
            # GPT-5, GPT-5-mini, GPT-5-nano do NOT support temperature at all
            supports_temperature = False
            if self.model.startswith("gpt-5.1"):
                # GPT-5.1 supports temperature only with reasoning effort "none"
                reasoning_effort = kwargs.get("reasoning", {}).get("effort", "none") if isinstance(kwargs.get("reasoning"), dict) else "none"
                if reasoning_effort == "none":
                    supports_temperature = True

            if supports_temperature:
                if "temperature" in kwargs:
                    api_params["temperature"] = kwargs["temperature"]
                elif self.temperature:
                    api_params["temperature"] = self.temperature

            # Add tools if provided (convert from Chat Completions format to Responses API format)
            if tools:
                api_params["tools"] = self._convert_tools_format(tools)

            # Make API call using Responses API
            response = self.client.responses.create(**api_params)

            # Convert to unified format
            return self._convert_response(response)

        except OpenAIError as e:
            error_msg = str(e)

            # Map to specific error types
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                raise LLMAuthenticationError(f"OpenAI authentication failed: {error_msg}")

            elif "rate limit" in error_msg.lower():
                raise LLMRateLimitError(f"OpenAI rate limit exceeded: {error_msg}")

            elif "context length" in error_msg.lower() or "maximum context" in error_msg.lower():
                raise LLMContextLengthError(f"Context too long: {error_msg}")

            else:
                raise LLMAPIError(f"OpenAI API error: {error_msg}")

        except Exception as e:
            raise LLMAPIError(f"Unexpected error calling OpenAI: {str(e)}")

    def _convert_tools_format(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert tools from Chat Completions format to Responses API format.

        Chat Completions format:
        {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "...",
                "parameters": {...}
            }
        }

        Responses API format:
        {
            "type": "function",
            "name": "tool_name",
            "description": "...",
            "parameters": {...}
        }

        Args:
            tools: Tools in Chat Completions format

        Returns:
            Tools in Responses API format
        """
        converted_tools = []
        for tool in tools:
            if tool.get("type") == "function" and "function" in tool:
                # Flatten the nested structure
                func = tool["function"]
                converted_tools.append({
                    "type": "function",
                    "name": func.get("name"),
                    "description": func.get("description"),
                    "parameters": func.get("parameters", {}),
                })
            else:
                # Already in correct format or unknown type, pass through
                converted_tools.append(tool)

        return converted_tools

    def _convert_response(self, response: Any) -> LLMResponse:
        """
        Convert Responses API response to unified LLMResponse format.

        Args:
            response: OpenAI Responses API response

        Returns:
            LLMResponse with unified format
        """
        from vishwa.llm.response import ToolCall, Usage
        import json

        # Use the convenient output_text property for simple text responses
        content_text = getattr(response, "output_text", None)

        # Extract tool calls from output
        tool_calls = []
        if hasattr(response, "output") and response.output:
            for output_item in response.output:
                # Check if this is a function call
                if hasattr(output_item, "type") and output_item.type == "function_call":
                    tool_calls.append(
                        ToolCall(
                            id=getattr(output_item, "call_id", ""),
                            name=output_item.name,
                            arguments=json.loads(output_item.arguments)
                            if isinstance(output_item.arguments, str)
                            else output_item.arguments,
                        )
                    )
                # Also check for text content in message-type outputs if output_text wasn't set
                elif not content_text and hasattr(output_item, "content") and output_item.content:
                    for content_block in output_item.content:
                        if hasattr(content_block, "text"):
                            if content_text is None:
                                content_text = content_block.text
                            else:
                                content_text += content_block.text

        # Extract usage information
        # Responses API uses: prompt_tokens, completion_tokens, total_tokens (same as Chat Completions)
        usage_obj = None
        if hasattr(response, "usage") and response.usage:
            usage_obj = Usage(
                prompt_tokens=getattr(response.usage, "prompt_tokens", 0),
                completion_tokens=getattr(response.usage, "completion_tokens", 0),
                total_tokens=getattr(response.usage, "total_tokens", 0),
            )

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            finish_reason=getattr(response, "finish_reason", "stop"),
            model=getattr(response, "model", self.model),
            usage=usage_obj,
            raw_response=response,
        )
