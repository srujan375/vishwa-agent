#!/usr/bin/env python
"""
Interactive environment setup for Vishwa.

This script helps you:
1. Check if API keys are set
2. Detect available Ollama models
3. Test LLM providers
4. Create/update .env file
"""

import os
import sys
from pathlib import Path


def print_header(text):
    """Print a header"""
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def print_section(text):
    """Print a section"""
    print(f"\n{text}")
    print("-" * 60)


def check_api_keys():
    """Check if API keys are set"""
    print_section("1. Checking API Keys")

    # Load .env if it exists
    env_file = Path(".env")
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv()
        print("✓ Found .env file")
    else:
        print("✗ No .env file found")
        print("  We'll help you create one")

    # Check keys
    keys = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    }

    has_any_key = False
    for key_name, key_value in keys.items():
        if key_value:
            # Mask the key
            masked = key_value[:8] + "..." + key_value[-4:] if len(key_value) > 12 else "***"
            print(f"  ✓ {key_name}: {masked}")
            has_any_key = True
        else:
            print(f"  ✗ {key_name}: Not set")

    return has_any_key, keys


def check_ollama():
    """Check Ollama status and available models"""
    print_section("2. Checking Ollama (Local Models)")

    try:
        from vishwa.llm.ollama_provider import OllamaProvider

        # Check if running
        if not OllamaProvider.is_ollama_running():
            print("✗ Ollama is not running")
            print("\nTo use local models:")
            print("  1. Install Ollama: https://ollama.com/download")
            print("  2. Run: ollama serve")
            print("  3. Pull a model: ollama pull deepseek-coder:33b")
            return False, []

        print("✓ Ollama is running")

        # List available models
        models = OllamaProvider.list_available_models()

        if not models:
            print("\n⚠️  No models installed yet")
            print("\nRecommended models for coding:")
            print("  ollama pull deepseek-coder:33b   # Best for code (19GB)")
            print("  ollama pull qwen2.5-coder:32b    # Also excellent (18GB)")
            print("  ollama pull codestral:22b        # Good (13GB)")
            print("  ollama pull llama3.1:8b          # Fast, smaller (5GB)")
            return True, []

        print(f"\n✓ Found {len(models)} installed model(s):")
        for i, model in enumerate(models, 1):
            print(f"  {i}. {model}")

        return True, models

    except ImportError:
        print("✗ Vishwa not installed yet")
        print("  Run: pip install -e .")
        return False, []
    except Exception as e:
        print(f"✗ Error checking Ollama: {e}")
        return False, []


def test_providers(has_api_keys, has_ollama, ollama_models):
    """Test which providers are available"""
    print_section("3. Available LLM Providers")

    available = []

    # Test Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        print("✓ Anthropic (Claude)")
        print("  Models: claude-sonnet-4, claude-opus-4, claude-haiku-4")
        available.append("anthropic")

    # Test OpenAI
    if os.getenv("OPENAI_API_KEY"):
        print("✓ OpenAI (GPT)")
        print("  Models: gpt-4o, gpt-4-turbo, o1")
        available.append("openai")

    # Test Ollama
    if has_ollama and ollama_models:
        print("✓ Ollama (Local)")
        print(f"  Models: {', '.join(ollama_models[:3])}")
        if len(ollama_models) > 3:
            print(f"          ... and {len(ollama_models) - 3} more")
        available.append("ollama")

    if not available:
        print("✗ No LLM providers available")
        print("\nYou need at least one of:")
        print("  - Anthropic API key")
        print("  - OpenAI API key")
        print("  - Ollama with installed models")

    return available


def create_env_file():
    """Interactively create .env file"""
    print_section("4. Environment Configuration")

    env_file = Path(".env")

    if env_file.exists():
        print("Found existing .env file")
        update = input("Update it? [y/N]: ").strip().lower()
        if update not in ["y", "yes"]:
            print("Keeping existing .env file")
            return

    print("\nLet's set up your .env file")
    print("(Press Enter to skip any field)\n")

    # Get API keys
    anthropic_key = input("Anthropic API Key (sk-ant-...): ").strip()
    openai_key = input("OpenAI API Key (sk-...): ").strip()

    # Optional settings
    print("\nOptional settings (press Enter for defaults):")
    model = input("Default model [claude-sonnet-4]: ").strip() or "claude-sonnet-4"
    max_iter = input("Max iterations [15]: ").strip() or "15"

    # Write .env file
    content = f"""# Vishwa Environment Configuration

# API Keys (at least one required)
ANTHROPIC_API_KEY={anthropic_key}
OPENAI_API_KEY={openai_key}

# Ollama (optional, for local models)
OLLAMA_BASE_URL=http://localhost:11434

# Default Configuration
VISHWA_MODEL={model}
VISHWA_MAX_ITERATIONS={max_iter}
VISHWA_LOG_LEVEL=INFO
VISHWA_AUTO_APPROVE=false
"""

    env_file.write_text(content)
    print(f"\n✓ Created {env_file}")

    # Reload environment
    from dotenv import load_dotenv
    load_dotenv(override=True)


def show_next_steps(available_providers):
    """Show next steps"""
    print_section("5. Next Steps")

    if not available_providers:
        print("❌ Setup incomplete - no LLM providers available")
        print("\nPlease:")
        print("  1. Get an API key from Anthropic or OpenAI")
        print("  2. Run this script again: python setup_env.py")
        return False

    print("✅ Setup complete! You can now use Vishwa.")
    print("\nTry these commands:")
    print('  vishwa check                              # Verify setup')
    print('  vishwa models                             # List all models')
    print('  vishwa "list all Python files"            # Simple task')
    print('  python examples/demo.py                   # Run demo')

    print("\nUsing different providers:")
    if "anthropic" in available_providers:
        print('  vishwa "task" --model claude-sonnet-4')
    if "openai" in available_providers:
        print('  vishwa "task" --model gpt-4o')
    if "ollama" in available_providers:
        print('  vishwa "task" --model local')

    return True


def main():
    """Main setup flow"""
    print_header("Vishwa Environment Setup")

    print("\nThis script will help you configure Vishwa")
    print("to work with your preferred LLM providers.")

    # Step 1: Check API keys
    has_api_keys, keys = check_api_keys()

    # Step 2: Check Ollama
    has_ollama, ollama_models = check_ollama()

    # Step 3: Test providers
    available = test_providers(has_api_keys, has_ollama, ollama_models)

    # Step 4: Create/update .env if needed
    if not has_api_keys and not (has_ollama and ollama_models):
        print_section("⚠️  Configuration Needed")
        print("\nYou don't have any LLM providers configured.")

        create = input("\nCreate .env file now? [Y/n]: ").strip().lower()
        if create not in ["n", "no"]:
            create_env_file()
            # Re-check
            has_api_keys, keys = check_api_keys()
            available = test_providers(has_api_keys, has_ollama, ollama_models)

    # Step 5: Show next steps
    success = show_next_steps(available)

    print("\n" + "=" * 60)

    if success:
        print("\n🎉 You're all set! Happy coding with Vishwa!")
    else:
        print("\n⚠️  Please complete the setup and run this script again.")

    print()

    return 0 if success else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
