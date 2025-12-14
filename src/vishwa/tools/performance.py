"""
Performance Monitoring - Comprehensive performance tracking and analysis.

This module provides detailed performance monitoring for:
- Tool execution times
- LLM response times
- Memory usage
- Cache hit rates
- Iteration efficiency
- User interaction patterns
"""

import psutil
import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path

from vishwa.utils.logger import logger


@dataclass
class PerformanceMetrics:
    """Performance metrics for a single operation"""
    operation: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    success: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def complete(self, success: bool = True, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Mark operation as complete"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.success = success
        
        if metadata:
            self.metadata.update(metadata)


@dataclass
class PerformanceReport:
    """Comprehensive performance report"""
    total_operations: int
    successful_operations: int
    failed_operations: int
    total_duration_ms: float
    avg_duration_ms: float
    p50_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    slowest_operations: List[Dict[str, Any]]
    operation_counts: Dict[str, int]
    memory_usage_mb: float
    cache_stats: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system.
    
    This class tracks:
    - Tool execution times
    - LLM response times
    - Memory usage
    - Cache performance
    - Iteration efficiency
    """

    def __init__(self, max_history: int = 1000):
        """
        Initialize performance monitor.
        
        Args:
            max_history: Maximum number of operations to keep in history
        """
        self.max_history = max_history
        self.metrics: deque = deque(maxlen=max_history)
        self.active_operations: Dict[str, PerformanceMetrics] = {}
        self.operation_stats: defaultdict = defaultdict(lambda: {
            "count": 0,
            "total_duration": 0,
            "success_count": 0,
            "fail_count": 0,
            "durations": deque(maxlen=100)
        })
        
        # System monitoring
        self.memory_samples: deque = deque(maxlen=100)
        self.cpu_samples: deque = deque(maxlen=100)
        
        # Cache monitoring
        self.cache_operations: deque = deque(maxlen=500)
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Start system monitoring
        self._start_system_monitoring()

    def start_operation(self, operation: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Start tracking an operation.
        
        Args:
            operation: Operation name
            metadata: Optional metadata
            
        Returns:
            Operation ID for stopping
        """
        operation_id = f"{operation}_{time.time()}_{id(threading.current_thread())}"
        
        metrics = PerformanceMetrics(
            operation=operation,
            start_time=time.time(),
            metadata=metadata or {}
        )
        
        with self._lock:
            self.active_operations[operation_id] = metrics
        
        return operation_id

    def stop_operation(
        self,
        operation_id: str,
        success: bool = True,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Stop tracking an operation.
        
        Args:
            operation_id: Operation ID from start_operation
            success: Whether operation was successful
            additional_metadata: Additional metadata to add
        """
        with self._lock:
            metrics = self.active_operations.pop(operation_id, None)
            
            if metrics:
                if additional_metadata:
                    metrics.metadata.update(additional_metadata)
                
                metrics.complete(success=success)
                self.metrics.append(metrics)
                
                # Update stats
                stats = self.operation_stats[metrics.operation]
                stats["count"] += 1
                stats["total_duration"] += metrics.duration_ms
                
                if success:
                    stats["success_count"] += 1
                else:
                    stats["fail_count"] += 1
                
                if metrics.duration_ms:
                    stats["durations"].append(metrics.duration_ms)

    def track_tool_execution(
        self,
        tool_name: str,
        start_time: float,
        end_time: float,
        success: bool,
        output_size: Optional[int] = None
    ) -> None:
        """Track tool execution performance"""
        operation_id = self.start_operation(
            f"tool.{tool_name}",
            metadata={
                "tool_name": tool_name,
                "output_size": output_size
            }
        )
        
        self.stop_operation(
            operation_id,
            success=success,
            additional_metadata={
                "duration_ms": (end_time - start_time) * 1000
            }
        )

    def track_llm_request(
        self,
        provider: str,
        model: str,
        start_time: float,
        end_time: float,
        tokens_used: Optional[int] = None,
        success: bool = True
    ) -> None:
        """Track LLM request performance"""
        operation_id = self.start_operation(
            "llm.request",
            metadata={
                "provider": provider,
                "model": model,
                "tokens_used": tokens_used
            }
        )
        
        self.stop_operation(
            operation_id,
            success=success,
            additional_metadata={
                "duration_ms": (end_time - start_time) * 1000,
                "tokens_per_second": tokens_used / ((end_time - start_time)) if tokens_used and end_time > start_time else None
            }
        )

    def track_cache_operation(
        self,
        operation: str,
        hit: bool,
        key: Optional[str] = None,
        duration_ms: Optional[float] = None
    ) -> None:
        """Track cache operations"""
        with self._lock:
            self.cache_operations.append({
                "operation": operation,
                "hit": hit,
                "key": key,
                "duration_ms": duration_ms,
                "timestamp": time.time()
            })

    def _start_system_monitoring(self) -> None:
        """Start system monitoring thread"""
        def monitor_system():
            while True:
                try:
                    # Get memory usage
                    process = psutil.Process()
                    memory_info = process.memory_info()
                    memory_mb = memory_info.rss / 1024 / 1024
                    
                    with self._lock:
                        self.memory_samples.append({
                            "timestamp": time.time(),
                            "memory_mb": memory_mb
                        })
                    
                    # Get CPU usage
                    cpu_percent = process.cpu_percent()
                    with self._lock:
                        self.cpu_samples.append({
                            "timestamp": time.time(),
                            "cpu_percent": cpu_percent
                        })
                    
                    time.sleep(5)  # Sample every 5 seconds
                    
                except Exception as e:
                    logger.error("monitoring", f"System monitoring error: {e}")
                    time.sleep(10)
        
        thread = threading.Thread(target=monitor_system, daemon=True)
        thread.start()

    def get_operation_stats(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics for operations.
        
        Args:
            operation: Specific operation to get stats for (None for all)
            
        Returns:
            Dictionary with statistics
        """
        with self._lock:
            if operation:
                stats = self.operation_stats.get(operation, {})
                if not stats:
                    return {}
                
                durations = list(stats["durations"])
                durations.sort()
                
                return {
                    "operation": operation,
                    "count": stats["count"],
                    "total_duration_ms": stats["total_duration"],
                    "avg_duration_ms": stats["total_duration"] / stats["count"] if stats["count"] > 0 else 0,
                    "success_rate": stats["success_count"] / stats["count"] if stats["count"] > 0 else 0,
                    "failure_rate": stats["fail_count"] / stats["count"] if stats["count"] > 0 else 0,
                    "p50_duration_ms": durations[len(durations) // 2] if durations else 0,
                    "p95_duration_ms": durations[int(len(durations) * 0.95)] if durations else 0,
                    "p99_duration_ms": durations[int(len(durations) * 0.99)] if durations else 0,
                    "max_duration_ms": max(durations) if durations else 0,
                    "min_duration_ms": min(durations) if durations else 0
                }
            else:
                # Return all operations
                return {
                    op: self.get_operation_stats(op)
                    for op in self.operation_stats.keys()
                }

    def get_slowest_operations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get slowest operations"""
        with self._lock:
            slowest = []
            
            for metrics in self.metrics:
                if metrics.duration_ms:
                    slowest.append({
                        "operation": metrics.operation,
                        "duration_ms": metrics.duration_ms,
                        "success": metrics.success,
                        "timestamp": metrics.end_time,
                        "metadata": metrics.metadata
                    })
            
            slowest.sort(key=lambda x: x["duration_ms"], reverse=True)
            return slowest[:limit]

    def get_current_memory_usage(self) -> Optional[float]:
        """Get current memory usage in MB"""
        with self._lock:
            if self.memory_samples:
                return self.memory_samples[-1]["memory_mb"]
            return None

    def get_memory_trend(self) -> Dict[str, float]:
        """Get memory usage trend"""
        with self._lock:
            if len(self.memory_samples) < 2:
                return {}
            
            samples = list(self.memory_samples)
            first_mb = samples[0]["memory_mb"]
            last_mb = samples[-1]["memory_mb"]
            
            return {
                "start_mb": first_mb,
                "end_mb": last_mb,
                "change_mb": last_mb - first_mb,
                "change_percent": ((last_mb - first_mb) / first_mb * 100) if first_mb > 0 else 0
            }

    def get_cache_performance(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        with self._lock:
            if not self.cache_operations:
                return {}
            
            total_ops = len(self.cache_operations)
            hits = sum(1 for op in self.cache_operations if op["hit"])
            hit_rate = hits / total_ops if total_ops > 0 else 0
            
            durations = [op["duration_ms"] for op in self.cache_operations if op["duration_ms"]]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            return {
                "total_operations": total_ops,
                "hits": hits,
                "misses": total_ops - hits,
                "hit_rate": hit_rate,
                "avg_duration_ms": avg_duration
            }

    def generate_report(self) -> PerformanceReport:
        """Generate comprehensive performance report"""
        with self._lock:
            # Calculate overall stats
            completed_ops = [m for m in self.metrics if m.end_time]
            total_ops = len(completed_ops)
            successful = sum(1 for m in completed_ops if m.success)
            failed = total_ops - successful
            
            # Calculate durations
            durations = [m.duration_ms for m in completed_ops if m.duration_ms]
            durations.sort()
            
            total_duration = sum(durations)
            avg_duration = total_duration / len(durations) if durations else 0
            
            p50 = durations[int(len(durations) * 0.50)] if durations else 0
            p95 = durations[int(len(durations) * 0.95)] if durations else 0
            p99 = durations[int(len(durations) * 0.99)] if durations else 0
            
            # Get operation counts
            op_counts = {}
            for stats in self.operation_stats.values():
                op_name = None
                # Find the operation name (this is a bit hacky)
                for name, stat in self.operation_stats.items():
                    if stat == stats:
                        op_name = name
                        break
                
                if op_name:
                    op_counts[op_name] = stats["count"]
            
            # Get cache stats
            cache_stats = self.get_cache_performance()
            
            # Get memory usage
            memory_usage = self.get_current_memory_usage() or 0
            
            return PerformanceReport(
                total_operations=total_ops,
                successful_operations=successful,
                failed_operations=failed,
                total_duration_ms=total_duration,
                avg_duration_ms=avg_duration,
                p50_duration_ms=p50,
                p95_duration_ms=p95,
                p99_duration_ms=p99,
                slowest_operations=self.get_slowest_operations(),
                operation_counts=op_counts,
                memory_usage_mb=memory_usage,
                cache_stats=cache_stats
            )

    def save_report(self, file_path: str) -> None:
        """Save performance report to file"""
        report = self.generate_report()
        
        # Convert to dict for JSON serialization
        report_dict = {
            "total_operations": report.total_operations,
            "successful_operations": report.successful_operations,
            "failed_operations": report.failed_operations,
            "total_duration_ms": report.total_duration_ms,
            "avg_duration_ms": report.avg_duration_ms,
            "p50_duration_ms": report.p50_duration_ms,
            "p95_duration_ms": report.p95_duration_ms,
            "p99_duration_ms": report.p99_duration_ms,
            "slowest_operations": report.slowest_operations,
            "operation_counts": report.operation_counts,
            "memory_usage_mb": report.memory_usage_mb,
            "cache_stats": report.cache_stats,
            "timestamp": report.timestamp
        }
        
        with open(file_path, 'w') as f:
            import json
            json.dump(report_dict, f, indent=2)

    def print_report(self) -> None:
        """Print performance report to console"""
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        
        console = Console()
        report = self.generate_report()
        
        # Summary panel
        summary = f"""Total Operations: {report.total_operations}
Successful: {report.successful_operations}
Failed: {report.failed_operations}
Average Duration: {report.avg_duration_ms:.2f}ms
P95 Duration: {report.p95_duration_ms:.2f}ms
Memory Usage: {report.memory_usage_mb:.2f}MB"""
        
        console.print(Panel(summary, title="Performance Summary", expand=False))
        
        # Operation statistics table
        if report.operation_counts:
            table = Table(title="Operation Statistics")
            table.add_column("Operation", style="cyan")
            table.add_column("Count", style="green")
            table.add_column("Avg Duration", style="yellow")
            table.add_column("Success Rate", style="blue")
            
            for op, stats in report.operation_counts.items():
                op_stats = self.get_operation_stats(op)
                success_rate = op_stats.get("success_rate", 0) * 100
                avg_duration = op_stats.get("avg_duration_ms", 0)
                
                table.add_row(
                    op,
                    str(stats),
                    f"{avg_duration:.2f}ms",
                    f"{success_rate:.1f}%"
                )
            
            console.print(table)
        
        # Cache performance
        if report.cache_stats.get("total_operations", 0) > 0:
            cache_panel = f"""Total Operations: {report.cache_stats['total_operations']}
Hit Rate: {report.cache_stats['hit_rate']:.1%}
Average Duration: {report.cache_stats['avg_duration_ms']:.2f}ms"""
            
            console.print(Panel(cache_panel, title="Cache Performance", expand=False))
        
        # Slowest operations
        if report.slowest_operations:
            console.print("\n[bold red]Slowest Operations:[/bold red]")
            for op in report.slowest_operations[:5]:
                console.print(f"  {op['operation']}: {op['duration_ms']:.2f}ms")


# Global monitor instance
_global_monitor: Optional[PerformanceMonitor] = None


def get_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    global _global_monitor
    
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    
    return _global_monitor


# Context manager for easy performance tracking
class track_performance:
    """
    Context manager for tracking performance of code blocks.
    
    Usage:
        with track_performance("database_query"):
            # Your code here
            pass
    """
    
    def __init__(self, operation: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize performance tracker.
        
        Args:
            operation: Operation name
            metadata: Optional metadata
        """
        self.operation = operation
        self.metadata = metadata
        self.operation_id = None
        self.monitor = get_monitor()
    
    def __enter__(self):
        self.operation_id = self.monitor.start_operation(self.operation, self.metadata)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None
        self.monitor.stop_operation(self.operation_id, success=success)


# Decorator for function performance tracking
def performance_timer(operation: str):
    """
    Decorator for tracking function performance.
    
    Usage:
        @performance_timer("user_authentication")
        def authenticate_user():
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with track_performance(operation, {"function": func.__name__}):
                return func(*args, **kwargs)
        return wrapper
    return decorator