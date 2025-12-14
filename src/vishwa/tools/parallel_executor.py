"""
Parallel Executor Tool - Execute multiple tool calls concurrently.

This significantly improves performance by running independent operations
in parallel instead of sequentially.
"""

import asyncio
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from vishwa.tools.base import Tool, ToolResult, ToolRegistry
from vishwa.utils.logger import logger


@dataclass
class BatchOperation:
    """Single operation in a batch"""
    tool_name: str
    arguments: Dict[str, Any]
    operation_id: str


class ParallelExecutorTool(Tool):
    """
    Execute multiple tool operations in parallel.

    This tool accepts a list of operations and executes them concurrently
    using ThreadPoolExecutor. Operations that don't have dependencies
    can run in parallel, significantly reducing total execution time.

    Example use cases:
    - Reading multiple files at once
    - Running multiple grep searches
    - Executing independent bash commands
    - File analysis operations
    """

    @property
    def name(self) -> str:
        return "execute_parallel"

    @property
    def description(self) -> str:
        return """Execute multiple tool operations in parallel for improved performance.

This tool can run independent operations concurrently, reducing total execution time.
Perfect for reading multiple files, running searches, or executing independent bash commands.

Parameters:
- operations: List of operations to execute (each with tool_name, arguments, operation_id)
- max_workers: Maximum concurrent workers (default: 4, max: 8)
- timeout: Timeout per operation in seconds (default: 30)

Example:
[
  {
    "tool_name": "read_file",
    "arguments": {"path": "file1.py"},
    "operation_id": "read_file1"
  },
  {
    "tool_name": "grep",
    "arguments": {"pattern": "TODO", "glob": "**/*.py"},
    "operation_id": "search_todos"
  }
]

Returns results for each operation with their operation_id for easy reference.
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operations": {
                    "type": "array",
                    "description": "List of operations to execute in parallel",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tool_name": {
                                "type": "string",
                                "description": "Name of the tool to execute"
                            },
                            "arguments": {
                                "type": "object",
                                "description": "Arguments for the tool"
                            },
                            "operation_id": {
                                "type": "string",
                                "description": "Unique identifier for this operation"
                            }
                        },
                        "required": ["tool_name", "arguments", "operation_id"]
                    }
                },
                "max_workers": {
                    "type": "integer",
                    "description": "Maximum concurrent workers (1-8, default: 4)",
                    "default": 4
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout per operation in seconds (default: 30)",
                    "default": 30
                }
            },
            "required": ["operations"]
        }

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        """Initialize with access to tool registry"""
        self.tool_registry = tool_registry

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute operations in parallel"""
        self.validate_params(**kwargs)
        operations_data = kwargs["operations"]
        max_workers = min(kwargs.get("max_workers", 4), 8)  # Cap at 8
        timeout = kwargs.get("timeout", 30)

        # Validate operations
        if not operations_data:
            return ToolResult(
                success=False,
                error="No operations provided"
            )

        if len(operations_data) > 20:  # Limit batch size
            return ToolResult(
                success=False,
                error="Too many operations (max: 20)",
                suggestion="Split into smaller batches"
            )

        # Convert to BatchOperation objects
        operations = []
        operation_ids = set()
        
        for op_data in operations_data:
            op = BatchOperation(
                tool_name=op_data["tool_name"],
                arguments=op_data["arguments"],
                operation_id=op_data["operation_id"]
            )
            
            # Check for duplicate IDs
            if op.operation_id in operation_ids:
                return ToolResult(
                    success=False,
                    error=f"Duplicate operation_id: {op.operation_id}"
                )
            operation_ids.add(op.operation_id)
            
            operations.append(op)

        # Check if all tools exist
        missing_tools = []
        for op in operations:
            if not self.tool_registry or not self.tool_registry.get(op.tool_name):
                missing_tools.append(op.tool_name)
        
        if missing_tools:
            return ToolResult(
                success=False,
                error=f"Tools not found: {missing_tools}",
                suggestion="Use only available tools from the registry"
            )

        # Execute in parallel
        try:
            results = self._execute_parallel(operations, max_workers, timeout)
            
            # Format output
            output_lines = [f"Parallel execution completed: {len(operations)} operations"]
            output_lines.append(f"Successful: {sum(1 for r in results.values() if r.success)}")
            output_lines.append(f"Failed: {sum(1 for r in results.values() if not r.success)}")
            output_lines.append("")
            
            for op_id, result in results.items():
                status = "✓" if result.success else "✗"
                output_lines.append(f"[{status}] {op_id}:")
                
                if result.success and result.output:
                    # Truncate long outputs
                    output = result.output
                    if len(output) > 200:
                        output = output[:200] + "..."
                    output_lines.append(f"  {output}")
                elif not result.success and result.error:
                    output_lines.append(f"  Error: {result.error}")
            
            output = "\n".join(output_lines)
            
            return ToolResult(
                success=True,
                output=output,
                metadata={
                    "total_operations": len(operations),
                    "successful": sum(1 for r in results.values() if r.success),
                    "failed": sum(1 for r in results.values() if not r.success),
                    "results": {
                        op_id: {
                            "success": result.success,
                            "output": result.output,
                            "error": result.error
                        }
                        for op_id, result in results.items()
                    }
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Parallel execution failed: {str(e)}"
            )

    def _execute_parallel(
        self,
        operations: List[BatchOperation],
        max_workers: int,
        timeout: int
    ) -> Dict[str, ToolResult]:
        """Execute operations in parallel using ThreadPoolExecutor"""
        results = {}
        
        # Use ThreadPoolExecutor for CPU-bound operations
        # For I/O-bound operations, could use asyncio
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all operations
            future_to_op = {
                executor.submit(self._execute_single, op): op.operation_id
                for op in operations
            }
            
            # Collect results
            for future in as_completed(future_to_op):
                op_id = future_to_op[future]
                try:
                    result = future.result(timeout=timeout)
                    results[op_id] = result
                except concurrent.futures.TimeoutError:
                    results[op_id] = ToolResult(
                        success=False,
                        error=f"Operation timed out after {timeout} seconds"
                    )
                except Exception as e:
                    results[op_id] = ToolResult(
                        success=False,
                        error=f"Execution failed: {str(e)}"
                    )
        
        return results

    def _execute_single(self, operation: BatchOperation) -> ToolResult:
        """Execute a single operation"""
        try:
            tool = self.tool_registry.get(operation.tool_name)
            if not tool:
                return ToolResult(
                    success=False,
                    error=f"Tool not found: {operation.tool_name}"
                )
            
            # Execute the tool
            result = tool.execute(**operation.arguments)
            
            # Log execution
            logger.tool_result(
                operation.tool_name,
                result.success,
                result.output,
                result.error
            )
            
            return result
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(e)}"
            )


class BatchFileReader(Tool):
    """
    Read multiple files efficiently in a single operation.
    
    This is a specialized tool for the common pattern of reading multiple files,
    providing better UX and performance than general parallel execution.
    """

    @property
    def name(self) -> str:
        return "batch_read_files"

    @property
    def description(self) -> str:
        return """Read multiple files in a single efficient operation.
        
This tool reads multiple files concurrently, making it much faster than
reading them one by one. Perfect for analyzing project structure or
reading related configuration files.

Parameters:
- file_paths: List of file paths to read (max: 10 files)
- show_line_numbers: Include line numbers in output (default: true)

Example:
{
  "file_paths": ["config.py", "requirements.txt", "README.md"],
  "show_line_numbers": true
}

Returns file contents with clear separators between files.
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_paths": {
                    "type": "array",
                    "description": "List of file paths to read (max: 10)",
                    "items": {"type": "string"},
                    "maxItems": 10
                },
                "show_line_numbers": {
                    "type": "boolean",
                    "description": "Include line numbers in output (default: true)",
                    "default": true
                }
            },
            "required": ["file_paths"]
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Read multiple files in parallel"""
        self.validate_params(**kwargs)
        file_paths = kwargs["file_paths"]
        show_line_numbers = kwargs.get("show_line_numbers", True)

        if len(file_paths) > 10:
            return ToolResult(
                success=False,
                error="Too many files (max: 10)"
            )

        # Use parallel executor internally
        from vishwa.tools.file_ops import ReadFileTool
        
        operations = []
        for i, path in enumerate(file_paths):
            operations.append({
                "tool_name": "read_file",
                "arguments": {
                    "path": path,
                    "show_line_numbers": show_line_numbers
                },
                "operation_id": f"read_{i}"
            })
        
        # Create temporary parallel executor
        from vishwa.tools.base import ToolRegistry
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        
        executor = ParallelExecutorTool(registry)
        result = executor.execute(
            operations=operations,
            max_workers=min(len(file_paths), 4)
        )
        
        # Reformat output for better UX
        if result.success and result.metadata:
            output_lines = [f"Read {len(file_paths)} files:\n"]
            
            # Parse results back to individual files
            for i, path in enumerate(file_paths):
                op_id = f"read_{i}"
                file_result = result.metadata["results"].get(op_id)
                
                if file_result and file_result["success"]:
                    output_lines.append(f"\n=== {path} ===")
                    output_lines.append(file_result["output"])
                else:
                    output_lines.append(f"\n=== {path} ===")
                    output_lines.append(f"Error: {file_result['error'] if file_result else 'Unknown error'}")
            
            result.output = "\n".join(output_lines)
        
        return result