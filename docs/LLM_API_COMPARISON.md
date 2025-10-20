# LLM Tool Calling API Comparison & Unified Format

**Date:** January 2025
**Purpose:** Research and select a unified API format for Vishwa's LLM abstraction layer

---

## Executive Summary

After analyzing the latest documentation from Claude (Anthropic), OpenAI, and Ollama, the recommendation is:

**✅ Use OpenAI's Tool Calling Format as the Unified Standard**

**Reasoning:**
1. ✅ **OpenAI format is the industry standard** - Most widely adopted
2. ✅ **Ollama is fully OpenAI-compatible** - Uses same exact format
3. ✅ **Claude supports conversion** - Can be normalized to OpenAI format
4. ✅ **Ecosystem support** - Most libraries/tools support OpenAI format
5. ✅ **Future-proof** - New providers tend to adopt OpenAI compatibility

---

## 1. OpenAI Tool Calling Format (RECOMMENDED STANDARD)

### Latest Models (2025)
- `gpt-4-turbo-2024-04-09`
- `gpt-4o` (multimodal)
- `gpt-4o-mini`
- `o1`, `o1-mini` (reasoning models)

### Request Format

```python
from openai import OpenAI

client = OpenAI(api_key="sk-...")

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What's the weather in San Francisco?"}
    ],
    tools=[
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA"
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "Temperature unit"
                        }
                    },
                    "required": ["location"],
                    "additionalProperties": False
                },
                "strict": True  # ⭐ NEW 2025: Structured Outputs feature
            }
        }
    ],
    tool_choice="auto"  # or "none", "required", {"type": "function", "function": {"name": "..."}}
)
```

### Response Format

```python
# Response with tool call
{
    "id": "chatcmpl-...",
    "object": "chat.completion",
    "model": "gpt-4o",
    "choices": [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": null,
            "tool_calls": [
                {
                    "id": "call_abc123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "San Francisco, CA", "unit": "celsius"}'
                    }
                }
            ]
        },
        "finish_reason": "tool_calls"
    }],
    "usage": {...}
}
```

### Providing Tool Results Back

```python
messages.append({
    "role": "tool",
    "tool_call_id": "call_abc123",
    "name": "get_weather",
    "content": '{"temperature": 22, "condition": "sunny"}'
})

# Continue conversation
response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=tools
)
```

### Key Features (2025)
- ✅ **Structured Outputs** (`strict: True`) - Guaranteed schema compliance
- ✅ **Parallel function calling** - Multiple tools in one response
- ✅ **Tool choice control** - Force specific tool or auto-select
- ✅ **JSON Schema validation** - Full JSON Schema Draft 2020-12 support

---

## 2. Claude (Anthropic) Tool Use Format

### Latest Models (2025)
- `claude-sonnet-4-20250514` (Sonnet 4.5 - best for coding)
- `claude-opus-4-20250514` (Opus 4 - most capable)
- `claude-haiku-4-20250514` (Haiku 4.5 - fastest)

### Request Format

```python
import anthropic

client = anthropic.Anthropic(api_key="sk-ant-...")

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    system="You are a helpful assistant.",
    messages=[
        {"role": "user", "content": "What's the weather in San Francisco?"}
    ],
    tools=[
        {
            "name": "get_weather",
            "description": "Get the current weather in a given location",
            "input_schema": {  # ⚠️ Different from OpenAI: "input_schema" not "parameters"
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"]
                    }
                },
                "required": ["location"]
            }
        }
    ]
)
```

### Response Format

```python
{
    "id": "msg_...",
    "type": "message",
    "role": "assistant",
    "content": [
        {
            "type": "tool_use",
            "id": "toolu_abc123",
            "name": "get_weather",
            "input": {
                "location": "San Francisco, CA",
                "unit": "celsius"
            }
        }
    ],
    "model": "claude-sonnet-4-20250514",
    "stop_reason": "tool_use",
    "usage": {...}
}
```

### Providing Tool Results Back

```python
messages.append({
    "role": "user",
    "content": [
        {
            "type": "tool_result",
            "tool_use_id": "toolu_abc123",
            "content": '{"temperature": 22, "condition": "sunny"}'
        }
    ]
})

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=messages,
    tools=tools
)
```

### Key Features (2025)
- ✅ **Fine-grained tool streaming** - Stream tool parameters without buffering
- ✅ **Automatic tool clearing** - Auto-removes old tool results near token limits
- ✅ **Server-side tools** - Built-in web_search, text_editor (versioned: web_search_20250305)
- ✅ **Thinking blocks** - Extended thinking mode for complex reasoning

### Differences from OpenAI
| Feature | OpenAI | Claude |
|---------|--------|--------|
| Schema key | `parameters` | `input_schema` |
| Tool call ID | `call_abc123` | `toolu_abc123` |
| Response structure | `tool_calls` array | `content` array with `type: "tool_use"` |
| Tool result role | `"tool"` | `"user"` with `type: "tool_result"` |
| Arguments format | JSON string | Parsed object |

---

## 3. Ollama Tool Calling Format

### Supported Models (2025)
- `llama3.1` (8B, 70B, 405B)
- `codestral` (Mistral's code model, 22B)
- `deepseek-coder` (33B)
- `qwen2.5-coder` (32B)
- `mistral-nemo`
- `firefunction-v2`

### Request Format

```python
from openai import OpenAI

# ⭐ Ollama uses OpenAI-compatible API!
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # Required but unused
)

response = client.chat.completions.create(
    model="llama3.1",
    messages=[
        {"role": "user", "content": "What's the weather in San Francisco?"}
    ],
    tools=[
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state"
                        }
                    },
                    "required": ["location"]
                }
            }
        }
    ]
)
```

### Response Format

**IDENTICAL to OpenAI format** - Same structure, same keys, same workflow.

### Key Features (2025)
- ✅ **100% OpenAI-compatible** - Drop-in replacement
- ✅ **Streaming tool calls** - New parser for streaming tool parameters
- ✅ **Local & private** - No data leaves your machine
- ✅ **Free** - No API costs
- ✅ **Context window aware** - Works best with 32k+ context

### Performance Notes
- Smaller models (8B-13B) may struggle with complex tool schemas
- Best results with: `deepseek-coder:33b`, `qwen2.5-coder:32b`, `codestral:22b`
- Requires good hardware (16GB+ RAM for 33B models)

---

## Format Comparison Table

| Feature | OpenAI | Claude | Ollama |
|---------|--------|--------|--------|
| **Standard** | ✅ Industry standard | ❌ Proprietary | ✅ OpenAI-compatible |
| **Schema key** | `parameters` | `input_schema` | `parameters` |
| **Tool call structure** | `tool_calls[]` | `content[type="tool_use"]` | `tool_calls[]` |
| **Arguments** | JSON string | Parsed object | JSON string |
| **Tool result role** | `"tool"` | `"user"` | `"tool"` |
| **Parallel calls** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Streaming** | ✅ Yes | ✅ Fine-grained | ✅ Yes |
| **Local support** | ❌ API only | ❌ API only | ✅ Local |

---

## Recommendation: Unified Format Strategy

### ✅ Decision: Use OpenAI Format as the Internal Standard

**Implementation Approach:**

```python
# Internal Vishwa tool format (OpenAI-compatible)
TOOL_FORMAT = {
    "type": "function",
    "function": {
        "name": "tool_name",
        "description": "Tool description",
        "parameters": {  # ← OpenAI standard
            "type": "object",
            "properties": {...},
            "required": [...]
        }
    }
}
```

### Conversion Layer

```python
class LLMProvider:
    def _convert_tools_to_provider_format(self, tools: List[Dict]) -> List[Dict]:
        """Convert OpenAI format to provider-specific format"""

        if self.provider == "anthropic":
            # Convert "parameters" → "input_schema"
            return self._to_anthropic_format(tools)

        elif self.provider in ["openai", "ollama"]:
            # Already in correct format
            return tools

        return tools

    def _normalize_response(self, response: Any) -> ToolCallResponse:
        """Convert provider response to unified format"""

        if self.provider == "anthropic":
            return self._from_anthropic_response(response)

        elif self.provider in ["openai", "ollama"]:
            return self._from_openai_response(response)
```

---

## Latest Models & Pricing (January 2025)

### Claude (Anthropic)
| Model | Input (per 1M tokens) | Output (per 1M tokens) | Context Window | Best For |
|-------|----------------------|------------------------|----------------|----------|
| Sonnet 4.5 | $3.00 | $15.00 | 200k | **Coding tasks** |
| Opus 4 | $15.00 | $75.00 | 200k | Complex reasoning |
| Haiku 4.5 | $0.80 | $4.00 | 200k | Fast tasks |

### OpenAI
| Model | Input (per 1M tokens) | Output (per 1M tokens) | Context Window | Best For |
|-------|----------------------|------------------------|----------------|----------|
| GPT-4o | $2.50 | $10.00 | 128k | General purpose |
| GPT-4 Turbo | $10.00 | $30.00 | 128k | Legacy |
| o1 | $15.00 | $60.00 | 128k | Reasoning |

### Ollama (Local)
| Model | Size | RAM Required | Best For |
|-------|------|--------------|----------|
| deepseek-coder:33b | 19GB | 32GB+ | **Coding** |
| qwen2.5-coder:32b | 18GB | 32GB+ | **Coding** |
| codestral:22b | 13GB | 24GB+ | Coding |
| llama3.1:8b | 4.7GB | 8GB+ | Fast tasks |

---

## Implementation Plan for Vishwa

### 1. Internal Tool Registry (OpenAI Format)
```python
# tools/base.py
class Tool:
    def to_openai_format(self) -> Dict:
        """Convert tool to OpenAI format"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters  # JSON Schema
            }
        }
```

### 2. LLM Provider Abstraction
```python
# llm/provider.py
class LLMProvider:
    def chat(self, messages, tools):
        # 1. Convert tools to provider format
        provider_tools = self._convert_tools(tools)

        # 2. Make API call
        response = self._make_request(messages, provider_tools)

        # 3. Normalize response to OpenAI format
        return self._normalize_response(response)
```

### 3. Unified Response Format
```python
@dataclass
class ToolCall:
    id: str                    # "call_abc123" or "toolu_abc123"
    name: str                  # "get_weather"
    arguments: Dict[str, Any]  # Parsed JSON

@dataclass
class LLMResponse:
    content: Optional[str]
    tool_calls: List[ToolCall]
    finish_reason: str
    model: str
    usage: Dict[str, int]
```

---

## Testing Strategy

### Test Matrix
| Provider | Model | Tool Format | Expected Result |
|----------|-------|-------------|-----------------|
| OpenAI | gpt-4o | OpenAI | ✅ Direct |
| Claude | sonnet-4 | OpenAI → Claude | ✅ Convert |
| Ollama | llama3.1 | OpenAI | ✅ Direct |

### Example Test
```python
def test_unified_tool_calling():
    tool = {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute shell command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"}
                },
                "required": ["command"]
            }
        }
    }

    # Test with all providers
    for provider in ["openai", "anthropic", "ollama"]:
        llm = LLMFactory.create(provider)
        response = llm.chat(messages=[...], tools=[tool])

        assert isinstance(response, LLMResponse)
        assert len(response.tool_calls) > 0
        assert response.tool_calls[0].name == "bash"
```

---

## Conclusion

**Selected Standard: OpenAI Tool Calling Format**

**Benefits:**
1. ✅ Works natively with OpenAI and Ollama
2. ✅ Single conversion layer needed (for Claude)
3. ✅ Industry standard with wide ecosystem support
4. ✅ Future providers will likely adopt it
5. ✅ Simplifies testing and documentation

**Next Steps:**
1. Implement tool registry with OpenAI format
2. Create Claude converter (parameters → input_schema)
3. Build unified LLM provider abstraction
4. Test with all three providers

