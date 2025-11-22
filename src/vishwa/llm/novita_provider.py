"""
Novita AI LLM provider.

Supports Novita AI's OpenAI-compatible API for various open-source models.
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


class NovitaProvider(BaseLLM):
    """
    Novita AI LLM provider.

    Uses the OpenAI-compatible API provided by Novita AI.
    """

    # Context limits for different models
    CONTEXT_LIMITS = {
        "moonshotai/kimi-k2-thinking": 128000,
        "minimax/minimax-m2": 128000,
        "deepseek/deepseek-v3.2-exp": 64000,
        "zai-org/glm-4.6": 128000,
    }

    def __init__(
        self,
        model: str = "deepseek/deepseek-v3.2-exp",
        api_key: Optional[str] = None,
        base_url: str = "https://api.novita.ai/v3/openai",
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ):
        """
        Initialize Novita provider.

        Args:
            model: Model name (e.g., 'deepseek/deepseek-v3.2-exp')
            api_key: Novita API key (default: from NOVITA_API_KEY env var)
            base_url: Novita API base URL
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 2.0)
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Initialize OpenAI client with Novita base URL
        api_key = api_key or os.getenv("NOVITA_API_KEY")
        if not api_key:
            raise LLMAuthenticationError(
                "Novita API key not found. Set NOVITA_API_KEY environment variable."
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
        return "novita"

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
        Send chat request to Novita AI.

        Args:
            messages: Conversation history
            tools: Optional tools in OpenAI format
            system: Optional system prompt
            **kwargs: Additional API parameters

        Returns:
            LLMResponse with unified format

        Raises:
            LLMAPIError: If API call fails
        """
        try:
            # Build messages array
            api_messages = []

            # Add system message if provided
            if system:
                api_messages.append({"role": "system", "content": system})

            # Add conversation messages
            api_messages.extend(messages)

            # Prepare API call parameters
            api_params = {
                "model": self.model,
                "messages": api_messages,
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "temperature": kwargs.get("temperature", self.temperature),
            }

            # Add tools if provided
            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = kwargs.get("tool_choice", "auto")

            # Make API call
            response = self.client.chat.completions.create(**api_params)

            # Convert to unified format
            return LLMResponse.from_openai(response)

        except OpenAIError as e:
            error_msg = str(e)

            # Map to specific error types
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                raise LLMAuthenticationError(f"Novita authentication failed: {error_msg}")

            elif "rate limit" in error_msg.lower():
                raise LLMRateLimitError(f"Novita rate limit exceeded: {error_msg}")

            elif "context length" in error_msg.lower() or "maximum context" in error_msg.lower():
                raise LLMContextLengthError(f"Context too long: {error_msg}")

            else:
                raise LLMAPIError(f"Novita API error: {error_msg}")

        except Exception as e:
            raise LLMAPIError(f"Unexpected error calling Novita: {str(e)}")
