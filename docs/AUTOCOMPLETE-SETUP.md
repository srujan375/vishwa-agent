# Vishwa Autocomplete Setup

Quick setup guide for AI-powered code autocomplete in VS Code.

## Prerequisites

- VS Code installed
- Python 3.8+
- Vishwa installed (`pip install -e .`)

## Installation

### 1. Build the VS Code Extension

```bash
cd vscode-extension
npm install
npm run compile
```

### 2. Package the Extension

```bash
npx vsce package
```

This creates `vishwa-autocomplete-0.1.0.vsix`

### 3. Install in VS Code

```bash
code --install-extension vishwa-autocomplete-0.1.0.vsix
```

Or install via VS Code UI: Extensions → `...` → Install from VSIX

## Configuration

### Set the Model in `.env`

The autocomplete model is configured in your `.env` file:

```bash
# Option 1: Use dedicated autocomplete model (recommended for speed)
VISHWA_AUTOCOMPLETE_MODEL=gemma3:4b

# Option 2: Share model with main CLI
VISHWA_MODEL=claude-haiku-4-5

# If both are set, VISHWA_AUTOCOMPLETE_MODEL takes priority
```

### Recommended Models

**For ultra-fast local autocomplete (free):**
```bash
VISHWA_AUTOCOMPLETE_MODEL=gemma3:4b
```

**For cloud-based autocomplete:**
```bash
VISHWA_AUTOCOMPLETE_MODEL=claude-haiku-4-5
```

### Optional VS Code Settings

Add to your VS Code `settings.json`:

```json
{
  "vishwa.autocomplete.enabled": true,
  "vishwa.autocomplete.autoTrigger": true,
  "vishwa.autocomplete.debounceDelay": 200,
  "vishwa.autocomplete.contextLines": 20,
  "vishwa.autocomplete.pythonPath": "python"
}
```

## Usage

Once installed and configured:

1. Open any code file in VS Code
2. Start typing - suggestions appear automatically
3. Press `Tab` to accept suggestions
4. Press `Esc` to dismiss

### Commands

- **Toggle Autocomplete**: `Cmd/Ctrl+Shift+P` → "Vishwa: Toggle Autocomplete"
- **Clear Cache**: `Cmd/Ctrl+Shift+P` → "Vishwa: Clear Autocomplete Cache"
- **Show Statistics**: `Cmd/Ctrl+Shift+P` → "Vishwa: Show Autocomplete Statistics"

## Troubleshooting

### Check Service Logs

View logs in VS Code: **View → Output → "Vishwa Autocomplete"**

Or check the log file:
```bash
tail -f /tmp/vishwa-autocomplete.log
```

### Test Service Manually

```bash
echo '{"jsonrpc":"2.0","method":"ping","params":{},"id":1}' | python -m vishwa.autocomplete.service
```

Should return: `{"jsonrpc":"2.0","result":{"status":"ok"},"id":1}`

### Common Issues

**"Service not starting"**
- Verify Python path: `which python`
- Check `.env` is loaded
- Ensure Vishwa is installed: `pip show vishwa`

**"Slow suggestions"**
- Use a local model: `VISHWA_AUTOCOMPLETE_MODEL=gemma3:4b`
- Install Ollama and pull the model: `ollama pull gemma3:4b`

**"No suggestions appearing"**
- Check autocomplete is enabled in settings
- Verify the service is running in Output panel
- Clear cache and restart VS Code

## Updating

After making changes to the extension code:

```bash
cd vscode-extension
npm run compile
npx vsce package
code --install-extension vishwa-autocomplete-0.1.0.vsix --force
```

Then reload VS Code window.

## More Information

For technical details and architecture, see [AUTOCOMPLETE.md](AUTOCOMPLETE.md)
