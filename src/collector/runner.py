from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import yaml

from src.collector.nextjs import fetch_nextjs
from src.collector.rss import fetch_rss
from src.collector.web import fetch_page
from src.models import Article


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def collect_all(sources_path: str = "data/sources.yaml") -> list[Article]:
    """Collect articles from all configured sources concurrently.

    Reads source definitions from a YAML file, spawns RSS and web fetch tasks
    in parallel, deduplicates results by article id, and returns the merged list.

    Args:
        sources_path: Path to the sources YAML config file.
    """
    with open(sources_path, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    tasks: list[asyncio.Task] = []

    # RSS sources.
    for src in config.get("rss", []):
        task = asyncio.create_task(
            fetch_rss(
                source_name=src["name"],
                url=src["url"],
                keywords=src.get("keywords"),
            ),
            name=f"rss:{src['name']}",
        )
        tasks.append(task)

    # Web scrape sources.
    for src in config.get("web", []):
        task = asyncio.create_task(
            fetch_page(
                source_name=src["name"],
                base_url=src["url"],
                article_selector=src["article_selector"],
                title_selector=src["title_selector"],
                link_selector=src.get("link_selector", "a"),
            ),
            name=f"web:{src['name']}",
        )
        tasks.append(task)

    # Next.js sources.
    for src in config.get("nextjs", []):
        task = asyncio.create_task(
            fetch_nextjs(
                source_name=src["name"],
                url=src["url"],
                data_path=src["data_path"],
                title_field=src["title_field"],
                id_field=src["id_field"],
                url_prefix=src["url_prefix"],
                keywords=src.get("keywords"),
            ),
            name=f"nextjs:{src['name']}",
        )
        tasks.append(task)

    print(f"[{_timestamp()}] collector: launching {len(tasks)} source task(s)")

    results = await asyncio.gather(*tasks, return_exceptions=True)

    seen: dict[str, Article] = {}
    for name, result in zip([t.get_name() for t in tasks], results):
        if isinstance(result, BaseException):
            print(f"[{_timestamp()}] collector: ERROR in {name}: {result}")
            continue
        for article in result:
            if article.id not in seen:
                seen[article.id] = article

    articles = list(seen.values())
    print(f"[{_timestamp()}] collector: collected {len(articles)} unique article(s)")
    return articles
