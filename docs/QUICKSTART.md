# Vishwa Quick Start

Get started with Vishwa in 3 minutes.

---

## ⚡ Install

### Option 1: Using requirements.txt (Simpler)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Vishwa in editable mode
pip install -e .

# 3. Set your API key
cp .env.example .env
# Edit .env and add ANTHROPIC_API_KEY or OPENAI_API_KEY
```

### Option 2: Using pyproject.toml

```bash
# Install everything at once (dependencies + vishwa)
pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"
```

That's it!

---

## 🎯 Environment Variables

Create `.env` file with:

```bash
# Required: At least ONE of these
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here

# Optional: For local models
OLLAMA_BASE_URL=http://localhost:11434
```

**Get API Keys:**
- Claude: https://console.anthropic.com/
- OpenAI: https://platform.openai.com/api-keys

---

## 🚀 Usage

```bash
# Basic usage
vishwa "your task here"

# Examples
vishwa "list all Python files in src/"
vishwa "add docstring to main function in app.py"
vishwa "find all TODO comments"

# With options
vishwa "task" --model claude-sonnet-4
vishwa "task" --model gpt-4o
vishwa "task" --model local        # Ollama
vishwa "task" --auto-approve       # Skip confirmations
```

**Note:** Vishwa automatically detects your OS and uses the appropriate commands (Windows: dir, findstr; Unix: ls, grep).

---

## 📍 Where Everything Is

### Prompts
**Location:** `src/vishwa/prompts/system_prompt.txt`

Edit this file to change how Vishwa behaves:
```bash
code src/vishwa/prompts/system_prompt.txt
```

See [src/vishwa/prompts/README.md](src/vishwa/prompts/README.md) for customization guide.

### Environment
**Location:** `.env` (create from `.env.example`)

```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OLLAMA_BASE_URL=http://localhost:11434
VISHWA_MODEL=claude-sonnet-4
VISHWA_MAX_ITERATIONS=15
```

### Tools
**Location:** `src/vishwa/tools/`

- `bash.py` - Execute shell commands
- `file_ops.py` - Read/edit/create files
- `git_ops.py` - Git operations

### Agent Logic
**Location:** `src/vishwa/agent/core.py`

The ReAct loop that orchestrates everything.

---

## 🧪 Test Installation

```bash
# Check environment
vishwa check

# List available models
vishwa models

# Run test
python test_install.py

# Try demo
python examples/demo.py
```

---

## 🎨 Ollama (Local Models)

### Install Ollama
```bash
# Windows/Mac: Download from https://ollama.com/download
# Linux:
curl -fsSL https://ollama.com/install.sh | sh
```

### Pull Models
```bash
# Best for coding
ollama pull deepseek-coder:33b    # 19GB, needs 32GB RAM
ollama pull qwen2.5-coder:32b     # 18GB, needs 32GB RAM
ollama pull codestral:22b         # 13GB, needs 24GB RAM

# Smaller/faster
ollama pull llama3.1:8b           # 5GB, needs 8GB RAM
```

### Check Available Models
```bash
ollama list
```

### Use with Vishwa
```bash
vishwa "task" --model local
vishwa "task" --model ollama/deepseek-coder:33b
```

---

## 🔧 Common Commands

```bash
# Check what's configured
vishwa check

# List all available models
vishwa models

# Show version
vishwa version

# Get help
vishwa --help
```

---

## 📚 Documentation

- **Full Usage Guide:** [docs/USAGE.md](docs/USAGE.md)
- **Setup Guide:** [SETUP.md](SETUP.md)
- **Prompt Customization:** [src/vishwa/prompts/README.md](src/vishwa/prompts/README.md)
- **Implementation Details:** [docs/IMPLEMENTATION_COMPLETE.md](docs/IMPLEMENTATION_COMPLETE.md)

---

## ❓ Troubleshooting

### "vishwa: command not found"
```bash
# Activate virtual environment
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Reinstall
pip install -e .
```

### "API key not found"
```bash
# Create .env file (Windows)
copy .env.example .env
# Or (Mac/Linux)
cp .env.example .env

# Edit and add your key
code .env      # VS Code (all platforms)
notepad .env   # Windows
nano .env      # Mac/Linux
```

### "Cannot connect to Ollama"
```bash
# Start Ollama
ollama serve

# Pull a model
ollama pull deepseek-coder:33b
```

---

## 🎯 Next Steps

1. **Configure:** Set your API key in `.env`
2. **Try it:** Run `vishwa "list all Python files"`
3. **Customize:** Edit prompts in `src/vishwa/prompts/`
4. **Explore:** Check out `examples/` and `docs/`

---

**Ready to code? Let's go!** 🚀

```bash
vishwa "help me refactor this code"
```
