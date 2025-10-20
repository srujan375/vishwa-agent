"""
LLM response data models.

Unified response format across all providers (OpenAI-compatible).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    """
    Represents a tool/function call from the LLM.

    Normalized format across all providers.
    """

    id: str
    name: str
    arguments: Dict[str, Any]

    @classmethod
    def from_openai(cls, tool_call: Any) -> "ToolCall":
        """Parse from OpenAI/Ollama format"""
        import json

        return cls(
            id=tool_call.id,
            name=tool_call.function.name,
            arguments=json.loads(tool_call.function.arguments),
        )

    @classmethod
    def from_anthropic(cls, content_block: Dict[str, Any]) -> "ToolCall":
        """Parse from Claude format"""
        return cls(
            id=content_block["id"],
            name=content_block["name"],
            arguments=content_block["input"],  # Already parsed dict
        )


@dataclass
class Usage:
    """Token usage statistics"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class LLMResponse:
    """
    Unified LLM response format.

    Works with responses from Claude, OpenAI, and Ollama.
    """

    content: Optional[str]
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    model: str = ""
    usage: Optional[Usage] = None
    raw_response: Optional[Any] = None

    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls"""
        return len(self.tool_calls) > 0

    def is_final_answer(self) -> bool:
        """Check if this is a final answer (no more tool calls)"""
        return not self.has_tool_calls() and self.finish_reason == "stop"

    @classmethod
    def from_openai(cls, response: Any) -> "LLMResponse":
        """Create from OpenAI/Ollama response"""
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            tool_calls = [ToolCall.from_openai(tc) for tc in message.tool_calls]

        usage_obj = None
        if hasattr(response, "usage") and response.usage:
            usage_obj = Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        return cls(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
            model=response.model,
            usage=usage_obj,
            raw_response=response,
        )

    @classmethod
    def from_anthropic(cls, response: Any) -> "LLMResponse":
        """Create from Claude response"""
        # Claude returns content as a list of blocks
        content_text = None
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_text = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall.from_anthropic(
                        {
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )
                )

        usage_obj = None
        if hasattr(response, "usage") and response.usage:
            usage_obj = Usage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            )

        return cls(
            content=content_text,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason,
            model=response.model,
            usage=usage_obj,
            raw_response=response,
        )
