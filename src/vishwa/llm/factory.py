"""
LLM Factory for creating provider instances.

Handles provider selection, instantiation, and fallback logic.
"""

from typing import Optional

from vishwa.llm.anthropic_provider import AnthropicProvider
from vishwa.llm.base import BaseLLM, LLMAuthenticationError
from vishwa.llm.config import LLMConfig
from vishwa.llm.ollama_provider import OllamaProvider
from vishwa.llm.openai_provider import OpenAIProvider


class LLMFactory:
    """
    Factory for creating LLM provider instances.

    Handles:
    - Model name resolution (aliases -> full names)
    - Provider detection (anthropic, openai, ollama)
    - Provider instantiation with configuration
    """

    @staticmethod
    def create(
        model: Optional[str] = None,
        **kwargs,
    ) -> BaseLLM:
        """
        Create an LLM provider instance.

        Args:
            model: Model name or alias (default: from config)
            **kwargs: Additional provider-specific parameters

        Returns:
            BaseLLM instance (OpenAIProvider, AnthropicProvider, or OllamaProvider)

        Raises:
            LLMAuthenticationError: If API key is missing
            ValueError: If provider is unknown

        Examples:
            >>> llm = LLMFactory.create("claude")  # Claude Sonnet 4
            >>> llm = LLMFactory.create("gpt-4o")
            >>> llm = LLMFactory.create("local")  # Ollama deepseek-coder
        """
        # Resolve model name
        model_alias = model or LLMConfig.DEFAULT_MODEL
        full_model_name = LLMConfig.resolve_model_name(model_alias)

        # Detect provider
        provider_name = LLMConfig.detect_provider(full_model_name)

        # Create provider instance
        if provider_name == "anthropic":
            return AnthropicProvider(model=full_model_name, **kwargs)

        elif provider_name == "openai":
            return OpenAIProvider(model=full_model_name, **kwargs)

        elif provider_name == "ollama":
            return OllamaProvider(model=full_model_name, **kwargs)

        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    @staticmethod
    def create_with_fallback(
        primary_model: Optional[str] = None,
        fallback_chain: str = "default",
        **kwargs,
    ) -> "FallbackLLM":
        """
        Create an LLM with automatic fallback support.

        Args:
            primary_model: Primary model to try first
            fallback_chain: Fallback chain name ("quality", "cost", "privacy", "default")
            **kwargs: Additional provider-specific parameters

        Returns:
            FallbackLLM instance with retry logic

        Examples:
            >>> llm = LLMFactory.create_with_fallback()  # Use default chain
            >>> llm = LLMFactory.create_with_fallback(fallback_chain="cost")
        """
        from vishwa.llm.fallback import FallbackLLM

        # Get fallback chain
        chain = LLMConfig.get_fallback_chain(fallback_chain)

        # If primary model specified, put it first
        if primary_model:
            full_model = LLMConfig.resolve_model_name(primary_model)
            if full_model not in chain:
                chain = [full_model] + chain

        return FallbackLLM(models=chain, **kwargs)

    @staticmethod
    def list_models() -> dict:
        """
        List all available models grouped by provider.

        Returns:
            Dict with provider names as keys
        """
        return LLMConfig.list_available_models()

    @staticmethod
    def check_ollama() -> bool:
        """
        Check if Ollama is running and accessible.

        Returns:
            bool: True if Ollama is available
        """
        return OllamaProvider.is_ollama_running()
