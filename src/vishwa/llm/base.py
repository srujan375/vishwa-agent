"""
Base LLM interface.

All LLM providers must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from vishwa.llm.response import LLMResponse


class BaseLLM(ABC):
    """
    Abstract base class for all LLM providers.

    Providers must implement:
    - chat(): Send messages and get response
    - supports_tools(): Whether provider supports tool/function calling
    """

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Send chat messages and get response.

        Args:
            messages: List of message dicts with 'role' and 'content'
            tools: Optional list of tools in OpenAI format
            system: Optional system prompt
            **kwargs: Provider-specific parameters

        Returns:
            LLMResponse: Unified response format

        Raises:
            LLMError: If API call fails
        """
        pass

    @abstractmethod
    def supports_tools(self) -> bool:
        """Check if provider supports tool/function calling"""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the model name being used"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name (e.g., 'openai', 'anthropic', 'ollama')"""
        pass

    def get_max_tokens(self) -> Optional[int]:
        """
        Get maximum context window size.

        Override in subclasses to provide model-specific limits.
        """
        return None


# Exceptions
class LLMError(Exception):
    """Base exception for LLM-related errors"""

    pass


class LLMAPIError(LLMError):
    """Raised when API call fails"""

    pass


class LLMAuthenticationError(LLMError):
    """Raised when API key is invalid or missing"""

    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded"""

    pass


class LLMContextLengthError(LLMError):
    """Raised when context exceeds model's limit"""

    pass
