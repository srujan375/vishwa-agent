"""
Tests for LSP tools and integrations.

These tests verify:
1. Standalone LSP tools work correctly
2. LSP module components function properly
3. Enhanced existing tools with LSP fallback
4. Explore sub-agent has access to LSP tools
"""

import pytest
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestLSPProtocol:
    """Test LSP protocol types and message encoding."""

    def test_position(self):
        from vishwa.lsp.protocol import Position

        pos = Position(line=10, character=5)
        assert pos.line == 10
        assert pos.character == 5
        assert pos.to_dict() == {"line": 10, "character": 5}

        # Test from_dict
        pos2 = Position.from_dict({"line": 20, "character": 15})
        assert pos2.line == 20
        assert pos2.character == 15

    def test_range(self):
        from vishwa.lsp.protocol import Range, Position

        start = Position(line=10, character=0)
        end = Position(line=15, character=20)
        range_obj = Range(start=start, end=end)

        assert range_obj.start.line == 10
        assert range_obj.end.line == 15

        dict_repr = range_obj.to_dict()
        assert dict_repr["start"]["line"] == 10
        assert dict_repr["end"]["character"] == 20

    def test_location(self):
        from vishwa.lsp.protocol import Location, Range, Position

        loc = Location(
            uri="file:///home/user/project/src/main.py",
            range=Range(
                start=Position(line=10, character=0),
                end=Position(line=10, character=20),
            ),
        )

        assert loc.to_file_path() == "/home/user/project/src/main.py"
        assert loc.range.start.line == 10

    def test_lsp_message_encoding(self):
        from vishwa.lsp.protocol import LSPMessage

        # Test initialize message
        msg = LSPMessage.initialize("file:///project", 1)
        assert b"Content-Length:" in msg
        assert b"initialize" in msg
        assert b'"id": 1' in msg

        # Test goto_definition message
        msg = LSPMessage.goto_definition("file:///test.py", 10, 5, 2)
        assert b"textDocument/definition" in msg
        assert b'"line": 10' in msg

        # Test decoding
        decoded = LSPMessage.decode(msg)
        assert decoded["method"] == "textDocument/definition"
        assert decoded["id"] == 2


class TestLSPConfig:
    """Test LSP server configuration."""

    def test_default_servers_exist(self):
        from vishwa.lsp.config import get_lsp_config

        config = get_lsp_config()
        servers = config.list_all_servers()

        # Check that default servers are configured
        assert "python" in servers
        assert "typescript" in servers
        assert "javascript" in servers
        assert "go" in servers
        assert "rust" in servers

    def test_get_server_for_file(self):
        from vishwa.lsp.config import get_lsp_config

        config = get_lsp_config()

        # Test Python file
        python_config = config._servers.get("python")
        assert ".py" in python_config.extensions

        # Test TypeScript file
        ts_config = config._servers.get("typescript")
        assert ".ts" in ts_config.extensions
        assert ".tsx" in ts_config.extensions

    def test_install_hints(self):
        from vishwa.lsp.config import get_lsp_config

        config = get_lsp_config()

        hint = config.get_install_hint("python")
        assert "pyright" in hint

        hint = config.get_install_hint("typescript")
        assert "typescript-language-server" in hint


class TestLSPServerManager:
    """Test LSP server manager."""

    def test_server_manager_creation(self):
        from vishwa.lsp.server_manager import LSPServerManager

        manager = LSPServerManager("/tmp/test_project")
        assert manager.project_root == "/tmp/test_project"
        assert manager.root_uri == "file:///tmp/test_project"

    def test_is_available(self):
        from vishwa.lsp.server_manager import get_server_manager

        manager = get_server_manager()

        # Should return False if server not installed, but should not crash
        result = manager.is_available("test.py")
        assert isinstance(result, bool)

    def test_get_available_servers(self):
        from vishwa.lsp.server_manager import get_server_manager

        manager = get_server_manager()
        available = manager.get_available_servers()

        assert isinstance(available, dict)
        assert "python" in available
        assert isinstance(available["python"], bool)


class TestDocumentManager:
    """Test document manager."""

    def test_document_manager_creation(self):
        from vishwa.lsp.document_manager import DocumentManager

        manager = DocumentManager()
        assert len(manager.list_open_documents()) == 0

    def test_is_open(self):
        from vishwa.lsp.document_manager import DocumentManager

        manager = DocumentManager()
        assert not manager.is_open("/some/nonexistent/file.py")


class TestGoToDefinitionTool:
    """Test goto_definition tool."""

    def test_tool_properties(self):
        from vishwa.tools.lsp_tools import GoToDefinitionTool

        tool = GoToDefinitionTool()
        assert tool.name == "goto_definition"
        assert "definition" in tool.description.lower()

        params = tool.parameters
        assert params["type"] == "object"
        assert "file_path" in params["properties"]
        assert "line" in params["properties"]
        assert "character" in params["properties"]
        assert params["required"] == ["file_path", "line", "character"]

    def test_openai_format(self):
        from vishwa.tools.lsp_tools import GoToDefinitionTool

        tool = GoToDefinitionTool()
        openai_format = tool.to_openai_format()

        assert openai_format["type"] == "function"
        assert openai_format["function"]["name"] == "goto_definition"

    def test_graceful_failure_no_server(self):
        from vishwa.tools.lsp_tools import GoToDefinitionTool

        tool = GoToDefinitionTool()

        # Should fail gracefully when no LSP server is available
        result = tool.execute(
            file_path="nonexistent.py",
            line=0,
            character=0
        )

        assert not result.success or "No definition found" in (result.output or "")


class TestFindReferencesTool:
    """Test find_references tool."""

    def test_tool_properties(self):
        from vishwa.tools.lsp_tools import FindReferencesTool

        tool = FindReferencesTool()
        assert tool.name == "find_references"
        assert "references" in tool.description.lower()

        params = tool.parameters
        assert "include_declaration" in params["properties"]
        assert "max_results" in params["properties"]

    def test_graceful_failure_no_server(self):
        from vishwa.tools.lsp_tools import FindReferencesTool

        tool = FindReferencesTool()

        result = tool.execute(
            file_path="nonexistent.py",
            line=0,
            character=0
        )

        assert not result.success or "No references found" in (result.output or "")


class TestHoverTool:
    """Test hover_info tool."""

    def test_tool_properties(self):
        from vishwa.tools.lsp_tools import HoverTool

        tool = HoverTool()
        assert tool.name == "hover_info"
        assert "documentation" in tool.description.lower() or "type" in tool.description.lower()

    def test_graceful_failure_no_server(self):
        from vishwa.tools.lsp_tools import HoverTool

        tool = HoverTool()

        result = tool.execute(
            file_path="nonexistent.py",
            line=0,
            character=0
        )

        assert not result.success or "No hover information" in (result.output or "")


class TestLSPStatusTool:
    """Test lsp_status tool."""

    def test_tool_properties(self):
        from vishwa.tools.lsp_tools import LSPStatusTool

        tool = LSPStatusTool()
        assert tool.name == "lsp_status"
        assert tool.parameters["required"] == []

    def test_execute(self):
        from vishwa.tools.lsp_tools import LSPStatusTool

        tool = LSPStatusTool()
        result = tool.execute()

        assert result.success
        assert "python" in result.output.lower()
        assert "typescript" in result.output.lower()
        assert result.metadata is not None
        assert "available" in result.metadata


class TestToolRegistration:
    """Test that LSP tools are registered correctly."""

    def test_lsp_tools_registered(self):
        from vishwa.tools.base import ToolRegistry

        registry = ToolRegistry.load_default()
        tool_names = registry.list_names()

        # Check all LSP tools are registered
        assert "goto_definition" in tool_names
        assert "find_references" in tool_names
        assert "hover_info" in tool_names
        assert "lsp_status" in tool_names

    def test_tools_have_valid_format(self):
        from vishwa.tools.base import ToolRegistry

        registry = ToolRegistry.load_default()

        for tool_name in ["goto_definition", "find_references", "hover_info", "lsp_status"]:
            tool = registry.get(tool_name)
            assert tool is not None

            openai_format = tool.to_openai_format()
            assert openai_format["type"] == "function"
            assert "name" in openai_format["function"]
            assert "description" in openai_format["function"]
            assert "parameters" in openai_format["function"]


class TestReadSymbolToolWithLSP:
    """Test enhanced ReadSymbolTool with LSP support."""

    def test_has_use_lsp_parameter(self):
        from vishwa.tools.analyze import ReadSymbolTool

        tool = ReadSymbolTool()
        params = tool.parameters

        assert "use_lsp" in params["properties"]
        assert params["properties"]["use_lsp"]["type"] == "boolean"

    def test_fallback_to_regex(self):
        """Test that it falls back to regex when LSP not available."""
        from vishwa.tools.analyze import ReadSymbolTool

        tool = ReadSymbolTool()

        # Create a test file
        test_file = Path(__file__).parent.parent / "src" / "vishwa" / "tools" / "base.py"

        if test_file.exists():
            result = tool.execute(
                path=str(test_file),
                symbol_name="Tool",
                symbol_type="class",
                use_lsp=False  # Force regex
            )

            # Should succeed with regex fallback
            if result.success:
                assert "method" in result.metadata
                assert result.metadata["method"] == "regex"


class TestCodebaseExplorerWithLSP:
    """Test enhanced CodebaseExplorerTool with LSP support."""

    def test_has_lsp_parameters(self):
        from vishwa.tools.codebase_explorer import CodebaseExplorerTool

        tool = CodebaseExplorerTool()
        params = tool.parameters

        assert "find_symbol_usages" in params["properties"]
        assert "symbol_file" in params["properties"]
        assert "symbol_line" in params["properties"]
        assert "symbol_character" in params["properties"]


class TestExploreAgentHasLSPTools:
    """Test that Explore sub-agent has access to LSP tools."""

    def test_explore_agent_tool_list(self):
        from vishwa.tools.task import TaskTool

        # Check the description mentions LSP tools
        tool = TaskTool(llm=None, tool_registry=None)
        description = tool.description

        assert "goto_definition" in description
        assert "find_references" in description
        assert "hover_info" in description

    def test_explore_prompt_mentions_lsp(self):
        from vishwa.tools.task import TaskTool

        tool = TaskTool(llm=None, tool_registry=None)
        prompt = tool._build_explore_prompt("test task", "medium")

        assert "goto_definition" in prompt
        assert "find_references" in prompt
        assert "hover_info" in prompt
        assert "LSP" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
