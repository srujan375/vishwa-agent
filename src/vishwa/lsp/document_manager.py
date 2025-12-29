"""
Document Manager - tracks open documents for LSP synchronization.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Set
from pathlib import Path
import logging

from vishwa.lsp.server_manager import get_server_manager

logger = logging.getLogger(__name__)


@dataclass
class DocumentState:
    """State of an open document."""

    path: str
    version: int
    content: str
    language: str


class DocumentManager:
    """
    Manages document state for LSP synchronization.

    LSP requires servers to be notified when documents are:
    - Opened (textDocument/didOpen)
    - Changed (textDocument/didChange)
    - Closed (textDocument/didClose)

    This manager tracks document state and sends appropriate notifications.
    """

    def __init__(self, project_root: Optional[str] = None):
        self._documents: Dict[str, DocumentState] = {}
        self._project_root = project_root

    def open_document(self, file_path: str, content: Optional[str] = None) -> bool:
        """
        Open a document and notify the language server.

        Args:
            file_path: Absolute path to the file
            content: Optional file content (reads from disk if not provided)

        Returns:
            True if document was opened successfully
        """
        abs_path = str(Path(file_path).resolve())

        if abs_path in self._documents:
            return True  # Already open

        # Read content if not provided
        if content is None:
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"Failed to read {file_path}: {e}")
                return False

        # Get client for this file
        server_manager = get_server_manager(self._project_root)
        client = server_manager.get_client_for_file(abs_path)
        if client is None:
            # No LSP server available for this file type
            return False

        # Notify server
        client.notify_document_open(abs_path, content)

        # Track state
        self._documents[abs_path] = DocumentState(
            path=abs_path,
            version=1,
            content=content,
            language=client.config.language_id,
        )

        logger.debug(f"Opened document: {abs_path}")
        return True

    def close_document(self, file_path: str):
        """Close a document and notify the language server."""
        abs_path = str(Path(file_path).resolve())

        if abs_path not in self._documents:
            return

        server_manager = get_server_manager(self._project_root)
        client = server_manager.get_client_for_file(abs_path)
        if client:
            client.notify_document_close(abs_path)

        del self._documents[abs_path]
        logger.debug(f"Closed document: {abs_path}")

    def ensure_open(self, file_path: str) -> bool:
        """Ensure a document is open (open if needed)."""
        abs_path = str(Path(file_path).resolve())
        if abs_path in self._documents:
            return True
        return self.open_document(file_path)

    def is_open(self, file_path: str) -> bool:
        """Check if a document is open."""
        abs_path = str(Path(file_path).resolve())
        return abs_path in self._documents

    def get_document(self, file_path: str) -> Optional[DocumentState]:
        """Get document state if open."""
        abs_path = str(Path(file_path).resolve())
        return self._documents.get(abs_path)

    def list_open_documents(self) -> Set[str]:
        """List all open document paths."""
        return set(self._documents.keys())

    def close_all(self):
        """Close all open documents."""
        for path in list(self._documents.keys()):
            self.close_document(path)

    def refresh_document(self, file_path: str) -> bool:
        """
        Re-read a document from disk and update state.

        Useful if the file has changed on disk.
        """
        abs_path = str(Path(file_path).resolve())

        if abs_path not in self._documents:
            return self.open_document(file_path)

        # Re-read content
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to refresh {file_path}: {e}")
            return False

        # Update state
        doc = self._documents[abs_path]
        doc.content = content
        doc.version += 1

        # TODO: Send didChange notification if needed
        # For now, we just close and reopen
        self.close_document(abs_path)
        return self.open_document(abs_path, content)


# Global instance
_document_manager: Optional[DocumentManager] = None


def get_document_manager(project_root: Optional[str] = None) -> DocumentManager:
    """Get the global document manager."""
    global _document_manager
    if _document_manager is None:
        _document_manager = DocumentManager(project_root)
    return _document_manager


def reset_document_manager():
    """Reset the global document manager. Useful for testing."""
    global _document_manager
    if _document_manager is not None:
        _document_manager.close_all()
        _document_manager = None
