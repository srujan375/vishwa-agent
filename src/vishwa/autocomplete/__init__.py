"""
Vishwa Autocomplete Module

Provides intelligent code autocomplete suggestions similar to Cursor Tab.
"""

from .service import AutocompleteService
from .suggestion_engine import SuggestionEngine
from .context_builder import ContextBuilder

__all__ = ['AutocompleteService', 'SuggestionEngine', 'ContextBuilder']
