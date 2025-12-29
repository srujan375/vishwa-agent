#!/usr/bin/env python3
"""Test script to verify sub-agent functionality"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from vishwa.llm.factory import LLMFactory
from vishwa.tools.base import ToolRegistry, Tool
from vishwa.tools.task import TaskTool

def main():
    print("Testing Vishwa Sub-Agents")
    print("=" * 50)

    # Load LLM
    print("\n1. Loading LLM provider...")
    llm = LLMFactory.create()
    print(f"   Provider: {llm.provider_name}")
    print(f"   Model: {llm.model_name}")

    # Load default tools
    print("\n2. Loading default tool registry...")
    tools = ToolRegistry.load_default()
    print(f"   Available tools: {len(tools.all())}")
    print(f"   Tool names: {tools.list_names()}")

    # Register TaskTool manually for testing
    print("\n3. Registering TaskTool...")
    task_tool = TaskTool(llm_provider=llm, tools=tools)
    tools.register(task_tool)
    print(f"   TaskTool registered: {tools.get('task') is not None}")

    # Check task tool capabilities
    print("\n4. TaskTool Capabilities:")
    print(f"   Sub-agent types: {task_tool.subagent_types}")

    # Test a simple Explore sub-agent task
    print("\n5. Testing Explore sub-agent...")
    result = task_tool.execute(
        subagent_type="Explore",
        description="Find Python files",
        prompt="Find all Python files in the src directory and list their paths. Be very brief - just list the files.",
        thoroughness="quick"
    )

    print(f"\n   Result:")
    print(f"   Success: {result.success}")
    print(f"   Stop reason: {result.metadata.get('stop_reason', 'N/A') if result.metadata else 'N/A'}")
    print(f"   Iterations: {result.metadata.get('iterations_used', 'N/A') if result.metadata else 'N/A'}")
    print(f"   Output: {result.output[:200] if result.output else 'None'}...")

    print("\n" + "=" * 50)
    print("Sub-agent test completed!")
    print("=" * 50)

if __name__ == "__main__":
    main()
