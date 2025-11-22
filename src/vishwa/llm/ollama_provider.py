"""
Ollama LLM provider.

Supports local models via Ollama's OpenAI-compatible API.
"""

import os
from typing import Any, Dict, List, Optional

from openai import OpenAI, OpenAIError

from vishwa.llm.base import (
    BaseLLM,
    LLMAPIError,
    LLMAuthenticationError,
)
from vishwa.llm.response import LLMResponse


class OllamaProvider(BaseLLM):
    """
    Ollama LLM provider.

    Uses Ollama's OpenAI-compatible API endpoint.
    Since Ollama is OpenAI-compatible, this is very similar to OpenAIProvider.
    """

    # Context limits for popular Ollama models
    CONTEXT_LIMITS = {
        "llama3.1": 128000,
        "llama3.1:8b": 128000,
        "llama3.1:70b": 128000,
        "llama3.1:405b": 128000,
        "codestral": 32768,
        "codestral:22b": 32768,
        "deepseek-coder": 16384,
        "deepseek-coder:33b": 16384,
        "qwen2.5-coder": 32768,
        "qwen2.5-coder:32b": 32768,
        "mistral-nemo": 128000,
        "gemma3:4b": 8192,
    }

    def __init__(
        self,
        model: str = "deepseek-coder:33b",
        base_url: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ):
        """
        Initialize Ollama provider.

        Args:
            model: Ollama model name (e.g., 'llama3.1', 'deepseek-coder:33b')
            base_url: Ollama base URL (default: http://localhost:11434/v1)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 2.0)
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Ollama base URL
        base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

        # Initialize OpenAI client pointing to Ollama
        self.client = OpenAI(
            base_url=base_url,
            api_key="ollama",  # Required but unused by Ollama
        )

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def provider_name(self) -> str:
        return "ollama"

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
        Send chat request to Ollama.

        Args:
            messages: Conversation history
            tools: Optional tools in OpenAI format
            system: Optional system prompt
            **kwargs: Additional parameters

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

            # Add tools if provided (Ollama uses OpenAI format directly!)
            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = kwargs.get("tool_choice", "auto")

            # Make API call
            response = self.client.chat.completions.create(**api_params)

            # Convert to unified format (same as OpenAI)
            return LLMResponse.from_openai(response)

        except OpenAIError as e:
            error_msg = str(e)

            # Check if Ollama is running
            if "connection" in error_msg.lower() or "refused" in error_msg.lower():
                raise LLMAPIError(
                    "Cannot connect to Ollama. Make sure Ollama is running: "
                    "https://ollama.com/download"
                )

            elif "model" in error_msg.lower() and "not found" in error_msg.lower():
                raise LLMAPIError(
                    f"Model '{self.model}' not found. "
                    f"Pull it with: ollama pull {self.model}"
                )

            else:
                raise LLMAPIError(f"Ollama API error: {error_msg}")

        except Exception as e:
            raise LLMAPIError(f"Unexpected error calling Ollama: {str(e)}")

    @staticmethod
    def is_ollama_running(base_url: Optional[str] = None) -> bool:
        """
        Check if Ollama is running.

        Returns:
            bool: True if Ollama is accessible
        """
        try:
            import requests

            base_url = base_url or os.getenv(
                "OLLAMA_BASE_URL", "http://localhost:11434"
            )
            # Remove /v1 suffix for health check
            health_url = base_url.replace("/v1", "")

            response = requests.get(f"{health_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    @staticmethod
    def list_available_models(base_url: Optional[str] = None) -> List[str]:
        """
        List available Ollama models.

        Returns:
            List of model names
        """
        try:
            import requests

            base_url = base_url or os.getenv(
                "OLLAMA_BASE_URL", "http://localhost:11434"
            )
            health_url = base_url.replace("/v1", "")

            response = requests.get(f"{health_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            return []
        except Exception:
            return []

    @staticmethod
    def is_model_available(model_name: str, base_url: Optional[str] = None) -> bool:
        """
        Check if a specific Ollama model is available locally.

        Args:
            model_name: Name of the model to check
            base_url: Ollama base URL

        Returns:
            True if model is installed locally
        """
        available_models = OllamaProvider.list_available_models(base_url)
        return model_name in available_models

    @staticmethod
    def pull_model(model_name: str, base_url: Optional[str] = None, show_progress: bool = True) -> bool:
        """
        Pull an Ollama model.

        Args:
            model_name: Name of the model to pull
            base_url: Ollama base URL
            show_progress: Whether to show progress output

        Returns:
            True if successful, False otherwise
        """
        try:
            import subprocess

            if show_progress:
                print(f"Pulling Ollama model: {model_name}")
                print("This may take a few minutes for large models...")

            # Run ollama pull command
            result = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=not show_progress,
                text=True,
                check=True
            )

            if show_progress:
                print(f"✓ Successfully pulled {model_name}")

            return True

        except subprocess.CalledProcessError as e:
            if show_progress:
                print(f"✗ Failed to pull model: {e.stderr if e.stderr else str(e)}")
            return False
        except FileNotFoundError:
            if show_progress:
                print("✗ 'ollama' command not found. Make sure Ollama is installed.")
            return False
        except Exception as e:
            if show_progress:
                print(f"✗ Error pulling model: {e}")
            return False
