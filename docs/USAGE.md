# Vishwa Usage Guide

Complete guide to using Vishwa, the terminal-based agentic coding assistant.

---

## Quick Start

### 1. Installation

```bash
# Install in development mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### 2. Configuration

Create a `.env` file in your project root:

```bash
# Copy example
cp .env.example .env

# Edit and add your API keys
nano .env
```

Required (at least one):
```bash
ANTHROPIC_API_KEY=sk-ant-your-key-here  # For Claude
OPENAI_API_KEY=sk-your-key-here          # For GPT-4
```

Optional:
```bash
OLLAMA_BASE_URL=http://localhost:11434   # For local models
VISHWA_MAX_ITERATIONS=15
VISHWA_MODEL=claude-sonnet-4
```

### 3. Basic Usage

```bash
# Run a task
vishwa "add docstring to the main function in app.py"

# Specify model
vishwa "fix type errors" --model gpt-4o

# Use local model (Ollama)
vishwa "search for TODO comments" --model local

# Auto-approve all actions (use with caution!)
vishwa "run tests" --auto-approve
```

---

## Commands

### Main Command

```bash
vishwa "TASK" [OPTIONS]
```

**Options:**
- `--model, -m TEXT` - Model to use (default: fallback chain)
- `--max-iter INTEGER` - Max iterations (default: 15)
- `--auto-approve` - Auto-approve all actions
- `--fallback TEXT` - Fallback chain: quality/cost/privacy/default
- `--verbose/--quiet` - Show/hide detailed output

### Subcommands

#### List Available Models

```bash
vishwa models
```

Shows all available models grouped by provider.

#### Check Environment

```bash
vishwa check
```

Verifies:
- API keys are set
- Ollama is running
- Available local models

#### Show Version

```bash
vishwa version
```

---

## Usage Examples

### Example 1: Simple Code Search

```bash
vishwa "find all functions that use the requests library"
```

**What happens:**
1. Agent uses bash/grep to search
2. Returns list of files and functions
3. No modifications made (read-only)

### Example 2: Add Documentation

```bash
vishwa "add docstrings to all functions in src/utils.py"
```

**What happens:**
1. Reads the file
2. Identifies functions without docstrings
3. Asks for approval before each change
4. Uses str_replace to add docstrings
5. Shows diff of changes

### Example 3: Fix Tests

```bash
vishwa "run pytest and fix any failing tests" --max-iter 20
```

**What happens:**
1. Runs pytest using bash tool
2. Reads test output
3. Identifies failures
4. Reads relevant code
5. Makes fixes
6. Re-runs tests
7. Continues until all pass or max iterations

### Example 4: Refactoring

```bash
vishwa "extract the database logic from api.py into a new dal.py file"
```

**What happens:**
1. Reads api.py
2. Identifies database code
3. Creates new dal.py file
4. Updates api.py to use dal.py
5. Shows all changes before applying

---

## Model Selection

### Using Specific Models

```bash
# Claude Sonnet 4 (best for coding)
vishwa "task" --model claude-sonnet-4

# GPT-4o
vishwa "task" --model gpt-4o

# Ollama local model
vishwa "task" --model deepseek-coder:33b
```

### Using Aliases

```bash
vishwa "task" --model claude    # → claude-sonnet-4-20250514
vishwa "task" --model openai    # → gpt-4o
vishwa "task" --model local     # → deepseek-coder:33b
```

### Using Fallback Chains

```bash
# Quality-first (Claude → GPT-4o → local)
vishwa "task" --fallback quality

# Cost-first (local → Claude Haiku → GPT-4o)
vishwa "task" --fallback cost

# Privacy-first (only local models)
vishwa "task" --fallback privacy

# Default (balanced)
vishwa "task" --fallback default
```

---

## Programmatic Usage

You can also use Vishwa as a Python library:

### Basic Example

```python
from vishwa.agent import VishwaAgent
from vishwa.llm import LLMFactory
from vishwa.tools import ToolRegistry

# Create LLM
llm = LLMFactory.create("claude-sonnet-4")

# Create agent
agent = VishwaAgent(
    llm=llm,
    tools=ToolRegistry.load_default(),
    max_iterations=15,
    auto_approve=False,
    verbose=True
)

# Run task
result = agent.run("add type hints to all functions in utils.py")

# Check result
if result.success:
    print(f"✅ Success: {result.message}")
    print(f"Iterations: {result.iterations_used}")
    print(f"Modified files: {len(result.modifications)}")
else:
    print(f"❌ Failed: {result.message}")
```

### With Fallback

```python
from vishwa.llm import LLMFactory

# Automatic fallback across providers
llm = LLMFactory.create_with_fallback(fallback_chain="quality")

agent = VishwaAgent(llm=llm)
result = agent.run("your task")
```

### Custom Tools

```python
from vishwa.tools.base import Tool, ToolResult

class CustomTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Does something custom"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"}
            },
            "required": ["input"]
        }

    def execute(self, **kwargs) -> ToolResult:
        # Your logic here
        return ToolResult(success=True, output="Done!")

# Register custom tool
from vishwa.tools import ToolRegistry

registry = ToolRegistry()
registry.register(CustomTool())

agent = VishwaAgent(llm=llm, tools=registry)
```

---

## Best Practices

### 1. Be Specific in Tasks

❌ Bad: "fix the code"
✅ Good: "fix the TypeError in auth.py line 42"

❌ Bad: "improve performance"
✅ Good: "optimize the database query in get_users() to use a single query instead of N+1"

### 2. Use Appropriate Models

- **Complex reasoning**: Claude Sonnet 4, GPT-4o
- **Fast tasks**: Claude Haiku, local models
- **Privacy-sensitive**: Ollama local models
- **Cost-sensitive**: Local models → Claude Haiku

### 3. Set Reasonable Iteration Limits

- Simple tasks: 5-10 iterations
- Complex tasks: 15-20 iterations
- Refactoring: 20-30 iterations

### 4. Review Changes Before Committing

```bash
# Run task
vishwa "refactor authentication module"

# Review changes
git diff

# Commit if satisfied
git add .
git commit -m "Refactor authentication module"
```

### 5. Use Auto-Approve Carefully

Only use `--auto-approve` for:
- Read-only tasks (search, analysis)
- Trusted, well-defined tasks
- Non-production code

Never use for:
- Tasks that modify critical files
- Production databases
- Git operations

---

## Troubleshooting

### "API key not found"

```bash
# Check environment
vishwa check

# Set API key
export ANTHROPIC_API_KEY=sk-ant-...
# Or add to .env file
```

### "Ollama not running"

```bash
# Check if Ollama is installed
ollama --version

# Start Ollama
ollama serve

# Pull a model
ollama pull deepseek-coder:33b
```

### "Max iterations reached"

```bash
# Increase limit
vishwa "task" --max-iter 30

# Or break task into smaller subtasks
vishwa "step 1: search for login functions"
vishwa "step 2: add logging to login"
```

### "Tool execution failed"

Common issues:
- File paths: Use relative or absolute paths correctly
- Exact string match: For str_replace, copy exact string from read_file
- Permissions: Ensure write access to files
- Git repo: Some tools require being in a git repository

---

## Tips & Tricks

### 1. Chain Tasks

```bash
# First, analyze
vishwa "analyze the error in logs.txt"

# Then, fix based on analysis
vishwa "fix the issue identified in the analysis"
```

### 2. Use Context from Previous Runs

The agent maintains context within a single run:

```bash
vishwa "find all TODO comments, then create a file with a list of them"
# Single run, agent maintains context of found TODOs
```

### 3. Leverage Git for Undo

```bash
# Make changes
vishwa "refactor the code"

# Review
git diff

# Undo if needed
git restore .
```

### 4. Combine with Other Tools

```bash
# Use Vishwa for code changes
vishwa "add error handling to all API calls"

# Then run your linter
ruff check .

# Then run tests
pytest
```

---

## Environment Variables

All supported environment variables:

```bash
# API Keys (at least one required)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Ollama (optional)
OLLAMA_BASE_URL=http://localhost:11434

# Vishwa Config (optional)
VISHWA_MODEL=claude-sonnet-4
VISHWA_MAX_ITERATIONS=15
VISHWA_LOG_LEVEL=INFO
VISHWA_AUTO_APPROVE=false
```

---

## Next Steps

- Read [Architecture Overview](IMPLEMENTATION_PROGRESS.md)
- Review [API Comparison](LLM_API_COMPARISON.md)
- Check [Examples](../examples/)
- Contribute: See [Contributing Guide](CONTRIBUTING.md) (coming soon)

