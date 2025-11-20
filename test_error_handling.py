"""
Test for improved tool parameter validation error handling.

This verifies that missing tool parameters are caught early with helpful error messages.
"""

from vishwa.agent.core import VishwaAgent
from vishwa.llm.response import LLMResponse, ToolCall
from vishwa.tools.base import ToolRegistry


def test_missing_parameter_validation():
    """Test that missing required parameters are caught with helpful error messages"""
    print("Testing missing parameter validation...")

    # Create a registry with tools
    registry = ToolRegistry.load_default(auto_approve=True)

    # Get the write_file tool
    write_file_tool = registry.get("write_file")
    assert write_file_tool is not None, "write_file tool should be in registry"

    # Create a tool call missing the required 'content' parameter
    tool_call = ToolCall(
        id="test_123",
        name="write_file",
        arguments={"path": "/tmp/test.txt"}  # Missing 'content' parameter
    )

    # Create a mock LLM that just returns this tool call
    class MockLLM:
        @property
        def model_name(self):
            return "mock-model"

        @property
        def provider_name(self):
            return "mock"

        def chat(self, messages, tools=None, system=None):
            # Return a response with the problematic tool call
            return LLMResponse(
                content="Testing parameter validation",
                tool_calls=[tool_call],
                model="mock-model",
                usage=None
            )

        def supports_tools(self):
            return True

    # Create agent with mock LLM
    agent = VishwaAgent(
        llm=MockLLM(),
        tools=registry,
        max_iterations=1,
        auto_approve=True,
        verbose=False
    )

    # Execute the tool call directly (simulating what happens in the agent loop)
    result = agent._execute_tool_call(tool_call)

    # Verify the result
    print(f"\nResult success: {result.success}")
    print(f"Error message:\n{result.error}")
    print(f"Suggestion: {result.suggestion}")

    # Assertions
    assert not result.success, "Tool call should fail"
    assert "Missing required parameter: content" in result.error, "Error should mention missing parameter"
    assert "Required parameters for write_file" in result.error, "Error should list required parameters"
    assert "['path', 'content']" in result.error, "Error should show what parameters are required"
    assert "Provided parameters: ['path']" in result.error, "Error should show what was provided"
    assert "Missing: ['content']" in result.error, "Error should explicitly list missing parameters"

    print("\n✓ All assertions passed!")
    print("\nThe error message now provides:")
    print("  1. Clear identification of the missing parameter")
    print("  2. List of all required parameters")
    print("  3. List of what was actually provided")
    print("  4. Explicit list of what's missing")
    print("  5. Suggestion to retry with all parameters")

    return True


def test_all_parameters_provided():
    """Test that tool calls with all parameters work correctly"""
    print("\n\nTesting tool call with all required parameters...")

    registry = ToolRegistry.load_default(auto_approve=True)
    write_file_tool = registry.get("write_file")

    # This time provide all required parameters
    tool_call = ToolCall(
        id="test_456",
        name="write_file",
        arguments={
            "path": "/tmp/test_success.txt",
            "content": "This is a test file"
        }
    )

    class MockLLM:
        @property
        def model_name(self):
            return "mock-model"

        @property
        def provider_name(self):
            return "mock"

        def chat(self, messages, tools=None, system=None):
            return LLMResponse(
                content="Creating test file",
                tool_calls=[tool_call],
                model="mock-model",
                usage=None
            )

        def supports_tools(self):
            return True

    agent = VishwaAgent(
        llm=MockLLM(),
        tools=registry,
        max_iterations=1,
        auto_approve=True,
        verbose=False
    )

    # Execute the tool call
    result = agent._execute_tool_call(tool_call)

    print(f"\nResult success: {result.success}")
    if not result.success:
        print(f"Error: {result.error}")
    else:
        print(f"Output: {result.output}")

    # Should succeed since all parameters are provided
    assert result.success, "Tool call with all parameters should succeed"

    print("\n✓ Tool call succeeded with all required parameters!")

    # Clean up
    import os
    if os.path.exists("/tmp/test_success.txt"):
        os.remove("/tmp/test_success.txt")

    return True


def main():
    """Run all error handling tests"""
    print("=" * 70)
    print("Vishwa Tool Parameter Validation Error Handling Test")
    print("=" * 70)

    results = []

    try:
        results.append(("Missing parameter validation", test_missing_parameter_validation()))
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Missing parameter validation", False))

    try:
        results.append(("Valid parameters", test_all_parameters_provided()))
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Valid parameters", False))

    print("\n" + "=" * 70)
    print("Test Results")
    print("=" * 70)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False

    print("=" * 70)

    if all_passed:
        print("\n✅ All tests passed! Error handling is working correctly.")
        print("\nWhat was improved:")
        print("  • Early parameter validation before tool execution")
        print("  • Clear error messages showing required vs provided parameters")
        print("  • Explicit list of missing parameters")
        print("  • Helpful suggestions for fixing the error")
        print("  • System prompt instructions for LLM to learn from errors")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
