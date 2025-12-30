"""
Novita AI and OpenRouter LLM provider.

Supports OpenAI-compatible APIs from Novita AI and OpenRouter.
Uses model prefix to determine which service to use:
- openrouter:model/name -> OpenRouter API
- model/name -> Novita API (default)
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
    Novita AI and OpenRouter LLM provider.

    Uses OpenAI-compatible APIs. Detects service from model prefix:
    - openrouter:model/name -> OpenRouter API
    - model/name -> Novita API (default)
    """

    # Base URLs for different services
    BASE_URLS = {
        "novita": "https://api.novita.ai/v3/openai",
        "openrouter": "https://openrouter.ai/api/v1",
    }

    # Context limits for different models
    CONTEXT_LIMITS = {
        # Novita models
        "moonshotai/kimi-k2-thinking": 128000,
        "minimax/minimax-m2": 128000,
        "deepseek/deepseek-v3.2-exp": 64000,
        "zai-org/glm-4.6": 128000,
        # OpenRouter models (add as needed)
        "openrouter:openai/gpt-4o": 128000,
        "openrouter:anthropic/claude-sonnet-4": 200000,
        "openrouter:google/gemini-2.5-pro": 1000000,
    }

    def __init__(
        self,
        model: str = "deepseek/deepseek-v3.2-exp",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ):
        """
        Initialize Novita/OpenRouter provider.

        Args:
            model: Model name. Use 'openrouter:' prefix for OpenRouter models
                   (e.g., 'openrouter:openai/gpt-4o', 'deepseek/deepseek-v3.2-exp')
            api_key: API key (default: from OPENROUTER_API_KEY or NOVITA_API_KEY env var)
            base_url: Optional custom base URL (auto-detected if not provided)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 2.0)
        """
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Detect service from model prefix
        if model.startswith("openrouter:"):
            self._service = "openrouter"
            self.model = model[len("openrouter:"):]  # Strip prefix for API calls
            self._original_model = model  # Keep original for reference
            env_key = "OPENROUTER_API_KEY"
            default_base_url = self.BASE_URLS["openrouter"]
        else:
            self._service = "novita"
            self.model = model
            self._original_model = model
            env_key = "NOVITA_API_KEY"
            default_base_url = self.BASE_URLS["novita"]

        # Get API key
        api_key = api_key or os.getenv(env_key)
        if not api_key:
            raise LLMAuthenticationError(
                f"{self._service.capitalize()} API key not found. Set {env_key} environment variable."
            )

        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url or default_base_url,
        )

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def provider_name(self) -> str:
        return self._service

    def supports_tools(self) -> bool:
        return True

    def get_max_tokens(self) -> Optional[int]:
        """Get context limit for current model"""
        # Check both with and without prefix
        return self.CONTEXT_LIMITS.get(self._original_model) or self.CONTEXT_LIMITS.get(self.model)

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
            service_name = self._service.capitalize()

            # Map to specific error types
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower():
                raise LLMAuthenticationError(f"{service_name} authentication failed: {error_msg}")

            elif "rate limit" in error_msg.lower():
                raise LLMRateLimitError(f"{service_name} rate limit exceeded: {error_msg}")

            elif "context length" in error_msg.lower() or "maximum context" in error_msg.lower():
                raise LLMContextLengthError(f"Context too long: {error_msg}")

            else:
                raise LLMAPIError(f"{service_name} API error: {error_msg}")

        except Exception as e:
            raise LLMAPIError(f"Unexpected error calling {self._service}: {str(e)}")
