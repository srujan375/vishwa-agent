"""
LSP (Language Server Protocol) module for Vishwa.

Provides code intelligence through external language servers:
- Go-to-definition
- Find references
- Hover documentation

Supports multiple languages: Python, TypeScript, Go, Rust, C/C++, Java
"""

from vishwa.lsp.client import LSPClient
from vishwa.lsp.server_manager import LSPServerManager, get_server_manager
from vishwa.lsp.document_manager import DocumentManager, get_document_manager
from vishwa.lsp.config import LSPConfig, LSPServerConfig, get_lsp_config

__all__ = [
    "LSPClient",
    "LSPServerManager",
    "get_server_manager",
    "DocumentManager",
    "get_document_manager",
    "LSPConfig",
    "LSPServerConfig",
    "get_lsp_config",
]
