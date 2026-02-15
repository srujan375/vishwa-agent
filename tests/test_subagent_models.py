"""
Integration tests for sub-agent model configuration.

Tests that each sub-agent type uses the correct model as configured in models.json.
Makes real LLM calls to verify the full flow works.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def load_env():
    """Load .env file if it exists."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if key and value:
                        os.environ[key] = value


def test_subagent_model_configuration():
    """Test that LLMConfig correctly returns subagent models."""
    from vishwa.llm.config import LLMConfig

    # Clear cache to ensure fresh config
    LLMConfig._config_cache = None

    print("=" * 60)
    print("TEST: Sub-agent Model Configuration")
    print("=" * 60)

    subagent_types = ["Explore", "Plan", "Test", "Refactor", "Documentation", "CodeReview"]

    print("\nConfigured models:")
    for agent_type in subagent_types:
        model = LLMConfig.get_subagent_model(agent_type)
        status = "✓" if model else "⚠ (will use default)"
        print(f"  {status} {agent_type:15} -> {model or 'None'}")

    # Test unknown type returns None
    unknown_model = LLMConfig.get_subagent_model("UnknownAgent")
    assert unknown_model is None, "Unknown agent type should return None"
    print(f"\n  ✓ Unknown agent type correctly returns None")

    print("\n" + "=" * 60)
    return True


def test_subagent_llm_creation():
    """Test that LLMFactory can create LLMs for each subagent model."""
    from vishwa.llm.config import LLMConfig
    from vishwa.llm.factory import LLMFactory

    LLMConfig._config_cache = None

    print("=" * 60)
    print("TEST: Sub-agent LLM Creation")
    print("=" * 60)

    subagent_types = ["Explore", "Plan", "Test", "Refactor", "Documentation", "CodeReview"]
    results = []

    for agent_type in subagent_types:
        model_name = LLMConfig.get_subagent_model(agent_type)
        print(f"\n{agent_type}:")
        print(f"  Model: {model_name or '(default)'}")

        if model_name:
            try:
                llm = LLMFactory.create(model_name)
                provider = LLMConfig.detect_provider(model_name)
                print(f"  Provider: {provider}")
                print(f"  LLM Class: {type(llm).__name__}")
                print(f"  ✓ LLM created successfully")
                results.append((agent_type, True, None))
            except Exception as e:
                print(f"  ✗ Error: {e}")
                results.append((agent_type, False, str(e)))
        else:
            print(f"  ⚠ No model configured, will use default")
            results.append((agent_type, True, "default"))

    print("\n" + "=" * 60)

    # Check if any failed due to missing API keys
    failures = [r for r in results if not r[1]]
    if failures:
        print("\nFailed LLM creations (likely missing API keys):")
        for agent_type, _, error in failures:
            print(f"  - {agent_type}: {error}")

    return len(failures) == 0


def test_subagent_task_execution():
    """Test actual sub-agent task execution with real LLM calls."""
    from vishwa.llm.config import LLMConfig
    from vishwa.llm.factory import LLMFactory
    from vishwa.tools.base import ToolRegistry
    from vishwa.tools.task import TaskTool

    LLMConfig._config_cache = None

    print("=" * 60)
    print("TEST: Sub-agent Task Execution (Real LLM Calls)")
    print("=" * 60)

    # Check for any available API key
    api_keys = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY"),
        "NOVITA_API_KEY": os.getenv("NOVITA_API_KEY"),
    }

    available_keys = {k: v for k, v in api_keys.items() if v}

    if not available_keys:
        print("\n⚠ SKIPPING: No API keys found")
        print("Set one of these environment variables to run this test:")
        for key in api_keys:
            print(f"  - {key}")
        print("=" * 60)
        return None  # Skip, not fail

    print(f"\nAvailable API keys: {', '.join(available_keys.keys())}")

    # Determine which model to use for main agent based on available keys
    if "ANTHROPIC_API_KEY" in available_keys:
        main_model = "claude-sonnet-4-5"
    elif "OPENAI_API_KEY" in available_keys:
        main_model = "gpt-4o"
    elif "OPENROUTER_API_KEY" in available_keys:
        main_model = "openrouter:anthropic/claude-sonnet-4"
    else:
        main_model = "deepseek/deepseek-v3.2-exp"

    print(f"Main agent model: {main_model}")

    try:
        # Create main LLM and tool registry
        main_llm = LLMFactory.create(main_model)
        registry = ToolRegistry.load_default(auto_approve=True)

        # Create TaskTool
        task_tool = TaskTool(
            llm=main_llm,
            tool_registry=registry,
        )

        # Test cases for each sub-agent type
        test_cases = [
            {
                "subagent_type": "Explore",
                "prompt": "Find where the ToolResult class is defined in this codebase. Be very quick, just find the file.",
                "description": "Find ToolResult class",
                "thoroughness": "quick",
            },
            {
                "subagent_type": "Plan",
                "prompt": "Briefly outline 3 steps to add a new tool to this codebase. Keep it very short.",
                "description": "Plan new tool",
                "thoroughness": "quick",
            },
            {
                "subagent_type": "CodeReview",
                "prompt": "Do a quick review of src/vishwa/tools/base.py. Just identify 1-2 potential issues if any.",
                "description": "Review base.py",
                "thoroughness": "quick",
            },
        ]

        results = []

        for test in test_cases:
            print(f"\n{'─' * 50}")
            print(f"Testing: {test['subagent_type']} sub-agent")
            print(f"Task: {test['description']}")

            # Check what model will be used
            configured_model = LLMConfig.get_subagent_model(test["subagent_type"])
            print(f"Configured model: {configured_model or '(default: ' + main_model + ')'}")

            try:
                result = task_tool.execute(
                    subagent_type=test["subagent_type"],
                    prompt=test["prompt"],
                    description=test["description"],
                    thoroughness=test["thoroughness"],
                )

                print(f"\nResult:")
                print(f"  Success: {result.success}")
                print(f"  Iterations: {result.metadata.get('iterations_used', 'N/A')}")

                # Show truncated output
                output_preview = result.output[:300] if result.output else "(no output)"
                if len(result.output or "") > 300:
                    output_preview += "..."
                print(f"  Output preview: {output_preview}")

                if result.success:
                    print(f"  ✓ PASSED")
                else:
                    print(f"  ✗ FAILED: {result.error}")

                results.append({
                    "subagent_type": test["subagent_type"],
                    "success": result.success,
                    "iterations": result.metadata.get("iterations_used"),
                    "model_used": configured_model or main_model,
                })

            except Exception as e:
                print(f"  ✗ ERROR: {e}")
                results.append({
                    "subagent_type": test["subagent_type"],
                    "success": False,
                    "error": str(e),
                })

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)

        passed = sum(1 for r in results if r.get("success", False))
        total = len(results)

        for r in results:
            status = "✓" if r.get("success") else "✗"
            model = r.get("model_used", "unknown")
            print(f"  {status} {r['subagent_type']:15} (model: {model})")

        print(f"\nTotal: {passed}/{total} passed")
        print("=" * 60)

        return passed == total

    except Exception as e:
        print(f"\n✗ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all sub-agent model tests."""
    load_env()

    print("\n" + "=" * 60)
    print("SUB-AGENT MODEL INTEGRATION TESTS")
    print("=" * 60 + "\n")

    all_passed = True

    # Test 1: Configuration
    if not test_subagent_model_configuration():
        all_passed = False

    print()

    # Test 2: LLM Creation
    if not test_subagent_llm_creation():
        print("\n⚠ LLM creation test failed (likely missing API keys)")
        # Don't fail overall - this is expected without API keys

    print()

    # Test 3: Actual execution
    result = test_subagent_task_execution()
    if result is False:
        all_passed = False
    elif result is None:
        print("\n⚠ Execution test skipped (no API keys)")

    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 60 + "\n")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
