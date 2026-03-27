from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from src.models import Article, ProcessedArticle
from src.processor.pipeline import process_article


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def process_all(
    articles: list[Article],
    max_concurrent: int = 5,
) -> list[ProcessedArticle]:
    """Batch-process articles through the LLM pipeline with a concurrency cap.

    Args:
        articles: Raw articles to process.
        max_concurrent: Maximum number of simultaneous LLM calls.

    Returns:
        List of ProcessedArticle objects with relevance_score >= 3.0.
    """
    total = len(articles)
    print(f"[{_timestamp()}] processor: starting — {total} article(s) to process")

    semaphore = asyncio.Semaphore(max_concurrent)
    processed_count = 0
    results: list[ProcessedArticle] = []

    async def _process_one(article: Article) -> ProcessedArticle | None:
        nonlocal processed_count
        async with semaphore:
            result = await process_article(article, client_kwargs={})
            processed_count += 1
            status = f"score={result.relevance_score:.1f}" if result else "filtered"
            print(
                f"[{_timestamp()}] processor: [{processed_count}/{total}] "
                f"{article.source} — {article.title[:40]!r} ({status})"
            )
            return result

    tasks = [asyncio.create_task(_process_one(a)) for a in articles]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    for article, outcome in zip(articles, raw_results):
        if isinstance(outcome, BaseException):
            print(
                f"[{_timestamp()}] processor: ERROR processing {article.id} "
                f"({article.source}): {outcome}"
            )
            continue
        if outcome is not None:
            results.append(outcome)

    print(
        f"[{_timestamp()}] processor: done — {len(results)}/{total} article(s) passed relevance filter"
    )
    return results
