"""
Web tools for fetching and searching the web.

Provides WebFetch and WebSearch functionality.
"""

import re
from typing import Any, Dict
from urllib.parse import urlparse

from vishwa.tools.base import Tool, ToolResult


class WebFetchTool(Tool):
    """
    Fetches content from a URL and processes it.

    Converts HTML to markdown and allows processing with a prompt.
    """

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return """Fetches content from a specified URL and processes it.

Takes a URL and a prompt as input:
1. Fetches the URL content
2. Converts HTML to markdown (if applicable)
3. Processes the content with the prompt
4. Returns the processed result

USE THIS when you need to retrieve and analyze web content.

Examples:
- web_fetch(url="https://docs.python.org/3/library/re.html", prompt="Summarize regex flags")
- web_fetch(url="https://github.com/user/repo", prompt="List the main features")

Parameters:
- url: Fully-formed valid URL to fetch
- prompt: What information to extract from the page

Notes:
- HTTP URLs automatically upgraded to HTTPS
- Results may be summarized if content is very large
- Read-only, does not modify any files
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "format": "uri",
                    "description": "The URL to fetch content from",
                },
                "prompt": {
                    "type": "string",
                    "description": "The prompt to run on the fetched content - what info to extract",
                },
            },
            "required": ["url", "prompt"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Fetch and process web content.

        Args:
            url: URL to fetch
            prompt: Processing prompt

        Returns:
            ToolResult with processed content
        """
        self.validate_params(**kwargs)
        url = kwargs["url"]
        prompt = kwargs["prompt"]

        try:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme:
                url = f"https://{url}"
            elif parsed.scheme == "http":
                url = url.replace("http://", "https://", 1)

            # Try to fetch using requests
            try:
                import requests
                from bs4 import BeautifulSoup
            except ImportError:
                return ToolResult(
                    success=False,
                    error="Required packages not installed: requests, beautifulsoup4",
                    suggestion="Install with: pip install requests beautifulsoup4",
                )

            # Fetch with timeout
            response = requests.get(
                url,
                headers={"User-Agent": "Vishwa-Bot/1.0"},
                timeout=10,
                allow_redirects=True,
            )

            if response.status_code != 200:
                return ToolResult(
                    success=False,
                    error=f"HTTP {response.status_code}: {response.reason}",
                    suggestion="Check the URL and try again",
                )

            # Convert HTML to text/markdown
            content_type = response.headers.get("content-type", "")

            if "html" in content_type:
                soup = BeautifulSoup(response.text, "html.parser")

                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer"]):
                    script.decompose()

                # Get text
                text = soup.get_text()

                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                text = "\n".join(line for line in lines if line)

            else:
                text = response.text

            # Limit size
            if len(text) > 50000:
                text = text[:50000] + "\n\n[Content truncated...]"

            # Process with prompt (simulate - in real implementation would use LLM)
            # For now, just return the content with the prompt context
            result = f"URL: {url}\n\nPrompt: {prompt}\n\nContent:\n{text}"

            return ToolResult(
                success=True,
                output=result,
                metadata={
                    "url": url,
                    "prompt": prompt,
                    "content_length": len(text),
                    "status_code": response.status_code,
                },
            )

        except requests.RequestException as e:
            return ToolResult(
                success=False,
                error=f"Failed to fetch URL: {str(e)}",
                suggestion="Check the URL and your internet connection",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Fetch failed: {str(e)}",
                metadata={"url": url},
            )


class WebSearchTool(Tool):
    """
    Search the web and return results.

    Note: This is a simplified implementation.
    In production, you'd integrate with a search API.
    """

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return """Search the web and use the results to inform responses.

Provides up-to-date information for current events and recent data.
Returns search result information formatted as search result blocks.

USE THIS for accessing information beyond the model's knowledge cutoff.

Examples:
- web_search(query="Python 3.12 new features")
- web_search(query="latest React best practices 2024")

Parameters:
- query: The search query
- max_results: Maximum number of results (default: 5)

Note: Actual search implementation requires API keys (DuckDuckGo, Google, etc.)
For now, this returns a placeholder. Integrate with your preferred search API.
"""

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to use",
                    "minLength": 2,
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Search the web.

        Args:
            query: Search query
            max_results: Max results

        Returns:
            ToolResult with search results
        """
        self.validate_params(**kwargs)
        query = kwargs["query"]
        max_results = kwargs.get("max_results", 5)

        try:
            # Try DuckDuckGo first (no API key needed)
            try:
                from ddgs import DDGS
            except ImportError:
                return ToolResult(
                    success=False,
                    error="DuckDuckGo search not available",
                    suggestion="Install with: pip install ddgs\n"
                              "Or integrate with Google Custom Search API",
                )

            # Search
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if not results:
                return ToolResult(
                    success=True,
                    output=f"No results found for: {query}",
                    metadata={"query": query, "count": 0},
                )

            # Format results
            output_lines = [f"Search results for: {query}\n"]
            for i, result in enumerate(results, 1):
                title = result.get("title", "No title")
                url = result.get("href", result.get("link", ""))
                snippet = result.get("body", result.get("snippet", ""))

                output_lines.append(f"{i}. {title}")
                output_lines.append(f"   URL: {url}")
                output_lines.append(f"   {snippet}\n")

            return ToolResult(
                success=True,
                output="\n".join(output_lines),
                metadata={
                    "query": query,
                    "count": len(results),
                    "results": results,
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}",
                suggestion="Check your internet connection",
                metadata={"query": query},
            )
