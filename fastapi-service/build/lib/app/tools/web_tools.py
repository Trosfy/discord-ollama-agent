"""Custom web search and fetch tools using DuckDuckGo and BeautifulSoup."""
import sys
sys.path.insert(0, '/shared')

from typing import Dict, List
from ddgs import DDGS
import httpx
from bs4 import BeautifulSoup
from strands import tool
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


@tool(
    name="web_search",
    description="Search the web using DuckDuckGo. Returns titles, URLs, and snippets."
)
def web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search the web for current information.

    Args:
        query: Search query string (e.g., "Traveloka promotions December 2024")
        max_results: Maximum number of results to return (default: 5, max: 10)

    Returns:
        List of search results, each containing:
        - position: Result ranking (1-based)
        - title: Page title
        - url: Page URL
        - snippet: Preview text from the page
    """
    logger.info(f"🔍 Tool: web_search | Query: '{query}' | Max results: {max_results}")

    try:
        # DuckDuckGo search with context manager
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=min(max_results, 10)))

        # Format results
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append({
                "position": i,
                "title": result.get("title", ""),
                "url": result.get("href", ""),
                "snippet": result.get("body", "")
            })

        logger.info(f"✅ Tool: web_search | Found {len(formatted)} results for '{query}'")
        return formatted
    except Exception as e:
        logger.error(f"❌ Tool: web_search | Error: {str(e)}")
        return [{"error": f"Search failed: {str(e)}"}]


@tool(
    name="fetch_webpage",
    description="Fetch and extract readable text content from a webpage URL."
)
def fetch_webpage(url: str) -> Dict[str, str]:
    """
    Fetch full content from a specific webpage.

    Args:
        url: Full URL of the webpage to fetch

    Returns:
        Dictionary containing:
        - url: The fetched URL
        - title: Page title
        - content: Extracted text content (full, no truncation)
        - length: Content length in characters
    """
    logger.info(f"🌐 Tool: fetch_webpage | URL: {url}")

    try:
        # Set realistic browser headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # Fetch with timeout and redirect handling
        response = httpx.get(
            url,
            headers=headers,
            timeout=10.0,
            follow_redirects=True
        )
        response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove noise elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()

        # Extract title
        title = soup.title.string if soup.title else url.split('/')[2]

        # Extract text with line breaks
        text = soup.get_text(separator='\n', strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned = '\n'.join(lines)

        logger.info(f"✅ Tool: fetch_webpage | Successfully fetched '{title}' ({len(cleaned)} chars)")
        return {
            "url": url,
            "title": title,
            "content": cleaned,
            "length": len(cleaned)
        }
    except httpx.TimeoutException:
        logger.error(f"❌ Tool: fetch_webpage | Timeout: {url}")
        return {"error": f"Timeout fetching {url} (>10s)"}
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ Tool: fetch_webpage | HTTP {e.response.status_code}: {url}")
        return {"error": f"HTTP {e.response.status_code} error: {url}"}
    except Exception as e:
        logger.error(f"❌ Tool: fetch_webpage | Error: {str(e)}")
        return {"error": f"Failed to fetch {url}: {str(e)}"}
