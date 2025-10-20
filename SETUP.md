# Vishwa Setup Guide

Complete step-by-step guide to set up and run Vishwa on your machine.

---

## Prerequisites

### Required
- **Python 3.10 or higher** - [Download](https://www.python.org/downloads/)
- **Git** - [Download](https://git-scm.com/downloads)
- **pip** - Usually comes with Python

### Optional but Recommended
- **Virtual environment** - venv or conda
- **Ollama** - For local/private models [Download](https://ollama.com/download)

### API Keys (at least one required)
You need **at least ONE** of these:
- **Anthropic API Key** (for Claude) - [Get one here](https://console.anthropic.com/)
- **OpenAI API Key** (for GPT-4) - [Get one here](https://platform.openai.com/api-keys)
- **Ollama installed and running** (for free local models)

---

## Step 1: Clone/Navigate to Project

Since you already have the project:

```bash
cd c:\Workspace\vishwa
```

---

## Step 2: Create Virtual Environment (Recommended)

### Option A: Using venv (Built-in)

```bash
# Create virtual environment
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on Mac/Linux
source venv/bin/activate
```

### Option B: Using conda

```bash
# Create environment
conda create -n vishwa python=3.10

# Activate
conda activate vishwa
```

You should see `(venv)` or `(vishwa)` in your terminal prompt.

---

## Step 3: Install Vishwa

### Install in Development Mode

```bash
# Install Vishwa and all dependencies
pip install -e .

# Or with development tools (pytest, ruff, mypy)
pip install -e ".[dev]"
```

This will:
- Install all required dependencies
- Make the `vishwa` command available
- Allow you to edit code and see changes immediately

### Verify Installation

```bash
# Check if vishwa command is available
vishwa --help

# Should show:
# Usage: vishwa [OPTIONS] [TASK]
# Vishwa - Terminal-based Agentic Coding Assistant
```

---

## Step 4: Configure API Keys

### Create .env File

```bash
# Copy the example
cp .env.example .env

# Edit with your favorite editor
notepad .env        # Windows
nano .env           # Mac/Linux
code .env           # VS Code
```

### Add Your API Keys

Edit `.env` and add **at least one** of these:

```bash
# For Claude (Recommended for coding tasks)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# For GPT-4
OPENAI_API_KEY=sk-your-key-here

# Optional: Ollama base URL (if using local models)
OLLAMA_BASE_URL=http://localhost:11434

# Optional: Default configuration
VISHWA_MODEL=claude-sonnet-4
VISHWA_MAX_ITERATIONS=15
```

### Get API Keys

**Anthropic (Claude):**
1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Go to API Keys section
4. Create a new key
5. Copy and paste into `.env`

**OpenAI (GPT-4):**
1. Go to https://platform.openai.com/api-keys
2. Sign up or log in
3. Create a new secret key
4. Copy and paste into `.env`

---

## Step 5: (Optional) Install Ollama for Local Models

If you want to use **free local models** (no API costs, privacy-focused):

### Install Ollama

**Windows:**
```bash
# Download and run installer from:
# https://ollama.com/download
```

**Mac:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Start Ollama

```bash
# Start the Ollama service
ollama serve
```

### Pull a Model (in a new terminal)

```bash
# For coding tasks - recommended models:

# DeepSeek Coder (33B) - Excellent for code
ollama pull deepseek-coder:33b

# Qwen 2.5 Coder (32B) - Also very good
ollama pull qwen2.5-coder:32b

# Codestral (22B) - Mistral's code model
ollama pull codestral:22b

# Llama 3.1 (8B) - Smaller, faster
ollama pull llama3.1:8b
```

**Note:** These models require significant disk space and RAM:
- 33B models: ~19GB disk, 32GB+ RAM recommended
- 22B models: ~13GB disk, 24GB+ RAM recommended
- 8B models: ~5GB disk, 8GB+ RAM recommended

---

## Step 6: Verify Setup

Run the installation test:

```bash
python test_install.py
```

You should see:
```
============================================================
Vishwa Installation Test
============================================================
Testing imports...
✓ vishwa (v0.1.0)
✓ vishwa.tools
✓ vishwa.llm
✓ vishwa.agent
✓ vishwa.cli

Testing dependencies...
✓ Anthropic
✓ OpenAI
✓ Click
✓ Rich
...

✅ All tests passed! Vishwa is ready to use.
```

Or check manually:

```bash
# Check environment
vishwa check

# Should show:
# Environment Check:
#   ✓ ANTHROPIC_API_KEY: sk-ant-...
#   ✓ OPENAI_API_KEY: sk-...
#   ✓ Ollama is running
```

---

## Step 7: Test with a Simple Task

```bash
# Try a simple read-only task
vishwa "list all Python files in the src directory"

# Should output:
# 🎯 Task: list all Python files in the src directory
# [1/15] → bash(command='...')  # Uses platform-appropriate commands
#   ✓ src/vishwa/__init__.py
#     src/vishwa/__main__.py
#     ...
# ✅ Task completed
```

**Note:** Vishwa automatically uses platform-appropriate commands (Windows: dir, findstr; Unix: ls, grep).

---

## Troubleshooting

### Issue: "vishwa: command not found"

**Solution:**
```bash
# Make sure you're in the virtual environment
# You should see (venv) or (vishwa) in your prompt

# If not, activate it:
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# Then reinstall:
pip install -e .
```

### Issue: "API key not found"

**Solution:**
```bash
# Check if .env file exists (Windows)
dir .env
# Or (Mac/Linux)
ls -la .env

# If not, create it (Windows)
copy .env.example .env
# Or (Mac/Linux)
cp .env.example .env

# Then edit and add your API key
notepad .env     # Windows
nano .env        # Mac/Linux
code .env        # VS Code (all platforms)
```

### Issue: "Cannot connect to Ollama"

**Solution:**
```bash
# Check if Ollama is running
ollama list

# If not installed, install it:
# https://ollama.com/download

# Start Ollama
ollama serve

# In another terminal, pull a model:
ollama pull deepseek-coder:33b
```

### Issue: "ModuleNotFoundError: No module named 'vishwa'"

**Solution:**
```bash
# Make sure you installed in editable mode
pip install -e .

# Check installation
pip show vishwa

# If still not working, check your Python path:
python -c "import sys; print(sys.path)"
# Should include your vishwa/src directory
```

### Issue: "No LLM provider available"

**Solution:**
```bash
# You need at least ONE of these:
# 1. Set ANTHROPIC_API_KEY in .env
# 2. Set OPENAI_API_KEY in .env
# 3. Install and run Ollama with a model

# Check what you have:
vishwa check
```

---

## Quick Reference

### Installation Commands

**Windows:**
```bash
# 1. Navigate to project
cd c:\Workspace\vishwa

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
venv\Scripts\activate

# 4. Install Vishwa
pip install -e .

# 5. Configure API keys
copy .env.example .env
# Edit .env and add your API key

# 6. Test installation
python test_install.py

# 7. Run your first task
vishwa "list all Python files"
```

**Mac/Linux:**
```bash
# 1. Navigate to project
cd ~/workspace/vishwa

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
source venv/bin/activate

# 4. Install Vishwa
pip install -e .

# 5. Configure API keys
cp .env.example .env
# Edit .env and add your API key

# 6. Test installation
python test_install.py

# 7. Run your first task
vishwa "list all Python files"
```

### Common Commands

```bash
# Basic usage
vishwa "your task here"

# With specific model
vishwa "task" --model claude-sonnet-4
vishwa "task" --model gpt-4o
vishwa "task" --model local

# Auto-approve (use with caution)
vishwa "task" --auto-approve

# Check environment
vishwa check

# List available models
vishwa models

# Show version
vishwa version

# Get help
vishwa --help
```

---

## Directory Structure After Setup

```
vishwa/
├── venv/                    # Virtual environment (created in Step 2)
├── .env                     # Your API keys (created in Step 4)
├── src/vishwa/              # Source code
├── docs/                    # Documentation
├── examples/                # Example scripts
├── tests/                   # Tests (pending)
├── pyproject.toml           # Project configuration
├── README.md                # Project overview
├── SETUP.md                 # This file
└── test_install.py          # Installation test
```

---

## Next Steps

Once setup is complete:

1. **Read the usage guide**: `docs/USAGE.md`
2. **Try the demo**: `python examples/demo.py`
3. **Run a real task**: `vishwa "add docstring to main()"`
4. **Review documentation**: Check `docs/` folder
5. **Experiment with models**: Try different LLM providers

---

## Getting Help

### Documentation
- **Usage Guide**: `docs/USAGE.md`
- **API Comparison**: `docs/LLM_API_COMPARISON.md`
- **Implementation Details**: `docs/IMPLEMENTATION_COMPLETE.md`

### Check Environment
```bash
# See what's configured
vishwa check

# List available models
vishwa models
```

### Common Issues
- No API key → Set in `.env` file
- Ollama not running → Run `ollama serve`
- Command not found → Activate virtual environment
- Module not found → Run `pip install -e .`

---

## Uninstall

If you want to remove Vishwa:

**Windows:**
```bash
# Deactivate virtual environment
deactivate

# Remove virtual environment
rmdir /s venv

# Or just uninstall the package
pip uninstall vishwa
```

**Mac/Linux:**
```bash
# Deactivate virtual environment
deactivate

# Remove virtual environment
rm -rf venv

# Or just uninstall the package
pip uninstall vishwa
```

---

## System Requirements

### Minimum
- Python 3.10+
- 2GB RAM
- 500MB disk space
- Internet connection (for API-based models)

### Recommended
- Python 3.11+
- 8GB+ RAM (for local models)
- 20GB+ disk space (if using Ollama)
- Internet connection

### For Local Models (Ollama)
- **8B models**: 8GB+ RAM
- **22-33B models**: 32GB+ RAM
- **GPU**: Optional but recommended for speed

---

**You're now ready to use Vishwa! 🚀**

Try your first task:
```bash
vishwa "search for TODO comments in the codebase"
```

