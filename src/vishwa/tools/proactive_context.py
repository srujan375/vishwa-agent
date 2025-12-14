"""
Proactive Context Manager - Smart context management with predictive sizing.

This enhanced context manager prevents context overflow through:
- Predictive sizing before adding content
- Proactive summarization based on usage patterns
- Smart file tracking with dependency analysis
- Context budgeting with early warnings
- Intelligent content prioritization
"""

import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from vishwa.utils.logger import logger


@dataclass
class ContextBudget:
    """Context budget tracking"""
    max_tokens: int
    reserved_tokens: int = 5000  # Reserve space for responses
    warning_threshold: float = 0.7
    critical_threshold: float = 0.9
    
    @property
    def available_tokens(self) -> int:
        """Tokens available for content"""
        return self.max_tokens - self.reserved_tokens
    
    @property
    def warning_limit(self) -> int:
        """Token limit for warning level"""
        return int(self.max_tokens * self.warning_threshold)
    
    @property
    def critical_limit(self) -> int:
        """Token limit for critical level"""
        return int(self.max_tokens * self.critical_threshold)


@dataclass
class ContentItem:
    """Content item in context"""
    content: str
    content_type: str  # "message", "file", "tool_result"
    importance: float  # 0-1 score
    last_accessed: float
    access_count: int = 0
    file_path: Optional[str] = None
    dependencies: Set[str] = field(default_factory=set)


@dataclass
class PredictionResult:
    """Result of context size prediction"""
    estimated_tokens: int
    will_exceed: bool
    suggested_actions: List[str]
    required_reduction: int


class ProactiveContextManager:
    """
    Enhanced context manager with predictive capabilities.
    
    This manager:
    - Predicts context size before adding content
    - Proactively summarizes content
    - Manages context budget
    - Provides early warnings
    - Optimizes content priority
    """

    def __init__(self, max_tokens: int = 150000):
        """
        Initialize proactive context manager.
        
        Args:
            max_tokens: Maximum context window size
        """
        self.budget = ContextBudget(max_tokens=max_tokens)
        self.messages: List[ContentItem] = []
        self.files_in_context: Dict[str, ContentItem] = {}
        self.file_dependencies: Dict[str, Set[str]] = {}
        self.modifications: List[Any] = []
        
        # Predictive analytics
        self.size_history: deque = deque(maxlen=100)
        self.content_patterns: Dict[str, int] = {}
        self.prediction_accuracy: List[float] = []
        
        # Early warning system
        self.warning_level: str = "normal"  # normal, warning, critical
        self.last_prune_time: float = 0
        
        # Access tracking
        self.content_importance_cache: Dict[str, float] = {}

    def predict_size(self, additional_content: Optional[List[ContentItem]] = None) -> PredictionResult:
        """
        Predict context size after adding content.
        
        Args:
            additional_content: Content to be added
            
        Returns:
            PredictionResult with size estimate and recommendations
        """
        current_size = self._estimate_current_tokens()
        
        additional_size = 0
        if additional_content:
            for item in additional_content:
                additional_size += self._estimate_tokens_for_content(item)
        
        total_size = current_size + additional_size
        
        # Determine if we'll exceed limits
        will_exceed = total_size > self.budget.max_tokens
        
        # Generate suggestions
        suggestions = []
        if will_exceed:
            if total_size > self.budget.critical_limit:
                suggestions.extend([
                    "Summarize old messages",
                    "Remove least important files",
                    "Prune tool results",
                    "Consider starting new context"
                ])
            elif total_size > self.budget.warning_limit:
                suggestions.extend([
                    "Summarize old content",
                    "Remove unused files",
                    "Prune old tool results"
                ])
        
        return PredictionResult(
            estimated_tokens=total_size,
            will_exceed=will_exceed,
            suggested_actions=suggestions,
            required_reduction=max(0, total_size - self.budget.max_tokens)
        )

    def add_content_with_prediction(self, content: ContentItem) -> bool:
        """
        Add content with automatic size prediction.
        
        Args:
            content: Content to add
            
        Returns:
            True if content was added, False if prevented
        """
        prediction = self.predict_size([content])
        
        if prediction.will_exceed and prediction.required_reduction > 1000:
            # Too much content, try to make space
            if not self._make_space_for_content(content):
                logger.warning("context", "Context full, content rejected")
                return False
        
        # Add content
        self._add_content_internal(content)
        
        # Update prediction history
        self.size_history.append({
            "timestamp": time.time(),
            "size": self._estimate_current_tokens(),
            "content_count": len(self.messages)
        })
        
        # Check warning level
        self._update_warning_level()
        
        return True

    def _make_space_for_content(self, new_content: ContentItem) -> bool:
        """
        Make space for new content by removing least important items.
        
        Args:
            new_content: Content that needs space
            
        Returns:
            True if space was made
        """
        current_size = self._estimate_current_tokens()
        new_size = self._estimate_tokens_for_content(new_content)
        max_size = self.budget.available_tokens
        
        if current_size + new_size <= max_size:
            return True
        
        # Calculate how much space we need
        needed_reduction = current_size + new_size - max_size
        
        # Get removable content (not critical)
        removable_items = self._get_removable_content(new_content.importance)
        
        if not removable_items:
            return False
        
        # Sort by importance (remove least important first)
        removable_items.sort(key=lambda x: x.importance)
        
        # Remove items until we have enough space
        removed_size = 0
        for item in removable_items:
            self._remove_content_item(item)
            removed_size += self._estimate_tokens_for_content(item)
            
            if removed_size >= needed_reduction:
                break
        
        return removed_size >= needed_reduction

    def _get_removable_content(self, new_content_importance: float) -> List[ContentItem]:
        """Get list of removable content items"""
        removable = []
        
        # Messages that are not the current task
        for item in self.messages:
            if (item.content_type == "message" and 
                item.importance < new_content_importance and
                item.access_count == 0):  # Not recently accessed
                removable.append(item)
        
        # Old tool results
        for item in self.messages:
            if (item.content_type == "tool_result" and
                item.importance < 0.3):  # Low importance
                removable.append(item)
        
        # Unused files
        for path, item in list(self.files_in_context.items()):
            if item.access_count == 0 and item.importance < new_content_importance:
                removable.append(item)
        
        return removable

    def _remove_content_item(self, item: ContentItem) -> None:
        """Remove a content item"""
        if item.content_type == "file" and item.file_path:
            self.files_in_context.pop(item.file_path, None)
        else:
            # Remove from messages
            self.messages = [m for m in self.messages if m != item]
        
        logger.debug("context", f"Removed content item, importance: {item.importance}")

    def _estimate_current_tokens(self) -> int:
        """Estimate current token usage"""
        total = 0
        
        # Estimate messages
        for item in self.messages:
            total += self._estimate_tokens_for_content(item)
        
        # Estimate files
        for item in self.files_in_context.values():
            total += self._estimate_tokens_for_content(item)
        
        return total

    def _estimate_tokens_for_content(self, item: ContentItem) -> int:
        """Estimate tokens for a content item"""
        # Rough estimation: 4 characters per token
        content_tokens = len(item.content) // 4
        
        # Add overhead for metadata
        overhead = 100  # Token overhead for structure
        
        return content_tokens + overhead

    def _add_content_internal(self, content: ContentItem) -> None:
        """Internal method to add content"""
        if content.content_type == "file" and content.file_path:
            self.files_in_context[content.file_path] = content
        else:
            self.messages.append(content)
        
        content.last_accessed = time.time()

    def _update_warning_level(self) -> None:
        """Update warning level based on current usage"""
        current_size = self._estimate_current_tokens()
        
        if current_size > self.budget.critical_limit:
            self.warning_level = "critical"
            logger.warning("context", "Context usage critical!")
        elif current_size > self.budget.warning_limit:
            self.warning_level = "warning"
            logger.info("context", "Context usage warning")
        else:
            self.warning_level = "normal"

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get detailed usage statistics"""
        current_size = self._estimate_current_tokens()
        
        return {
            "current_tokens": current_size,
            "max_tokens": self.budget.max_tokens,
            "available_tokens": self.budget.available_tokens,
            "usage_percent": (current_size / self.budget.max_tokens) * 100,
            "warning_level": self.warning_level,
            "message_count": len(self.messages),
            "file_count": len(self.files_in_context),
            "content_items": len(self.messages) + len(self.files_in_context),
            "prediction_accuracy": sum(self.prediction_accuracy) / len(self.prediction_accuracy) if self.prediction_accuracy else 0
        }

    def proactive_summarize(self) -> None:
        """
        Proactively summarize old content before hitting limits.
        
        This is called periodically or when usage is high.
        """
        if self.warning_level == "normal":
            return
        
        logger.info("context", "Running proactive summarization")
        
        # Summarize old messages
        old_messages = [m for m in self.messages 
                       if time.time() - m.last_accessed > 300]  # 5 minutes old
        
        if len(old_messages) > 10:
            summary = self._create_messages_summary(old_messages)
            
            # Add summary and remove old messages
            summary_item = ContentItem(
                content=summary,
                content_type="summary",
                importance=0.7,
                last_accessed=time.time()
            )
            
            # Remove old messages
            self.messages = [m for m in self.messages if m not in old_messages]
            
            # Add summary
            self.messages.append(summary_item)
            
            logger.info("context", f"Summarized {len(old_messages)} messages")

    def _create_messages_summary(self, messages: List[ContentItem]) -> str:
        """Create summary of multiple messages"""
        if not messages:
            return ""
        
        # Simple summary: count by type
        message_types = {}
        for msg in messages:
            msg_type = msg.content_type
            message_types[msg_type] = message_types.get(msg_type, 0) + 1
        
        summary = f"[Summary of {len(messages)} messages]\n"
        summary += f"Message types: {message_types}\n"
        summary += f"Time range: {min(m.last_accessed for m in messages):.0f} - {max(m.last_accessed for m in messages):.0f}\n"
        
        return summary

    def optimize_content_priority(self) -> None:
        """
        Optimize content priority based on access patterns.
        
        This adjusts importance scores based on how often content is accessed.
        """
        for item in self.messages + list(self.files_in_context.values()):
            # Increase importance for frequently accessed content
            if item.access_count > 5:
                item.importance = min(1.0, item.importance + 0.1)
            
            # Decrease importance for rarely accessed content
            elif item.access_count == 0 and time.time() - item.last_accessed > 600:
                item.importance = max(0.1, item.importance - 0.1)

    def get_optimal_content_size(self) -> int:
        """
        Get optimal content size to maintain for best performance.
        
        Returns:
            Optimal token count
        """
        # Aim for 70% utilization for best performance
        return int(self.budget.max_tokens * 0.7)

    def should_start_new_context(self) -> bool:
        """
        Check if we should start a new context.
        
        Returns:
            True if new context recommended
        """
        stats = self.get_usage_stats()
        
        # Recommend new context if:
        # 1. Usage > 90% consistently
        # 2. Too many small files (> 20)
        # 3. High fragmentation
        
        return (
            stats["usage_percent"] > 90 or
            stats["file_count"] > 20 or
            len(self.messages) > 100
        )

    def create_migration_summary(self) -> str:
        """
        Create summary for context migration.
        
        This creates a summary of current context to transfer to new session.
        
        Returns:
            Migration summary
        """
        stats = self.get_usage_stats()
        
        summary = "Context Migration Summary\n"
        summary += "=" * 50 + "\n\n"
        summary += f"Session Duration: {time.time() - (self.size_history[0]['timestamp'] if self.size_history else time.time()):.0f} seconds\n"
        summary += f"Total Operations: {stats['content_items']}\n"
        summary += f"Peak Usage: {max(s['size'] for s in self.size_history) if self.size_history else 0} tokens\n"
        summary += f"Files Modified: {len(self.modifications)}\n\n"
        
        # Key files
        if self.files_in_context:
            summary += "Key Files in Context:\n"
            for path, item in sorted(self.files_in_context.items(), 
                                   key=lambda x: x[1].importance, reverse=True)[:10]:
                summary += f"  • {path} (importance: {item.importance:.2f})\n"
        
        # Recent modifications
        if self.modifications:
            summary += "\nRecent Modifications:\n"
            for mod in self.modifications[-5:]:
                summary += f"  • {mod.get('file_path', 'unknown')}\n"
        
        return summary


# Integration with existing ContextManager
class EnhancedContextManager:
    """
    Enhanced version of the original ContextManager with proactive features.
    
    This maintains backward compatibility while adding predictive capabilities.
    """

    def __init__(self, max_tokens: int = 150000):
        """Initialize enhanced context manager"""
        from vishwa.agent.context import ContextManager
        
        # Use original manager for compatibility
        self.original = ContextManager(max_tokens)
        
        # Add proactive features
        self.proactive = ProactiveContextManager(max_tokens)
        
        # Sync initial state
        self._sync_to_proactive()

    def _sync_to_proactive(self) -> None:
        """Sync original context to proactive manager"""
        # This would sync messages, files, etc.
        # Implementation depends on original ContextManager structure
        pass

    def add_message(self, role: str, content: str, **kwargs) -> None:
        """Add message with proactive management"""
        # Create content item
        item = ContentItem(
            content=content,
            content_type="message",
            importance=self._calculate_message_importance(role, content),
            last_accessed=time.time()
        )
        
        # Try to add with proactive management
        if self.proactive.add_content_with_prediction(item):
            # Also add to original for compatibility
            self.original.add_message(role, content, **kwargs)
        else:
            # Context full, summarize proactively
            self.proactive.proactive_summarize()
            
            # Try again
            if self.proactive.add_content_with_prediction(item):
                self.original.add_message(role, content, **kwargs)

    def _calculate_message_importance(self, role: str, content: str) -> float:
        """Calculate importance score for a message"""
        base_importance = 0.5
        
        # User messages are more important
        if role == "user":
            base_importance += 0.3
        
        # Error messages are less important
        if role == "tool" and "error" in content.lower():
            base_importance -= 0.2
        
        return max(0.1, min(1.0, base_importance))

    def add_file_to_context(self, path: str, content: str) -> None:
        """Add file to context with proactive management"""
        item = ContentItem(
            content=content,
            content_type="file",
            importance=self._calculate_file_importance(path, content),
            last_accessed=time.time(),
            file_path=path
        )
        
        self.proactive.add_content_with_prediction(item)
        self.original.add_file_to_context(path, content)

    def _calculate_file_importance(self, path: str, content: str) -> float:
        """Calculate importance score for a file"""
        base_importance = 0.6
        
        # Configuration files are important
        if any(ext in path.lower() for ext in ['.json', '.yaml', '.yml', '.conf', '.config']):
            base_importance += 0.2
        
        # Large files are more important
        if len(content) > 10000:
            base_importance += 0.1
        
        return min(1.0, base_importance)

    def __getattr__(self, name):
        """Proxy all other methods to original ContextManager"""
        return getattr(self.original, name)


# Utility functions
def create_enhanced_context_manager(max_tokens: int = 150000) -> EnhancedContextManager:
    """Create enhanced context manager with proactive features"""
    return EnhancedContextManager(max_tokens=max_tokens)


def monitor_context_health(manager: ProactiveContextManager) -> Dict[str, Any]:
    """
    Monitor context health and provide recommendations.
    
    Args:
        manager: ProactiveContextManager instance
        
    Returns:
        Health report with recommendations
    """
    stats = manager.get_usage_stats()
    
    health_score = 100
    recommendations = []
    
    # Check usage levels
    if stats["usage_percent"] > 90:
        health_score -= 30
        recommendations.append("Context nearly full - consider summarization")
    elif stats["usage_percent"] > 80:
        health_score -= 15
        recommendations.append("High usage - monitor closely")
    
    # Check file count
    if stats["file_count"] > 20:
        health_score -= 10
        recommendations.append("Many files in context - consider pruning")
    
    # Check prediction accuracy
    if stats["prediction_accuracy"] < 0.8:
        health_score -= 10
        recommendations.append("Poor prediction accuracy - model needs calibration")
    
    # Check warning level
    if stats["warning_level"] != "normal":
        health_score -= 20
        recommendations.append(f"Warning level: {stats['warning_level']}")
    
    return {
        "health_score": max(0, health_score),
        "stats": stats,
        "recommendations": recommendations,
        "should_optimize": health_score < 70,
        "should_migrate": stats["usage_percent"] > 95
    }