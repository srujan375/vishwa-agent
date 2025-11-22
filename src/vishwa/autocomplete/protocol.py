"""
Protocol definitions for VS Code <-> Vishwa autocomplete communication.

Uses JSON-RPC over stdio for communication.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import json


@dataclass
class CursorPosition:
    """Represents cursor position in a file."""
    line: int
    character: int


@dataclass
class AutocompleteRequest:
    """Request for autocomplete suggestion."""
    file_path: str
    content: str
    cursor: CursorPosition
    context_lines: int = 50

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AutocompleteRequest':
        """Create request from dictionary."""
        cursor_data = data.get('cursor', {})
        return cls(
            file_path=data.get('file_path', ''),
            content=data.get('content', ''),
            cursor=CursorPosition(
                line=cursor_data.get('line', 0),
                character=cursor_data.get('character', 0)
            ),
            context_lines=data.get('context_lines', 50)
        )


@dataclass
class AutocompleteSuggestion:
    """Autocomplete suggestion response."""
    suggestion: str
    suggestion_type: str  # 'insertion' or 'edit'
    range: Optional[Dict[str, Any]] = None  # For edits: which lines to replace

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'suggestion': self.suggestion,
            'type': self.suggestion_type,
            'range': self.range
        }


class JSONRPCMessage:
    """JSON-RPC 2.0 message format."""

    @staticmethod
    def request(method: str, params: Dict[str, Any], id: int) -> str:
        """Create a JSON-RPC request."""
        return json.dumps({
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'id': id
        })

    @staticmethod
    def response(result: Any, id: int) -> str:
        """Create a JSON-RPC response."""
        return json.dumps({
            'jsonrpc': '2.0',
            'result': result,
            'id': id
        })

    @staticmethod
    def error(code: int, message: str, id: int) -> str:
        """Create a JSON-RPC error response."""
        return json.dumps({
            'jsonrpc': '2.0',
            'error': {
                'code': code,
                'message': message
            },
            'id': id
        })

    @staticmethod
    def parse(message: str) -> Dict[str, Any]:
        """Parse a JSON-RPC message."""
        return json.loads(message)
