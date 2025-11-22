"""
Autocomplete service that communicates with VS Code via stdio.

This service runs as a background process and handles autocomplete requests.
"""

import sys
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path

from vishwa.autocomplete.suggestion_engine import SuggestionEngine
from vishwa.autocomplete.cache import SuggestionCache
from vishwa.autocomplete.protocol import (
    AutocompleteRequest,
    AutocompleteSuggestion,
    JSONRPCMessage
)


# Setup logging to file (not stdout, which is used for protocol)
logging.basicConfig(
    filename='/tmp/vishwa-autocomplete.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AutocompleteService:
    """
    Autocomplete service that handles requests via JSON-RPC over stdio.
    """

    def __init__(self, default_model: str = "claude-haiku"):
        """
        Initialize autocomplete service.

        Args:
            default_model: Default model to use for suggestions
        """
        self.suggestion_engine = SuggestionEngine(model=default_model)
        self.cache = SuggestionCache(max_size=100, ttl=300)
        self.default_model = default_model
        logger.info(f"Autocomplete service initialized with model: {default_model}")

    def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a JSON-RPC request.

        Args:
            request_data: Parsed JSON-RPC request

        Returns:
            Response dictionary
        """
        method = request_data.get('method')
        params = request_data.get('params', {})
        request_id = request_data.get('id')

        logger.debug(f"Handling request: method={method}, id={request_id}")

        try:
            if method == 'getSuggestion':
                result = self._handle_get_suggestion(params)
            elif method == 'setModel':
                result = self._handle_set_model(params)
            elif method == 'clearCache':
                result = self._handle_clear_cache()
            elif method == 'getStats':
                result = self._handle_get_stats()
            elif method == 'ping':
                result = {'status': 'ok'}
            else:
                return json.loads(JSONRPCMessage.error(
                    code=-32601,
                    message=f"Method not found: {method}",
                    id=request_id
                ))

            return json.loads(JSONRPCMessage.response(result, request_id))

        except Exception as e:
            logger.error(f"Error handling request: {e}", exc_info=True)
            return json.loads(JSONRPCMessage.error(
                code=-32603,
                message=str(e),
                id=request_id
            ))

    def _handle_get_suggestion(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle getSuggestion request.

        Args:
            params: Request parameters

        Returns:
            Suggestion result
        """
        file_path = params.get('file_path', '')
        content = params.get('content', '')
        cursor = params.get('cursor', {})
        cursor_line = cursor.get('line', 0)
        cursor_char = cursor.get('character', 0)

        logger.debug(f"Getting suggestion for {file_path} at {cursor_line}:{cursor_char}")

        # Build context for cache key
        lines = content.split('\n')
        start_line = max(0, cursor_line - 5)
        end_line = min(len(lines), cursor_line + 2)
        context = '\n'.join(lines[start_line:end_line])

        # Check cache first
        cached_suggestion = self.cache.get(
            file_path, cursor_line, cursor_char, context, content
        )

        if cached_suggestion:
            logger.debug("Returning cached suggestion")
            return {
                'suggestion': cached_suggestion,
                'type': 'insertion',
                'cached': True
            }

        # Generate new suggestion
        suggestion = self.suggestion_engine.generate_suggestion(
            file_path, content, cursor_line, cursor_char
        )

        if suggestion:
            # Cache the suggestion
            self.cache.put(
                file_path, cursor_line, cursor_char, context, content, suggestion.text
            )

            logger.debug(f"Generated suggestion: {suggestion.text[:50]}...")
            return {
                'suggestion': suggestion.text,
                'type': suggestion.suggestion_type,
                'cached': False
            }
        else:
            logger.debug("No suggestion generated")
            return {
                'suggestion': '',
                'type': 'none',
                'cached': False
            }

    def _handle_set_model(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle setModel request.

        Args:
            params: Request parameters with 'model' key

        Returns:
            Success result
        """
        model = params.get('model', self.default_model)
        logger.info(f"Switching model to: {model}")
        self.suggestion_engine.set_model(model)
        return {'status': 'ok', 'model': model}

    def _handle_clear_cache(self) -> Dict[str, Any]:
        """
        Handle clearCache request.

        Returns:
            Success result
        """
        logger.info("Clearing cache")
        self.cache.clear()
        return {'status': 'ok'}

    def _handle_get_stats(self) -> Dict[str, Any]:
        """
        Handle getStats request.

        Returns:
            Statistics about the service
        """
        cache_stats = self.cache.get_stats()
        return {
            'cache': cache_stats,
            'model': self.suggestion_engine.model
        }

    def run(self):
        """
        Run the service loop, reading from stdin and writing to stdout.
        """
        logger.info("Starting autocomplete service loop")

        try:
            while True:
                # Read line from stdin
                line = sys.stdin.readline()

                if not line:
                    logger.info("EOF received, shutting down")
                    break

                line = line.strip()
                if not line:
                    continue

                logger.debug(f"Received: {line[:100]}...")

                try:
                    # Parse JSON-RPC request
                    request_data = json.loads(line)

                    # Handle request
                    response = self.handle_request(request_data)

                    # Send response to stdout
                    response_str = json.dumps(response)
                    print(response_str, flush=True)
                    logger.debug(f"Sent: {response_str[:100]}...")

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    error_response = JSONRPCMessage.error(
                        code=-32700,
                        message="Parse error",
                        id=None
                    )
                    print(error_response, flush=True)

        except KeyboardInterrupt:
            logger.info("Service interrupted by user")
        except Exception as e:
            logger.error(f"Unexpected error in service loop: {e}", exc_info=True)
        finally:
            logger.info("Autocomplete service shutting down")


def main():
    """Main entry point for the autocomplete service."""
    import argparse

    parser = argparse.ArgumentParser(description='Vishwa Autocomplete Service')
    parser.add_argument(
        '--model',
        default='claude-haiku',
        help='Default model to use (e.g., claude-haiku, gpt-4o-mini, codestral)'
    )
    parser.add_argument(
        '--stdio',
        action='store_true',
        default=True,
        help='Use stdio for communication (default)'
    )

    args = parser.parse_args()

    logger.info(f"Starting Vishwa autocomplete service with model: {args.model}")

    service = AutocompleteService(default_model=args.model)
    service.run()


if __name__ == '__main__':
    main()
