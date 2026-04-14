"""
Firecrawl URL ingestion service.

Fetches web pages and converts them to clean markdown using Firecrawl.
This is online-only — documented as the one feature that requires internet.

If Firecrawl is unavailable (no API key, offline, rate limited), the error
is surfaced to the user via the ingest job status endpoint.
"""

import logging
from typing import Optional, Tuple

import httpx

logger = logging.getLogger("vanilla.ingestion.firecrawl")

# Fallback: simple HTTP fetch + basic HTML stripping when Firecrawl unavailable
SIMPLE_FALLBACK_ENABLED = True


async def fetch_url(url: str, api_key: Optional[str] = None) -> Tuple[str, str]:
    """
    Fetch a URL and return (markdown_content, title).

    Tries Firecrawl first, falls back to simple HTTP fetch if Firecrawl
    is not installed or API key is missing.

    Args:
        url: The URL to fetch
        api_key: Firecrawl API key (optional)

    Returns:
        Tuple of (markdown_content, page_title)

    Raises:
        ImportError: If firecrawl-py is not installed and fallback is disabled
        RuntimeError: If fetch fails
    """
    # Try Firecrawl first
    if api_key:
        try:
            return await _fetch_with_firecrawl(url, api_key)
        except ImportError:
            logger.warning("firecrawl-py not installed, trying simple fallback")
        except Exception as e:
            logger.warning("Firecrawl failed (%s), trying simple fallback", e)

    # Fallback: simple HTTP fetch with basic content extraction
    if SIMPLE_FALLBACK_ENABLED:
        return await _fetch_simple(url)

    raise ImportError("firecrawl-py is not installed and simple fallback is disabled")


async def _fetch_with_firecrawl(url: str, api_key: str) -> Tuple[str, str]:
    """Fetch using the Firecrawl API."""
    from firecrawl import FirecrawlApp

    app = FirecrawlApp(api_key=api_key)

    logger.info("Fetching URL with Firecrawl: %s", url)
    result = app.scrape_url(url, params={"formats": ["markdown"]})

    markdown = result.get("markdown", "")
    metadata = result.get("metadata", {})
    title = metadata.get("title", "") or metadata.get("og:title", "") or url

    return markdown, title


async def _fetch_simple(url: str) -> Tuple[str, str]:
    """
    Simple HTTP fetch fallback — fetches HTML and does basic conversion.

    This is much lower quality than Firecrawl but works offline
    (for locally-hosted URLs) and without an API key.
    """
    logger.info("Fetching URL with simple fallback: %s", url)

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "Vanilla/0.1 (Knowledge Base)"},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text

    # Extract title from <title> tag
    title = _extract_html_title(html) or url

    # Basic HTML to text conversion (strips tags, keeps structure)
    text = _html_to_basic_markdown(html)

    return text, title


def _extract_html_title(html: str) -> str:
    """Extract <title> content from HTML."""
    import re
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def _html_to_basic_markdown(html: str) -> str:
    """
    Very basic HTML to markdown conversion.

    This is intentionally simple — Firecrawl is the proper solution.
    This fallback just strips HTML tags and preserves some structure.
    """
    import re

    # Remove script and style blocks
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Convert headings
    for i in range(1, 7):
        text = re.sub(
            rf'<h{i}[^>]*>(.*?)</h{i}>',
            lambda m, level=i: f'\n{"#" * level} {m.group(1).strip()}\n',
            text, flags=re.DOTALL | re.IGNORECASE,
        )

    # Convert paragraphs and line breaks
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\1\n', text, flags=re.DOTALL | re.IGNORECASE)

    # Convert links
    text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.DOTALL | re.IGNORECASE)

    # Convert bold and italic
    text = re.sub(r'<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>', r'**\1**', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<(?:i|em)[^>]*>(.*?)</(?:i|em)>', r'*\1*', text, flags=re.DOTALL | re.IGNORECASE)

    # Convert list items
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1', text, flags=re.DOTALL | re.IGNORECASE)

    # Strip remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)

    # Decode HTML entities
    import html
    text = html.unescape(text)

    return text.strip()
