"""Collector for Next.js pages that embed article data in __NEXT_DATA__ JSON."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Optional

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


def _dig(data: dict, path: str):
    """Navigate nested dict/list using dot-notation path (e.g. 'props.pageProps.staticData.news')."""
    node = data
    for key in path.split("."):
        if isinstance(node, dict):
            node = node[key]
        else:
            raise KeyError(f"Cannot navigate into {type(node)} with key '{key}'")
    return node


async def fetch_nextjs(
    source_name: str,
    url: str,
    data_path: str,
    title_field: str,
    id_field: str,
    url_prefix: str,
    max_items: int = 20,
    keywords: Optional[list[str]] = None,
) -> list[Article]:
    """Fetch a Next.js page and extract articles from __NEXT_DATA__ JSON.

    Args:
        source_name: Human-readable source label.
        url: Page URL containing __NEXT_DATA__.
        data_path: Dot-notation path to the article array in the JSON (e.g. 'props.pageProps.staticData.news').
        title_field: Field name for the article title within each item.
        id_field: Field name for the unique article ID within each item.
        url_prefix: Prefix to construct article URL: url_prefix + item[id_field].
        max_items: Maximum articles to return.
        keywords: If provided, only include articles whose title contains at least one keyword.
    """
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    collected_at = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=15.0) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if script_tag is None:
        raise ValueError(f"No __NEXT_DATA__ script tag found on {url}")

    next_data = json.loads(script_tag.string)

    try:
        items = _dig(next_data, data_path)
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Could not navigate path '{data_path}' in __NEXT_DATA__: {exc}") from exc

    if not isinstance(items, list):
        raise ValueError(f"Expected list at '{data_path}', got {type(items)}")

    articles: list[Article] = []
    for item in items:
        if len(articles) >= max_items:
            break

        title = str(item.get(title_field, "")).strip()
        if not title:
            continue

        if keywords and not any(kw in title for kw in keywords):
            continue

        item_id = str(item.get(id_field, "")).strip()
        if not item_id:
            continue

        article_url = url_prefix + item_id

        articles.append(
            Article(
                id=_make_id(article_url),
                url=article_url,
                source=source_name,
                title=title,
                content=title,  # processor uses title for relevance scoring
                published_at="",
                collected_at=collected_at,
            )
        )

    return articles
