from __future__ import annotations

import asyncio
import hashlib
import html
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Optional

import feedparser

from src.models import Article


class _HTMLStripper(HTMLParser):
    """Minimal HTML stripper using stdlib html.parser."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts).strip()


def _strip_html(raw: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html.unescape(raw))
    return stripper.get_text()


def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:8]


def _parse_published(entry: feedparser.FeedParserDict) -> str:
    """Return ISO datetime string from feed entry, or empty string."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass
    return ""


def _entry_matches_keywords(entry: feedparser.FeedParserDict, keywords: list[str]) -> bool:
    if not keywords:
        return True
    text = " ".join([
        entry.get("title", ""),
        entry.get("summary", ""),
        entry.get("description", ""),
    ])
    return any(kw in text for kw in keywords)


async def fetch_rss(
    source_name: str,
    url: str,
    max_items: int = 20,
    keywords: Optional[list[str]] = None,
) -> list[Article]:
    """Fetch and parse an RSS feed, returning a list of Article objects.

    Args:
        source_name: Human-readable source label (e.g. "36氪").
        url: RSS feed URL.
        max_items: Maximum number of articles to return.
        keywords: If provided, only include entries that contain at least one keyword.
    """
    loop = asyncio.get_event_loop()
    # feedparser.parse is synchronous; run in executor to avoid blocking the loop.
    feed = await loop.run_in_executor(None, feedparser.parse, url)

    collected_at = datetime.now(timezone.utc).isoformat()
    articles: list[Article] = []

    for entry in feed.entries:
        if len(articles) >= max_items:
            break

        if keywords and not _entry_matches_keywords(entry, keywords):
            continue

        entry_url: str = entry.get("link", "")
        if not entry_url:
            continue

        title: str = _strip_html(entry.get("title", ""))

        # Prefer full content over summary when available.
        raw_content = ""
        if entry.get("content"):
            raw_content = entry["content"][0].get("value", "")
        if not raw_content:
            raw_content = entry.get("summary", entry.get("description", ""))
        content = _strip_html(raw_content)[:2000]

        articles.append(
            Article(
                id=_make_id(entry_url),
                url=entry_url,
                source=source_name,
                title=title,
                content=content,
                published_at=_parse_published(entry),
                collected_at=collected_at,
            )
        )

    return articles
