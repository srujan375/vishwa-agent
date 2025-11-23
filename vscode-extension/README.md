# Vishwa Autocomplete - VS Code Extension

AI-powered code autocomplete using Vishwa's LLM backend.

## Features

- **Ultra-fast suggestions** - Optimized for <100ms latency with local models
- **Always-on mode** - Automatic suggestions while typing
- **Smart caching** - Prefix matching for better cache hit rates
- **Local-first** - Uses gemma3:4b via Ollama by default (no API costs!)
- **Context-aware** - Understands your code and current position
- **Ghost text display** - Non-intrusive inline suggestions
- **Multiple LLM support** - Choose from local (Ollama) or cloud models (Claude, GPT)

## Prerequisites

1. **Python 3.8+** with Vishwa installed
2. **Ollama** (recommended for local models) - [Install Ollama](https://ollama.ai)
3. **Node.js 18+** and npm (for building the extension)

## Installation

### Option 1: Development Mode (Recommended for Testing)

1. **Install dependencies:**
   ```bash
   cd vscode-extension
   npm install
   ```

2. **Compile TypeScript:**
   ```bash
   npm run compile
   ```

3. **Launch Extension Development Host:**
   ```bash
   code .
   # Press F5 to open a new VS Code window with the extension loaded
   ```

### Option 2: Package and Install

1. **Install vsce (VS Code Extension Manager):**
   ```bash
   npm install -g @vscode/vsce
   ```

2. **Build and package:**
   ```bash
   cd vscode-extension
   npm install
   npm run compile
   vsce package
   ```

3. **Install the extension:**
   ```bash
   code --install-extension vishwa-autocomplete-0.1.0.vsix
   ```

## Setup

### 1. Install Ollama (Recommended)

For ultra-fast local autocomplete with zero API costs:

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull the default model
ollama pull gemma3:4b

# Start Ollama service (usually auto-starts)
ollama serve
```

### 2. Install Vishwa Python Package

```bash
# Navigate to the main Vishwa directory
cd ..

# Install Vishwa
pip install -e .
```

### 3. Configure API Keys (Optional, for Cloud Models)

If you want to use cloud models:

```bash
# For Claude (Anthropic)
export ANTHROPIC_API_KEY="sk-ant-..."

# For GPT (OpenAI)
export OPENAI_API_KEY="sk-..."
```

## Usage

1. **Open VS Code** with the extension installed
2. **Open any code file** (.py, .js, .ts, etc.)
3. **Start typing** - suggestions will appear as ghost text
4. **Press `Tab`** to accept the suggestion
5. **Press `Esc`** to dismiss the suggestion

## Configuration

Access settings via: **File > Preferences > Settings** → Search for "Vishwa"

### Available Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `vishwa.autocomplete.enabled` | `true` | Enable/disable autocomplete |
| `vishwa.autocomplete.autoTrigger` | `true` | Auto-trigger while typing |
| `vishwa.autocomplete.model` | `gemma3:4b` | LLM model to use |
| `vishwa.autocomplete.debounceDelay` | `200` | Wait time after typing (ms) |
| `vishwa.autocomplete.contextLines` | `20` | Lines of context before/after cursor |
| `vishwa.autocomplete.pythonPath` | `python` | Path to Python executable |

### Model Options

**Local Models (Fast & Free):**
- `gemma3:4b` - Default, best balance (50-150ms)
- `gpt-oss:20b-cloud` - Larger, better quality
- `deepseek-coder` - Code-specialized
- `codestral` - Mistral's code model

**Cloud Models (Slower but Powerful):**
- `claude-haiku-4-5` - Fast Claude (~500ms)
- `gpt-4o-mini` - Fast OpenAI (~500ms)
- `claude-sonnet-4-5` - Balanced Claude (~1s)
- `gpt-4o` - Most capable OpenAI (~2s)

### Example Configuration

**Speed First:**
```json
{
  "vishwa.autocomplete.model": "gemma3:4b",
  "vishwa.autocomplete.debounceDelay": 150,
  "vishwa.autocomplete.contextLines": 15
}
```

**Quality First:**
```json
{
  "vishwa.autocomplete.model": "claude-haiku-4-5",
  "vishwa.autocomplete.debounceDelay": 300,
  "vishwa.autocomplete.contextLines": 30
}
```

## Commands

Access via Command Palette (`Cmd+Shift+P` / `Ctrl+Shift+P`):

- **Vishwa: Toggle Autocomplete** - Enable/disable autocomplete
- **Vishwa: Clear Autocomplete Cache** - Clear cached suggestions
- **Vishwa: Show Autocomplete Statistics** - View cache stats and model info

## Troubleshooting

### Extension Not Working

1. **Check Output Panel:**
   - View → Output → Select "Vishwa Autocomplete" from dropdown
   - Look for error messages

2. **Verify Python Service:**
   ```bash
   python -m vishwa.autocomplete.service --model gemma3:4b
   ```

3. **Check Vishwa Installation:**
   ```bash
   pip show vishwa
   # Or try reinstalling:
   pip install -e .
   ```

### No Suggestions Appearing

1. **Verify extension is enabled:**
   - Check `vishwa.autocomplete.enabled` setting

2. **Try different model:**
   - Change `vishwa.autocomplete.model` setting

3. **Clear cache:**
   - Run "Vishwa: Clear Autocomplete Cache" command

4. **Check if Ollama is running:**
   ```bash
   ollama list
   ```

### Slow Suggestions

1. **Use local model:**
   - Switch to `gemma3:4b` (default)

2. **Reduce context:**
   - Lower `vishwa.autocomplete.contextLines` to 15-20

3. **Increase debounce:**
   - Set `vishwa.autocomplete.debounceDelay` to 250-300ms

### Python Service Fails to Start

1. **Check Python path:**
   - Verify `vishwa.autocomplete.pythonPath` setting
   - Try setting to absolute path: `/usr/local/bin/python3`

2. **Verify Vishwa is installed:**
   ```bash
   python -c "import vishwa; print(vishwa.__file__)"
   ```

3. **Check API keys (for cloud models):**
   ```bash
   echo $ANTHROPIC_API_KEY
   echo $OPENAI_API_KEY
   ```

## Development

### Building from Source

```bash
cd vscode-extension
npm install
npm run compile
```

### Watching for Changes

```bash
npm run watch
```

### Running Tests

```bash
npm test
```

### Debugging

1. Open `vscode-extension/` folder in VS Code
2. Press `F5` to launch Extension Development Host
3. Set breakpoints in TypeScript files
4. Check Debug Console for logs

## Performance

### Expected Latency

**Local Model (gemma3:4b - Default):**
- Debounce: ~200ms
- LLM inference: ~50-100ms
- **Total: ~250ms** (feels instant!)

**Cloud Model (claude-haiku-4-5):**
- Debounce: ~200ms
- API call: ~400-600ms
- **Total: ~600-800ms**

### Cache Hit Rates

With prefix matching, expect:
- **50-70% cache hit rate** during normal coding
- Instant suggestions on cache hits (no LLM call)

## Architecture

```
┌─────────────────┐
│   VS Code       │
│  (TypeScript)   │
│                 │
│  • extension.ts │ ← Main entry point
│  • provider.ts  │ ← InlineCompletionProvider
│  • client.ts    │ ← JSON-RPC client
│                 │
└────────┬────────┘
         │ JSON-RPC (stdio)
         │
┌────────▼────────┐
│ Python Service  │
│ (vishwa.auto    │
│  complete)      │
│                 │
│  • service.py   │ ← JSON-RPC server
│  • suggestion   │ ← LLM suggestions
│    _engine.py   │
│  • context_     │ ← Context extraction
│    builder.py   │
│  • cache.py     │ ← Smart caching
│                 │
└────────┬────────┘
         │
    ┌────▼────┐
    │   LLM   │ (Ollama / Claude / GPT)
    └─────────┘
```

## License

MIT

## Support

For issues and questions, see the main Vishwa documentation.
