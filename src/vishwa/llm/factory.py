"""
LLM Factory for creating provider instances.

Handles provider selection, instantiation, and fallback logic.
"""

import os
from typing import TYPE_CHECKING, Optional

from vishwa.llm.anthropic_provider import AnthropicProvider
from vishwa.llm.base import BaseLLM, LLMAuthenticationError
from vishwa.llm.config import LLMConfig
from vishwa.llm.ollama_provider import OllamaProvider
from vishwa.llm.openai_provider import OpenAIProvider

if TYPE_CHECKING:
    from vishwa.llm.fallback import FallbackLLM


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
            # Check if Ollama model is available, offer to pull if not
            if not OllamaProvider.is_ollama_running():
                raise LLMAuthenticationError(
                    "Ollama is not running. Install from https://ollama.com/download"
                )

            if not OllamaProvider.is_model_available(full_model_name):
                # Model not available - offer to pull it
                print(f"\nOllama model '{full_model_name}' not found locally.")

                # Auto-pull if environment variable is set
                auto_pull = os.getenv("VISHWA_AUTO_PULL_OLLAMA", "").lower() in ("true", "1", "yes")

                if auto_pull:
                    print("Auto-pulling model (VISHWA_AUTO_PULL_OLLAMA=true)...")
                    if not OllamaProvider.pull_model(full_model_name, show_progress=True):
                        raise LLMAuthenticationError(
                            f"Failed to pull Ollama model: {full_model_name}"
                        )
                else:
                    # Ask user
                    try:
                        response = input(f"Pull '{full_model_name}' now? [Y/n]: ").strip().lower()
                        if response in ("", "y", "yes"):
                            if not OllamaProvider.pull_model(full_model_name, show_progress=True):
                                raise LLMAuthenticationError(
                                    f"Failed to pull Ollama model: {full_model_name}"
                                )
                        else:
                            raise LLMAuthenticationError(
                                f"Ollama model '{full_model_name}' not available. "
                                f"Pull it with: ollama pull {full_model_name}"
                            )
                    except (KeyboardInterrupt, EOFError):
                        print("\nCancelled.")
                        raise LLMAuthenticationError(
                            f"Ollama model '{full_model_name}' not available"
                        )

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
        DEPRECATED: Create an LLM with automatic fallback support.

        This method is deprecated. Use LLMFactory.create() instead.
        Fallback logic has been removed from Vishwa.

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
        import warnings
        warnings.warn(
            "create_with_fallback is deprecated. Use LLMFactory.create() instead.",
            DeprecationWarning,
            stacklevel=2
        )

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
