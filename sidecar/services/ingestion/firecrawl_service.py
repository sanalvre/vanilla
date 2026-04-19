"""
Web scraping service — cascading scraper with multiple backends.

Priority order:
  1. Firecrawl   (if api_key provided) — best quality, paid, handles most sites
  2. Crawl4AI    (if installed)        — Playwright-based, handles JS-heavy SPAs, free
                                         Only available when running sidecar from raw Python;
                                         not bundled in the PyInstaller binary due to Playwright size.
  3. Jina Reader (always available)    — r.jina.ai proxy, free, no API key, handles JS via Jina's infra

All backends return (markdown_content, page_title).
"""

import logging
from typing import Optional, Tuple

import httpx

logger = logging.getLogger("vanilla.ingestion.firecrawl")


async def fetch_url(url: str, api_key: Optional[str] = None) -> Tuple[str, str]:
    """
    Fetch a URL and return (markdown_content, title).

    Tries backends in priority order: Firecrawl → Crawl4AI → Jina Reader.
    Raises RuntimeError only if all backends fail.
    """
    # 1. Firecrawl — highest quality for standard pages
    if api_key:
        try:
            return await _fetch_with_firecrawl(url, api_key)
        except ImportError:
            logger.warning("firecrawl-py not installed, falling back")
        except Exception as e:
            logger.warning("Firecrawl failed (%s), trying next scraper", e)

    # 2. Crawl4AI — Playwright-based, handles JS-heavy sites (dev/power-user only)
    try:
        return await _fetch_with_crawl4ai(url)
    except ImportError:
        pass  # Not installed — expected in production binary
    except Exception as e:
        logger.warning("Crawl4AI failed (%s), trying Jina Reader", e)

    # 3. Jina Reader — reliable free fallback, handles most pages including JS
    try:
        return await _fetch_with_jina(url)
    except Exception as e:
        logger.warning("Jina Reader failed (%s)", e)

    raise RuntimeError(
        f"All scrapers failed for: {url}. "
        "Configure a Firecrawl API key in Settings for more reliable scraping."
    )


async def _fetch_with_firecrawl(url: str, api_key: str) -> Tuple[str, str]:
    """Fetch using the Firecrawl API (firecrawl-py package)."""
    from firecrawl import FirecrawlApp

    logger.info("Fetching with Firecrawl: %s", url)
    app = FirecrawlApp(api_key=api_key)
    result = app.scrape_url(url, params={"formats": ["markdown"]})

    markdown = result.get("markdown", "")
    metadata = result.get("metadata", {})
    title = metadata.get("title") or metadata.get("og:title") or url

    return markdown, title


async def _fetch_with_crawl4ai(url: str) -> Tuple[str, str]:
    """
    Fetch via Crawl4AI — Playwright-based, handles complex JS/SPAs.

    Raises ImportError if crawl4ai is not installed (expected in production binary).
    Install with: pip install crawl4ai && playwright install chromium
    """
    from crawl4ai import AsyncWebCrawler

    logger.info("Fetching with Crawl4AI: %s", url)
    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(url=url)

    if not result.success:
        raise RuntimeError(f"Crawl4AI: {result.error_message}")

    content = result.markdown or ""
    title = url
    if result.metadata:
        title = result.metadata.get("title", url)

    return content, title


async def _fetch_with_jina(url: str) -> Tuple[str, str]:
    """
    Fetch via Jina Reader (r.jina.ai) — free, no API key required.

    Jina renders pages server-side and returns clean markdown.
    Works on most sites including JS-rendered pages. Rate limit: ~20 req/min on free tier.
    """
    jina_url = f"https://r.jina.ai/{url}"
    logger.info("Fetching with Jina Reader: %s", url)

    async with httpx.AsyncClient(
        timeout=60.0,
        follow_redirects=True,
        headers={
            "Accept": "text/markdown, text/plain, */*",
            "User-Agent": "Vanilla/0.1 (Knowledge Base)",
        },
    ) as client:
        resp = await client.get(jina_url)
        resp.raise_for_status()
        content = resp.text

    # Jina prepends metadata lines: "Title: ...\nURL: ...\nPublished: ...\n---\n"
    title = url
    for line in content.splitlines()[:8]:
        if line.lower().startswith("title:"):
            title = line[6:].strip()
            break

    return content, title
