"""
LSP Server Manager - manages multiple language server instances.
"""

import logging
import atexit
from typing import Dict, Optional
from pathlib import Path

from vishwa.lsp.client import LSPClient
from vishwa.lsp.config import get_lsp_config, LSPServerConfig

logger = logging.getLogger(__name__)


class LSPServerManager:
    """
    Manages LSP server lifecycle across languages.

    Features:
    - Lazy initialization (servers start on first use)
    - One server per language per project root
    - Automatic cleanup on exit
    - Graceful error handling
    """

    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize the server manager.

        Args:
            project_root: Project root directory. Defaults to cwd.
        """
        self.project_root = project_root or str(Path.cwd())
        self.root_uri = f"file://{self.project_root}"
        self._clients: Dict[str, LSPClient] = {}
        self._config = get_lsp_config()

        # Register cleanup on exit
        atexit.register(self.shutdown_all)

    def get_client_for_file(self, file_path: str) -> Optional[LSPClient]:
        """
        Get or create an LSP client for a file.

        Args:
            file_path: Path to the file

        Returns:
            LSPClient if a suitable server is available, None otherwise
        """
        server_config = self._config.get_server_for_file(file_path)
        if server_config is None:
            logger.debug(f"No LSP server available for {file_path}")
            return None

        return self._get_or_create_client(server_config)

    def get_client_for_language(self, language: str) -> Optional[LSPClient]:
        """
        Get or create an LSP client for a language.

        Args:
            language: Language identifier (e.g., 'python', 'typescript')

        Returns:
            LSPClient if server is available, None otherwise
        """
        server_config = self._config.get_server_for_language(language)
        if server_config is None:
            logger.debug(f"No LSP server available for {language}")
            return None

        return self._get_or_create_client(server_config)

    def _get_or_create_client(self, config: LSPServerConfig) -> Optional[LSPClient]:
        """Get existing client or create a new one."""
        language = config.language_id

        if language in self._clients:
            client = self._clients[language]
            # Check if client is still running
            if client.is_running:
                return client
            # Client died, remove it
            del self._clients[language]

        # Create and initialize new client
        client = LSPClient(config, self.root_uri)

        if client.start():
            self._clients[language] = client
            return client

        return None

    def shutdown_all(self):
        """Shutdown all running language servers."""
        for language, client in list(self._clients.items()):
            try:
                logger.info(f"Shutting down {language} language server")
                client.stop()
            except Exception as e:
                logger.error(f"Error shutting down {language} server: {e}")

        self._clients.clear()

    def shutdown_language(self, language: str):
        """Shutdown a specific language server."""
        if language in self._clients:
            try:
                self._clients[language].stop()
            except Exception as e:
                logger.error(f"Error shutting down {language} server: {e}")
            finally:
                del self._clients[language]

    def is_available(self, file_path: str) -> bool:
        """Check if LSP is available for a file type."""
        return self._config.get_server_for_file(file_path) is not None

    def get_running_servers(self) -> Dict[str, bool]:
        """Get status of all running servers."""
        return {lang: client.is_running for lang, client in self._clients.items()}

    def get_available_servers(self) -> Dict[str, bool]:
        """Get all configured servers and their availability."""
        return self._config.list_available_servers()

    def set_project_root(self, project_root: str):
        """
        Change project root. This will restart all servers.

        Args:
            project_root: New project root directory
        """
        if project_root != self.project_root:
            self.shutdown_all()
            self.project_root = project_root
            self.root_uri = f"file://{project_root}"


# Global server manager instance
_server_manager: Optional[LSPServerManager] = None


def get_server_manager(project_root: Optional[str] = None) -> LSPServerManager:
    """Get the global LSP server manager."""
    global _server_manager
    if _server_manager is None:
        _server_manager = LSPServerManager(project_root)
    elif project_root and project_root != _server_manager.project_root:
        # Project root changed, update it
        _server_manager.set_project_root(project_root)
    return _server_manager


def reset_server_manager():
    """Reset the global server manager. Useful for testing."""
    global _server_manager
    if _server_manager is not None:
        _server_manager.shutdown_all()
        _server_manager = None
