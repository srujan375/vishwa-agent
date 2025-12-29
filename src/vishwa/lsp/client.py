"""
LSP Client - communicates with a single language server.
"""

import subprocess
import threading
import queue
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from vishwa.lsp.protocol import LSPMessage, Location, Position, Range
from vishwa.lsp.config import LSPServerConfig

logger = logging.getLogger(__name__)


class LSPClient:
    """
    Client for communicating with a Language Server.

    Manages:
    - Server process lifecycle (spawn, shutdown)
    - JSON-RPC message exchange over stdio
    - Request/response correlation via IDs
    - Asynchronous response handling
    """

    def __init__(self, config: LSPServerConfig, root_uri: str):
        """
        Initialize LSP client.

        Args:
            config: Server configuration
            root_uri: Project root as file:// URI
        """
        self.config = config
        self.root_uri = root_uri
        self.process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._pending_requests: Dict[int, queue.Queue] = {}
        self._reader_thread: Optional[threading.Thread] = None
        self._initialized = False
        self._lock = threading.Lock()
        self._shutdown_requested = False

    def start(self) -> bool:
        """
        Start the language server process and initialize.

        Returns:
            True if successfully initialized
        """
        if self.process is not None:
            return True

        try:
            logger.info(f"Starting LSP server: {' '.join(self.config.command)}")

            self.process = subprocess.Popen(
                self.config.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self._uri_to_path(self.root_uri),
            )

            # Start reader thread
            self._reader_thread = threading.Thread(target=self._read_responses, daemon=True)
            self._reader_thread.start()

            # Send initialize request
            init_response = self._send_request_sync(
                LSPMessage.initialize(self.root_uri, self._next_id())
            )

            if init_response and "result" in init_response:
                # Send initialized notification
                self._send_notification(LSPMessage.initialized())
                self._initialized = True
                logger.info(f"LSP server initialized for {self.config.language_id}")
                return True

            logger.error("LSP server failed to initialize")
            return False

        except Exception as e:
            logger.error(f"Failed to start LSP server: {e}")
            self.stop()
            return False

    def stop(self):
        """Shutdown the language server gracefully."""
        if self.process is None:
            return

        self._shutdown_requested = True

        try:
            # Send shutdown request
            self._send_request_sync(LSPMessage.shutdown(self._next_id()), timeout=5.0)

            # Send exit notification
            self._send_notification(LSPMessage.exit())

            # Wait for process to terminate
            self.process.wait(timeout=5.0)

        except Exception as e:
            logger.warning(f"Error during graceful shutdown: {e}")
            if self.process:
                self.process.kill()

        finally:
            self.process = None
            self._initialized = False
            self._shutdown_requested = False

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self.process is not None and self.process.poll() is None

    def goto_definition(
        self, file_path: str, line: int, character: int
    ) -> Optional[Location]:
        """
        Get definition location for symbol at position.

        Args:
            file_path: Absolute path to file
            line: 0-indexed line number
            character: 0-indexed character offset

        Returns:
            Location of definition, or None
        """
        if not self._initialized:
            return None

        uri = self._path_to_uri(file_path)
        request = LSPMessage.goto_definition(uri, line, character, self._next_id())

        response = self._send_request_sync(request)

        if response and "result" in response:
            result = response["result"]
            return self._parse_location(result)

        return None

    def find_references(
        self,
        file_path: str,
        line: int,
        character: int,
        include_declaration: bool = True,
    ) -> List[Location]:
        """
        Find all references to symbol at position.

        Args:
            file_path: Absolute path to file
            line: 0-indexed line number
            character: 0-indexed character offset
            include_declaration: Include the definition itself

        Returns:
            List of Location objects
        """
        if not self._initialized:
            return []

        uri = self._path_to_uri(file_path)
        request = LSPMessage.find_references(
            uri, line, character, self._next_id(), include_declaration
        )

        response = self._send_request_sync(request)

        if response and "result" in response:
            result = response["result"]
            if isinstance(result, list):
                return [loc for loc in (self._parse_location(item) for item in result) if loc]

        return []

    def hover(self, file_path: str, line: int, character: int) -> Optional[str]:
        """
        Get hover information (documentation/type info) for symbol.

        Args:
            file_path: Absolute path to file
            line: 0-indexed line number
            character: 0-indexed character offset

        Returns:
            Hover contents as string, or None
        """
        if not self._initialized:
            return None

        uri = self._path_to_uri(file_path)
        request = LSPMessage.hover(uri, line, character, self._next_id())

        response = self._send_request_sync(request)

        if response and "result" in response:
            result = response["result"]
            return self._parse_hover_contents(result)

        return None

    def document_symbols(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Get all symbols in a document.

        Args:
            file_path: Absolute path to file

        Returns:
            List of symbol information dictionaries
        """
        if not self._initialized:
            return []

        uri = self._path_to_uri(file_path)
        request = LSPMessage.document_symbols(uri, self._next_id())

        response = self._send_request_sync(request)

        if response and "result" in response:
            result = response["result"]
            if isinstance(result, list):
                return result

        return []

    def notify_document_open(self, file_path: str, content: str):
        """Notify server that a document was opened."""
        uri = self._path_to_uri(file_path)
        self._send_notification(
            LSPMessage.text_document_did_open(
                uri, self.config.language_id, version=1, text=content
            )
        )

    def notify_document_close(self, file_path: str):
        """Notify server that a document was closed."""
        uri = self._path_to_uri(file_path)
        self._send_notification(LSPMessage.text_document_did_close(uri))

    # --- Internal methods ---

    def _next_id(self) -> int:
        """Get next request ID."""
        with self._lock:
            self._request_id += 1
            return self._request_id

    def _send_notification(self, message: bytes):
        """Send notification (no response expected)."""
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(message)
                self.process.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                logger.warning(f"Failed to send notification: {e}")

    def _send_request_sync(
        self, message: bytes, timeout: float = 30.0
    ) -> Optional[Dict]:
        """Send request and wait for response."""
        if not self.process or not self.process.stdin:
            return None

        # Parse message to get ID
        msg_data = LSPMessage.decode(message)
        if not msg_data or "id" not in msg_data:
            return None

        request_id = msg_data["id"]
        response_queue: queue.Queue = queue.Queue()

        with self._lock:
            self._pending_requests[request_id] = response_queue

        try:
            # Send request
            self.process.stdin.write(message)
            self.process.stdin.flush()

            # Wait for response
            return response_queue.get(timeout=timeout)

        except queue.Empty:
            logger.warning(f"Request {request_id} timed out")
            return None
        except (BrokenPipeError, OSError) as e:
            logger.warning(f"Failed to send request: {e}")
            return None
        finally:
            with self._lock:
                self._pending_requests.pop(request_id, None)

    def _read_responses(self):
        """Background thread to read server responses."""
        buffer = b""

        while self.process and self.process.poll() is None and not self._shutdown_requested:
            try:
                chunk = self.process.stdout.read(4096)
                if not chunk:
                    break

                buffer += chunk

                # Try to parse complete messages
                while b"\r\n\r\n" in buffer:
                    header_end = buffer.index(b"\r\n\r\n")
                    header = buffer[:header_end].decode("utf-8")

                    # Parse Content-Length
                    content_length = 0
                    for line in header.split("\r\n"):
                        if line.startswith("Content-Length:"):
                            content_length = int(line.split(":")[1].strip())

                    # Check if we have full message
                    message_start = header_end + 4
                    message_end = message_start + content_length

                    if len(buffer) < message_end:
                        break  # Wait for more data

                    # Parse message
                    content = buffer[message_start:message_end].decode("utf-8")
                    buffer = buffer[message_end:]

                    try:
                        response = json.loads(content)
                        self._handle_response(response)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse response: {e}")

            except Exception as e:
                if not self._shutdown_requested:
                    logger.error(f"Error reading from LSP server: {e}")
                break

    def _handle_response(self, response: Dict):
        """Handle incoming response from server."""
        if "id" in response:
            # This is a response to a request
            request_id = response["id"]
            with self._lock:
                if request_id in self._pending_requests:
                    self._pending_requests[request_id].put(response)
        else:
            # This is a notification from server (diagnostics, etc.)
            method = response.get("method", "")
            if method == "textDocument/publishDiagnostics":
                # Could be extended to handle diagnostics
                pass

    def _parse_location(self, result: Any) -> Optional[Location]:
        """Parse location from LSP response."""
        if result is None:
            return None

        # Handle array (multiple definitions)
        if isinstance(result, list):
            if len(result) == 0:
                return None
            result = result[0]

        # Handle LocationLink format
        if "targetUri" in result:
            range_data = result.get("targetRange", result.get("targetSelectionRange"))
            return Location(
                uri=result["targetUri"], range=self._parse_range(range_data)
            )

        # Handle Location format
        if "uri" in result:
            return Location(uri=result["uri"], range=self._parse_range(result.get("range")))

        return None

    def _parse_range(self, range_data: Optional[Dict]) -> Range:
        """Parse range from LSP response."""
        if range_data is None:
            return Range(start=Position(0, 0), end=Position(0, 0))
        return Range(
            start=Position.from_dict(range_data["start"]),
            end=Position.from_dict(range_data["end"]),
        )

    def _parse_hover_contents(self, hover_result: Optional[Dict]) -> Optional[str]:
        """Parse hover contents from LSP response."""
        if hover_result is None:
            return None

        contents = hover_result.get("contents")
        if contents is None:
            return None

        # Handle MarkupContent
        if isinstance(contents, dict):
            return contents.get("value", str(contents))

        # Handle MarkedString array
        if isinstance(contents, list):
            parts = []
            for item in contents:
                if isinstance(item, dict):
                    parts.append(item.get("value", str(item)))
                else:
                    parts.append(str(item))
            return "\n".join(parts)

        return str(contents)

    @staticmethod
    def _path_to_uri(path: str) -> str:
        """Convert file path to file:// URI."""
        abs_path = str(Path(path).resolve())
        return f"file://{abs_path}"

    @staticmethod
    def _uri_to_path(uri: str) -> str:
        """Convert file:// URI to file path."""
        if uri.startswith("file://"):
            return uri[7:]
        return uri
