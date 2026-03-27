from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.models import Article

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:8]


def _absolute_url(base_url: str, href: str) -> str:
    """Resolve a potentially relative href against the base URL."""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin(base_url, href)


async def fetch_page(
    source_name: str,
    base_url: str,
    article_selector: str,
    title_selector: str,
    link_selector: str = "a",
) -> list[Article]:
    """Scrape a listing page for articles using CSS selectors.

    Fetches only the listing page (no detail page fetching) and extracts
    article titles and links. Sets content to the title since detail pages
    are not fetched — the downstream processor uses title for scoring.

    Args:
        source_name: Human-readable source label.
        base_url: Listing page URL to scrape.
        article_selector: CSS selector for each article container element.
        title_selector: CSS selector for the title/link within each container.
        link_selector: CSS selector for the anchor element within each container.
    """
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    collected_at = datetime.now(timezone.utc).isoformat()
    articles: list[Article] = []

    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        timeout=15.0,
    ) as client:
        response = await client.get(base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        containers = soup.select(article_selector)
        for container in containers:
            if len(articles) >= 20:
                break

            # Extract the link element. If selector finds nothing but the
            # container itself is an <a>, treat it as its own link element.
            link_el = container.select_one(link_selector)
            if link_el is None and container.name == "a":
                link_el = container
            if link_el is None:
                continue

            href = link_el.get("href", "")
            if not href:
                continue
            article_url = _absolute_url(base_url, str(href))

            # Extract title: prefer title_selector text, fall back to link text.
            title_el = container.select_one(title_selector)
            if title_el is not None:
                title = title_el.get_text(strip=True)
            else:
                title = link_el.get_text(strip=True)

            if not title:
                continue

            articles.append(
                Article(
                    id=_make_id(article_url),
                    url=article_url,
                    source=source_name,
                    title=title,
                    content=title,  # processor uses title for scoring
                    published_at="",
                    collected_at=collected_at,
                )
            )

    return articles
