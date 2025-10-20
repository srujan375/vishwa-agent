"""
OpenAI LLM provider.

Supports GPT-4, GPT-4 Turbo, GPT-4o, and other OpenAI models.
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

    Uses the official OpenAI Python SDK.
    """

    # Context limits for different models
    CONTEXT_LIMITS = {
        "gpt-4o": 128000,
        "gpt-4-turbo": 128000,
        "gpt-4-turbo-2024-04-09": 128000,
        "gpt-4": 8192,
        "gpt-4-32k": 32768,
        "o1": 128000,
        "o1-mini": 128000,
    }

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: int = 4096,
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
        Send chat request to OpenAI.

        Args:
            messages: Conversation history
            tools: Optional tools in OpenAI format
            system: Optional system prompt
            **kwargs: Additional OpenAI parameters

        Returns:
            LLMResponse with unified format

        Raises:
            LLMAPIError: If API call fails
        """
        try:
            # Prepare messages
            formatted_messages = []

            # Add system message if provided
            if system:
                formatted_messages.append({"role": "system", "content": system})

            # Add conversation messages
            formatted_messages.extend(messages)

            # Prepare API call parameters
            api_params = {
                "model": self.model,
                "messages": formatted_messages,
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "temperature": kwargs.get("temperature", self.temperature),
            }

            # Add tools if provided
            if tools:
                api_params["tools"] = tools
                # Default to auto tool choice
                api_params["tool_choice"] = kwargs.get("tool_choice", "auto")

            # Make API call
            response = self.client.chat.completions.create(**api_params)

            # Convert to unified format
            return LLMResponse.from_openai(response)

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
