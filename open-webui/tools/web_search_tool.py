"""
title: Web Search
author: open-webui, atgehrhardt, improved by claude
author_url: https://github.com/atgehrhardt
funding_url: https://github.com/open-webui
version: 2.2.0
required_open_webui_version: 0.3.30
requirements: beautifulsoup4, requests

Multi-engine web search with SearXNG integration for bot detection avoidance.
"""

from typing import List
from pydantic import BaseModel, Field
import requests
from bs4 import BeautifulSoup
import urllib.parse
import random
import time


class Tools:
    """Fast multi-engine web search with advanced anti-WAF protection"""

    class Valves(BaseModel):
        # Search engine URLs
        searxng_url: str = Field(default="http://searxng:8080", description="SearXNG instance URL")

        # Enable/disable search engines
        enable_duckduckgo: bool = Field(default=False, description="Enable DuckDuckGo search (may get blocked)")
        enable_searxng: bool = Field(default=True, description="Enable SearXNG search (recommended)")
        enable_google: bool = Field(default=False, description="Enable Google search (may get blocked)")

        # Results per engine
        default_max_results: int = Field(default=5, description="Default max results to return")

        # Anti-detection settings
        request_timeout: int = Field(default=15, description="Request timeout in seconds")
        retry_attempts: int = Field(default=2, description="Number of retry attempts")
        retry_delay: float = Field(default=1.5, description="Base delay between retries (seconds)")

        # Behavior settings
        enable_fallback: bool = Field(default=True, description="Auto-fallback to other engines on failure")
        add_human_delay: bool = Field(default=True, description="Add random delays to appear more human")

    def __init__(self):
        self.valves = self.Valves()
        self.session = requests.Session()
        self.session.mount('http://', requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20))
        self.session.mount('https://', requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20))

    def run(self, query: str) -> str:
        """
        Search the web for information. Returns formatted search results with titles, descriptions, and URLs.

        Args:
            query: The search query string (required)

        Returns:
            Formatted search results from SearXNG, DuckDuckGo, or Google
        """
        try:
            if not query or not query.strip():
                return "⚠ No search query provided. Please provide a search query."

            # Use default settings (defaults to SearXNG if enabled)
            result = self.search_web(query, engine="auto", max_results=self.valves.default_max_results)
            return result

        except Exception as e:
            error_msg = f"❌ Web search error: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return error_msg

    def search_web(
        self,
        query: str,
        engine: str = "auto",
        max_results: int = None
    ) -> str:
        """
        Search the web using multiple search engines with automatic fallback.
        """
        if not query or not query.strip():
            return "⚠ No search query provided"

        if max_results is None:
            max_results = self.valves.default_max_results

        # Determine search engine and fallbacks - prefer SearXNG if enabled
        if engine == "auto":
            if self.valves.enable_searxng:
                engine = "searxng"
            elif self.valves.enable_duckduckgo:
                engine = "duckduckgo"
            elif self.valves.enable_google:
                engine = "google"
            else:
                return "❌ No search engines enabled. Please enable at least one in Valves configuration."

        if engine == "searxng":
            search_func = self._search_searxng
            engine_name = "SearXNG"
            fallback_funcs = [
                (self._search_duckduckgo, "DuckDuckGo"),
                (self._search_google, "Google")
            ] if self.valves.enable_fallback else []

        elif engine == "duckduckgo":
            search_func = self._search_duckduckgo
            engine_name = "DuckDuckGo"
            fallback_funcs = [
                (self._search_searxng, "SearXNG"),
                (self._search_google, "Google")
            ] if self.valves.enable_fallback else []

        elif engine == "google":
            search_func = self._search_google
            engine_name = "Google"
            fallback_funcs = [
                (self._search_searxng, "SearXNG"),
                (self._search_duckduckgo, "DuckDuckGo")
            ] if self.valves.enable_fallback else []

        else:
            # Fallback to SearXNG
            search_func = self._search_searxng
            engine_name = "SearXNG (auto)"
            fallback_funcs = [
                (self._search_duckduckgo, "DuckDuckGo"),
                (self._search_google, "Google")
            ] if self.valves.enable_fallback else []

        # Try primary search engine
        try:
            result = search_func(query, max_results)

            # Check if result is successful
            if not any(x in result.lower() for x in ["no results", "error", "failed", "disabled"]):
                return result

        except Exception as e:
            print(f"✗ Primary search ({engine_name}) failed: {str(e)}")

        # Try fallback engines if enabled
        if self.valves.enable_fallback:
            for fallback_func, fallback_name in fallback_funcs:
                try:
                    # Check if fallback is enabled
                    if fallback_name == "DuckDuckGo" and not self.valves.enable_duckduckgo:
                        continue
                    if fallback_name == "SearXNG" and not self.valves.enable_searxng:
                        continue
                    if fallback_name == "Google" and not self.valves.enable_google:
                        continue

                    print(f"🔄 Trying fallback: {fallback_name}")
                    result = fallback_func(query, max_results)

                    if not any(x in result.lower() for x in ["no results", "error", "failed", "disabled"]):
                        return f"ℹ️ *Primary search failed, showing {fallback_name} results:*\n\n{result}"

                except Exception as e:
                    print(f"✗ Fallback {fallback_name} failed: {str(e)}")
                    continue

        return f"❌ All search engines failed for query: {query}\n\n💡 Try:\n- Checking your internet connection\n- Simplifying your search query\n- Using a different search engine"

    def _get_random_headers(self) -> dict:
        """Generate realistic, rotating headers to avoid WAF detection"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
        ]

        accept_languages = [
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "en-US,en;q=0.9,th;q=0.8",
            "en-US,en;q=0.9,es;q=0.8",
        ]

        return {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": random.choice(accept_languages),
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

    def _make_request(self, url: str, params: dict = None, max_retries: int = None) -> requests.Response:
        """Make HTTP request with retry logic and anti-detection"""
        if max_retries is None:
            max_retries = self.valves.retry_attempts

        # Add human-like delay before first request
        if self.valves.add_human_delay:
            time.sleep(random.uniform(0.5, 1.5))

        for attempt in range(max_retries):
            try:
                # Exponential backoff with jitter on retries
                if attempt > 0:
                    delay = self.valves.retry_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"⟳ Retry attempt {attempt + 1}/{max_retries}, waiting {delay:.2f}s")
                    time.sleep(delay)

                headers = self._get_random_headers()

                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.valves.request_timeout,
                    allow_redirects=True
                )

                # Check for rate limiting
                if response.status_code == 429:
                    print(f"⚠ Rate limited (429), attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        time.sleep(self.valves.retry_delay * 3)
                        continue
                    else:
                        raise Exception("Rate limited after all retries")

                # Check for other client errors
                if response.status_code == 403:
                    print(f"⚠ Forbidden (403) - possible bot detection")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        raise Exception("Access forbidden - bot detection likely")

                response.raise_for_status()

                return response

            except requests.exceptions.Timeout:
                print(f"⏱ Timeout (attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    raise Exception(f"Request timed out after {max_retries} attempts")

            except requests.exceptions.RequestException as e:
                print(f"✗ Request failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    raise

        raise Exception(f"Failed after {max_retries} attempts")

    def _search_duckduckgo(self, query: str, max_results: int = None) -> str:
        """Search using DuckDuckGo (API + HTML fallback)"""
        if not self.valves.enable_duckduckgo:
            return "DuckDuckGo search is disabled"

        if not max_results:
            max_results = self.valves.default_max_results

        print(f"🦆 Searching DuckDuckGo for: {query}")

        try:
            # First try the instant answer API (more reliable, no scraping)
            api_url = "https://api.duckduckgo.com/"
            api_params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1
            }

            try:
                api_response = self._make_request(api_url, params=api_params)
                api_data = api_response.json()

                formatted_results = "🦆 **DuckDuckGo Search Results:**\n\n"
                has_results = False

                # Abstract (instant answer)
                if api_data.get("Abstract"):
                    formatted_results += f"📋 **Quick Answer:**\n{api_data['Abstract']}\n"
                    if api_data.get('AbstractURL'):
                        formatted_results += f"🔗 Source: {api_data['AbstractURL']}\n\n"
                    has_results = True

                # Related topics
                topics_found = 0

                for topic in api_data.get("RelatedTopics", []):
                    if topics_found >= max_results:
                        break

                    if isinstance(topic, dict) and "Text" in topic:
                        formatted_results += f"{topics_found + 1}. {topic['Text']}\n"
                        if topic.get('FirstURL'):
                            formatted_results += f"   🔗 {topic['FirstURL']}\n\n"
                        topics_found += 1
                        has_results = True
                    elif isinstance(topic, dict) and "Topics" in topic:
                        # Nested topics
                        for subtopic in topic["Topics"]:
                            if topics_found >= max_results:
                                break
                            if "Text" in subtopic:
                                formatted_results += f"{topics_found + 1}. {subtopic['Text']}\n"
                                if subtopic.get('FirstURL'):
                                    formatted_results += f"   🔗 {subtopic['FirstURL']}\n\n"
                                topics_found += 1
                                has_results = True

                if has_results:
                    return formatted_results

            except Exception as e:
                print(f"⚠ DDG API failed, trying HTML scraping: {str(e)}")

            # Fallback to HTML scraping
            html_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            response = self._make_request(html_url)

            soup = BeautifulSoup(response.text, "html.parser")

            # Try multiple selectors (DDG changes these occasionally)
            results_list = (
                soup.find_all("div", class_="result__body") or
                soup.find_all("div", class_="results_links") or
                soup.find_all("div", class_="result") or
                soup.find_all("div", {"class": lambda x: x and "result" in x})
            )

            if not results_list:
                return f"No results found for: {query}"

            formatted_results = "🦆 **DuckDuckGo Search Results:**\n\n"

            for i, result in enumerate(results_list[:max_results], 1):
                try:
                    title_elem = (
                        result.find("a", class_="result__a") or
                        result.find("a", class_="result__title") or
                        result.find("h2", class_="result__title")
                    )
                    snippet_elem = (
                        result.find("a", class_="result__snippet") or
                        result.find("div", class_="result__snippet")
                    )

                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.get("href", "No URL")
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else "No description"

                        formatted_results += f"{i}. **{title}**\n   {snippet}\n   🔗 {link}\n\n"
                except Exception as e:
                    print(f"⚠ Error parsing DDG result {i}: {str(e)}")
                    continue

            return formatted_results

        except Exception as e:
            return f"DuckDuckGo search error: {str(e)}"

    def _search_google(self, query: str, max_results: int = None) -> str:
        """Search using Google (may get blocked - use with caution)"""
        if not self.valves.enable_google:
            return "Google search is disabled"

        if not max_results:
            max_results = self.valves.default_max_results

        print(f"🔎 Searching Google for: {query}")

        try:
            # Add extra delay for Google (they're strict)
            if self.valves.add_human_delay:
                time.sleep(random.uniform(2, 4))

            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num={max_results + 5}"

            response = self._make_request(url)
            soup = BeautifulSoup(response.text, "html.parser")

            # Multiple fallback selectors for Google (they change frequently)
            search_containers = (
                soup.find_all("div", class_="g") or
                soup.find_all("div", {"data-sokoban-container": True}) or
                soup.find_all("div", class_="Gx5Zad") or
                soup.find_all("div", class_="tF2Cxc")
            )

            # Alternative: find via h3 tags if containers don't work
            if not search_containers:
                h3_tags = soup.find_all("h3")
                results_list = []
                for h3 in h3_tags:
                    parent = h3.find_parent("div")
                    if parent and parent not in results_list:
                        results_list.append(parent)
                search_containers = results_list

            if not search_containers:
                return f"No results found for: {query}\n⚠ Possible bot detection - try SearXNG instead"

            formatted_results = f"🔎 **Google Search Results for '{query}':**\n\n"
            found_count = 0

            for container in search_containers:
                if found_count >= max_results:
                    break

                try:
                    # Try multiple title selectors
                    title_elem = (
                        container.find("h3") or
                        container.find("div", {"role": "heading"}) or
                        container.find("span", class_="CVA68e")
                    )

                    # Try multiple link selectors
                    link_elem = container.find("a", href=True)

                    # Try multiple snippet selectors
                    snippet_elem = (
                        container.find("div", class_="VwiC3b") or
                        container.find("div", class_="IsZvec") or
                        container.find("span", class_="aCOpRe") or
                        container.find("div", {"data-sncf": "1"}) or
                        container.find("div", class_="kb0PBd") or
                        container.find("span", class_="hgKElc")
                    )

                    if title_elem and link_elem:
                        title = title_elem.get_text(strip=True)
                        link = link_elem["href"]

                        # Filter out internal Google links
                        if not link.startswith("http") or "google.com" in link:
                            continue

                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else "No description"

                        found_count += 1
                        formatted_results += f"{found_count}. **{title}**\n   {snippet}\n   🔗 {link}\n\n"

                except Exception as e:
                    print(f"⚠ Error parsing Google result: {str(e)}")
                    continue

            if found_count == 0:
                return f"Could not parse Google results for: {query}\n💡 Recommend using SearXNG instead"

            return formatted_results

        except Exception as e:
            return f"Google search error: {str(e)}\n💡 Recommend using SearXNG as fallback"

    def _search_searxng(self, query: str, max_results: int = None) -> str:
        """Search using SearXNG (meta-search engine)"""
        if not self.valves.enable_searxng:
            return "SearXNG search is disabled"

        if not max_results:
            max_results = self.valves.default_max_results

        print(f"🔍 Searching SearXNG for: {query}")

        try:
            searxng_url = f"{self.valves.searxng_url}/search"
            params = {
                "q": query,
                "format": "json",
                "language": "en"
            }

            response = self._make_request(searxng_url, params=params)
            search_results = response.json()

            if not search_results.get("results"):
                return f"No results found for: {query}"

            formatted_results = "🔍 **SearXNG Search Results:**\n\n"

            for i, result in enumerate(search_results["results"][:max_results], 1):
                title = result.get("title", "No title")
                snippet = result.get("content", "No description available")
                link = result.get("url", "No URL available")
                engine = result.get("engine", "")

                formatted_results += f"{i}. **{title}**"
                if engine:
                    formatted_results += f" [{engine}]"
                formatted_results += f"\n   {snippet}\n   🔗 {link}\n\n"

            return formatted_results

        except Exception as e:
            return f"SearXNG search error: {str(e)}\n(Make sure SearXNG is running at {self.valves.searxng_url})"
