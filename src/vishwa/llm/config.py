"""
LLM configuration and model registry.

Defines available models and their mappings.
"""

from typing import Dict, List


class LLMConfig:
    """
    Central configuration for LLM models.

    Defines model names, aliases, and fallback chains.
    """

    # Model registry with full model names
    MODELS: Dict[str, str] = {
        # Claude models (Anthropic) - Latest as of 2025
        "claude-sonnet-4.5": "claude-sonnet-4-5",
        "claude-sonnet-4-5": "claude-sonnet-4-5",
        "claude-sonnet-4": "claude-sonnet-4",
        "claude-opus-4": "claude-opus-4",
        "claude-haiku-4": "claude-haiku-4",
        "claude-haiku-4-5": "claude-haiku-4-5",
        "claude-haiku-4-5": "claude-haiku-4-5",
        # Aliases
        "claude": "claude-sonnet-4-5",  # Default to latest
        "sonnet": "claude-sonnet-4-5",
        "opus": "claude-opus-4-1",
        "haiku": "claude-haiku-4-5",
        # OpenAI models
        "gpt-4o": "gpt-4o",
        "gpt-4-turbo": "gpt-4-turbo-2024-04-09",
        "gpt-4": "gpt-4",
        "o1": "o1",
        "o1-mini": "o1-mini",
        # Aliases
        "openai": "gpt-4o",
        # Ollama models (local)
        "llama3.1": "llama3.1",
        "llama3.1:8b": "llama3.1:8b",
        "llama3.1:70b": "llama3.1:70b",
        "codestral": "codestral:22b",
        "codestral:22b": "codestral:22b",
        "deepseek-coder": "deepseek-coder:33b",
        "deepseek-coder:33b": "deepseek-coder:33b",
        "qwen2.5-coder": "qwen2.5-coder:32b",
        "qwen2.5-coder:32b": "qwen2.5-coder:32b",
        # Aliases
        "local": "deepseek-coder:33b",
        "ollama": "deepseek-coder:33b",
    }

    # Provider detection patterns
    PROVIDER_PATTERNS: Dict[str, str] = {
        "claude": "anthropic",
        "gpt": "openai",
        "o1": "openai",
    }

    # Default fallback chains
    FALLBACK_CHAINS: Dict[str, List[str]] = {
        "quality": [
            "claude-sonnet-4-5",
            "gpt-4o",
            "deepseek-coder:33b",
        ],
        "cost": [
            "deepseek-coder:33b",
            "claude-haiku-4-5",
            "gpt-4o",
        ],
        "privacy": [
            "deepseek-coder:33b",
            "qwen2.5-coder:32b",
            "codestral:22b",
        ],
        "default": [
            "claude-sonnet-4-5",
            "gpt-4o",
            "deepseek-coder:33b",
        ],
    }

    # Default model
    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    # Default fallback chain name
    DEFAULT_FALLBACK_CHAIN = "default"

    @classmethod
    def resolve_model_name(cls, model_alias: str) -> str:
        """
        Resolve model alias to full model name.

        Args:
            model_alias: Model name or alias

        Returns:
            Full model name

        Examples:
            "claude" -> "claude-sonnet-4-20250514"
            "gpt-4o" -> "gpt-4o"
            "local" -> "deepseek-coder:33b"
        """
        return cls.MODELS.get(model_alias, model_alias)

    @classmethod
    def detect_provider(cls, model_name: str) -> str:
        """
        Detect provider from model name.

        Args:
            model_name: Full or partial model name

        Returns:
            Provider name: "anthropic", "openai", or "ollama"

        Examples:
            "claude-sonnet-4-20250514" -> "anthropic"
            "gpt-4o" -> "openai"
            "deepseek-coder:33b" -> "ollama"
        """
        model_lower = model_name.lower()

        # Check patterns
        for pattern, provider in cls.PROVIDER_PATTERNS.items():
            if pattern in model_lower:
                return provider

        # Check for Ollama models (contain : or are in known local models)
        if ":" in model_name or model_name in [
            "llama3.1",
            "codestral",
            "deepseek-coder",
            "qwen2.5-coder",
            "mistral-nemo",
        ]:
            return "ollama"

        # Default to OpenAI for unknown models
        return "openai"

    @classmethod
    def get_fallback_chain(cls, chain_name: str = "default") -> List[str]:
        """
        Get fallback chain by name.

        Args:
            chain_name: Chain name ("quality", "cost", "privacy", "default")

        Returns:
            List of model names to try in order
        """
        return cls.FALLBACK_CHAINS.get(
            chain_name, cls.FALLBACK_CHAINS["default"]
        )

    @classmethod
    def list_available_models(cls) -> Dict[str, List[str]]:
        """
        List all available models grouped by provider.

        Returns:
            Dict with provider names as keys and model lists as values
        """
        models_by_provider: Dict[str, List[str]] = {
            "anthropic": [],
            "openai": [],
            "ollama": [],
        }

        for model_name in set(cls.MODELS.values()):
            provider = cls.detect_provider(model_name)
            models_by_provider[provider].append(model_name)

        return models_by_provider
