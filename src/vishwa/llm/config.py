"""
LLM configuration and model registry.

Defines available models and their mappings.
Loads from models.json for easy configuration.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


class LLMConfig:
    """
    Central configuration for LLM models.

    Loads configuration from models.json in project root.
    Falls back to hardcoded defaults if file not found.
    """

    # Cache for loaded config
    _config_cache: Optional[Dict] = None

    @classmethod
    def _load_config(cls) -> Dict:
        """Load models configuration from JSON file."""
        if cls._config_cache is not None:
            return cls._config_cache

        # Try to find models.json in project root
        config_paths = [
            Path.cwd() / "models.json",  # Current directory
            Path(__file__).parent.parent.parent.parent / "models.json",  # Project root
            Path.home() / ".vishwa" / "models.json",  # User home
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        cls._config_cache = json.load(f)
                        return cls._config_cache
                except Exception:
                    continue

        # Fallback to default config
        cls._config_cache = cls._get_default_config()
        return cls._config_cache

    @classmethod
    def _get_default_config(cls) -> Dict:
        """Get default configuration if models.json not found."""
        return {
            "default_model": "claude-sonnet-4-5",
            "providers": {
                "anthropic": {
                    "models": {
                        "claude-sonnet-4-5": {"name": "claude-sonnet-4-5", "description": "Claude Sonnet 4.5"},
                        "claude-opus-4": {"name": "claude-opus-4", "description": "Claude Opus 4"},
                        "claude-haiku-4-5": {"name": "claude-haiku-4-5", "description": "Claude Haiku 4.5"},
                    }
                },
                "openai": {
                    "models": {
                        "gpt-4o": {"name": "gpt-4o", "description": "GPT-4 Omni"},
                        "gpt-4": {"name": "gpt-4", "description": "GPT-4"},
                    }
                },
                "ollama": {
                    "models": {
                        "deepseek-coder:33b": {"name": "deepseek-coder:33b", "description": "DeepSeek Coder 33B"},
                        "gemma3:4b": {"name": "gemma3:4b", "description": "Google Gemma 3 4B"},
                    }
                }
            },
            "aliases": {
                "claude": "claude-sonnet-4-5",
                "openai": "gpt-4o",
                "local": "deepseek-coder:33b",
            }
        }

    @classmethod
    def _get_models_dict(cls) -> Dict[str, str]:
        """Build MODELS dict from config."""
        config = cls._load_config()
        models: Dict[str, str] = {}

        # Add all models from all providers
        for provider, provider_data in config.get("providers", {}).items():
            for model_key, model_data in provider_data.get("models", {}).items():
                models[model_key] = model_data["name"]

        # Add aliases
        for alias, target in config.get("aliases", {}).items():
            models[alias] = target

        return models

    # Backward compatibility - make MODELS accessible as class variable
    @classmethod
    def _get_models(cls) -> Dict[str, str]:
        """Get models dict - backward compatible."""
        return cls._get_models_dict()

    # Provider detection patterns
    PROVIDER_PATTERNS: Dict[str, str] = {
        "claude": "anthropic",
        "gpt": "openai",
        "o1": "openai",
    }

    # Default fallback chains (deprecated but kept for compatibility)
    FALLBACK_CHAINS: Dict[str, List[str]] = {
        "quality": ["claude-sonnet-4-5", "gpt-4o", "deepseek-coder:33b"],
        "cost": ["deepseek-coder:33b", "claude-haiku-4-5", "gpt-4o"],
        "privacy": ["deepseek-coder:33b", "qwen2.5-coder:32b", "codestral:22b"],
        "default": ["claude-sonnet-4-5", "gpt-4o", "deepseek-coder:33b"],
    }

    @classmethod
    def get_default_model(cls) -> str:
        """Get default model from config or fallback."""
        config = cls._load_config()
        return config.get("default_model", "claude-sonnet-4-5")

    # Backward compatibility
    DEFAULT_MODEL = None  # Will be set dynamically

    @classmethod
    def resolve_model_name(cls, model_alias: Optional[str] = None) -> str:
        """
        Resolve model alias to full model name.

        Args:
            model_alias: Model name or alias (None = use default from config or .env)

        Returns:
            Full model name

        Examples:
            "claude" -> "claude-sonnet-4-5"
            "gpt-4o" -> "gpt-4o"
            "local" -> "deepseek-coder:33b"
            None -> checks .env MODEL, then config default
        """
        # If no alias provided, check .env then config
        if model_alias is None:
            model_alias = os.getenv("MODEL") or os.getenv("VISHWA_MODEL")
            if model_alias is None:
                model_alias = cls.get_default_model()

        models = cls._get_models_dict()
        return models.get(model_alias, model_alias)

    @classmethod
    def detect_provider(cls, model_name: str) -> str:
        """
        Detect provider from model name.

        Args:
            model_name: Full or partial model name

        Returns:
            Provider name: "anthropic", "openai", "novita", or "ollama"

        Examples:
            "claude-sonnet-4-20250514" -> "anthropic"
            "gpt-4o" -> "openai"
            "deepseek/deepseek-v3.2-exp" -> "novita"
            "openrouter:openai/gpt-4o" -> "novita" (handled by NovitaProvider)
            "deepseek-coder:33b" -> "ollama"
        """
        model_lower = model_name.lower()

        # Check for OpenRouter prefix - route to novita provider (it handles both)
        if model_lower.startswith("openrouter:"):
            return "novita"

        # Check patterns
        for pattern, provider in cls.PROVIDER_PATTERNS.items():
            if pattern in model_lower:
                return provider

        # Check for Novita models (contain / but not :)
        # Novita uses namespace/model format (e.g., deepseek/deepseek-v3.2-exp)
        if "/" in model_name and ":" not in model_name:
            return "novita"

        # Check for Ollama models (contain : or are in known local models)
        if ":" in model_name or model_name in [
            "llama3.1",
            "codestral",
            "deepseek-coder",
            "qwen2.5-coder",
            "mistral-nemo",
            "gemma3",
        ]:
            return "ollama"

        # Default to OpenAI for unknown models
        return "openai"

    # ═══════════════════════════════════════════════════════════════════════════
    # TODO STEP 2: Add a method to get model for a specific subagent type
    # ═══════════════════════════════════════════════════════════════════════════
    #
    # Your method should:
    #   1. Take a subagent_type parameter (string like "Explore", "Plan", etc.)
    #   2. Load the config using cls._load_config()
    #   3. Look up subagent_type in config["subagent_models"]
    #   4. If found, return that model name
    #   5. If not found, return None (so the caller can fall back to default)
    #
    # Method signature:
    #   @classmethod
    #   def get_subagent_model(cls, subagent_type: str) -> Optional[str]:
    #
    # Example implementation structure:
    #   config = cls._load_config()
    #   subagent_models = config.get("subagent_models", {})
    #   return subagent_models.get(subagent_type)
    #
    # ═══════════════════════════════════════════════════════════════════════════

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
            "novita": [],
            "openrouter": [],
            "ollama": [],
        }

        for model_name in set(cls._get_models_dict().values()):
            # Separate openrouter models for display purposes
            if model_name.startswith("openrouter:"):
                models_by_provider["openrouter"].append(model_name)
            else:
                provider = cls.detect_provider(model_name)
                models_by_provider[provider].append(model_name)

        return models_by_provider
