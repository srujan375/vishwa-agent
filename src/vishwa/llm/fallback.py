"""
Fallback LLM with automatic retry logic.

DEPRECATED: This module is deprecated and will be removed in a future version.
Vishwa now uses single LLM instances without automatic fallback.

Tries multiple models in sequence if one fails.
"""

from typing import Any, Dict, List, Optional

from vishwa.llm.base import BaseLLM, LLMAPIError, LLMAuthenticationError
from vishwa.llm.factory import LLMFactory
from vishwa.llm.response import LLMResponse


class FallbackLLM(BaseLLM):
    """
    DEPRECATED: LLM with automatic fallback support.

    This class is deprecated and will be removed in a future version.
    Use LLMFactory.create() instead for single model instances.

    Tries models in sequence:
    1. Try primary model
    2. If fails, try next model in chain
    3. Continue until success or all models exhausted

    Example fallback chain:
    - Claude Sonnet 4 (best quality)
    - GPT-4o (fallback if Claude is down)
    - Ollama deepseek-coder (local fallback)
    """

    def __init__(
        self,
        models: List[str],
        max_retries: int = 3,
        **kwargs: Any,
    ):
        """
        Initialize fallback LLM.

        Args:
            models: List of model names to try in order
            max_retries: Max retries per model
            **kwargs: Additional parameters for providers
        """
        if not models:
            raise ValueError("At least one model must be specified")

        self.models = models
        self.max_retries = max_retries
        self.kwargs = kwargs

        # Track current provider
        self._current_provider: Optional[BaseLLM] = None
        self._current_model_index = 0

    @property
    def model_name(self) -> str:
        if self._current_provider:
            return self._current_provider.model_name
        return self.models[0]

    @property
    def provider_name(self) -> str:
        if self._current_provider:
            return self._current_provider.provider_name
        return "fallback"

    def supports_tools(self) -> bool:
        return True  # All our providers support tools

    def _get_next_provider(self, errors: list) -> Optional[BaseLLM]:
        """
        Get next provider in fallback chain.

        Args:
            errors: List to append initialization errors to

        Returns:
            BaseLLM instance or None if all exhausted
        """
        while self._current_model_index < len(self.models):
            model = self.models[self._current_model_index]
            self._current_model_index += 1

            try:
                # Create provider
                provider = LLMFactory.create(model, **self.kwargs)
                return provider

            except LLMAuthenticationError as e:
                # Skip models with missing API keys but log the error
                errors.append(f"{model}: Authentication failed - {str(e)}")
                continue

            except Exception as e:
                # Skip models that fail to initialize but log the error
                errors.append(f"{model}: Initialization failed - {str(e)}")
                continue

        return None

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Send chat request with automatic fallback.

        Args:
            messages: Conversation history
            tools: Optional tools
            system: Optional system prompt
            **kwargs: Additional parameters

        Returns:
            LLMResponse from first successful provider

        Raises:
            LLMAPIError: If all providers fail
        """
        errors: List[str] = []
        self._current_model_index = 0

        # Try each provider in sequence
        while True:
            provider = self._get_next_provider(errors)

            if provider is None:
                # All providers exhausted
                error_summary = "\n".join(errors) if errors else "No models could be initialized"
                raise LLMAPIError(
                    f"All models failed. Errors:\n{error_summary}"
                )

            # Try this provider
            for attempt in range(self.max_retries):
                try:
                    self._current_provider = provider

                    response = provider.chat(
                        messages=messages,
                        tools=tools,
                        system=system,
                        **kwargs,
                    )

                    # Success!
                    return response

                except LLMAuthenticationError as e:
                    # Don't retry auth errors, skip to next provider
                    errors.append(
                        f"{provider.model_name}: Authentication failed - {str(e)}"
                    )
                    break

                except LLMAPIError as e:
                    # Retry or move to next provider
                    error_msg = f"{provider.model_name}: {str(e)}"

                    if attempt < self.max_retries - 1:
                        # Retry
                        continue
                    else:
                        # Max retries reached, try next provider
                        errors.append(error_msg)
                        break

                except Exception as e:
                    # Unexpected error, try next provider
                    errors.append(
                        f"{provider.model_name}: Unexpected error - {str(e)}"
                    )
                    break
