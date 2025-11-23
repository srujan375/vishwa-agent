# Vishwa

Terminal-based Agentic Coding Assistant

Named after Vishwakarma, the Hindu god of engineering and craftsmanship.

## Quick Start

```bash
# Install
pip install -r requirements.txt
pip install -e .

# Configure
cp .env.example .env
# Add your API key to .env

# Run
vishwa "your task here"

# Run in interactive mode
vishwa
```

## Features

- Multi-LLM support (Claude, GPT-4, Ollama)
- ReAct agent loop
- 5 core tools (bash, read, edit, write, git)
- Customizable prompts
- No embeddings - uses grep for search

## Documentation

### Getting Started
- [docs/QUICKSTART.md](docs/QUICKSTART.md) - Quick start guide
- [docs/SETUP.md](docs/SETUP.md) - Detailed setup
- [docs/USAGE.md](docs/USAGE.md) - Usage guide

### Features
- [docs/AUTOCOMPLETE-SETUP.md](docs/AUTOCOMPLETE-SETUP.md) - VS Code autocomplete setup
- [docs/INTERACTIVE_BUTTONS.md](docs/INTERACTIVE_BUTTONS.md) - Interactive TUI features

### Technical
- [docs/AUTOCOMPLETE.md](docs/AUTOCOMPLETE.md) - Autocomplete architecture
- [docs/LLM_API_COMPARISON.md](docs/LLM_API_COMPARISON.md) - LLM provider comparison

## License

MIT
