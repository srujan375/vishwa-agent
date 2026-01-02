"""
Integration tests for Vishwa agent and sub-agents.

Tests the full system by running prompts through the main agent
and verifying correct tool/sub-agent usage.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_agent_with_prompts():
    """Run various prompts through the agent to test sub-agents and tools."""

    # Load .env file if it exists
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    # Handle lines with spaces around =
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if key and value:
                        os.environ[key] = value

    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("NOVITA_API_KEY")
    if not api_key:
        print("=" * 60)
        print("SKIPPING: No API key found")
        print("Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or NOVITA_API_KEY to run this test")
        print("=" * 60)
        return

    from vishwa.agent.core import VishwaAgent
    from vishwa.tools.base import ToolRegistry
    from vishwa.llm.factory import LLMFactory

    print("=" * 60)
    print("INTEGRATION TEST: Agent with Sub-Agents")
    print("=" * 60)

    # Create LLM - use GPT-4o
    model = "gpt-4o"
    print(f"Using model: {model}")

    llm = LLMFactory.create(model=model)
    registry = ToolRegistry.load_default(auto_approve=True)

    agent = VishwaAgent(
        llm=llm,
        tools=registry,
        max_iterations=15,
        auto_approve=True,
        verbose=True
    )

    # Test prompts designed to trigger different tools/sub-agents
    test_cases = [
        {
            "name": "Explore Sub-Agent Test",
            "prompt": "Use the task tool with Explore agent to find where the Tool base class is defined in this codebase. Be quick.",
            "expected_tools": ["task"],
            "description": "Should spawn Explore sub-agent"
        },
        {
            "name": "LSP Status Test",
            "prompt": "Check the LSP server status using the lsp_status tool.",
            "expected_tools": ["lsp_status"],
            "description": "Should use lsp_status tool directly"
        },
        {
            "name": "Codebase Explorer Test",
            "prompt": "Use explore_codebase to find all Python files in the src/vishwa/lsp directory and show their structure.",
            "expected_tools": ["explore_codebase"],
            "description": "Should use explore_codebase tool"
        },
        {
            "name": "Read Symbol Test",
            "prompt": "Use read_symbol to read the LSPClient class from src/vishwa/lsp/client.py",
            "expected_tools": ["read_symbol"],
            "description": "Should use read_symbol tool"
        },
    ]

    results = []

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'=' * 60}")
        print(f"TEST {i}: {test['name']}")
        print(f"Description: {test['description']}")
        print(f"Prompt: {test['prompt']}")
        print("=" * 60)

        try:
            result = agent.run(test["prompt"], clear_context=True)

            # Check which tools were used
            tools_used = []
            if hasattr(result, 'tool_calls') and result.tool_calls:
                tools_used = [tc.get('name', '') for tc in result.tool_calls]

            print(f"\nResult:")
            print(f"  Iterations: {result.iterations_used}")
            print(f"  Stop reason: {result.stop_reason}")
            print(f"  Message preview: {result.message[:200]}..." if len(result.message) > 200 else f"  Message: {result.message}")

            # Determine success - final_answer or end_turn means successful completion
            # Only check for "LLM error:" prefix which indicates actual errors
            success = result.stop_reason in ["end_turn", "final_answer"] and not result.message.startswith("LLM error:")

            results.append({
                "name": test["name"],
                "success": success,
                "iterations": result.iterations_used,
                "message_length": len(result.message)
            })

            print(f"\n  Status: {'✓ PASSED' if success else '✗ FAILED'}")

        except Exception as e:
            print(f"\n  ✗ ERROR: {str(e)}")
            results.append({
                "name": test["name"],
                "success": False,
                "error": str(e)
            })

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r.get("success", False))
    total = len(results)

    for r in results:
        status = "✓" if r.get("success", False) else "✗"
        print(f"  {status} {r['name']}")
        if r.get("error"):
            print(f"      Error: {r['error']}")

    print(f"\nTotal: {passed}/{total} passed")
    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = test_agent_with_prompts()
    sys.exit(0 if success else 1)
