"""Safe web search and page summarization for JARVIS.

Uses DuckDuckGo HTML scraping (no API key needed) as the primary search engine.
Page content is fetched with httpx and returned as plain text for the AI to summarize.
No cookies, no form submissions, no authentication.
"""

from __future__ import annotations

import re
from typing import List, Dict
from urllib.parse import quote_plus, urljoin

# httpx is a modern HTTP client; falls back to urllib if unavailable
try:
    import httpx
    _USE_HTTPX = True
except ImportError:
    import urllib.request
    _USE_HTTPX = False

TIMEOUT = 10  # seconds
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
DDG_URL = "https://html.duckduckgo.com/html/?q={query}"


def _fetch(url: str) -> str:
    """Fetch a URL and return the response text."""
    if _USE_HTTPX:
        with httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.text
    else:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")


def _strip_html(html: str) -> str:
    """Very lightweight HTML → plain-text stripper (no dependency on BeautifulSoup)."""
    # Remove scripts and styles
    html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", html, flags=re.S | re.I)
    # Remove all tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search DuckDuckGo and return up to *max_results* results.

    Each result is a dict with keys: ``title``, ``url``, ``snippet``.
    Returns an empty list (never raises) on network failure.
    """
    try:
        url = DDG_URL.format(query=quote_plus(query))
        html = _fetch(url)
    except Exception as e:
        return [{"title": "Search failed", "url": "", "snippet": str(e)}]

    results: List[Dict[str, str]] = []

    # Parse result blocks: DuckDuckGo HTML returns <a class="result__a"> links
    blocks = re.findall(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html, flags=re.S
    )
    snippets = re.findall(
        r'class="result__snippet"[^>]*>(.*?)</a>',
        html, flags=re.S
    )

    for i, (href, title_html) in enumerate(blocks[:max_results]):
        title = _strip_html(title_html)
        snippet = _strip_html(snippets[i]) if i < len(snippets) else ""
        results.append({"title": title, "url": href, "snippet": snippet})

    if not results:
        results.append({
            "title": "No results found",
            "url": "",
            "snippet": f"DuckDuckGo returned no results for '{query}'.",
        })

    return results


def fetch_page_text(url: str, max_chars: int = 8000) -> str:
    """Fetch a web page and return its plain text content (stripped of HTML).

    Useful for the AI to summarize an article or documentation page.
    Returns an error string (never raises) on failure.
    """
    try:
        html = _fetch(url)
        text = _strip_html(html)
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[truncated – {len(text)} total chars]"
        return text
    except Exception as e:
        return f"[Failed to fetch page: {e}]"
