"""
LSP Protocol definitions - extends base JSON-RPC for LSP communication.

Implements the Language Server Protocol message types and encoding.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import json


@dataclass
class Position:
    """LSP Position (0-indexed line and character)."""

    line: int
    character: int

    def to_dict(self) -> Dict[str, int]:
        return {"line": self.line, "character": self.character}

    @classmethod
    def from_dict(cls, data: Dict) -> "Position":
        return cls(line=data["line"], character=data["character"])


@dataclass
class Range:
    """LSP Range with start and end positions."""

    start: Position
    end: Position

    def to_dict(self) -> Dict:
        return {"start": self.start.to_dict(), "end": self.end.to_dict()}

    @classmethod
    def from_dict(cls, data: Dict) -> "Range":
        return cls(
            start=Position.from_dict(data["start"]), end=Position.from_dict(data["end"])
        )


@dataclass
class Location:
    """LSP Location - file URI with range."""

    uri: str
    range: Range

    def to_file_path(self) -> str:
        """Convert URI to file path."""
        if self.uri.startswith("file://"):
            return self.uri[7:]
        return self.uri

    def to_dict(self) -> Dict:
        return {"uri": self.uri, "range": self.range.to_dict()}

    @classmethod
    def from_dict(cls, data: Dict) -> "Location":
        return cls(uri=data["uri"], range=Range.from_dict(data["range"]))


@dataclass
class TextDocumentIdentifier:
    """Identifies a text document."""

    uri: str

    def to_dict(self) -> Dict[str, str]:
        return {"uri": self.uri}


@dataclass
class TextDocumentPositionParams:
    """Parameters for position-based requests."""

    text_document: TextDocumentIdentifier
    position: Position

    def to_dict(self) -> Dict:
        return {
            "textDocument": self.text_document.to_dict(),
            "position": self.position.to_dict(),
        }


class LSPMessage:
    """LSP-specific message formatting."""

    @staticmethod
    def initialize(root_uri: str, request_id: int) -> bytes:
        """Create initialize request."""
        params = {
            "processId": None,
            "rootUri": root_uri,
            "capabilities": {
                "textDocument": {
                    "definition": {"linkSupport": True},
                    "references": {},
                    "hover": {"contentFormat": ["markdown", "plaintext"]},
                    "synchronization": {
                        "didOpen": True,
                        "didClose": True,
                        "didChange": True,
                    },
                }
            },
        }
        return LSPMessage._encode(
            {"jsonrpc": "2.0", "id": request_id, "method": "initialize", "params": params}
        )

    @staticmethod
    def initialized() -> bytes:
        """Create initialized notification."""
        return LSPMessage._encode({"jsonrpc": "2.0", "method": "initialized", "params": {}})

    @staticmethod
    def shutdown(request_id: int) -> bytes:
        """Create shutdown request."""
        return LSPMessage._encode({"jsonrpc": "2.0", "id": request_id, "method": "shutdown"})

    @staticmethod
    def exit() -> bytes:
        """Create exit notification."""
        return LSPMessage._encode({"jsonrpc": "2.0", "method": "exit"})

    @staticmethod
    def text_document_did_open(
        uri: str, language_id: str, version: int, text: str
    ) -> bytes:
        """Notify server that a document was opened."""
        return LSPMessage._encode(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": uri,
                        "languageId": language_id,
                        "version": version,
                        "text": text,
                    }
                },
            }
        )

    @staticmethod
    def text_document_did_close(uri: str) -> bytes:
        """Notify server that a document was closed."""
        return LSPMessage._encode(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didClose",
                "params": {"textDocument": {"uri": uri}},
            }
        )

    @staticmethod
    def goto_definition(uri: str, line: int, character: int, request_id: int) -> bytes:
        """Create textDocument/definition request."""
        return LSPMessage._encode(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "textDocument/definition",
                "params": {
                    "textDocument": {"uri": uri},
                    "position": {"line": line, "character": character},
                },
            }
        )

    @staticmethod
    def find_references(
        uri: str,
        line: int,
        character: int,
        request_id: int,
        include_declaration: bool = True,
    ) -> bytes:
        """Create textDocument/references request."""
        return LSPMessage._encode(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "textDocument/references",
                "params": {
                    "textDocument": {"uri": uri},
                    "position": {"line": line, "character": character},
                    "context": {"includeDeclaration": include_declaration},
                },
            }
        )

    @staticmethod
    def hover(uri: str, line: int, character: int, request_id: int) -> bytes:
        """Create textDocument/hover request."""
        return LSPMessage._encode(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "textDocument/hover",
                "params": {
                    "textDocument": {"uri": uri},
                    "position": {"line": line, "character": character},
                },
            }
        )

    @staticmethod
    def document_symbols(uri: str, request_id: int) -> bytes:
        """Create textDocument/documentSymbol request."""
        return LSPMessage._encode(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "textDocument/documentSymbol",
                "params": {"textDocument": {"uri": uri}},
            }
        )

    @staticmethod
    def _encode(message: Dict) -> bytes:
        """Encode message with Content-Length header (LSP wire format)."""
        content = json.dumps(message)
        header = f"Content-Length: {len(content)}\r\n\r\n"
        return (header + content).encode("utf-8")

    @staticmethod
    def decode(data: bytes) -> Optional[Dict]:
        """Decode LSP message from wire format."""
        text = data.decode("utf-8")
        # Find header/content separator
        if "\r\n\r\n" not in text:
            return None
        header_end = text.index("\r\n\r\n")
        content = text[header_end + 4 :]
        return json.loads(content)


# LSP Error Codes
class LSPErrorCodes:
    """Standard LSP error codes."""

    ParseError = -32700
    InvalidRequest = -32600
    MethodNotFound = -32601
    InvalidParams = -32602
    InternalError = -32603
    ServerNotInitialized = -32002
    UnknownErrorCode = -32001
    RequestCancelled = -32800
    ContentModified = -32801
