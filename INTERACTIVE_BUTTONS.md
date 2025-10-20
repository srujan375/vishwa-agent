# Interactive Button-Based Approvals in Vishwa

Vishwa now features modern, interactive button-based approvals using `prompt-toolkit` instead of simple text prompts.

## Features

### ✨ Arrow Key Navigation
- Use **← →** (left/right arrows) to move between buttons
- Press **Enter** to select
- Press **Esc** or **Ctrl+C** to cancel

### 🎨 Visual Feedback
- Selected button is **highlighted in blue** with bold text
- Non-selected buttons have a gray background
- Clear visual distinction between options

### 📝 Context-Aware Dialogs

Different types of operations show different information:

#### 1. File Creation (`write_file`)
```
📝 Creating new file: script.py
============================================================
  1 | def multiply(num1, num2):
  2 |     """Multiply two numbers."""
  3 |     return num1 * num2
  ...
============================================================
Total: 30 lines, 843 characters

┌─ Confirmation ──────────────────────────────────────────┐
│                                                          │
│  ⚠️  Create file 'script.py'?                           │
│                                                          │
│  < Yes >  < No >                                        │
└──────────────────────────────────────────────────────────┘
```

#### 2. File Modification (`str_replace`)
```
📝 Modifying file: script.py

┌─ 📝 Diff: script.py ────────────────────────────────────┐
│ --- a/script.py                                          │
│ +++ b/script.py                                          │
│ @@ -1,2 +1,3 @@                                          │
│  def multiply(num1, num2):                               │
│ -    return num1 * num2                                  │
│ +    """Multiply two numbers."""                         │
│ +    return num1 * num2                                  │
└──────────────────────────────────────────────────────────┘

┌─ Confirmation ──────────────────────────────────────────┐
│                                                          │
│  ⚠️  Apply changes to 'script.py'?                      │
│                                                          │
│  < Yes >  < No >                                        │
└──────────────────────────────────────────────────────────┘
```

#### 3. Other Operations (`bash`, etc.)
```
┌─ Confirmation ──────────────────────────────────────────┐
│                                                          │
│  ⚠️  Execute bash(command='rm -rf temp')?               │
│                                                          │
│  < Yes >  < No >                                        │
└──────────────────────────────────────────────────────────┘
```

## Implementation Details

### Files Modified

1. **[src/vishwa/cli/ui.py](src/vishwa/cli/ui.py)** - UI Components
   - Added `confirm_action()` function for Yes/No dialogs
   - Added `confirm_file_change()` function for multi-option dialogs
   - Uses `prompt_toolkit.shortcuts.button_dialog()`

2. **[src/vishwa/agent/core.py](src/vishwa/agent/core.py)** - Agent Integration
   - Modified `_get_user_approval()` method
   - Replaced `input()` calls with `confirm_action()`
   - Enhanced with colored diff display

### How It Works

```python
from vishwa.cli.ui import confirm_action

# Simple Yes/No confirmation
approved = confirm_action("Proceed with operation?", default=False)

if approved:
    print("User approved!")
else:
    print("User declined")
```

The `confirm_action()` function:
1. Creates a styled dialog using `prompt-toolkit`
2. Displays buttons with custom styling (blue highlight for selected)
3. Returns `True` for Yes, `False` for No
4. Handles Ctrl+C gracefully

### Styling

The buttons use a dark theme that matches modern terminal aesthetics:

```python
style = Style.from_dict({
    'dialog': 'bg:#1e1e1e',           # Dark background
    'dialog.body': 'bg:#1e1e1e #ffffff', # White text
    'button': 'bg:#4a4a4a #ffffff',   # Gray buttons
    'button.focused': 'bg:#0078d4 #ffffff bold', # Blue highlight
})
```

## Benefits Over Text Input

| Feature | Old (`input()`) | New (Buttons) |
|---------|----------------|---------------|
| User Experience | Type "y" or "n" | Press arrows + Enter |
| Visual Feedback | None | Highlighted selection |
| Clarity | Ambiguous | Clear buttons |
| Error Handling | Need to validate input | Built-in validation |
| Accessibility | Keyboard only | Keyboard only (no mouse needed) |
| Modern Look | Plain text | Styled dialog |

## Cross-Platform Compatibility

The `prompt-toolkit` library works on:
- ✅ Windows (Command Prompt, PowerShell, Windows Terminal)
- ✅ macOS (Terminal, iTerm2)
- ✅ Linux (GNOME Terminal, Konsole, xterm, etc.)

## Example Usage in Vishwa

When running a task that requires approval:

```bash
vishwa "create a hello world script"
```

You'll see:
1. **Preview** of what will be created/modified
2. **Interactive dialog** with arrow-navigable buttons
3. **Colored diff** for file modifications (using Rich syntax highlighting)

No more typing "y" or "n" - just use arrows and press Enter!

## Fallback Behavior

If for any reason the interactive dialog can't be displayed (e.g., non-TTY environment), the function gracefully falls back to returning the default value.

```python
try:
    result = button_dialog(...).run()
except (KeyboardInterrupt, EOFError):
    console.print("\n[yellow]Action cancelled[/yellow]")
    return False  # Safe default
```

## User Feedback on Rejection ✨ NEW!

When you reject a proposed change, Vishwa now asks for your feedback instead of blindly retrying!

### How It Works

1. **Agent proposes a change** (e.g., create a file)
2. **You review and press "No"**
3. **Vishwa asks for feedback:**

```
💬 Help me understand:
What would you like me to change about this approach?
(Press Enter to skip, or Ctrl+C to cancel the task)

Your feedback: _
```

4. **You provide guidance** (e.g., "use async/await instead of callbacks")
5. **Agent adjusts** based on your feedback!

### Example Flow

```
📝 Creating new file: api_client.py
... [file preview] ...

┌─ Confirmation ──────────────────────────────────────────┐
│                                                          │
│  ⚠️  Create file 'api_client.py'?                       │
│                                                          │
│  < Yes >  < No >  ← You select "No"                     │
└──────────────────────────────────────────────────────────┘

💬 Help me understand:
What would you like me to change about this approach?
(Press Enter to skip, or Ctrl+C to cancel the task)

Your feedback: Use httpx instead of requests

✓ Got it! Let me try a different approach...
```

The agent receives your feedback as:
```
Error: Action rejected by user
Suggestion: Use httpx instead of requests
```

And adjusts its next attempt accordingly!

### Benefits

- **No infinite loops** - Agent doesn't blindly retry the same thing
- **Better collaboration** - You guide the implementation
- **Faster iterations** - Get exactly what you want
- **Learning opportunity** - Agent understands your preferences

### Skip Feedback

If you don't want to provide feedback, just press Enter to skip:
```
Your feedback: [press Enter]
```

The agent will receive: `Error: Action rejected by user` (no suggestion)

---

## Future Enhancements

Potential improvements:
- **Multi-option buttons**: Approve / Reject / Edit / Skip
- **Batch operations**: "Approve All" / "Reject All" options
- **Preview modes**: Toggle between full/minimal previews
- **Undo support**: Track changes for rollback
- **Feedback templates**: Common responses like "simplify", "add tests", etc.

---

*Interactive buttons implemented: 2025-10-20*
*User feedback on rejection added: 2025-10-20*
*Powered by prompt-toolkit and Rich*
