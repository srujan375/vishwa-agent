"""
Quick installation and import test for Vishwa.

Run this to verify everything is installed correctly.
"""

import sys


def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")

    try:
        # Core imports
        import vishwa
        print(f"✓ vishwa (v{vishwa.__version__})")

        from vishwa.tools import ToolRegistry
        print("✓ vishwa.tools")

        from vishwa.llm import LLMFactory, LLMConfig
        print("✓ vishwa.llm")

        from vishwa.agent import VishwaAgent, ContextManager
        print("✓ vishwa.agent")

        from vishwa.cli import main, ui
        print("✓ vishwa.cli")

        return True

    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_dependencies():
    """Test that all dependencies are installed"""
    print("\nTesting dependencies...")

    required = [
        ("anthropic", "Anthropic"),
        ("openai", "OpenAI"),
        ("click", "Click"),
        ("rich", "Rich"),
        ("prompt_toolkit", "Prompt Toolkit"),
        ("git", "GitPython"),
        ("unidiff", "Unidiff"),
        ("pydantic", "Pydantic"),
        ("dotenv", "python-dotenv"),
    ]

    all_ok = True
    for module_name, display_name in required:
        try:
            __import__(module_name)
            print(f"✓ {display_name}")
        except ImportError:
            print(f"✗ {display_name} - NOT INSTALLED")
            all_ok = False

    return all_ok


def test_tools():
    """Test that tools can be loaded"""
    print("\nTesting tools...")

    try:
        from vishwa.tools import ToolRegistry

        registry = ToolRegistry.load_default()
        tools = registry.list_names()

        print(f"✓ Loaded {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool}")

        return True

    except Exception as e:
        print(f"✗ Failed to load tools: {e}")
        return False


def test_llm_providers():
    """Test that LLM providers can be created"""
    print("\nTesting LLM providers...")

    import os
    from vishwa.llm import LLMFactory, LLMConfig

    print("\nAvailable models by provider:")
    models = LLMConfig.list_available_models()
    for provider, model_list in models.items():
        print(f"\n{provider.upper()}:")
        for model in sorted(set(model_list))[:3]:  # Show first 3
            print(f"  - {model}")

    # Check API keys
    print("\nAPI Keys:")
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))

    print(f"  {'✓' if has_anthropic else '✗'} ANTHROPIC_API_KEY")
    print(f"  {'✓' if has_openai else '✗'} OPENAI_API_KEY")

    # Check Ollama
    from vishwa.llm.ollama_provider import OllamaProvider

    ollama_running = OllamaProvider.is_ollama_running()
    print(f"  {'✓' if ollama_running else '✗'} Ollama")

    if not (has_anthropic or has_openai or ollama_running):
        print("\n⚠️  No LLM provider available!")
        print("   Set ANTHROPIC_API_KEY or OPENAI_API_KEY")
        print("   Or install and run Ollama for local models")
        return False

    return True


def test_agent():
    """Test that agent can be created"""
    print("\nTesting agent creation...")

    try:
        from vishwa.agent import VishwaAgent
        from vishwa.llm import LLMFactory
        from vishwa.tools import ToolRegistry

        # Try to create with fallback (will use any available provider)
        try:
            llm = LLMFactory.create_with_fallback()
        except Exception as e:
            print(f"✗ Could not create LLM: {e}")
            print("  (This is OK if no API keys are set)")
            return True  # Still pass, as this is expected without API keys

        tools = ToolRegistry.load_default()

        agent = VishwaAgent(
            llm=llm, tools=tools, max_iterations=5, verbose=False
        )

        print(f"✓ Agent created successfully")
        print(f"  Model: {agent.llm.model_name}")
        print(f"  Provider: {agent.llm.provider_name}")
        print(f"  Tools: {len(agent.tools.all())}")

        return True

    except Exception as e:
        print(f"✗ Failed to create agent: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Vishwa Installation Test")
    print("=" * 60)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Dependencies", test_dependencies()))
    results.append(("Tools", test_tools()))
    results.append(("LLM Providers", test_llm_providers()))
    results.append(("Agent", test_agent()))

    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✅ All tests passed! Vishwa is ready to use.")
        print("\nTry running:")
        print('  vishwa "list all Python files"')
        print("  python examples/demo.py")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
