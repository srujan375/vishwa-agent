"""
Demo script to test Vishwa agent.

This demonstrates the basic usage of the agent without CLI.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from vishwa.agent import VishwaAgent
from vishwa.llm import LLMFactory
from vishwa.tools import ToolRegistry


def demo_basic():
    """Basic demo - list files in current directory"""
    print("=" * 60)
    print("DEMO 1: Basic file listing")
    print("=" * 60)

    # Create LLM (try Ollama first, fallback to others)
    try:
        llm = LLMFactory.create("ollama/llama3.1:8b")
        print("Using: Ollama (local)")
    except Exception:
        try:
            llm = LLMFactory.create("claude-sonnet-4")
            print("Using: Claude Sonnet 4")
        except Exception:
            llm = LLMFactory.create("gpt-4o")
            print("Using: GPT-4o")

    # Create agent
    agent = VishwaAgent(
        llm=llm,
        tools=ToolRegistry.load_default(),
        max_iterations=5,
        auto_approve=True,  # Auto-approve for demo
        verbose=True,
    )

    # Run task
    result = agent.run("List all Python files in the current directory using bash")

    # Show result
    print("\n" + "=" * 60)
    print("RESULT:")
    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    print(f"Iterations: {result.iterations_used}")
    print(f"Stop reason: {result.stop_reason}")
    print("=" * 60)


def demo_read_file():
    """Demo - read a specific file"""
    print("\n\n" + "=" * 60)
    print("DEMO 2: Read README.md")
    print("=" * 60)

    # Use fallback chain
    llm = LLMFactory.create_with_fallback(fallback_chain="default")

    agent = VishwaAgent(
        llm=llm,
        max_iterations=5,
        auto_approve=True,
        verbose=True,
    )

    result = agent.run("Read the README.md file and tell me what this project is about")

    print("\n" + "=" * 60)
    print("RESULT:")
    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    print("=" * 60)


def demo_search_code():
    """Demo - search for code pattern"""
    print("\n\n" + "=" * 60)
    print("DEMO 3: Search for imports")
    print("=" * 60)

    llm = LLMFactory.create_with_fallback()

    agent = VishwaAgent(
        llm=llm,
        max_iterations=5,
        auto_approve=True,
        verbose=True,
    )

    result = agent.run(
        "Find all files that import 'BaseLLM' using grep"
    )

    print("\n" + "=" * 60)
    print("RESULT:")
    print(f"Success: {result.success}")
    print(f"Iterations: {result.iterations_used}")
    print("=" * 60)


if __name__ == "__main__":
    # Check if API keys are set
    has_anthropic = os.getenv("ANTHROPIC_API_KEY")
    has_openai = os.getenv("OPENAI_API_KEY")

    print("Environment Check:")
    print(f"  ANTHROPIC_API_KEY: {'✓' if has_anthropic else '✗'}")
    print(f"  OPENAI_API_KEY: {'✓' if has_openai else '✗'}")
    print()

    if not (has_anthropic or has_openai):
        print("⚠️  No API keys found. Please set ANTHROPIC_API_KEY or OPENAI_API_KEY")
        print("   Or install and run Ollama for local models")
        sys.exit(1)

    # Run demos
    try:
        demo_basic()
        # Uncomment to run more demos:
        # demo_read_file()
        # demo_search_code()

    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed: {e}")
        import traceback

        traceback.print_exc()
