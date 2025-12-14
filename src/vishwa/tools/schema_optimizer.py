"""
Tool Schema Optimization - Reduce overhead and improve performance.

This module optimizes tool schemas by:
- Lazy loading schema definitions
- Compressing repeated schema patterns
- Caching schema validations
- Reducing serialization overhead
- Optimizing parameter validation
"""

import json
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from dataclasses import dataclass, field
from functools import lru_cache, wraps

from vishwa.utils.logger import logger


@dataclass
class SchemaOptimizationConfig:
    """Configuration for schema optimization"""
    enable_caching: bool = True
    enable_compression: bool = True
    enable_lazy_loading: bool = True
    cache_ttl: int = 3600  # 1 hour
    max_cached_schemas: int = 100


@dataclass
class OptimizedSchema:
    """Optimized schema representation"""
    name: str
    description: str
    parameters: Dict[str, Any]
    required_params: List[str]
    param_validators: Dict[str, Callable]
    serialization_cache: Optional[str] = None
    compressed: bool = False
    cache_hit_count: int = 0


class SchemaOptimizer:
    """
    Optimizer for tool schemas.
    
    This class provides:
    - Schema caching with TTL
    - Parameter validation caching
    - Serialization optimization
    - Lazy loading of complex schemas
    """

    def __init__(self, config: Optional[SchemaOptimizationConfig] = None):
        """
        Initialize schema optimizer.
        
        Args:
            config: Optimization configuration
        """
        self.config = config or SchemaOptimizationConfig()
        
        # Cache for schemas
        self.schema_cache: Dict[str, Tuple[OptimizedSchema, float]] = {}
        
        # Cache for parameter validators
        self.validator_cache: Dict[str, Callable] = {}
        
        # Serialization cache
        self.serialization_cache: Dict[str, str] = {}
        
        # Schema usage statistics
        self.usage_stats: Dict[str, int] = {}
        
        # Compressed schema patterns
        self.common_patterns: Dict[str, Dict[str, Any]] = {}

    def optimize_schema(self, tool_name: str, raw_schema: Dict[str, Any]) -> OptimizedSchema:
        """
        Optimize a tool schema.
        
        Args:
            tool_name: Name of the tool
            raw_schema: Raw schema dictionary
            
        Returns:
            OptimizedSchema instance
        """
        # Check cache first
        if self.config.enable_caching:
            cached = self._get_cached_schema(tool_name)
            if cached:
                cached.cache_hit_count += 1
                return cached
        
        # Extract required parameters
        required_params = raw_schema.get("required", [])
        
        # Build parameter validators
        param_validators = self._build_parameter_validators(raw_schema)
        
        # Create optimized schema
        optimized = OptimizedSchema(
            name=tool_name,
            description=raw_schema.get("description", ""),
            parameters=raw_schema,
            required_params=required_params,
            param_validators=param_validators,
            compressed=self.config.enable_compression
        )
        
        # Cache if caching is enabled
        if self.config.enable_caching:
            self._cache_schema(tool_name, optimized)
        
        # Update usage stats
        self.usage_stats[tool_name] = self.usage_stats.get(tool_name, 0) + 1
        
        return optimized

    def _get_cached_schema(self, tool_name: str) -> Optional[OptimizedSchema]:
        """Get schema from cache"""
        if tool_name not in self.schema_cache:
            return None
        
        schema, timestamp = self.schema_cache[tool_name]
        
        # Check if cache is still valid
        if time.time() - timestamp > self.config.cache_ttl:
            del self.schema_cache[tool_name]
            return None
        
        return schema

    def _cache_schema(self, tool_name: str, schema: OptimizedSchema) -> None:
        """Cache a schema"""
        # Evict old schemas if cache is full
        if len(self.schema_cache) >= self.config.max_cached_schemas:
            self._evict_oldest_schemas()
        
        self.schema_cache[tool_name] = (schema, time.time())

    def _evict_oldest_schemas(self) -> None:
        """Evict oldest schemas from cache"""
        # Sort by timestamp and remove oldest 20%
        sorted_schemas = sorted(
            self.schema_cache.items(),
            key=lambda x: x[1][1]  # Sort by timestamp
        )
        
        evict_count = max(1, len(sorted_schemas) // 5)
        for tool_name, _ in sorted_schemas[:evict_count]:
            del self.schema_cache[tool_name]

    def _build_parameter_validators(self, schema: Dict[str, Any]) -> Dict[str, Callable]:
        """Build parameter validators for schema"""
        validators = {}
        
        properties = schema.get("properties", {})
        
        for param_name, param_schema in properties.items():
            validator = self._create_parameter_validator(param_name, param_schema)
            if validator:
                validators[param_name] = validator
        
        return validators

    def _create_parameter_validator(self, param_name: str, param_schema: Dict[str, Any]) -> Optional[Callable]:
        """Create a parameter validator function"""
        # Create cache key
        cache_key = f"{param_name}:{json.dumps(param_schema, sort_keys=True)}"
        
        # Check validator cache
        if cache_key in self.validator_cache:
            return self.validator_cache[cache_key]
        
        # Build validator
        validator = self._build_validator(param_name, param_schema)
        
        # Cache validator
        self.validator_cache[cache_key] = validator
        
        return validator

    def _build_validator(self, param_name: str, param_schema: Dict[str, Any]) -> Callable:
        """Build a parameter validator function"""
        param_type = param_schema.get("type")
        
        if param_type == "string":
            return self._build_string_validator(param_name, param_schema)
        elif param_type == "integer":
            return self._build_integer_validator(param_name, param_schema)
        elif param_type == "number":
            return self._build_number_validator(param_name, param_schema)
        elif param_type == "boolean":
            return self._build_boolean_validator(param_name, param_schema)
        elif param_type == "array":
            return self._build_array_validator(param_name, param_schema)
        elif param_type == "object":
            return self._build_object_validator(param_name, param_schema)
        else:
            # No specific validator
            return lambda x: True

    def _build_string_validator(self, param_name: str, param_schema: Dict[str, Any]) -> Callable:
        """Build string validator"""
        def validate_string(value):
            if not isinstance(value, str):
                return False
            
            # Check enum
            if "enum" in param_schema:
                if value not in param_schema["enum"]:
                    return False
            
            # Check pattern
            if "pattern" in param_schema:
                import re
                if not re.match(param_schema["pattern"], value):
                    return False
            
            # Check min/max length
            if "minLength" in param_schema and len(value) < param_schema["minLength"]:
                return False
            if "maxLength" in param_schema and len(value) > param_schema["maxLength"]:
                return False
            
            return True
        
        return validate_string

    def _build_integer_validator(self, param_name: str, param_schema: Dict[str, Any]) -> Callable:
        """Build integer validator"""
        def validate_integer(value):
            if not isinstance(value, int):
                return False
            
            if "minimum" in param_schema and value < param_schema["minimum"]:
                return False
            if "maximum" in param_schema and value > param_schema["maximum"]:
                return False
            
            return True
        
        return validate_integer

    def _build_number_validator(self, param_name: str, param_schema: Dict[str, Any]) -> Callable:
        """Build number validator"""
        def validate_number(value):
            if not isinstance(value, (int, float)):
                return False
            
            if "minimum" in param_schema and value < param_schema["minimum"]:
                return False
            if "maximum" in param_schema and value > param_schema["maximum"]:
                return False
            
            return True
        
        return validate_number

    def _build_boolean_validator(self, param_name: str, param_schema: Dict[str, Any]) -> Callable:
        """Build boolean validator"""
        def validate_boolean(value):
            return isinstance(value, bool)
        
        return validate_boolean

    def _build_array_validator(self, param_name: str, param_schema: Dict[str, Any]) -> Callable:
        """Build array validator"""
        def validate_array(value):
            if not isinstance(value, list):
                return False
            
            if "minItems" in param_schema and len(value) < param_schema["minItems"]:
                return False
            if "maxItems" in param_schema and len(value) > param_schema["maxItems"]:
                return False
            
            return True
        
        return validate_array

    def _build_object_validator(self, param_name: str, param_schema: Dict[str, Any]) -> Callable:
        """Build object validator"""
        def validate_object(value):
            return isinstance(value, dict)
        
        return validate_object

    def validate_parameters_fast(self, schema: OptimizedSchema, **kwargs) -> Tuple[bool, Optional[str]]:
        """
        Fast parameter validation using pre-built validators.
        
        Args:
            schema: OptimizedSchema instance
            **kwargs: Parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required parameters
        for required_param in schema.required_params:
            if required_param not in kwargs:
                return False, f"Missing required parameter: {required_param}"
        
        # Use fast validators
        for param_name, value in kwargs.items():
            if param_name in schema.param_validators:
                if not schema.param_validators[param_name](value):
                    return False, f"Invalid parameter: {param_name}"
        
        return True, None

    def serialize_schema_fast(self, schema: OptimizedSchema) -> str:
        """
        Fast schema serialization with caching.
        
        Args:
            schema: OptimizedSchema instance
            
        Returns:
            Serialized schema string
        """
        # Check serialization cache
        cache_key = f"{schema.name}:{hash(str(schema.parameters))}"
        
        if cache_key in self.serialization_cache:
            return self.serialization_cache[cache_key]
        
        # Serialize
        serialized = json.dumps(schema.parameters, separators=(',', ':'))
        
        # Cache result
        self.serialization_cache[cache_key] = serialized
        
        return serialized

    def get_schema_stats(self) -> Dict[str, Any]:
        """Get schema optimization statistics"""
        return {
            "cached_schemas": len(self.schema_cache),
            "validator_cache_size": len(self.validator_cache),
            "serialization_cache_size": len(self.serialization_cache),
            "usage_stats": dict(self.usage_stats),
            "total_optimizations": sum(self.usage_stats.values())
        }

    def clear_cache(self) -> None:
        """Clear all caches"""
        self.schema_cache.clear()
        self.validator_cache.clear()
        self.serialization_cache.clear()
        logger.info("schema_optimizer", "Cleared all caches")


# Cached parameter validation
class CachedParameterValidator:
    """
    Parameter validator with caching for better performance.
    """

    def __init__(self, cache_size: int = 1000):
        """Initialize cached validator"""
        self.cache_size = cache_size
        self.validation_cache: Dict[str, Tuple[bool, str]] = {}

    def validate_with_cache(self, tool_name: str, schema: Dict[str, Any], **kwargs) -> Tuple[bool, Optional[str]]:
        """
        Validate parameters with caching.
        
        Args:
            tool_name: Tool name for cache key
            schema: Tool schema
            **kwargs: Parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Create cache key
        cache_key = self._create_cache_key(tool_name, schema, kwargs)
        
        # Check cache
        if cache_key in self.validation_cache:
            return self.validation_cache[cache_key]
        
        # Validate
        is_valid, error = self._validate_parameters(schema, **kwargs)
        
        # Cache result
        self._cache_result(cache_key, is_valid, error)
        
        return is_valid, error

    def _create_cache_key(self, tool_name: str, schema: Dict[str, Any], kwargs: Dict[str, Any]) -> str:
        """Create cache key for validation"""
        # Sort kwargs for consistent keys
        sorted_kwargs = json.dumps(kwargs, sort_keys=True, separators=(',', ':'))
        schema_hash = hash(json.dumps(schema, sort_keys=True, separators=(',', ':')))
        
        return f"{tool_name}:{schema_hash}:{sorted_kwargs}"

    def _validate_parameters(self, schema: Dict[str, Any], **kwargs) -> Tuple[bool, Optional[str]]:
        """Validate parameters (non-cached version)"""
        required_params = schema.get("required", [])
        
        # Check required parameters
        for required_param in required_params:
            if required_param not in kwargs:
                return False, f"Missing required parameter: {required_param}"
        
        # Validate parameter types
        properties = schema.get("properties", {})
        
        for param_name, value in kwargs.items():
            if param_name in properties:
                param_schema = properties[param_name]
                
                # Basic type validation
                expected_type = param_schema.get("type")
                if expected_type:
                    if not self._check_type(value, expected_type):
                        return False, f"Parameter {param_name} must be of type {expected_type}"
        
        return True, None

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type"""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        python_type = type_map.get(expected_type)
        if python_type:
            return isinstance(value, python_type)
        
        return True

    def _cache_result(self, cache_key: str, is_valid: bool, error: Optional[str]) -> None:
        """Cache validation result"""
        # Evict old entries if cache is full
        if len(self.validation_cache) >= self.cache_size:
            # Remove oldest 20% of entries
            keys_to_remove = list(self.validation_cache.keys())[:self.cache_size // 5]
            for key in keys_to_remove:
                del self.validation_cache[key]
        
        self.validation_cache[cache_key] = (is_valid, error)

    def clear_cache(self) -> None:
        """Clear validation cache"""
        self.validation_cache.clear()


# Lazy schema loader
class LazySchemaLoader:
    """
    Lazy loader for tool schemas.
    
    This defers schema loading until actually needed,
    reducing startup time and memory usage.
    """

    def __init__(self):
        """Initialize lazy loader"""
        self.loaded_schemas: Dict[str, Dict[str, Any]] = {}
        self.schema_loaders: Dict[str, Callable] = {}
        self.loading_stats: Dict[str, int] = {}

    def register_schema_loader(self, tool_name: str, loader_func: Callable) -> None:
        """
        Register a schema loader for a tool.
        
        Args:
            tool_name: Name of the tool
            loader_func: Function that returns the schema
        """
        self.schema_loaders[tool_name] = loader_func

    def get_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get schema, loading it if necessary.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool schema or None if not found
        """
        # Return cached if already loaded
        if tool_name in self.loaded_schemas:
            return self.loaded_schemas[tool_name]
        
        # Load if loader is registered
        if tool_name in self.schema_loaders:
            try:
                schema = self.schema_loaders[tool_name]()
                self.loaded_schemas[tool_name] = schema
                self.loading_stats[tool_name] = self.loading_stats.get(tool_name, 0) + 1
                return schema
            except Exception as e:
                logger.error("lazy_loader", f"Failed to load schema for {tool_name}: {e}")
                return None
        
        return None

    def preload_schemas(self, tool_names: List[str]) -> None:
        """
        Preload schemas for specific tools.
        
        Args:
            tool_names: List of tool names to preload
        """
        for tool_name in tool_names:
            self.get_schema(tool_name)

    def get_loading_stats(self) -> Dict[str, Any]:
        """Get lazy loading statistics"""
        return {
            "loaded_schemas": len(self.loaded_schemas),
            "registered_loaders": len(self.schema_loaders),
            "loading_stats": dict(self.loading_stats),
            "total_loads": sum(self.loading_stats.values())
        }


# Decorator for schema optimization
def optimize_schema_decorator(optimizer: SchemaOptimizer):
    """
    Decorator for automatic schema optimization.
    
    Usage:
        @optimize_schema_decorator(schema_optimizer)
        class MyTool(Tool):
            @property
            def parameters(self):
                return self._optimized_schema
    """
    def decorator(cls):
        # Store original parameters property
        if hasattr(cls, 'parameters'):
            original_parameters = cls.parameters.fget
            
            # Create optimized version
            @property
            def optimized_parameters(self):
                raw_schema = original_parameters(self)
                tool_name = self.name
                return optimizer.optimize_schema(tool_name, raw_schema)
            
            # Replace with optimized version
            setattr(cls, 'parameters', optimized_parameters)
        
        return cls
    return decorator


# Global optimizer instance
_global_optimizer: Optional[SchemaOptimizer] = None
_global_validator: Optional[CachedParameterValidator] = None
_global_loader: Optional[LazySchemaLoader] = None


def get_schema_optimizer() -> SchemaOptimizer:
    """Get global schema optimizer instance"""
    global _global_optimizer
    
    if _global_optimizer is None:
        _global_optimizer = SchemaOptimizer()
    
    return _global_optimizer


def get_parameter_validator() -> CachedParameterValidator:
    """Get global parameter validator instance"""
    global _global_validator
    
    if _global_validator is None:
        _global_validator = CachedParameterValidator()
    
    return _global_validator


def get_lazy_loader() -> LazySchemaLoader:
    """Get global lazy loader instance"""
    global _global_loader
    
    if _global_loader is None:
        _global_loader = LazySchemaLoader()
    
    return _global_loader


# Performance tracking decorator
def track_schema_performance(func):
    """Decorator to track schema performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        
        # Log slow operations
        if duration > 0.1:  # 100ms threshold
            logger.warning("schema_perf", f"{func.__name__} took {duration:.3f}s")
        
        return result
    return wrapper