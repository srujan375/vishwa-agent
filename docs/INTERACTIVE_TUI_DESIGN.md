# Vishwa Interactive TUI Design

Design document for Vishwa's interactive terminal user interface.

---

## Overview

Transform Vishwa from a one-shot CLI tool to an interactive REPL-style coding assistant, similar to Claude Code.

**Current State:**
```bash
vishwa "task description"  # One-shot execution
```

**Desired State:**
```bash
vishwa                      # Enter interactive mode
> list all Python files
> add docstrings to main.py
> /help
```

---

## Architecture

### Tech Stack

**Option 1: prompt-toolkit (Recommended)**
- ✅ Already in requirements.txt
- ✅ Powerful REPL capabilities
- ✅ Syntax highlighting, autocompletion
- ✅ Multiline editing, history
- ✅ Key bindings support
- Example: IPython, ptpython

**Option 2: Rich + prompt-toolkit**
- Combine Rich for beautiful output
- prompt-toolkit for interactive input
- Best of both worlds

**Option 3: Textual**
- Full TUI framework
- More complex, might be overkill

**Decision: Use prompt-toolkit + Rich**

---

## User Experience Flow

### 1. Starting Interactive Mode

```bash
# Enter interactive mode
vishwa

# Or with options
vishwa --model claude-sonnet-4
vishwa --auto-approve  # Skip all confirmations
```

### 2. Welcome Screen

```
╭─────────────────────────────────────────────────╮
│  Vishwa - Agentic Coding Assistant             │
│  Model: claude-sonnet-4 | Context: 0 files     │
╰─────────────────────────────────────────────────╯

Working directory: c:\Workspace\vishwa
Type /help for commands or start chatting

>
```

**Colors:**
- Border: Cyan accent (#00d7ff)
- Title: Bright white
- Metadata: Dim gray
- Prompt: Cyan accent

### 3. Chat Interface

```
> list all Python files in src/

⠋ Thinking...

[1/15] bash(command='dir /s /b src\*.py')
  ✓ Found 12 files

  src\vishwa\__init__.py
  src\vishwa\agent\core.py
  ...

─────────────────────────────────────────────────
Task completed in 2.3s

>
```

**Colors:**
- User input: White
- Spinner: Cyan (animated: ⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)
- Tool call: Dim white with cyan action verb
- Success checkmark: Green
- Error cross: Red
- Separator: Dim gray
- Timing: Dim cyan

### 4. Multiline Input

```
> /multiline
Multiline mode - Press Ctrl+D to submit, Ctrl+C to cancel

> Can you refactor the agent core to:
... 1. Improve error handling
... 2. Add better logging
... 3. Simplify the main loop
>

⠋ Thinking...
```

**Design Principles:**
- Minimal emoji usage (only ✓ for success, ✗ for errors)
- Subtle cyan accent color for interactive elements
- Animated spinners for loading states
- Clean separators with dim gray
- Professional, terminal-native aesthetic

---

## Features

### Core Features (MVP)

1. **REPL Loop**
   - Read user input
   - Execute task
   - Print results
   - Loop

2. **Session Persistence**
   - Keep context across messages
   - Track files in context
   - Maintain conversation history

3. **Slash Commands**
   - `/help` - Show help
   - `/clear` - Clear screen
   - `/reset` - Reset context
   - `/files` - Show files in context
   - `/model <name>` - Switch model
   - `/exit` or `/quit` - Exit

4. **File Tracking**
   - Show files in context in status bar
   - Automatically track modified files
   - `/files` to list all tracked files
   - `/forget <file>` to remove from context

### Enhanced Features (v2)

1. **@-Mentions**
   ```
   > @src/vishwa/agent/core.py add error handling here
   ```

2. **Keyboard Shortcuts**
   - `Ctrl+C` - Cancel current operation
   - `Ctrl+D` - Exit
   - `Shift+Enter` - Multiline input
   - `Ctrl+R` - Search history
   - `Up/Down` - Navigate history

3. **History**
   - Save command history to `.vishwa_history`
   - Search history with Ctrl+R
   - Browse with Up/Down arrows

4. **Auto-completion**
   - Complete file paths
   - Complete slash commands
   - Complete model names

5. **Streaming Output**
   - Show LLM responses as they stream
   - Show tool execution in real-time

6. **Progress Indicators**
   - Show spinner while thinking
   - Show progress bar for long operations
   - Show todo list for multi-step tasks

---

## Color Scheme

### Primary Colors
- **Accent (Cyan)**: `#00d7ff` - Borders, prompts, interactive elements
- **Success (Green)**: `#00ff00` - Checkmarks, success messages
- **Error (Red)**: `#ff5555` - Errors, warnings
- **Info (Blue)**: `#5f87ff` - Information, metadata

### Text Colors
- **Primary**: Bright white - User input, main content
- **Secondary**: Dim gray - Metadata, timestamps, separators
- **Highlight**: Cyan - Commands, file names, important info

### Semantic Usage
- Borders/boxes: Cyan accent
- Success indicators: Green ✓
- Error indicators: Red ✗
- Loading spinners: Cyan (animated)
- Separators: Dim gray
- Timestamps/metadata: Dim cyan

---

## UI Components

### Status Bar (Top)

```
╭─────────────────────────────────────────────────╮
│  Vishwa | Model: claude-sonnet-4 | Files: 3    │
│  Working: c:\Workspace\vishwa | Iteration: 5/15 │
╰─────────────────────────────────────────────────╯
```
- Border: Cyan
- Title: White
- Metadata: Dim gray

### Input Prompt

```
> Your message here
```

With file context:
```
[core.py] > Your message here
```

Multiline mode:
```
... Your message here (line 2)
```

- Prompt symbol: Cyan
- Input text: White
- Context indicator: Cyan brackets

### Output Sections

**Thinking (with spinner):**
```
⠋ Analyzing codebase...
```
- Spinner: Cyan, animated
- Text: Dim gray

**Action:**
```
[1/15] bash(command='dir /s /b *.py')
```
- Iteration: Dim cyan
- Tool name: Cyan
- Command: White

**Observation:**
```
  ✓ Found 12 files
  src\vishwa\agent\core.py
  ...
```
- Success mark: Green
- Content: White
- Files: Dim white

**Approval Request:**
```
Approve this action? [y/N/all/quit]
  write_file(path='test.py', ...)

Preview:
──────────────────────────────────────
  1 | def hello():
  2 |     print("Hello")
──────────────────────────────────────
```
- Prompt: Cyan
- Tool name: Cyan
- Preview border: Dim gray
- Line numbers: Dim cyan
- Code: White

### Separator

```
─────────────────────────────────────────────────
Task completed in 2.3s
```
- Line: Dim gray
- Timing: Dim cyan

---

## Implementation Plan

### Phase 1: Basic REPL (MVP)

1. **Create `interactive.py` module**
   - `InteractiveSession` class
   - Main REPL loop
   - Basic commands

2. **Update `cli/commands.py`**
   - Detect if task is provided
   - If no task: Enter interactive mode
   - If task: Use current one-shot mode

3. **Session Management**
   - Persist context between messages
   - Track conversation history
   - Maintain file context

4. **Basic UI**
   - Welcome message
   - Input prompt
   - Output formatting

### Phase 2: Slash Commands

1. **Command Registry**
   - Register slash commands
   - Parse command input
   - Execute commands

2. **Core Commands**
   - `/help` - Help text
   - `/clear` - Clear screen
   - `/reset` - Reset session
   - `/files` - List files
   - `/exit` - Exit

### Phase 3: Enhanced UX

1. **Keyboard Shortcuts**
   - Multiline input (Shift+Enter)
   - History search (Ctrl+R)
   - Cancel (Ctrl+C)

2. **Auto-completion**
   - File paths
   - Commands
   - Model names

3. **History**
   - Save to `.vishwa_history`
   - Load on startup
   - Search and navigate

### Phase 4: Advanced Features

1. **@-Mentions**
   - Parse @file.py syntax
   - Load file content
   - Add to context

2. **Streaming**
   - Stream LLM responses
   - Real-time tool execution
   - Progress indicators

3. **Session Save/Load**
   - Save session state
   - Resume previous sessions
   - Export conversations

---

## Code Structure

```
src/vishwa/
├── cli/
│   ├── commands.py         # Updated: Detect interactive vs one-shot
│   ├── interactive.py      # NEW: Interactive session manager
│   └── ui.py               # Updated: Interactive UI components
├── agent/
│   ├── core.py             # Updated: Support streaming/callbacks
│   └── session.py          # NEW: Session persistence
└── prompts/
    └── interactive_prompt.txt  # NEW: Prompt for interactive mode
```

### New Files

**`cli/interactive.py`**
```python
class InteractiveSession:
    """Manages interactive REPL session"""

    def __init__(self, agent, config):
        self.agent = agent
        self.config = config
        self.history = []
        self.commands = self._register_commands()

    def start(self):
        """Start interactive loop"""
        self.print_welcome()

        while True:
            try:
                user_input = self.get_input()

                if self.is_command(user_input):
                    self.execute_command(user_input)
                else:
                    self.execute_task(user_input)

            except KeyboardInterrupt:
                if self.confirm_exit():
                    break
            except EOFError:
                break

    def get_input(self) -> str:
        """Get user input with prompt-toolkit"""
        pass

    def execute_command(self, cmd: str):
        """Execute slash command"""
        pass

    def execute_task(self, task: str):
        """Execute coding task"""
        pass
```

**`agent/session.py`**
```python
@dataclass
class Session:
    """Represents a Vishwa session"""

    id: str
    started_at: datetime
    messages: List[Message]
    files_in_context: Dict[str, FileInfo]
    modifications: List[Modification]

    def save(self, path: Path):
        """Save session to disk"""
        pass

    @classmethod
    def load(cls, path: Path) -> "Session":
        """Load session from disk"""
        pass
```

---

## Slash Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `/help` | Show help | `/help` |
| `/clear` | Clear screen | `/clear` |
| `/reset` | Reset context | `/reset` |
| `/files` | List files in context | `/files` |
| `/forget <file>` | Remove file from context | `/forget main.py` |
| `/model <name>` | Switch LLM model | `/model gpt-4o` |
| `/models` | List available models | `/models` |
| `/auto` | Toggle auto-approve | `/auto` |
| `/save [name]` | Save session | `/save my-session` |
| `/load <name>` | Load session | `/load my-session` |
| `/history` | Show command history | `/history` |
| `/multiline` | Enter multiline mode | `/multiline` |
| `/exit`, `/quit` | Exit Vishwa | `/exit` |

---

## Configuration

Add to `.env`:

```bash
# Interactive mode settings
VISHWA_HISTORY_SIZE=1000
VISHWA_AUTO_SAVE_SESSION=true
VISHWA_SESSION_DIR=~/.vishwa/sessions
```

---

## Testing Plan

### Unit Tests

1. Test `InteractiveSession` class
2. Test command parsing
3. Test session save/load
4. Test @-mention parsing

### Integration Tests

1. Test REPL loop
2. Test context persistence
3. Test file tracking
4. Test command execution

### Manual Testing

1. Start interactive mode
2. Execute multiple tasks
3. Use slash commands
4. Test keyboard shortcuts
5. Test history
6. Save and resume session

---

## Migration Path

**Backward Compatibility:**
- Keep one-shot mode as default
- Interactive mode only when no task provided
- All existing flags work in both modes

**Current Usage (preserved):**
```bash
vishwa "task"              # One-shot mode
vishwa "task" --model gpt-4o
```

**New Usage:**
```bash
vishwa                     # Interactive mode
vishwa --interactive       # Explicit interactive mode
```

---

## Future Enhancements

1. **Web UI** (optional companion)
   - Browser-based interface
   - Same backend as TUI
   - Drag-and-drop files

2. **IDE Integration**
   - VS Code extension
   - Language Server Protocol (LSP)
   - Editor commands

3. **Collaborative Sessions**
   - Share sessions with team
   - Multiple users in same session
   - Session replay/review

4. **Voice Input** (experimental)
   - Speak commands
   - Hands-free coding

---

## Success Metrics

1. **User Experience**
   - Time to complete task < 30s
   - < 3 commands for common tasks
   - 90%+ positive user feedback

2. **Technical**
   - Response time < 1s
   - Zero crashes in 1hr session
   - Memory usage < 200MB

3. **Adoption**
   - 50%+ users prefer interactive mode
   - Average session length > 15min
   - 80%+ users use slash commands

---

**Ready to implement!** 🚀

Next steps:
1. Create `cli/interactive.py`
2. Update `cli/commands.py` to detect mode
3. Implement basic REPL loop
4. Add slash commands
5. Test and iterate
