"""
LSP Server configuration - maps languages to their servers.
"""

import os
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class LSPServerConfig:
    """Configuration for a language server."""

    language_id: str  # LSP language identifier
    extensions: List[str]  # File extensions this server handles
    command: List[str]  # Command to start the server
    initialization_options: Optional[Dict] = None

    def is_available(self) -> bool:
        """Check if the server command is available on PATH."""
        if not self.command:
            return False
        return shutil.which(self.command[0]) is not None


# Default LSP server configurations
DEFAULT_LSP_SERVERS: Dict[str, LSPServerConfig] = {
    "python": LSPServerConfig(
        language_id="python",
        extensions=[".py", ".pyi"],
        command=["pyright-langserver", "--stdio"],
        initialization_options={"python": {"analysis": {"autoSearchPaths": True}}},
    ),
    "typescript": LSPServerConfig(
        language_id="typescript",
        extensions=[".ts", ".tsx"],
        command=["typescript-language-server", "--stdio"],
    ),
    "javascript": LSPServerConfig(
        language_id="javascript",
        extensions=[".js", ".jsx", ".mjs"],
        command=["typescript-language-server", "--stdio"],
    ),
    "go": LSPServerConfig(
        language_id="go",
        extensions=[".go"],
        command=["gopls", "serve"],
    ),
    "rust": LSPServerConfig(
        language_id="rust",
        extensions=[".rs"],
        command=["rust-analyzer"],
    ),
    "c": LSPServerConfig(
        language_id="c",
        extensions=[".c", ".h"],
        command=["clangd"],
    ),
    "cpp": LSPServerConfig(
        language_id="cpp",
        extensions=[".cpp", ".hpp", ".cc", ".cxx", ".hxx"],
        command=["clangd"],
    ),
    "java": LSPServerConfig(
        language_id="java",
        extensions=[".java"],
        command=["jdtls"],  # Eclipse JDT Language Server
    ),
}


class LSPConfig:
    """LSP configuration manager."""

    def __init__(self):
        self._servers = {k: v for k, v in DEFAULT_LSP_SERVERS.items()}
        self._load_custom_config()

    def _load_custom_config(self):
        """Load custom LSP config from environment or config file."""
        # Check for custom server overrides via environment
        # VISHWA_LSP_PYTHON_CMD=mypy-langserver --stdio
        for lang in list(self._servers.keys()):
            env_key = f"VISHWA_LSP_{lang.upper()}_CMD"
            custom_cmd = os.getenv(env_key)
            if custom_cmd:
                self._servers[lang] = LSPServerConfig(
                    language_id=self._servers[lang].language_id,
                    extensions=self._servers[lang].extensions,
                    command=custom_cmd.split(),
                    initialization_options=self._servers[lang].initialization_options,
                )

    def get_server_for_file(self, file_path: str) -> Optional[LSPServerConfig]:
        """Get the LSP server config for a file based on extension."""
        ext = Path(file_path).suffix.lower()
        for config in self._servers.values():
            if ext in config.extensions:
                return config if config.is_available() else None
        return None

    def get_server_for_language(self, language: str) -> Optional[LSPServerConfig]:
        """Get the LSP server config for a language."""
        config = self._servers.get(language.lower())
        return config if config and config.is_available() else None

    def list_available_servers(self) -> Dict[str, bool]:
        """List all configured servers and their availability."""
        return {lang: config.is_available() for lang, config in self._servers.items()}

    def list_all_servers(self) -> Dict[str, LSPServerConfig]:
        """List all configured servers."""
        return dict(self._servers)

    def register_server(self, language: str, config: LSPServerConfig):
        """Register a custom LSP server."""
        self._servers[language] = config

    def get_install_hint(self, language: str) -> str:
        """Get installation hint for a language server."""
        hints = {
            "python": "pip install pyright",
            "typescript": "npm install -g typescript-language-server typescript",
            "javascript": "npm install -g typescript-language-server typescript",
            "go": "go install golang.org/x/tools/gopls@latest",
            "rust": "rustup component add rust-analyzer",
            "c": "Install clangd (e.g., apt install clangd, brew install llvm)",
            "cpp": "Install clangd (e.g., apt install clangd, brew install llvm)",
            "java": "Install Eclipse JDT Language Server",
        }
        return hints.get(language, f"Install an LSP server for {language}")


# Global config instance
_lsp_config: Optional[LSPConfig] = None


def get_lsp_config() -> LSPConfig:
    """Get the global LSP configuration."""
    global _lsp_config
    if _lsp_config is None:
        _lsp_config = LSPConfig()
    return _lsp_config
