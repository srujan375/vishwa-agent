"""
Streaming LLM Support - Real-time response streaming.

This module provides streaming support for LLM responses, allowing real-time
display of thinking and tool execution progress.
"""

import json
import time
from typing import Any, Dict, List, Optional, Callable, AsyncIterator
from dataclasses import dataclass

from vishwa.llm.response import LLMResponse, ToolCall
from vishwa.utils.logger import logger


@dataclass
class StreamChunk:
    """Represents a chunk of streamed data"""
    type: str  # "message", "tool_call", "observation", "thinking"
    content: str
    metadata: Optional[Dict[str, Any]] = None


class StreamingLLM:
    """
    Wrapper for LLM providers that support streaming.
    
    This class provides a streaming interface for LLM responses,
    allowing real-time display of thinking and partial responses.
    """

    def __init__(self, base_llm):
        """
        Initialize streaming wrapper.
        
        Args:
            base_llm: Base LLM provider instance
        """
        self.base_llm = base_llm
        self.provider_name = base_llm.provider_name
        self.model_name = base_llm.model_name

    def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system: Optional[str] = None,
        stream_handler: Optional[Callable[[StreamChunk], None]] = None
    ) -> LLMResponse:
        """
        Stream chat response from LLM.
        
        Args:
            messages: Chat messages
            tools: Available tools
            system: System prompt
            stream_handler: Callback for streaming chunks
            
        Returns:
            Final LLMResponse
        """
        # Try to use streaming if available
        try:
            return self._stream_with_handler(
                messages=messages,
                tools=tools,
                system=system,
                stream_handler=stream_handler
            )
        except Exception as e:
            logger.error("streaming", f"Streaming failed, falling back: {e}")
            # Fallback to non-streaming
            return self.base_llm.chat(
                messages=messages,
                tools=tools,
                system=system
            )

    def _stream_with_handler(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        system: Optional[str],
        stream_handler: Optional[Callable[[StreamChunk], None]]
    ) -> LLMResponse:
        """Stream with handler callback"""
        if stream_handler is None:
            # No handler, just return normal response
            return self.base_llm.chat(
                messages=messages,
                tools=tools,
                system=system
            )
        
        # This is a simplified implementation
        # In practice, you'd use the provider's actual streaming API
        partial_content = ""
        final_response = None
        
        # For now, we'll simulate streaming by chunking the response
        # In a real implementation, this would be:
        # async for chunk in self.base_llm.stream(...):
        #     stream_handler(chunk)
        
        # Get full response first (for demonstration)
        full_response = self.base_llm.chat(
            messages=messages,
            tools=tools,
            system=system
        )
        
        # Simulate streaming by sending chunks
        if full_response.content:
            # Split content into chunks
            words = full_response.content.split()
            chunk_size = max(1, len(words) // 10)  # 10 chunks
            
            for i in range(0, len(words), chunk_size):
                chunk_words = words[i:i + chunk_size]
                chunk_content = " ".join(chunk_words)
                
                if i == 0:
                    stream_chunk = StreamChunk(
                        type="thinking",
                        content=chunk_content
                    )
                else:
                    stream_chunk = StreamChunk(
                        type="message",
                        content=chunk_content,
                        metadata={"partial": True}
                    )
                
                stream_handler(stream_chunk)
                time.sleep(0.1)  # Small delay to simulate streaming
        
        # Send final tool calls if any
        if full_response.tool_calls:
            for tool_call in full_response.tool_calls:
                stream_chunk = StreamChunk(
                    type="tool_call",
                    content=f"Calling tool: {tool_call.name}",
                    metadata={"tool_call": tool_call.to_dict()}
                )
                stream_handler(stream_chunk)
        
        return full_response


class StreamingConsole:
    """
    Console for displaying streaming output.
    
    This class handles the display of streaming chunks with
    proper formatting and user experience considerations.
    """

    def __init__(self, console):
        """
        Initialize streaming console.
        
        Args:
            console: Rich Console instance
        """
        self.console = console
        self.current_tool = None
        self.tool_output_buffer = ""

    def stream_handler(self, chunk: StreamChunk) -> None:
        """Handle streaming chunk"""
        if chunk.type == "thinking":
            # Display thinking/analysis
            self.console.print(f"[dim]{chunk.content}[/dim]", end="")
            
        elif chunk.type == "message":
            # Display message content
            if chunk.metadata and chunk.metadata.get("partial"):
                # Partial message, just continue
                self.console.print(chunk.content, end="")
            else:
                # New message
                self.console.print(f"\n{chunk.content}")
                
        elif chunk.type == "tool_call":
            # Display tool call
            tool_name = chunk.metadata.get("tool_call", {}).get("name", "unknown")
            self.console.print(f"\n[cyan]→[/cyan] [bold]{tool_name}[/bold]")
            self.current_tool = tool_name
            
        elif chunk.type == "observation":
            # Display tool result
            self.console.print(f"[green]✓[/green] {chunk.content}")
            self.current_tool = None
            
        elif chunk.type == "error":
            # Display error
            self.console.print(f"[red]✗[/red] {chunk.content}")
            self.current_tool = None


class ProgressTracker:
    """
    Track and display progress of long-running operations.
    
    This helps users understand what's happening during
    parallel operations or file processing.
    """

    def __init__(self, console):
        """Initialize progress tracker"""
        self.console = console
        self.active_tasks: Dict[str, Any] = {}

    def start_task(
        self,
        task_id: str,
        description: str,
        total: Optional[int] = None
    ) -> None:
        """Start tracking a task"""
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
        
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn() if total else None,
            TaskProgressColumn() if total else None,
            console=self.console,
            transient=False
        )
        
        task = progress.add_task(description, total=total)
        
        self.active_tasks[task_id] = {
            "progress": progress,
            "task": task,
            "start_time": time.time()
        }
        
        progress.start()

    def update_task(
        self,
        task_id: str,
        completed: Optional[int] = None,
        description: Optional[str] = None
    ) -> None:
        """Update task progress"""
        task_info = self.active_tasks.get(task_id)
        if not task_info:
            return
        
        progress = task_info["progress"]
        task = task_info["task"]
        
        if completed is not None:
            progress.update(task, completed=completed)
        
        if description:
            progress.update(task, description=description)

    def stop_task(self, task_id: str, success: bool = True) -> None:
        """Stop tracking a task"""
        task_info = self.active_tasks.get(task_id)
        if not task_info:
            return
        
        progress = task_info["progress"]
        
        # Calculate duration
        duration = time.time() - task_info["start_time"]
        
        # Show completion message
        if success:
            self.console.print(f"[green]✓[/green] Completed in {duration:.2f}s")
        else:
            self.console.print(f"[red]✗[/red] Failed after {duration:.2f}s")
        
        progress.stop()
        del self.active_tasks[task_id]


class BatchOperationProgress:
    """
    Display progress for batch operations.
    
    This shows progress for operations like:
    - Parallel file reading
    - Multiple grep searches
    - Bulk file modifications
    """

    def __init__(self, console):
        """Initialize batch operation tracker"""
        self.console = console
        self.active_batches: Dict[str, Any] = {}

    def start_batch(
        self,
        batch_id: str,
        operation_type: str,
        total_items: int
    ) -> None:
        """Start tracking a batch operation"""
        from rich.table import Table
        from rich.live import Live
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
        
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold yellow]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
            transient=True
        )
        
        task = progress.add_task(
            f"{operation_type} ({total_items} items)",
            total=total_items
        )
        
        self.active_batches[batch_id] = {
            "progress": progress,
            "task": task,
            "total": total_items,
            "completed": 0,
            "successful": 0,
            "failed": 0,
            "start_time": time.time()
        }

    def update_batch(self, batch_id: str, completed: int = None, successful: int = None, failed: int = None) -> None:
        """Update batch progress"""
        batch_info = self.active_batches.get(batch_id)
        if not batch_info:
            return
        
        progress = batch_info["progress"]
        task = batch_info["task"]
        
        if completed is not None:
            batch_info["completed"] = completed
            progress.update(task, completed=completed)
        
        if successful is not None:
            batch_info["successful"] = successful
            
        if failed is not None:
            batch_info["failed"] = failed

    def complete_batch(self, batch_id: str) -> None:
        """Complete batch operation"""
        batch_info = self.active_batches.get(batch_id)
        if not batch_info:
            return
        
        progress = batch_info["progress"]
        duration = time.time() - batch_info["start_time"]
        
        # Show summary
        self.console.print(
            f"\n[bold]Batch completed:[/bold] "
            f"{batch_info['successful']} successful, "
            f"{batch_info['failed']} failed "
            f"in {duration:.2f}s"
        )
        
        progress.stop()
        del self.active_batches[batch_id]


def create_streaming_wrapper(base_llm):
    """
    Create streaming wrapper for LLM.
    
    Args:
        base_llm: Base LLM provider
        
    Returns:
        StreamingLLM instance
    """
    return StreamingLLM(base_llm)


def create_streaming_console(console):
    """
    Create streaming console for display.
    
    Args:
        console: Rich Console instance
        
    Returns:
        StreamingConsole instance
    """
    return StreamingConsole(console)


def create_progress_tracker(console):
    """
    Create progress tracker for operations.
    
    Args:
        console: Rich Console instance
        
    Returns:
        ProgressTracker instance
    """
    return ProgressTracker(console)


def create_batch_progress(console):
    """
    Create batch operation tracker.
    
    Args:
        console: Rich Console instance
        
    Returns:
        BatchOperationProgress instance
    """
    return BatchOperationProgress(console)


# Integration with existing agent
def enhance_agent_with_streaming(agent, console):
    """
    Enhance agent with streaming capabilities.
    
    Args:
        agent: VishwaAgent instance
        console: Rich Console instance
    """
    # Create streaming components
    streaming_console = create_streaming_console(console)
    progress_tracker = create_progress_tracker(console)
    batch_progress = create_batch_progress(console)
    
    # Store on agent for access by tools
    agent.streaming_console = streaming_console
    agent.progress_tracker = progress_tracker
    agent.batch_progress = batch_progress
    
    # Enhance LLM with streaming
    if hasattr(agent, 'llm'):
        agent.llm = create_streaming_wrapper(agent.llm)
    
    logger.info("streaming", "Agent enhanced with streaming capabilities")


# Tool integration for showing progress
class ProgressTool:
    """
    Tool for showing progress updates.
    
    This tool can be called by the agent to show
    progress for long-running operations.
    """

    @property
    def name(self) -> str:
        return "show_progress"

    @property
    def description(self) -> str:
        return """Show progress for ongoing operations.
        
This tool helps display progress for:
- Parallel operations
- File processing
- Long-running searches
- Batch modifications

Parameters:
- operation_type: Type of operation (e.g., "reading files", "searching")
- current: Current progress (0-100)
- total: Total items
- message: Additional message
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation_type": {
                    "type": "string",
                    "description": "Type of operation"
                },
                "current": {
                    "type": "integer",
                    "description": "Current progress (0-100)"
                },
                "total": {
                    "type": "integer",
                    "description": "Total items"
                },
                "message": {
                    "type": "string",
                    "description": "Additional message"
                }
            },
            "required": ["operation_type", "current"]
        }

    def execute(self, **kwargs) -> None:
        """Show progress update"""
        # This would integrate with the agent's streaming console
        # Implementation depends on how it's integrated
        pass