# Vishwa

AI-powered coding assistant with terminal agent and VS Code autocomplete.

Named after Vishwakarma, the Hindu god of engineering and craftsmanship.

## Features

- **Terminal Agent**: Interactive coding assistant with ReAct agent loop
- **VS Code Autocomplete**: AI-powered code suggestions in your editor
- **Multi-LLM Support**: Claude, GPT-5, Ollama, Novita (local models)
- **Privacy-First**: Run entirely locally with Ollama models
- **Core Tools**: Bash, read, edit, write, git operations

## Installation

### Prerequisites

- Python 3.8 or higher
- VS Code (for autocomplete)
- Ollama (for local models) - https://ollama.ai

### Setup

```bash
git clone https://github.com/srujan375/Vishwa.git
cd Vishwa

# Linux / macOS
./install.sh

# Windows (PowerShell)
.\install.ps1
```

## VS Code Autocomplete Setup

After running the install script:

1. Open VS Code
2. Go to Extensions (Ctrl+Shift+X)
3. Search for "Vishwa Autocomplete"
4. Click Install
5. Reload VS Code

### Test the Autocomplete

Create a Python file and type:

```python
def calculate_sum(a, b):
    return
```

Position your cursor after `return ` and wait. You should see ghost text suggesting `a + b`.

Press Tab to accept or Esc to dismiss.

### Verify Installation

1. In VS Code, go to View > Output
2. Select "Vishwa Autocomplete" from the dropdown
3. You should see "Vishwa service started successfully"

## Terminal Agent

Run the terminal-based coding assistant:

```bash
# Single task
vishwa "your task here"

# Interactive mode
vishwa
```

## Configuration

### Model Configuration

Edit `~/.vishwa/.env` to configure your model:

```bash
# For local models (Ollama)
VISHWA_MODEL=gemma3:4b

# For cloud models
# VISHWA_MODEL=claude-haiku-4-5
# ANTHROPIC_API_KEY=your-api-key

# VISHWA_MODEL=gpt-4o-mini
# OPENAI_API_KEY=your-api-key
```

### VS Code Settings

Add to your `settings.json`:

```json
{
  "vishwa.autocomplete.enabled": true,
  "vishwa.autocomplete.autoTrigger": true,
  "vishwa.autocomplete.debounceDelay": 200,
  "vishwa.autocomplete.contextLines": 20
}
```

### Available Models

| Model | Type | Notes |
|-------|------|-------|
| gemma3:4b | Local | Default, fast, runs on CPU/GPU |
| claude-haiku-4-5 | Cloud | Requires ANTHROPIC_API_KEY |
| gpt-4o-mini | Cloud | Requires OPENAI_API_KEY |
| deepseek-coder | Local | Code-specialized |

## VS Code Commands

Open Command Palette (Ctrl+Shift+P):

- **Vishwa: Show Autocomplete Statistics** - Display cache hits and model info
- **Vishwa: Change Autocomplete Model** - Switch between models
- **Vishwa: Toggle Autocomplete** - Enable or disable
- **Vishwa: Clear Autocomplete Cache** - Clear cached suggestions

## Troubleshooting

### No suggestions appearing

1. Check View > Output > "Vishwa Autocomplete" for errors
2. Verify Ollama is running: `ollama list`
3. Check logs: `tail -f /tmp/vishwa-autocomplete.log`

### Service fails to start

Verify the installation:

```bash
~/.vishwa/venv/bin/python -c "import vishwa.autocomplete.service; print('OK')"
```

If this fails, re-run the install script.

### Suggestions are slow

- Reduce debounce: `"vishwa.autocomplete.debounceDelay": 150`
- Reduce context: `"vishwa.autocomplete.contextLines": 15`
- First suggestion is slower due to model loading

## Performance

### Local Models (gemma3:4b)

- First suggestion: ~500ms (model loading)
- Subsequent: ~100-250ms
- Cached: <10ms

### Cloud Models

- claude-haiku-4-5: ~500-800ms
- gpt-5-mini: ~500-800ms

## Documentation

- [docs/AUTOCOMPLETE.md](docs/AUTOCOMPLETE.md) - Autocomplete architecture
- [docs/SETUP.md](docs/SETUP.md) - Detailed setup guide
- [docs/USAGE.md](docs/USAGE.md) - Usage guide

## License

MIT
