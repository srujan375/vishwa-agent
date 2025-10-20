# Vishwa Prompts

This directory contains the prompt templates used by Vishwa's agent.

## 📁 Files

### `system_prompt.txt`
The main system prompt that instructs the LLM on how to behave.

**Variables available:**
- `{tools_description}` - List of available tools and their descriptions
- `{working_directory}` - Current working directory
- `{files_in_context}` - Files currently being worked on
- `{modifications_count}` - Number of modifications made so far
- `{current_iteration}` - Current iteration number
- `{max_iterations}` - Maximum iterations allowed
- `{task}` - The user's task/request

## 🎨 Customizing Prompts

### Edit the System Prompt

Simply edit `system_prompt.txt` to change how Vishwa behaves:

```bash
# Open in your editor
code src/vishwa/prompts/system_prompt.txt
nano src/vishwa/prompts/system_prompt.txt
```

**Examples of what you can customize:**

1. **Change the agent's personality:**
   ```
   You are Vishwa, a helpful and concise coding assistant.
   ```

2. **Add new guidelines:**
   ```
   === GUIDELINES ===
   1. Always write tests for new functions
   2. Follow PEP 8 style guidelines
   3. Add type hints to all functions
   ```

3. **Modify the ReAct format:**
   ```
   Use this format:
   Analysis: [What you observe]
   Plan: [What you'll do]
   Execute: [Call a tool]
   Result: [Provided automatically]
   ```

### Create Custom Prompts

You can create additional prompt templates for specific use cases:

**Example: `code_review_prompt.txt`**
```
You are a code reviewer. Analyze the following code and provide:
1. Potential bugs or issues
2. Code quality improvements
3. Performance optimizations

Code to review:
{code}
```

**Use in code:**
```python
from vishwa.prompts import get_custom_prompt

prompt = get_custom_prompt("code_review_prompt", code=my_code)
```

## 🔧 Advanced Usage

### Use Different Prompts Per Task

You could create task-specific prompts:

- `refactoring_prompt.txt` - For refactoring tasks
- `testing_prompt.txt` - For writing tests
- `documentation_prompt.txt` - For adding documentation
- `debugging_prompt.txt` - For debugging issues

### Environment-Specific Prompts

Create prompts that adapt to your project:

```
You are working on a {project_type} project using {tech_stack}.

Follow these project-specific guidelines:
{project_guidelines}
```

## 💡 Tips

### 1. Be Specific
The more specific your prompt, the better results you'll get.

❌ **Bad:** "Fix the code"
✅ **Good:** "Analyze the code for potential null pointer exceptions and add defensive checks"

### 2. Use Examples
Include examples in your prompts to guide the LLM:

```
When editing files, always use this format:
- Read the file first
- Make surgical edits with str_replace
- Show the diff
- Run tests
```

### 3. Set Constraints
Add constraints to prevent unwanted behavior:

```
CONSTRAINTS:
- Never delete files
- Never commit changes
- Always ask before modifying critical files (config.py, .env)
```

### 4. Iterative Refinement
Test your prompts and refine them based on results:

1. Try a task
2. See what the agent does
3. Update the prompt
4. Try again

## 🧪 Testing Prompts

Before committing prompt changes, test them:

```bash
# Test with a simple task
vishwa "list all Python files"

# Test with a modification task
vishwa "add a comment to README.md" --auto-approve

# Check the agent's reasoning
# (enable verbose mode to see thinking)
```

## 📚 Template Syntax

Prompts use Python's `.format()` syntax:

- `{variable}` - Simple substitution
- `{variable:>10}` - Right-aligned, 10 chars
- `{variable:.2f}` - Float with 2 decimals

**Example:**
```
Current iteration: {current_iteration}/{max_iterations}
Progress: {current_iteration/max_iterations:.1%}
```

## 🔄 Reloading Prompts

Prompts are loaded fresh each time, so changes take effect immediately:

1. Edit `system_prompt.txt`
2. Save
3. Run `vishwa` - new prompt is used!

No restart required.

## 🎯 Best Practices

### DO:
✅ Keep prompts concise and clear
✅ Use structured sections (=== SECTION ===)
✅ Provide concrete examples
✅ Test changes before committing
✅ Version control your custom prompts

### DON'T:
❌ Make prompts too long (LLMs lose focus)
❌ Use vague language ("maybe", "try to")
❌ Overcomplicate the format
❌ Include sensitive information in prompts

## 🐛 Troubleshooting

### Prompt not loading?
Check the file path and encoding:
```bash
# Should be UTF-8
file src/vishwa/prompts/system_prompt.txt
```

### Variables not substituting?
Make sure variable names match exactly:
```python
# In prompt: {task}
# In code: task="my task"  ✅
# In code: Task="my task"  ❌ (case matters)
```

### Prompt too long?
LLMs have context limits. Keep prompts under ~2000 tokens.

```bash
# Count approximate tokens (4 chars ≈ 1 token)
wc -c src/vishwa/prompts/system_prompt.txt
```

## 📖 Examples

See `examples/custom_prompts/` for example custom prompts (coming soon).

## 🤝 Contributing

Have a great prompt template? Share it!

1. Create your prompt in `prompts/`
2. Test it thoroughly
3. Document the variables used
4. Submit a PR

---

**Happy prompting!** 🎨
